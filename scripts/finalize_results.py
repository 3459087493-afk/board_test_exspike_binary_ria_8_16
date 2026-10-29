#!/usr/bin/env python3
"""Validate the completed 1000-image result, write the final comparison, SHA256 and zip.

Run after results/subset1000/results.json is complete and the poller has
fetched predictions.csv/results.json.  This script refuses to finalize an
incomplete run and never copies a running accuracy into a final claim.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / 'results' / 'subset1000'
BIN_RESULTS = RESULT_DIR / 'results.json'
BIN_PRED = RESULT_DIR / 'predictions.csv'
V1_RESULTS = ROOT / 'reference' / 'v1_formal' / 'v1_formal_results.json'
V1_PRED = ROOT / 'reference' / 'v1_formal' / 'v1_formal_predictions.csv'
SOFTWARE = ROOT / 'reference' / 'software' / 'summary.json'
DATA = ROOT / 'data'
REPORTS = ROOT / 'reports'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read_rows(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def stats(values):
    a = np.asarray(values, dtype=np.float64)
    return {'mean': float(a.mean()), 'median': float(np.median(a)),
            'p75': float(np.percentile(a, 75)), 'p95': float(np.percentile(a, 95)),
            'min': float(a.min()), 'max': float(a.max()), 'std': float(a.std())}


def validate(rows, indices, labels, name):
    assert len(rows) == 1000, f'{name}: expected 1000 rows, got {len(rows)}'
    seq = np.asarray([int(r['sequence_id']) for r in rows])
    di = np.asarray([int(r['dataset_index']) for r in rows])
    lb = np.asarray([int(r['label']) for r in rows])
    pr = np.asarray([int(r['prediction']) for r in rows])
    assert np.array_equal(seq, np.arange(1000)), f'{name}: sequence mismatch'
    assert np.array_equal(di, indices), f'{name}: dataset_index order mismatch'
    assert np.array_equal(lb, labels), f'{name}: labels mismatch'
    assert len(set(di.tolist())) == 1000, f'{name}: duplicate indices'
    assert np.all((pr >= 0) & (pr < 10)), f'{name}: invalid predictions'
    calls = {(int(r['kernel_call_count']), int(r['matrix_call_count']),
              int(r['attention_call_count'])) for r in rows}
    assert calls == {(34, 30, 4)}, f'{name}: call counts {calls}'
    return seq, di, lb, pr


def collect(rows):
    e2e = [float(r['e2e_latency_ms']) for r in rows]
    ker = [float(r['kernel_latency_ms']) for r in rows]
    mat = [float(r['matrix_kernel_latency_ms']) for r in rows]
    att = [float(r['attention_kernel_latency_ms']) for r in rows]
    events = [float(r['event_count']) for r in rows]
    selected = [float(r['selected_mac_count']) for r in rows]
    skip = [float(r['mac_skip_rate']) for r in rows if r['mac_skip_rate'] not in ('', None)]
    return {
        'e2e': stats(e2e), 'kernel': stats(ker), 'matrix': stats(mat),
        'attention': stats(att), 'event_mean': float(np.mean(events)),
        'selected_mac_mean': float(np.mean(selected)),
        'mac_skip_mean': float(np.mean(skip)) if skip else None,
    }


def main():
    if not BIN_RESULTS.exists() or not BIN_PRED.exists():
        raise SystemExit('1000-image results are not present yet; refusing to finalize.')
    result = json.loads(BIN_RESULTS.read_text())
    if result.get('status') != 'complete' or result.get('completed_samples') != 1000:
        raise SystemExit(f'1000-image run is not complete: {result.get("status")} '
                         f'{result.get("completed_samples")}/1000')
    indices = np.load(DATA / 'cifar10_subset1000_indices.npy')
    labels = np.load(DATA / 'cifar10_subset1000_labels.npy')
    rows = read_rows(BIN_PRED)
    _, di, lb, pr = validate(rows, indices, labels, 'binary')
    correct = int(np.count_nonzero(pr == lb))
    assert correct == result['correct'], (correct, result['correct'])
    v1_rows = read_rows(V1_PRED)
    _, _, v1_lb, v1_pr = validate(v1_rows, indices, labels, 'v1')
    v1_result = json.loads(V1_RESULTS.read_text())

    bin_stats = collect(rows)
    v1_stats = collect(v1_rows)
    software = json.loads(SOFTWARE.read_text()) if SOFTWARE.exists() else {}

    comparison = {
        'status': 'complete',
        'binary': {
            'checkpoint_sha256': sha256(ROOT / 'model' / 'binary_ria_pruned_816.pth'),
            'weights_sha256': sha256(ROOT / 'deployment' / 'binary_ria_8_16_weights.npz'),
            'board_accuracy_percent': 100.0 * correct / 1000,
            'board_correct': correct,
            'board_errors': 1000 - correct,
            'board_e2e_mean_ms': bin_stats['e2e']['mean'],
            'board_e2e_median_ms': bin_stats['e2e']['median'],
            'board_e2e_p75_ms': bin_stats['e2e']['p75'],
            'board_e2e_p95_ms': bin_stats['e2e']['p95'],
            'board_kernel_mean_ms': bin_stats['kernel']['mean'],
            'board_matrix_mean_ms': bin_stats['matrix']['mean'],
            'board_attention_mean_ms': bin_stats['attention']['mean'],
            'board_throughput_img_s': 1000.0 / sum(float(r['e2e_latency_ms']) for r in rows) * 1000.0,
            'event_mean': bin_stats['event_mean'],
            'selected_mac_mean': bin_stats['selected_mac_mean'],
            'mac_skip_mean': bin_stats['mac_skip_mean'],
            'software_accuracy_percent': software.get('binary_reference_accuracy_percent'),
        },
        'ternary_v1': {
            'board_accuracy_percent': v1_result.get('accuracy_percent'),
            'board_correct': v1_result.get('correct'),
            'board_e2e_mean_ms': v1_result.get('e2e_mean_ms'),
            'board_e2e_median_ms': v1_result.get('e2e_median_ms'),
            'board_kernel_mean_ms': v1_result.get('kernel_mean_ms'),
            'board_matrix_mean_ms': v1_result.get('matrix_kernel_mean_ms'),
            'board_attention_mean_ms': v1_result.get('attention_kernel_mean_ms'),
            'board_throughput_img_s': v1_result.get('throughput_images_per_second'),
            'event_mean': v1_stats['event_mean'],
            'selected_mac_mean': v1_stats['selected_mac_mean'],
            'mac_skip_mean': v1_stats['mac_skip_mean'],
            'software_accuracy_percent': software.get('ternary_v1_software_accuracy_percent'),
        },
        'delta_board_accuracy_pp': 100.0 * correct / 1000 - float(v1_result['accuracy_percent']),
        'delta_e2e_ms': bin_stats['e2e']['mean'] - float(v1_result['e2e_mean_ms']),
        'delta_kernel_ms': bin_stats['kernel']['mean'] - float(v1_result['kernel_mean_ms']),
        'hashes': {
            'bit': sha256(ROOT / 'hardware' / 'exspike_migration_8_16.bit'),
            'hwh': sha256(ROOT / 'hardware' / 'exspike_migration_8_16.hwh'),
            'v1_formal_predictions': sha256(V1_PRED),
            'binary_predictions': sha256(BIN_PRED),
        },
    }
    (RESULT_DIR / 'final_summary.json').write_text(json.dumps(comparison, indent=2) + '\n')

    lines = [
        '# 二值 vs 三值最终结果（1000 张固定子集）', '',
        '| 指标 | 三值 V1 | 二值 | 差值（二值−三值） |', '|---|---:|---:|---:|',
        f"| 板端 Top-1 | {comparison['ternary_v1']['board_accuracy_percent']:.2f}% | "
        f"{comparison['binary']['board_accuracy_percent']:.2f}% | "
        f"{comparison['delta_board_accuracy_pp']:+.2f} pp |",
        f"| 正确/总数 | {comparison['ternary_v1']['board_correct']}/1000 | "
        f"{comparison['binary']['board_correct']}/1000 | "
        f"{comparison['binary']['board_correct'] - comparison['ternary_v1']['board_correct']:+d} |",
        f"| 平均 E2E | {comparison['ternary_v1']['board_e2e_mean_ms']:.4f} ms | "
        f"{comparison['binary']['board_e2e_mean_ms']:.4f} ms | {comparison['delta_e2e_ms']:+.4f} ms |",
        f"| 中位数 E2E | {comparison['ternary_v1']['board_e2e_median_ms']:.4f} ms | "
        f"{comparison['binary']['board_e2e_median_ms']:.4f} ms | — |",
        f"| 平均 Kernel | {comparison['ternary_v1']['board_kernel_mean_ms']:.4f} ms | "
        f"{comparison['binary']['board_kernel_mean_ms']:.4f} ms | {comparison['delta_kernel_ms']:+.4f} ms |",
        f"| 矩阵核 | {comparison['ternary_v1']['board_matrix_mean_ms']:.4f} ms | "
        f"{comparison['binary']['board_matrix_mean_ms']:.4f} ms | — |",
        f"| Attention 核 | {comparison['ternary_v1']['board_attention_mean_ms']:.4f} ms | "
        f"{comparison['binary']['board_attention_mean_ms']:.4f} ms | — |",
        f"| 吞吐率 | {comparison['ternary_v1']['board_throughput_img_s']:.6f} img/s | "
        f"{comparison['binary']['board_throughput_img_s']:.6f} img/s | — |",
        f"| 平均 event_count | {comparison['ternary_v1']['event_mean']:.0f} | "
        f"{comparison['binary']['event_mean']:.0f} | — |",
        f"| 平均 selected MAC | {comparison['ternary_v1']['selected_mac_mean']:.0f} | "
        f"{comparison['binary']['selected_mac_mean']:.0f} | — |",
        f"| 平均 MAC skip rate | {comparison['ternary_v1']['mac_skip_mean']:.6f} | "
        f"{comparison['binary']['mac_skip_mean']:.6f} | — |",
        f"| 软件 Top-1（同子集） | {comparison['ternary_v1']['software_accuracy_percent']:.2f}% | "
        f"{comparison['binary']['software_accuracy_percent']:.2f}% | — |",
        '', '## 说明', '',
        '- 二值/三值均使用同一 PYNQ-Z2、同一固定 1000 张、同一预处理、同一 34/30/4 调用图。',
        '- 二值板端数字来自本目录 `results/subset1000/`，不是软件 88.50% 的替代。',
        '- 硬件复用 V1 bit/HWH，资源/时序/DRC 与 V1 相同；`1.444 W` 是 V1 的 Vivado vectorless 估算，不是二值独立功耗或整板实测。',
        '- 二值模型源码与 checkpoint 键名兼容性见 `reports/PHASE2_BINARY_AUDIT.md`。',
    ]
    (REPORTS / 'FINAL_RESULTS.md').write_text('\n'.join(lines) + '\n')
    with (REPORTS / 'FINAL_COMPARISON.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['metric', 'ternary_v1', 'binary', 'delta_binary_minus_ternary'])
        w.writerow(['board_top1_percent', comparison['ternary_v1']['board_accuracy_percent'],
                    comparison['binary']['board_accuracy_percent'], comparison['delta_board_accuracy_pp']])
        w.writerow(['board_e2e_mean_ms', comparison['ternary_v1']['board_e2e_mean_ms'],
                    comparison['binary']['board_e2e_mean_ms'], comparison['delta_e2e_ms']])
        w.writerow(['board_kernel_mean_ms', comparison['ternary_v1']['board_kernel_mean_ms'],
                    comparison['binary']['board_kernel_mean_ms'], comparison['delta_kernel_ms']])
        w.writerow(['board_matrix_mean_ms', comparison['ternary_v1']['board_matrix_mean_ms'],
                    comparison['binary']['board_matrix_mean_ms'], ''])
        w.writerow(['board_attention_mean_ms', comparison['ternary_v1']['board_attention_mean_ms'],
                    comparison['binary']['board_attention_mean_ms'], ''])
        w.writerow(['software_top1_percent', comparison['ternary_v1']['software_accuracy_percent'],
                    comparison['binary']['software_accuracy_percent'], ''])

    # Package manifest and zip.  Exclude caches and the zip itself.
    cache_dirs = [p for p in ROOT.rglob('__pycache__') if p.is_dir()]
    for p in cache_dirs:
        shutil.rmtree(p, ignore_errors=True)
    manifest = ROOT / 'SHA256SUMS.txt'
    files = sorted(p for p in ROOT.rglob('*') if p.is_file()
                   and p.name != 'SHA256SUMS.txt' and p.suffix != '.pyc')
    manifest.write_text(''.join(f'{sha256(p)}  {p.relative_to(ROOT)}\n' for p in files))
    archive_path = ROOT.parent / 'board_test_exspike_binary_ria_8_16_package.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob('*')):
            if p.is_file() and p.suffix != '.pyc' and '__pycache__' not in p.parts:
                z.write(p, p.relative_to(ROOT))
    print(json.dumps(comparison, indent=2))
    print('wrote', REPORTS / 'FINAL_RESULTS.md')
    print('wrote', REPORTS / 'FINAL_COMPARISON.csv')
    print('wrote', manifest)
    print('wrote', archive_path, archive_path.stat().st_size)


if __name__ == '__main__':
    main()
