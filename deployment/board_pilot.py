#!/usr/bin/env python3
"""Run two warm-ups and a fixed 20-image, two-per-class PYNQ pilot."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import datetime
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
FIELDS = ["pilot_id", "dataset_index", "label", "prediction", "correct",
          "e2e_latency_ms", "kernel_latency_ms", "matrix_kernel_latency_ms",
          "attention_kernel_latency_ms", "kernel_call_count", "matrix_call_count",
          "attention_call_count", "event_count",
          "selected_mac_count", "mac_without_event_skip", "mac_skip_rate",
          "cycle_count", "matrix_read_beats", "attention_cycle_count",
          "attention_read_beats", "attention_write_beats", "attention_qk_terms",
          "attention_av_terms", "timestamp"]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=PACKAGE_ROOT / "results" / "pilot")
    parser.add_argument("--full-max-estimated-hours", type=float, default=8.0)
    parser.add_argument("--overhead-factor", type=float, default=1.10)
    args = parser.parse_args()
    if args.full_max_estimated_hours <= 0 or args.overhead_factor < 1.0:
        parser.error("hours must be >0 and overhead-factor must be >=1")
    for name, expected in EXPECTED.items():
        actual = sha256(PACKAGE_ROOT / name)
        if actual != expected:
            raise RuntimeError(f"artifact mismatch: {name}: {actual} != {expected}")

    images = np.load(PACKAGE_ROOT / "data" / "cifar10_subset1000_images.npy", mmap_mode="r", allow_pickle=False)
    labels = np.load(PACKAGE_ROOT / "data" / "cifar10_subset1000_labels.npy", mmap_mode="r", allow_pickle=False)
    indices = np.load(PACKAGE_ROOT / "data" / "cifar10_subset1000_indices.npy", mmap_mode="r", allow_pickle=False)
    pilot_positions = sorted(
        int(position)
        for class_id in range(10)
        for position in np.flatnonzero(labels == class_id)[:2]
    )
    pilot_labels = labels[pilot_positions]
    if not np.array_equal(np.bincount(pilot_labels.astype(np.int32), minlength=10), np.full(10, 2)):
        raise RuntimeError("pilot is not exactly two images per class")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    weights = WeightStore()
    backend = PynqBackend(weights)
    runtime = SpikformerRuntime(backend, weights)
    # Mandatory first-image functional gate: the real PL path must match the
    # independent integer NumPy model before timing is accepted.
    reference_backend = NumpyBackend(weights)
    reference = SpikformerRuntime(reference_backend, weights)(images[pilot_positions[0]:pilot_positions[0] + 1])
    hardware = runtime(images[pilot_positions[0]:pilot_positions[0] + 1])
    max_abs_error = float(np.max(np.abs(reference - hardware)))
    if max_abs_error > 1e-5 or int(reference.argmax(1)[0]) != int(hardware.argmax(1)[0]):
        raise RuntimeError(f"hardware functional gate failed: max_abs_error={max_abs_error}")
    functional_gate = {"status": "PASS", "dataset_index": int(indices[pilot_positions[0]]),
                       "max_abs_logit_error": max_abs_error,
                       "prediction": int(hardware.argmax(1)[0])}
    warmup_rows = []
    for position in pilot_positions[:2]:
        backend.event_records.clear()
        start = time.perf_counter()
        runtime(images[position:position + 1])
        warmup_rows.append({"dataset_index": int(indices[position]),
                            "elapsed_seconds": time.perf_counter() - start})
    backend.event_records.clear()
    backend.attention_records.clear()
    backend.kernel_seconds = 0.0
    backend.matrix_kernel_seconds = 0.0
    backend.attention_seconds = 0.0
    backend.calls = 0
    backend.matrix_calls = 0
    backend.attention_calls = 0

    rows = []
    for pilot_id, position in enumerate(pilot_positions):
        backend.event_records.clear()
        backend.attention_records.clear()
        before_kernel = backend.kernel_seconds
        before_matrix = backend.matrix_kernel_seconds
        before_attention = backend.attention_seconds
        before_calls = backend.calls
        before_matrix_calls = backend.matrix_calls
        before_attention_calls = backend.attention_calls
        start = time.perf_counter()
        logits = runtime(images[position:position + 1])
        e2e_ms = (time.perf_counter() - start) * 1000.0
        kernel_ms = (backend.kernel_seconds - before_kernel) * 1000.0
        matrix_ms = (backend.matrix_kernel_seconds - before_matrix) * 1000.0
        attention_ms = (backend.attention_seconds - before_attention) * 1000.0
        calls = backend.calls - before_calls
        matrix_calls = backend.matrix_calls - before_matrix_calls
        attention_calls = backend.attention_calls - before_attention_calls
        events = backend.event_records
        attentions = backend.attention_records
        if (calls, matrix_calls, attention_calls) != (34, 30, 4):
            raise RuntimeError(f"unexpected kernel graph: {(calls, matrix_calls, attention_calls)}")
        selected = sum(int(item["actual_selected_mac_issues"]) for item in events)
        no_skip = sum(int(item["selected_macs_without_event_skip"]) for item in events)
        prediction = int(logits.argmax(axis=1)[0])
        row = {
            "pilot_id": pilot_id,
            "dataset_index": int(indices[position]),
            "label": int(labels[position]),
            "prediction": prediction,
            "correct": int(prediction == int(labels[position])),
            "e2e_latency_ms": e2e_ms,
            "kernel_latency_ms": kernel_ms,
            "matrix_kernel_latency_ms": matrix_ms,
            "attention_kernel_latency_ms": attention_ms,
            "kernel_call_count": calls,
            "matrix_call_count": matrix_calls,
            "attention_call_count": attention_calls,
            "event_count": sum(int(item["events"]) for item in events),
            "selected_mac_count": selected,
            "mac_without_event_skip": no_skip,
            "mac_skip_rate": 1.0 - selected / no_skip if no_skip else None,
            "cycle_count": sum(int(item["cycles"]) for item in events),
            "matrix_read_beats": sum(int(item["read_beats"]) for item in events),
            "attention_cycle_count": sum(int(item["cycles"]) for item in attentions),
            "attention_read_beats": sum(int(item["read_beats"]) for item in attentions),
            "attention_write_beats": sum(int(item["write_beats"]) for item in attentions),
            "attention_qk_terms": sum(int(item["qk_terms"]) for item in attentions),
            "attention_av_terms": sum(int(item["av_terms"]) for item in attentions),
            "timestamp": datetime.now().astimezone().isoformat(),
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
    backend.event_records.clear()

    e2e = np.asarray([row["e2e_latency_ms"] for row in rows], dtype=np.float64)
    kernel = np.asarray([row["kernel_latency_ms"] for row in rows], dtype=np.float64)
    p75_ms = float(np.percentile(e2e, 75))
    conservative_ms = p75_ms * args.overhead_factor
    estimate_1000 = conservative_ms * 1000 / 3_600_000
    estimate_10000 = conservative_ms * 10000 / 3_600_000
    selected_mode = "full" if estimate_10000 <= args.full_max_estimated_hours else "subset1000"
    result = {
        "status": "actual_pynq_pilot",
        "functional_gate": functional_gate,
        "warmup_images": 2,
        "measured_images": 20,
        "samples_per_class": 2,
        "warmup_excluded_from_accuracy_and_statistics": True,
        "mean_e2e_latency_ms": float(e2e.mean()),
        "median_e2e_latency_ms": float(np.median(e2e)),
        "p75_e2e_latency_ms": p75_ms,
        "mean_kernel_latency_ms": float(kernel.mean()),
        "overhead_factor": args.overhead_factor,
        "conservative_ms_per_image": conservative_ms,
        "estimated_1000_hours": estimate_1000,
        "estimated_10000_hours": estimate_10000,
        "full_dataset_max_estimated_hours": args.full_max_estimated_hours,
        "selected_mode": selected_mode,
        "selection_reason": ("conservative full estimate is within threshold" if selected_mode == "full"
                             else "conservative full estimate exceeds threshold"),
        "warmup": warmup_rows,
        "rows": rows,
    }
    (args.output_dir / "pilot_results.json").write_text(json.dumps(result, indent=2) + "\n")
    with (args.output_dir / "pilot_predictions.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({key: value for key, value in result.items() if key not in {"rows", "warmup"}}, indent=2))


if __name__ == "__main__":
    main()
