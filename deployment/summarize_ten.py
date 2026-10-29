#!/usr/bin/env python3
"""Summarize the ten-image Phase B CSV written by board_runner.py.

This is host-side post-processing and does not claim a 1000-image result.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent
DEFAULT_OUTPUT = PACKAGE_ROOT / "results" / "ten"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    csv_path = args.output_dir / "predictions.csv"
    with csv_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 10:
        raise RuntimeError(f"expected 10 rows, got {len(rows)}")
    labels = np.asarray([int(row["label"]) for row in rows], dtype=np.int64)
    predictions = np.asarray([int(row["prediction"]) for row in rows], dtype=np.int64)
    correct = int(np.count_nonzero(labels == predictions))
    calls = {(int(row["kernel_call_count"]), int(row["matrix_call_count"]),
              int(row["attention_call_count"])) for row in rows}
    if calls != {(34, 30, 4)}:
        raise RuntimeError(f"unexpected call counts in ten-image rows: {calls}")
    software_path = PACKAGE_ROOT / "reference" / "software" / "binary_ref_preds.npy"
    software_agreement = None
    if software_path.exists():
        software = np.load(software_path, allow_pickle=False)[:len(rows)]
        software_agreement = int(np.count_nonzero(predictions == software))
    e2e = np.asarray([float(row["e2e_latency_ms"]) for row in rows], dtype=np.float64)
    kernel = np.asarray([float(row["kernel_latency_ms"]) for row in rows], dtype=np.float64)
    matrix = np.asarray([float(row["matrix_kernel_latency_ms"]) for row in rows], dtype=np.float64)
    attention = np.asarray([float(row["attention_kernel_latency_ms"]) for row in rows], dtype=np.float64)
    summary = {
        "status": "PASS",
        "phase": "B_ten_images",
        "samples": len(rows),
        "correct": correct,
        "accuracy_percent": 100.0 * correct / len(rows),
        "software_reference_agreement": software_agreement,
        "call_counts": sorted(calls),
        "mean_e2e_latency_ms": float(e2e.mean()),
        "mean_kernel_latency_ms": float(kernel.mean()),
        "mean_matrix_kernel_latency_ms": float(matrix.mean()),
        "mean_attention_kernel_latency_ms": float(attention.mean()),
        "rows": rows,
    }
    (args.output_dir / "ten_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
