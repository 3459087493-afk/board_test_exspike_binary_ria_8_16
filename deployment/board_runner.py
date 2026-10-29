#!/usr/bin/env python3
"""Resumable PYNQ runner for full CIFAR-10 or the fixed stratified 1000 subset."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

import sys
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from board_runtime import PynqBackend, SpikformerRuntime, WeightStore

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent
DEFAULT_OUTPUT = Path("/home/xilinx/jupyter_notebooks/board_test_exspike_binary_ria_8_16/results")
EXPECTED = {
    "hardware/exspike_migration_8_16.bit": "92c8657baff4154ebf1c4339272d6b6f7d3c70ec0de1d8ad1561fd41a189b5a8",
    "hardware/exspike_migration_8_16.hwh": "3f3173d8a047be1a1c1ab80c78c50f33fdbb48f3c53836ec18c923d26dd5c043",
    "deployment/binary_ria_8_16_weights.npz": "7972f820b767e72465e89228a0cc93f4b54733cfd081b31172fbb4c6c10eaec9",
    "data/cifar10_subset1000_images.npy": "b1ade992f818f678a138e97a334d3134e1535c313acb0d2e816770abb76a26ba",
    "data/cifar10_subset1000_labels.npy": "998b571dc076fcb72fe5d9e6de50e89c958acc5b2779b9fade559026536868a8",
    "data/cifar10_subset1000_indices.npy": "54c4a168d718fdf1b5ea1273d95805a44f12254fcb9a5972a3885dffdf2e6610",
}
FIELDS = [
    "sequence_id", "dataset_index", "label", "prediction", "correct",
    "e2e_latency_ms", "kernel_latency_ms", "matrix_kernel_latency_ms",
    "attention_kernel_latency_ms", "kernel_call_count", "matrix_call_count",
    "attention_call_count", "kernel_mean_call_latency_ms", "timestamp", "event_count",
    "selected_mac_count", "mac_without_event_skip", "mac_skip_rate",
    "cycle_count", "matrix_read_beats", "attention_cycle_count",
    "attention_read_beats", "attention_write_beats", "attention_qk_terms", "attention_av_terms",
]
CLASS_NAMES = ["airplane", "automobile", "bird", "cat", "deer",
               "dog", "frog", "horse", "ship", "truck"]
STOP_REQUESTED = False


def request_stop(_signum, _frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_rows(path, valid_indices, expected_labels):
    if not path.exists():
        return []
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    seen = set()
    for row in rows:
        index = int(row["dataset_index"])
        if index not in valid_indices or int(row["label"]) != expected_labels[index]:
            raise RuntimeError(f"invalid resumed row for dataset index {index}")
        if index in seen:
            raise RuntimeError(f"duplicate resumed dataset index {index}")
        seen.add(index)
    return rows


def append_rows(path, rows):
    if not rows:
        return
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())


def numeric(rows, key):
    return np.asarray([float(row[key]) for row in rows], dtype=np.float64)


def progress_payload(rows, total, started_at, status, mode):
    completed = len(rows)
    correct = sum(int(row["correct"]) for row in rows)
    elapsed = max(0.0, time.time() - started_at)
    mean_e2e = float(numeric(rows, "e2e_latency_ms").mean()) if rows else None
    remaining_hours = ((total - completed) * mean_e2e / 3_600_000) if mean_e2e else None
    return {
        "status": status,
        "mode": mode,
        "implementation": "ExSpike-derived binary Spikformer RIA 8:16",
        "completed": completed,
        "total": total,
        "percentage": 100.0 * completed / total,
        "correct": correct,
        "running_accuracy_percent": 100.0 * correct / completed if completed else None,
        "elapsed_hours_this_process": elapsed / 3600.0,
        "estimated_remaining_hours": remaining_hours,
        "mean_e2e_latency_ms": mean_e2e,
        "mean_kernel_latency_ms": float(numeric(rows, "kernel_latency_ms").mean()) if rows else None,
        "mean_matrix_kernel_latency_ms": float(numeric(rows, "matrix_kernel_latency_ms").mean()) if rows else None,
        "mean_attention_kernel_latency_ms": float(numeric(rows, "attention_kernel_latency_ms").mean()) if rows else None,
        "recent_10_e2e_latency_ms": ([float(row["e2e_latency_ms"]) for row in rows[-10:]]
                                      if rows else []),
        "recent_10_kernel_latency_ms": ([float(row["kernel_latency_ms"]) for row in rows[-10:]]
                                         if rows else []),
        "updated_at": datetime.now().astimezone().isoformat(),
    }


def wilson(correct, total, z=1.959963984540054):
    p = correct / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [100 * (center - margin), 100 * (center + margin)]


def write_outputs(output, rows, total, mode, complete, status="running"):
    result_path = output / "results.json"
    result = {
        "status": "complete" if complete else status,
        "mode": mode,
        "samples_planned": total,
        "completed_samples": len(rows),
        "full_cifar10_test_split": mode == "full",
        "sampling": "all official test images" if mode == "full" else "fixed stratified 1000; 100 per class",
        "accuracy_percent": None,
        "ci95_wilson": None,
        "e2e_mean_ms": None,
        "kernel_mean_ms": None,
        "matrix_kernel_mean_ms": None,
        "attention_kernel_mean_ms": None,
    }
    if not complete:
        atomic_json(result_path, result)
        return
    if len(rows) != total or len({int(row["dataset_index"]) for row in rows}) != total:
        raise RuntimeError("completion requires all unique planned samples")
    labels = np.asarray([int(row["label"]) for row in rows], dtype=np.int64)
    predictions = np.asarray([int(row["prediction"]) for row in rows], dtype=np.int64)
    expected_per_class = 1000 if mode == "full" else 100
    counts = np.bincount(labels.astype(np.int32), minlength=10)
    if not np.array_equal(counts, np.full(10, expected_per_class)):
        raise RuntimeError(f"invalid final class counts: {counts.tolist()}")
    correct = int(np.count_nonzero(labels == predictions))
    e2e = numeric(rows, "e2e_latency_ms")
    kernel = numeric(rows, "kernel_latency_ms")
    matrix_kernel = numeric(rows, "matrix_kernel_latency_ms")
    attention_kernel = numeric(rows, "attention_kernel_latency_ms")
    result.update({
        "correct": correct,
        "accuracy_percent": 100.0 * correct / total,
        "ci95_wilson": wilson(correct, total),
        "e2e_mean_ms": float(e2e.mean()),
        "e2e_median_ms": float(np.median(e2e)),
        "kernel_mean_ms": float(kernel.mean()),
        "kernel_median_ms": float(np.median(kernel)),
        "matrix_kernel_mean_ms": float(matrix_kernel.mean()),
        "attention_kernel_mean_ms": float(attention_kernel.mean()),
        "throughput_images_per_second": float(1000.0 * total / e2e.sum()),
    })
    atomic_json(result_path, result)
    confusion = np.zeros((10, 10), dtype=np.int64)
    np.add.at(confusion, (labels, predictions), 1)
    with (output / "per_class.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["class_id", "class_name", "samples", "correct", "accuracy_percent"])
        for class_id, class_name in enumerate(CLASS_NAMES):
            class_correct = int(confusion[class_id, class_id])
            writer.writerow([class_id, class_name, int(counts[class_id]), class_correct,
                             100.0 * class_correct / counts[class_id]])
    with (output / "confusion_matrix.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["true\\pred"] + CLASS_NAMES)
        for class_id, class_name in enumerate(CLASS_NAMES):
            writer.writerow([class_name] + confusion[class_id].tolist())
    with (output / "latency.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["dataset_index", "e2e_latency_ms", "kernel_latency_ms"])
        for row in rows:
            writer.writerow([row["dataset_index"], row["e2e_latency_ms"], row["kernel_latency_ms"]])
    (output / "summary.md").write_text(
        f"# ExSpike-derived binary Spikformer RIA 8:16 — {mode}\n\n"
        f"- Status: complete\n- Samples: {total}\n- Correct: {correct}/{total}\n"
        f"- Accuracy: {result['accuracy_percent']:.4f}%\n"
        f"- Mean E2E: {result['e2e_mean_ms']:.4f} ms/image\n"
        f"- Median E2E: {result['e2e_median_ms']:.4f} ms/image\n"
        f"- Mean aggregate Kernel: {result['kernel_mean_ms']:.4f} ms/image\n"
        f"- Mean 30 matrix Kernels: {result['matrix_kernel_mean_ms']:.4f} ms/image\n"
        f"- Mean 4 Attention Kernels: {result['attention_kernel_mean_ms']:.4f} ms/image\n"
        f"- Full CIFAR-10 test accuracy: {'yes' if mode == 'full' else 'no; fixed stratified 1000 subset'}\n"
    )
    try:
        import matplotlib.pyplot as plt
        running = 100.0 * np.cumsum(labels == predictions) / np.arange(1, total + 1)
        figure, axes = plt.subplots(1, 2, figsize=(11, 4))
        axes[0].plot(running); axes[0].set(title="Running accuracy", xlabel="completed", ylabel="%")
        axes[1].hist(e2e, bins=40); axes[1].set(title="E2E latency", xlabel="ms/image")
        figure.tight_layout(); figure.savefig(output / "accuracy_latency.png", dpi=140); plt.close(figure)
        result["visualization"] = "accuracy_latency.png"
    except Exception as error:
        result["visualization"] = None
        result["visualization_error"] = repr(error)
    atomic_json(result_path, result)


def archive_existing(output):
    names = ["predictions.csv", "progress.json", "results.json", "runner.pid", "runner.log"]
    existing = [output / name for name in names if (output / name).exists()]
    if existing:
        archive = output / ("archive_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        archive.mkdir()
        for path in existing:
            shutil.move(str(path), archive / path.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("full", "subset1000"), required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--save-interval", type=int, default=10)
    parser.add_argument("--start-from-scratch", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.limit < 0 or args.save_interval < 1:
        parser.error("limit must be >=0 and save-interval must be >=1")
    output = args.output_dir or (DEFAULT_OUTPUT / args.mode)
    total = 10000 if args.mode == "full" else 1000
    per_class = 1000 if args.mode == "full" else 100

    for name, expected in EXPECTED.items():
        actual = sha256(PACKAGE_ROOT / name)
        if actual != expected:
            raise RuntimeError(f"protected artifact mismatch: {name}: {actual} != {expected}")
    if args.mode == "full":
        images = np.load(HERE / "cifar10_test_images.npy", mmap_mode="r", allow_pickle=False)
        labels = np.load(HERE / "cifar10_test_labels.npy", mmap_mode="r", allow_pickle=False)
        indices = np.load(HERE / "cifar10_test_indices.npy", mmap_mode="r", allow_pickle=False)
    else:
        images = np.load(PACKAGE_ROOT / "data" / "cifar10_subset1000_images.npy", mmap_mode="r", allow_pickle=False)
        labels = np.load(PACKAGE_ROOT / "data" / "cifar10_subset1000_labels.npy", mmap_mode="r", allow_pickle=False)
        indices = np.load(PACKAGE_ROOT / "data" / "cifar10_subset1000_indices.npy", mmap_mode="r", allow_pickle=False)
    if images.shape != (total, 3, 32, 32) or images.dtype != np.float32:
        raise RuntimeError("invalid selected image tensor")
    if len(indices) != total or np.unique(indices).size != total:
        raise RuntimeError("invalid selected indices")
    if not np.array_equal(np.bincount(labels.astype(np.int32), minlength=10), np.full(10, per_class)):
        raise RuntimeError("invalid class balance")
    if args.validate_only:
        print(json.dumps({"status": "PASS", "mode": args.mode, "samples": total,
                          "shape": list(images.shape), "dtype": str(images.dtype),
                          "class_counts": np.bincount(labels.astype(np.int32), minlength=10).tolist()}))
        return 0

    output.mkdir(parents=True, exist_ok=True)
    if args.start_from_scratch:
        archive_existing(output)

    csv_path = output / "predictions.csv"
    progress_path = output / "progress.json"
    pid_path = output / "runner.pid"
    expected_labels = {int(index): int(label) for index, label in zip(indices, labels)}
    rows = read_rows(csv_path, set(expected_labels), expected_labels)
    if progress_path.exists():
        previous = json.loads(progress_path.read_text())
        if (previous.get("mode") != args.mode or previous.get("total") != total or
                previous.get("completed") != len(rows)):
            raise RuntimeError("predictions.csv and progress.json are inconsistent; refusing silent resume")
    elif rows:
        raise RuntimeError("predictions.csv exists without progress.json; refusing silent resume")
    completed = {int(row["dataset_index"]) for row in rows}
    remaining = [position for position, index in enumerate(indices) if int(index) not in completed]
    if args.limit:
        remaining = remaining[:args.limit]
    started_at = time.time()
    atomic_json(pid_path, {"pid": os.getpid(), "mode": args.mode,
                           "started_at": datetime.now().astimezone().isoformat(),
                           "command": " ".join(sys.argv)})
    atomic_json(progress_path, progress_payload(rows, total, started_at, "initializing_hardware", args.mode))
    write_outputs(output, rows, total, args.mode, complete=False)
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    pending = []
    try:
        weights = WeightStore()
        backend = PynqBackend(weights)
        if not backend.is_hardware:
            raise RuntimeError("PynqBackend required; CPU fallback is refused")
        runtime = SpikformerRuntime(backend, weights)
        atomic_json(progress_path, progress_payload(rows, total, started_at, "running", args.mode))
        for position in remaining:
            if STOP_REQUESTED:
                break
            index = int(indices[position])
            label = int(labels[position])
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
            if not np.isfinite(logits).all():
                raise RuntimeError(f"non-finite logits at position {position}")
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
            prediction = int(np.argmax(logits[0]))
            event_count = sum(int(item["events"]) for item in events)
            selected_mac_count = sum(int(item["actual_selected_mac_issues"]) for item in events)
            mac_without_skip = sum(int(item["selected_macs_without_event_skip"]) for item in events)
            skip_rate = 1.0 - selected_mac_count / mac_without_skip if mac_without_skip else None
            pending.append({
                "sequence_id": int(position), "dataset_index": index, "label": label,
                "prediction": prediction, "correct": int(prediction == label),
                "e2e_latency_ms": f"{e2e_ms:.9f}",
                "kernel_latency_ms": f"{kernel_ms:.9f}",
                "matrix_kernel_latency_ms": f"{matrix_ms:.9f}",
                "attention_kernel_latency_ms": f"{attention_ms:.9f}",
                "kernel_call_count": calls,
                "matrix_call_count": matrix_calls,
                "attention_call_count": attention_calls,
                "kernel_mean_call_latency_ms": f"{kernel_ms / calls:.9f}" if calls else "",
                "timestamp": datetime.now().astimezone().isoformat(),
                "event_count": event_count,
                "selected_mac_count": selected_mac_count,
                "mac_without_event_skip": mac_without_skip,
                "mac_skip_rate": f"{skip_rate:.12f}" if skip_rate is not None else "",
                "cycle_count": sum(int(item["cycles"]) for item in events),
                "matrix_read_beats": sum(int(item["read_beats"]) for item in events),
                "attention_cycle_count": sum(int(item["cycles"]) for item in attentions),
                "attention_read_beats": sum(int(item["read_beats"]) for item in attentions),
                "attention_write_beats": sum(int(item["write_beats"]) for item in attentions),
                "attention_qk_terms": sum(int(item["qk_terms"]) for item in attentions),
                "attention_av_terms": sum(int(item["av_terms"]) for item in attentions),
            })
            backend.event_records.clear()
            if len(pending) >= args.save_interval or STOP_REQUESTED:
                append_rows(csv_path, pending)
                rows.extend(pending)
                pending.clear()
                status = "stopping" if STOP_REQUESTED else "running"
                atomic_json(progress_path, progress_payload(rows, total, started_at, status, args.mode))
                write_outputs(output, rows, total, args.mode, complete=False)
                print(json.dumps(progress_payload(rows, total, started_at, status, args.mode)), flush=True)
        if pending:
            append_rows(csv_path, pending)
            rows.extend(pending)
        complete = len(rows) == total
        status = "complete" if complete else ("interrupted" if STOP_REQUESTED else "diagnostic_limit_reached")
        atomic_json(progress_path, progress_payload(rows, total, started_at, status, args.mode))
        write_outputs(output, rows, total, args.mode, complete, status=status)
        return 0
    finally:
        try:
            state = json.loads(pid_path.read_text()) if pid_path.exists() else {}
            if state.get("pid") == os.getpid():
                pid_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
