#!/usr/bin/env python3
"""Independent host software audit of the binary checkpoint.

Requires the spikformer conda environment (torch 2.0.1, timm 0.5.4,
spikingjelly).  It builds the checkpoint-compatible Conv1d graph and the
available reference model, checks strict key coverage, compares the two graphs
bit-for-bit on the first images, and evaluates the fixed 1000-image subset.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from functools import partial
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[1]
CKPT = ROOT / "model" / "binary_ria_pruned_816.pth"
ADAPTER = ROOT / "model" / "binary_model_adapter.py"
REFERENCE = ROOT / "model" / "reference_training_model.py"
DATA = ROOT / "data"
OUT = ROOT / "reference" / "software"
OUT.mkdir(parents=True, exist_ok=True)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reset_all(model):
    for module in model.modules():
        reset = getattr(module, "reset", None)
        if callable(reset):
            reset()


def map_binary_key(key):
    prefix = "patch_embed."
    if not key.startswith(prefix):
        return key
    rest = key[len(prefix):]
    for index in range(5):
        token = f"block{index}_"
        if rest.startswith(token):
            target = "proj" if index == 0 else f"proj{index}"
            return prefix + target + "_" + rest[len(token):]
    return key


def materialize(raw):
    state = raw["state_dict"]
    masks = {k[:-len(".weight_mask")]: v for k, v in state.items() if k.endswith(".weight_mask")}
    result = {}
    for key, value in state.items():
        if key.endswith(".weight_mask"):
            continue
        if key.endswith(".weight_orig"):
            base = key[:-len(".weight_orig")]
            result[base + ".weight"] = value * masks[base]
        else:
            result[key] = value
    return result, masks


def run(model, images, reset_fn, tag):
    preds = np.zeros(len(images), dtype=np.int64)
    logits = np.zeros((len(images), 10), dtype=np.float32)
    started = time.time()
    with torch.no_grad():
        for i in range(len(images)):
            reset_fn(model)
            x = torch.from_numpy(np.array(images[i], copy=True)).float().unsqueeze(0)
            out = model(x)[0].cpu().numpy()
            logits[i] = out
            preds[i] = int(np.argmax(out))
            if (i + 1) % 100 == 0:
                print(f"{tag} {i+1}/{len(images)} {time.time()-started:.1f}s", flush=True)
    return preds, logits, time.time() - started


def main():
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    images = np.load(DATA / "cifar10_subset1000_images.npy")
    labels = np.load(DATA / "cifar10_subset1000_labels.npy")
    indices = np.load(DATA / "cifar10_subset1000_indices.npy")
    raw = torch.load(CKPT, map_location="cpu", weights_only=False)
    materialized, masks = materialize(raw)

    adapter_module = load_module("binary_adapter_local", ADAPTER)
    report, adapter, _ = adapter_module.audit_checkpoint(CKPT, attn_threshold=0.5)
    if report["status"] != "PASS":
        raise RuntimeError(report)

    reference_module = load_module("binary_reference_local", REFERENCE)
    reference = reference_module.vit_snn(
        img_size_h=32, img_size_w=32, patch_size=4, in_channels=3, num_classes=10,
        embed_dims=384, num_heads=12, mlp_ratios=4, depths=4, sr_ratios=1, T=4,
        drop_rate=0.0, drop_path_rate=0.0, norm_layer=partial(nn.LayerNorm, eps=1e-6))
    missing, unexpected = reference.load_state_dict(
        {map_binary_key(k): v for k, v in materialized.items()}, strict=False)
    if missing or unexpected:
        raise RuntimeError(f"reference key mismatch missing={missing} unexpected={unexpected}")
    adapter.eval()
    reference.eval()

    pairwise = []
    max_error = 0.0
    for i in range(20):
        x = torch.from_numpy(np.array(images[i], copy=True)).float().unsqueeze(0)
        adapter.reset_state()
        a = adapter(x)[0].detach().cpu().numpy()
        reset_all(reference)
        b = reference(x)[0].detach().cpu().numpy()
        max_error = max(max_error, float(np.max(np.abs(a - b))))
        pairwise.append({"position": i, "max_abs": float(np.max(np.abs(a - b))),
                         "adapter_prediction": int(np.argmax(a)),
                         "reference_prediction": int(np.argmax(b))})
    if max_error != 0.0:
        raise RuntimeError(f"adapter/reference mismatch max_abs={max_error}")

    preds, logits, seconds = run(reference, images, reset_all, "binary_reference")
    correct = int(np.count_nonzero(preds == labels))
    accuracy = 100.0 * correct / len(images)
    np.save(OUT / "binary_local_preds.npy", preds)
    np.save(OUT / "binary_local_logits.npy", logits)
    prior_logits_path = OUT / "binary_ref_logits.npy"
    prior_agreement = None
    prior_max_abs = None
    if prior_logits_path.exists():
        prior = np.load(prior_logits_path)
        prior_agreement = int(np.count_nonzero(preds == np.argmax(prior, axis=1)))
        prior_max_abs = float(np.max(np.abs(logits - prior)))
    metrics = {
        "status": "PASS",
        "samples": len(images),
        "correct": correct,
        "accuracy_percent": accuracy,
        "elapsed_seconds": seconds,
        "checkpoint_sha256": report["checkpoint_sha256"],
        "checkpoint_metadata": {k: raw.get(k) for k in ("ria_nm", "source_checkpoint", "model_source", "spike_mode")},
        "ria_masks": len(masks),
        "ria_kept": int(sum(int(m.sum()) for m in masks.values())),
        "ria_total": int(sum(int(m.numel()) for m in masks.values())),
        "adapter_missing": report["missing_keys"] if "missing_keys" in report else [],
        "adapter_vs_reference_first20_max_abs": max_error,
        "adapter_vs_reference_first20": pairwise,
        "prior_logits_agreement": prior_agreement,
        "prior_logits_max_abs": prior_max_abs,
        "spike_semantics": "binary 0/1, tau=2, base threshold=1, attention LIF threshold=0.5, hard reset",
        "indices_first10": indices[:10].tolist(),
    }
    (OUT / "binary_local_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
