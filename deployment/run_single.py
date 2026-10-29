#!/usr/bin/env python3
"""Phase A: one fixed image through the NumPy integer reference and the real PL.

The PL result must match the independent integer NumPy result bit-for-bit
(logit max absolute error <= 1e-5, identical prediction) before any timing or
larger test is accepted.  There is no CPU fallback: PynqBackend is mandatory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np

import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from board_runtime import NumpyBackend, PynqBackend, SpikformerRuntime, WeightStore

PACKAGE_ROOT = HERE.parent
EXPECTED = {
    "hardware/exspike_migration_8_16.bit": "92c8657baff4154ebf1c4339272d6b6f7d3c70ec0de1d8ad1561fd41a189b5a8",
    "hardware/exspike_migration_8_16.hwh": "3f3173d8a047be1a1c1ab80c78c50f33fdbb48f3c53836ec18c923d26dd5c043",
    "deployment/binary_ria_8_16_weights.npz": "7972f820b767e72465e89228a0cc93f4b54733cfd081b31172fbb4c6c10eaec9",
    "data/cifar10_subset1000_images.npy": "b1ade992f818f678a138e97a334d3134e1535c313acb0d2e816770abb76a26ba",
    "data/cifar10_subset1000_labels.npy": "998b571dc076fcb72fe5d9e6de50e89c958acc5b2779b9fade559026536868a8",
    "data/cifar10_subset1000_indices.npy": "54c4a168d718fdf1b5ea1273d95805a44f12254fcb9a5972a3885dffdf2e6610",
}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--position", type=int, default=0, help="position in the fixed 1000-image subset")
    parser.add_argument("--output-dir", type=Path, default=PACKAGE_ROOT / "results" / "single")
    parser.add_argument("--expected-prediction", type=int, default=None)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for name, expected in EXPECTED.items():
        actual = sha256(PACKAGE_ROOT / name)
        if actual != expected:
            raise RuntimeError(f"artifact mismatch: {name}: {actual} != {expected}")

    images = np.load(PACKAGE_ROOT / "data" / "cifar10_subset1000_images.npy", mmap_mode="r", allow_pickle=False)
    labels = np.load(PACKAGE_ROOT / "data" / "cifar10_subset1000_labels.npy", mmap_mode="r", allow_pickle=False)
    indices = np.load(PACKAGE_ROOT / "data" / "cifar10_subset1000_indices.npy", mmap_mode="r", allow_pickle=False)
    if not 0 <= args.position < len(images):
        raise ValueError(f"position {args.position} outside 0..{len(images)-1}")

    weights = WeightStore()

    # Independent integer reference, no PYNQ and no hardware.
    numpy_backend = NumpyBackend(weights)
    numpy_runtime = SpikformerRuntime(numpy_backend, weights)
    start = time.perf_counter()
    reference_logits = numpy_runtime(images[args.position:args.position + 1])
    numpy_e2e_ms = (time.perf_counter() - start) * 1000.0

    # Real PL path.  PynqBackend is mandatory; no fallback is accepted.
    hardware_backend = PynqBackend(weights)
    if not hardware_backend.is_hardware:
        raise RuntimeError("PynqBackend required; CPU fallback is refused")
    hardware_runtime = SpikformerRuntime(hardware_backend, weights)
    start = time.perf_counter()
    hardware_logits = hardware_runtime(images[args.position:args.position + 1])
    hardware_e2e_ms = (time.perf_counter() - start) * 1000.0

    calls = (hardware_backend.calls, hardware_backend.matrix_calls, hardware_backend.attention_calls)
    if calls != (34, 30, 4):
        raise RuntimeError(f"unexpected hardware call counts: {calls}")
    if not np.isfinite(hardware_logits).all():
        raise RuntimeError("non-finite hardware logits")

    max_abs_error = float(np.max(np.abs(reference_logits - hardware_logits)))
    reference_prediction = int(reference_logits.argmax(1)[0])
    hardware_prediction = int(hardware_logits.argmax(1)[0])
    if max_abs_error > 1e-5 or reference_prediction != hardware_prediction:
        raise RuntimeError(
            f"hardware functional gate failed: max_abs_error={max_abs_error}, "
            f"numpy_prediction={reference_prediction}, hardware_prediction={hardware_prediction}")

    label = int(labels[args.position])
    dataset_index = int(indices[args.position])
    expected_prediction = args.expected_prediction
    software_path = PACKAGE_ROOT / "reference" / "software" / "binary_ref_preds.npy"
    software_prediction = None
    if software_path.exists():
        software_prediction = int(np.load(software_path, allow_pickle=False)[args.position])

    result = {
        "status": "PASS",
        "phase": "A_single_image",
        "position": int(args.position),
        "dataset_index": dataset_index,
        "label": label,
        "numpy_prediction": reference_prediction,
        "hardware_prediction": hardware_prediction,
        "correct": int(hardware_prediction == label),
        "software_reference_prediction": software_prediction,
        "software_reference_agreement": (None if software_prediction is None
                                         else bool(software_prediction == hardware_prediction)),
        "expected_prediction": expected_prediction,
        "expected_prediction_match": (None if expected_prediction is None
                                      else bool(expected_prediction == hardware_prediction)),
        "max_abs_logit_error_numpy_vs_pl": max_abs_error,
        "kernel_calls": calls[0],
        "matrix_calls": calls[1],
        "attention_calls": calls[2],
        "numpy_e2e_ms": numpy_e2e_ms,
        "hardware_e2e_ms": hardware_e2e_ms,
        "hardware_kernel_ms": hardware_backend.kernel_seconds * 1000.0,
        "hardware_matrix_kernel_ms": hardware_backend.matrix_kernel_seconds * 1000.0,
        "hardware_attention_kernel_ms": hardware_backend.attention_seconds * 1000.0,
        "event_count": sum(int(item["events"]) for item in hardware_backend.event_records),
        "selected_mac_count": sum(int(item["actual_selected_mac_issues"]) for item in hardware_backend.event_records),
        "attention_qk_terms": sum(int(item["qk_terms"]) for item in hardware_backend.attention_records),
        "attention_av_terms": sum(int(item["av_terms"]) for item in hardware_backend.attention_records),
        "reference_logits": [float(x) for x in reference_logits[0]],
        "hardware_logits": [float(x) for x in hardware_logits[0]],
    }
    (args.output_dir / "single.json").write_text(json.dumps(result, indent=2) + "\n")
    with (args.output_dir / "single_predictions.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "position", "dataset_index", "label", "numpy_prediction",
            "hardware_prediction", "correct", "max_abs_logit_error_numpy_vs_pl",
            "kernel_calls", "matrix_calls", "attention_calls",
            "hardware_e2e_ms", "hardware_kernel_ms"])
        writer.writeheader()
        writer.writerow({key: result[key] for key in writer.fieldnames})
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
