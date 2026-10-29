"""Checkpoint-compatible binary Spikformer adapter.

The supplied checkpoint's parameter names and shapes match the Pruned
SpikingTokenizer/Conv1d graph (five tokenizer convolutions, Q/K/V Conv1d,
projection Conv1d, MLP Conv2d, no SPS rpe_conv).  This module implements that
graph with the original binary 0/1 multi-step LIF dynamics from model.py:
    v <- v + (x - v) / tau
    s <- (v >= threshold)
    v <- v * (1 - s)
It deliberately does not substitute the ternary LIF used by the V1 ternary
experiment.  The checkpoint's weight_orig/weight_mask pairs are materialized
with weight = weight_orig * weight_mask; the masks are checked as 8-of-16.
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn as nn

TAU = 2.0
THRESHOLD = 1.0
ATTN_THRESHOLD = 0.5


class BinaryLIF(nn.Module):
    def __init__(self, tau: float = TAU, threshold: float = THRESHOLD):
        super().__init__()
        self.tau = float(tau)
        self.threshold = float(threshold)
        self.v = None

    def reset(self):
        self.v = None

    def forward(self, x):
        if x.ndim < 2:
            raise ValueError("LIF input must have a time dimension")
        if self.v is None or self.v.shape != x[0].shape or self.v.device != x.device:
            self.v = torch.zeros_like(x[0])
        spikes = []
        for t in range(x.shape[0]):
            self.v = self.v + (x[t] - self.v) / self.tau
            spike = (self.v >= self.threshold).to(self.v.dtype)
            self.v = self.v * (1.0 - spike)
            spikes.append(spike)
        return torch.stack(spikes, dim=0)


class MLP(nn.Module):
    def __init__(self, dim: int, hidden: int):
        super().__init__()
        self.mlp1_lif = BinaryLIF()
        self.mlp1_conv = nn.Conv2d(dim, hidden, 1)
        self.mlp1_bn = nn.BatchNorm2d(hidden)
        self.mlp2_lif = BinaryLIF()
        self.mlp2_conv = nn.Conv2d(hidden, dim, 1)
        self.mlp2_bn = nn.BatchNorm2d(dim)

    def forward(self, x):
        t, b, c, h, w = x.shape
        x = self.mlp1_lif(x)
        x = self.mlp1_bn(self.mlp1_conv(x.flatten(0, 1))).reshape(t, b, -1, h, w)
        x = self.mlp2_lif(x)
        x = self.mlp2_bn(self.mlp2_conv(x.flatten(0, 1))).reshape(t, b, c, h, w)
        return x


class SpikingSelfAttention(nn.Module):
    def __init__(self, dim: int, heads: int, scale: float = 0.125,
                 attn_threshold: float = ATTN_THRESHOLD):
        super().__init__()
        self.heads = heads
        self.scale = scale
        self.attn_threshold = float(attn_threshold)
        self.proj_lif = BinaryLIF()
        self.q_conv = nn.Conv1d(dim, dim, 1, bias=False)
        self.q_bn = nn.BatchNorm1d(dim)
        self.q_lif = BinaryLIF()
        self.k_conv = nn.Conv1d(dim, dim, 1, bias=False)
        self.k_bn = nn.BatchNorm1d(dim)
        self.k_lif = BinaryLIF()
        self.v_conv = nn.Conv1d(dim, dim, 1, bias=False)
        self.v_bn = nn.BatchNorm1d(dim)
        self.v_lif = BinaryLIF()
        self.attn_lif = BinaryLIF(threshold=attn_threshold)
        self.proj_conv = nn.Conv1d(dim, dim, 1)
        self.proj_bn = nn.BatchNorm1d(dim)

    def forward(self, x):
        t, b, c, h, w = x.shape
        x = self.proj_lif(x).flatten(3)
        t, b, c, n = x.shape
        z = x.flatten(0, 1)

        def branch(conv, bn, lif):
            y = bn(conv(z)).reshape(t, b, c, n)
            y = lif(y).transpose(-1, -2)
            return y.reshape(t, b, n, self.heads, c // self.heads).permute(0, 1, 3, 2, 4)

        q = branch(self.q_conv, self.q_bn, self.q_lif)
        k = branch(self.k_conv, self.k_bn, self.k_lif)
        v = branch(self.v_conv, self.v_bn, self.v_lif)
        attn = q @ k.transpose(-2, -1)
        x = (attn @ v) * self.scale
        x = x.transpose(3, 4).reshape(t, b, c, n)
        x = self.attn_lif(x).flatten(0, 1)
        x = self.proj_bn(self.proj_conv(x)).reshape(t, b, c, h, w)
        return x


class SpikingTransformer(nn.Module):
    def __init__(self, dim: int, heads: int, attn_threshold: float = ATTN_THRESHOLD):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)
        self.attn = SpikingSelfAttention(dim, heads, attn_threshold=attn_threshold)
        self.mlp = MLP(dim, dim * 4)

    def forward(self, x):
        x = x + self.attn(x)
        x = x + self.mlp(x)
        return x


class SpikingTokenizer(nn.Module):
    def __init__(self, in_channels: int, dim: int):
        super().__init__()
        self.block0_conv = nn.Conv2d(in_channels, dim // 8, 3, padding=1, bias=False)
        self.block0_bn = nn.BatchNorm2d(dim // 8)
        self.block1_lif = BinaryLIF()
        self.block1_conv = nn.Conv2d(dim // 8, dim // 4, 3, padding=1, bias=False)
        self.block1_bn = nn.BatchNorm2d(dim // 4)
        self.block2_lif = BinaryLIF()
        self.block2_conv = nn.Conv2d(dim // 4, dim // 2, 3, padding=1, bias=False)
        self.block2_bn = nn.BatchNorm2d(dim // 2)
        self.block3_lif = BinaryLIF()
        self.block3_mp = nn.MaxPool2d(3, 2, 1)
        self.block3_conv = nn.Conv2d(dim // 2, dim, 3, padding=1, bias=False)
        self.block3_bn = nn.BatchNorm2d(dim)
        self.block4_lif = BinaryLIF()
        self.block4_mp = nn.MaxPool2d(3, 2, 1)
        self.block4_conv = nn.Conv2d(dim, dim, 3, padding=1, bias=False)
        self.block4_bn = nn.BatchNorm2d(dim)

    def forward(self, x):
        t, b, c, h, w = x.shape
        x = self.block0_bn(self.block0_conv(x.flatten(0, 1))).reshape(t, b, -1, h, w)
        x = self.block1_bn(self.block1_conv(self.block1_lif(x).flatten(0, 1))).reshape(t, b, -1, h, w)
        x = self.block2_bn(self.block2_conv(self.block2_lif(x).flatten(0, 1)))
        x = self.block3_mp(x).reshape(t, b, -1, h // 2, w // 2)
        x = self.block3_lif(x).flatten(0, 1)
        x = self.block3_bn(self.block3_conv(x))
        x = self.block4_mp(x).reshape(t, b, -1, h // 4, w // 4)
        x = self.block4_lif(x).flatten(0, 1)
        x = self.block4_bn(self.block4_conv(x)).reshape(t, b, -1, h // 4, w // 4)
        return x


class BinarySpikformer(nn.Module):
    def __init__(self, dim=384, heads=12, depths=4, time_steps=4,
                 in_channels=3, num_classes=10, attn_scale=0.125,
                 attn_threshold: float = ATTN_THRESHOLD):
        super().__init__()
        self.dim = dim
        self.heads = heads
        self.depths = depths
        self.time_steps = time_steps
        self.patch_embed = SpikingTokenizer(in_channels, dim)
        self.block = nn.ModuleList([SpikingTransformer(dim, heads, attn_threshold=attn_threshold) for _ in range(depths)])
        self.head = nn.Linear(dim, num_classes)

    def reset_state(self):
        for module in self.modules():
            if isinstance(module, BinaryLIF):
                module.reset()

    def forward(self, x):
        x = x.unsqueeze(0).repeat(self.time_steps, 1, 1, 1, 1)
        x = self.patch_embed(x)
        for block in self.block:
            x = block(x)
        x = x.flatten(3).mean(3).mean(0)
        return self.head(x)


def _materialize_state(raw):
    state = raw["state_dict"] if "state_dict" in raw else raw
    masks = {k[:-len(".weight_mask")]: v for k, v in state.items() if k.endswith(".weight_mask")}
    result = {}
    for key, value in state.items():
        if key.endswith(".weight_mask"):
            continue
        if key.endswith(".weight_orig"):
            base = key[:-len(".weight_orig")]
            mask = masks.get(base)
            if mask is None:
                raise RuntimeError(f"missing mask for {base}")
            result[base + ".weight"] = value * mask
        else:
            result[key] = value
    return result, masks


def audit_checkpoint(path, dim=384, heads=12, depths=4, time_steps=4, attn_threshold=ATTN_THRESHOLD):
    raw = torch.load(path, map_location="cpu", weights_only=False)
    state, masks = _materialize_state(raw)
    expected_masks = 0
    errors = []
    for name, mask in masks.items():
        if mask.ndim < 2 or mask.numel() % 16:
            errors.append(f"{name}: not divisible by 16")
            continue
        groups = mask.reshape(-1, 16)
        if not bool((groups.sum(dim=1) == 8).all()):
            errors.append(f"{name}: groups are not exact 8-of-16")
        expected_masks += 1
    if expected_masks != 20:
        errors.append(f"expected 20 RIA masks, got {expected_masks}")
    if raw.get("ria_nm") not in (None, "8:16"):
        errors.append(f"ria_nm={raw.get('ria_nm')}")
    if raw.get("spike_mode") not in (None, "binary"):
        errors.append(f"spike_mode={raw.get('spike_mode')}")
    model = BinarySpikformer(dim=dim, heads=heads, depths=depths, time_steps=time_steps, attn_threshold=attn_threshold)
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing or unexpected:
        errors.append(f"state_dict mismatch: missing={missing[:8]} unexpected={unexpected[:8]}")
    kept = int(sum(m.sum().item() for m in masks.values()))
    total = int(sum(m.numel() for m in masks.values()))
    return {
        "status": "PASS" if not errors else "FAIL",
        "attn_threshold": float(attn_threshold),
        "checkpoint_sha256": __import__("hashlib").sha256(Path(path).read_bytes()).hexdigest(),
        "state_dict_keys": len(state),
        "ria_masks": len(masks),
        "ria_total": total,
        "ria_kept": kept,
        "ria_sparsity": 1.0 - kept / total if total else None,
        "errors": errors,
        "source_checkpoint": raw.get("source_checkpoint"),
        "model_source": raw.get("model_source"),
        "spike_mode": raw.get("spike_mode"),
        "ria_nm": raw.get("ria_nm"),
    }, model, raw


def load_binary_model(path, **kwargs):
    report, model, raw = audit_checkpoint(path, **kwargs)
    if report["status"] != "PASS":
        raise RuntimeError("checkpoint audit failed: " + json.dumps(report["errors"]))
    return model.eval(), report, raw
