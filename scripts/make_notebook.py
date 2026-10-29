#!/usr/bin/env python3
"""Generate the runnable PYNQ notebook for the binary RIA 8:16 experiment."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'notebooks' / 'binary_ria_8_16_pynq_z2.ipynb'

CELLS = []

CELLS.append(('markdown', r'''# 二值脉冲 Spikformer + RIA 8:16 — PYNQ-Z2 上板 Notebook

本 Notebook 对应独立目录 `board_test_exspike_binary_ria_8_16`。

- 二值 checkpoint：`model/binary_ria_pruned_816.pth`，`spike_mode=binary`，20 个 RIA 8:16 mask，50% 结构稀疏。
- 硬件：复用 V1 最终 `exspike_migration_8_16.bit/.hwh`；PL 30 次矩阵 + 4 次 Attention；ARM 执行 im2col/BN/LIF/Pooling/残差/reshape/量化。
- 数据：与 V1 完全相同的固定 1000 张（每类 100 张）。
- 二值 0/1 Q/K/V 进入硬件；运行时断言 Q/K/V 只含 0/1，没有任何三值脉冲被送入 Attention 核。

> **注意**：如果 `pgrep board_runner.py` 显示 1000 张任务正在运行，请不要执行 Phase A/B 单元，只执行进度/最终单元。正式 1000 张已经通过 SSH 启动（PID 14668）；本 Notebook 的 Phase C 默认只打印 SSH 命令，避免在 Jupyter 内核中触发 PYNQ 2.7 的 XRT 分配问题。
'''))

CELLS.append(('code', r'''from pathlib import Path
import getpass, hashlib, json, os, subprocess, sys, time
import numpy as np

RUN_DIR = Path.cwd()
if not (RUN_DIR / 'deployment' / 'board_runtime.py').exists():
    RUN_DIR = Path('/home/xilinx/jupyter_notebooks/board_test_exspike_binary_ria_8_16')
PYTHON = '/usr/local/share/pynq-venv/bin/python3'
RESULT_ROOT = RUN_DIR / 'results'
SUDO_PASSWORD = os.environ.get('PYNQ_PASSWORD', 'xilinx')
EXPECTED = {
    'hardware/exspike_migration_8_16.bit': '92c8657baff4154ebf1c4339272d6b6f7d3c70ec0de1d8ad1561fd41a189b5a8',
    'hardware/exspike_migration_8_16.hwh': '3f3173d8a047be1a1c1ab80c78c50f33fdbb48f3c53836ec18c923d26dd5c043',
    'deployment/binary_ria_8_16_weights.npz': '7972f820b767e72465e89228a0cc93f4b54733cfd081b31172fbb4c6c10eaec9',
    'data/cifar10_subset1000_images.npy': 'b1ade992f818f678a138e97a334d3134e1535c313acb0d2e816770abb76a26ba',
    'data/cifar10_subset1000_labels.npy': '998b571dc076fcb72fe5d9e6de50e89c958acc5b2779b9fade559026536868a8',
    'data/cifar10_subset1000_indices.npy': '54c4a168d718fdf1b5ea1273d95805a44f12254fcb9a5972a3885dffdf2e6610',
}
def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()
bad = []
for name, expected in EXPECTED.items():
    actual = sha256(RUN_DIR / name)
    if actual != expected:
        bad.append((name, actual, expected))
assert not bad, bad
print('package hash: PASS', len(EXPECTED), 'files')
print(subprocess.run([PYTHON, '-c', 'import pynq; print("PYNQ", pynq.__version__)'],
                     capture_output=True, text=True).stdout.strip())
ACTIVE = subprocess.run(['pgrep', '-af', '[b]oard_runner.py'], capture_output=True, text=True).stdout.strip()
print('active 1000-image runner:', ACTIVE or 'none')
'''))

CELLS.append(('code', r'''def sudo_run(args, log_path):
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['sudo', '-S', 'env', 'XILINX_XRT=/usr', PYTHON, '-u'] + [str(a) for a in args]
    with log_path.open('wb') as log:
        proc = subprocess.run(cmd, cwd=RUN_DIR, input=(SUDO_PASSWORD + '\n').encode(),
                              stdout=log, stderr=subprocess.STDOUT)
    return proc.returncode
'''))

CELLS.append(('code', r'''# Phase A：单张。把 RUN_SINGLE 改为 True 才会执行。
RUN_SINGLE = False
if ACTIVE:
    print('REFUSED: 1000-image runner is active; do not run Phase A now.')
elif not RUN_SINGLE:
    print('Set RUN_SINGLE = True to run the single-image gate.')
else:
    rc = sudo_run(['deployment/run_single.py', '--position', '0'], '/tmp/binary_single.log')
    print(Path('/tmp/binary_single.log').read_text())
    single = json.loads((RUN_DIR / 'results' / 'single' / 'single.json').read_text())
    print(json.dumps(single, indent=2))
    assert single['status'] == 'PASS'
    assert single['max_abs_logit_error_numpy_vs_pl'] <= 1e-5
    assert (single['kernel_calls'], single['matrix_calls'], single['attention_calls']) == (34, 30, 4)
'''))

CELLS.append(('code', r'''# Phase B：10 张。把 RUN_TEN 改为 True 才会执行。
RUN_TEN = False
if ACTIVE:
    print('REFUSED: 1000-image runner is active; do not run Phase B now.')
elif not RUN_TEN:
    print('Set RUN_TEN = True to run the 10-image gate.')
else:
    rc = sudo_run(['deployment/run_10.py', '--fresh'], '/tmp/binary_ten.log')
    print(Path('/tmp/binary_ten.log').read_text())
    rc2 = sudo_run(['deployment/summarize_ten.py', '--output-dir', 'results/ten'],
                   '/tmp/binary_ten_summary.log')
    print(Path('/tmp/binary_ten_summary.log').read_text())
    ten = json.loads((RUN_DIR / 'results' / 'ten' / 'ten_summary.json').read_text())
    print(json.dumps(ten, indent=2))
    assert ten['samples'] == 10 and ten['call_counts'] == [[34, 30, 4]]
'''))

CELLS.append(('code', r'''# Phase C：1000 张。默认只打印 SSH 命令，不在 Notebook 内核里启动。
CONFIRM_1000 = False
START_IN_NOTEBOOK = False
SSH_COMMAND = (
    'cd /home/xilinx/jupyter_notebooks/board_test_exspike_binary_ria_8_16 && '
    'sudo -S env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -u '
    'deployment/run_1000.py --confirm-1000 --output-dir results/subset1000 --save-interval 10'
)
if ACTIVE:
    print('1000-image runner already active:', ACTIVE)
elif not CONFIRM_1000:
    print('Set CONFIRM_1000 = True only after Phase A and Phase B pass.')
elif not START_IN_NOTEBOOK:
    print('Run this in a board SSH terminal:')
    print(SSH_COMMAND)
else:
    log_path = Path('/tmp/binary_1000_stdout.log')
    cmd = ['sudo', '-S', 'env', 'XILINX_XRT=/usr', PYTHON, '-u',
           str(RUN_DIR / 'deployment' / 'run_1000.py'), '--confirm-1000',
           '--output-dir', 'results/subset1000', '--save-interval', '10', '--fresh']
    log = log_path.open('wb')
    p = subprocess.Popen(cmd, cwd=RUN_DIR, stdin=subprocess.PIPE,
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    p.stdin.write((SUDO_PASSWORD + '\n').encode()); p.stdin.flush(); p.stdin.close()
    print('started PID', p.pid, 'log', log_path)
    print('If XRT CMA allocation fails, use the SSH command above.')
'''))

CELLS.append(('code', r'''# 进度：每 10 张更新；以 progress.json 为准。
progress_path = RUN_DIR / 'results' / 'subset1000' / 'progress.json'
if progress_path.exists():
    progress = json.loads(progress_path.read_text())
    print(json.dumps(progress, indent=2))
else:
    print('No results/subset1000/progress.json yet.')
'''))

CELLS.append(('code', r'''# 最终统计：只有 status=complete 且 completed_samples=1000 才显示最终结果。
from IPython.display import Markdown, display
result_path = RUN_DIR / 'results' / 'subset1000' / 'results.json'
if not result_path.exists():
    print('No formal results yet.')
else:
    result = json.loads(result_path.read_text())
    print(json.dumps(result, indent=2))
    if result.get('status') != 'complete' or result.get('completed_samples') != 1000:
        print('正式 1000 张尚未完成；当前数字不能作为最终 Top-1/延迟。')
    else:
        v1_path = RUN_DIR / 'reference' / 'v1_formal' / 'v1_formal_results.json'
        v1 = json.loads(v1_path.read_text()) if v1_path.exists() else {}
        def fmt(value, digits=2, suffix=''):
            return f'{value:.{digits}f}{suffix}' if isinstance(value, (int, float)) else 'N/A'
        lines = [
            '| 指标 | 三值 V1 | 二值 |', '|---|---:|---:|',
            f"| 板端 Top-1 | {fmt(v1.get('accuracy_percent'), 2, '%')} | {fmt(result.get('accuracy_percent'), 2, '%')} |",
            f"| 平均 E2E | {fmt(v1.get('e2e_mean_ms'), 4, ' ms')} | {fmt(result.get('e2e_mean_ms'), 4, ' ms')} |",
            f"| 平均 Kernel | {fmt(v1.get('kernel_mean_ms'), 4, ' ms')} | {fmt(result.get('kernel_mean_ms'), 4, ' ms')} |",
            f"| 矩阵核 | {fmt(v1.get('matrix_kernel_mean_ms'), 4, ' ms')} | {fmt(result.get('matrix_kernel_mean_ms'), 4, ' ms')} |",
            f"| Attention 核 | {fmt(v1.get('attention_kernel_mean_ms'), 4, ' ms')} | {fmt(result.get('attention_kernel_mean_ms'), 4, ' ms')} |",
            f"| 吞吐率 | {fmt(v1.get('throughput_images_per_second'), 6, ' img/s')} | {fmt(result.get('throughput_images_per_second'), 6, ' img/s')} |",
        ]
        display(Markdown('\n'.join(lines)))
'''))

CELLS.append(('markdown', r'''## 说明

- 二值软件参考为 885/1000 = 88.50%；这是软件 float 结果，不是 FPGA 实测。
- 二值板端 Phase A 为 max_abs=0.0；Phase B 为 10/10、34/30/4；Phase C 1000 张以 `results/subset1000/results.json` 为准。
- 硬件复用 V1 bit/HWH，没有独立二值综合；资源/时序相同，`1.444 W` 是 V1 的 Vivado vectorless 估算，不是板端实测。
- `spikformer-main/cifar10/model.py` 与 checkpoint 不兼容；实际执行图是 `model/binary_model_adapter.py`，详见 `reports/PHASE2_BINARY_AUDIT.md`。
'''))


def main():
    nb = {
        'cells': [],
        'metadata': {
            'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
            'language_info': {'name': 'python'},
        },
        'nbformat': 4,
        'nbformat_minor': 5,
    }
    for cell_type, source in CELLS:
        cell = {'cell_type': cell_type, 'metadata': {}, 'source': source.splitlines(keepends=True)}
        if cell_type == 'code':
            cell['execution_count'] = None
            cell['outputs'] = []
        nb['cells'].append(cell)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n')
    print('wrote', OUT)


if __name__ == '__main__':
    main()
