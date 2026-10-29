#!/usr/bin/env python3
"""Host-only smoke test of the integer NumPy backend used by the board runtime.

This is not a board result.  It checks that the exported V1-format packed
weights reproduce the software reference predictions on the first 20 fixed
images using the same integer arithmetic as the PL path.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deployment"))
from board_runtime import NumpyBackend, SpikformerRuntime, WeightStore  # noqa: E402

OUT = ROOT / "reference" / "software"


def main():
    images = np.load(ROOT / "data" / "cifar10_subset1000_images.npy", mmap_mode="r")
    labels = np.load(ROOT / "data" / "cifar10_subset1000_labels.npy")
    indices = np.load(ROOT / "data" / "cifar10_subset1000_indices.npy")
    software = np.load(OUT / "binary_ref_preds.npy")
    weights = WeightStore()
    backend = NumpyBackend(weights)
    runtime = SpikformerRuntime(backend, weights)
    rows = []
    started = time.time()
    for position in range(20):
        logits = runtime(images[position:position + 1])
        prediction = int(logits.argmax(1)[0])
        rows.append({
            "position": position,
            "dataset_index": int(indices[position]),
            "label": int(labels[position]),
            "numpy_prediction": prediction,
            "software_reference_prediction": int(software[position]),
            "correct": int(prediction == int(labels[position])),
            "agree_reference": int(prediction == int(software[position])),
            "calls": [backend.calls, backend.matrix_calls, backend.attention_calls],
            "logits": [float(x) for x in logits[0]],
        })
        print(position, rows[-1], flush=True)
    agree = int(sum(row["agree_reference"] for row in rows))
    result = {
        "status": "PASS" if agree == len(rows) else "CHECK",
        "scope": "host integer NumPy backend; not a board result",
        "samples": len(rows),
        "correct": int(sum(row["correct"] for row in rows)),
        "accuracy_percent": 100.0 * sum(row["correct"] for row in rows) / len(rows),
        "agree_reference": agree,
        "elapsed_seconds": time.time() - started,
        "rows": rows,
    }
    (OUT / "numpy_backend_smoke.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2), flush=True)
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
