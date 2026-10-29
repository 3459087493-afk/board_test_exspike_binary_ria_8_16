# 二值脉冲 Spikformer + RIA 8:16 — PYNQ-Z2 1000 张上板实验

本目录是与三值 V1（`board_test_exspike_main2_8_16_migration_v1`）并列的**独立二值上板实验目录**。V1、ExSpike-main、原始模型文件和 checkpoint 均未被修改。

## 0. 当前状态（2026-01-03）

| 阶段 | 状态 | 结果 |
|---|---|---|
| 软件参考（二值 1000 张） | **PASS** | 885/1000 = **88.50%**，与已有二值 logits 逐元素一致（max_abs=0.0，1000/1000 预测一致） |
| Phase A 单张上板 | **PASS** | 数据集索引 6764，标签 5；NumPy 整数参考与真实 PL 的 10 个 logits **完全一致（max_abs=0.0）**，预测均为 5；34/30/4 次调用 |
| Phase B 10 张上板 | **PASS** | **10/10 正确**，10/10 与软件参考预测一致；34/30/4 次调用；平均端到端 **17.3415 s/图**，Kernel **7.4506 s/图** |
| Phase C 1000 张上板 | **运行中** | 第一次运行 33/1000 因 PYNQ 2.7 CMA 泄漏停止；修复 Attention 共享缓冲区后，于 **2026-01-03 01:22:02** 从 0 重启，PID **15998**，输出 `results/subset1000/`；首 10 张 10/10；当前 240/1000（212 正确，running 88.33%；均值 16.9250 s/图），继续运行；以 `progress.json` 为准，**当前不得把进度当作最终 Top-1** |

> Phase C 启动后每 10 张原子保存 `predictions.csv` / `progress.json`。完成后最终 Top-1、端到端延迟、Kernel 延迟、资源/功耗对比必须从 `results/subset1000/results.json` 与逐样本 CSV 读取。本文档中所有“二值板端 1000 张”字段在任务完成前都标记为“待完成”。

## 1. 目标与对照

- 同一块 PYNQ-Z2（XC7Z020-CLG400-1），同一 1000 张固定 CIFAR-10 子集（每类 100 张），同一预处理、同一排序、同一统计口径。
- 三值 V1 是唯一对照基准：**板端 904/1000 = 90.40%**，平均端到端 16848.0378 ms/图，Kernel 7121.1221 ms/图。
- 二值模型使用同一 ExSpike 派生硬件分区：PL 执行 30 次 Conv/Linear 矩阵调用 + 4 次 Attention 调用；ARM/PS 执行 im2col、BN、LIF、Pooling、残差、reshape、量化/反量化。
- 二值模型与三值模型的差异必须来自**脉冲语义**（二值 0/1 vs 三值 −1/0/+1），不能通过伪造三值脉冲或 CPU 回退冒充。

## 2. 目录结构

```text
board_test_exspike_binary_ria_8_16/
  README.md                       本文件
  model/                          二值 checkpoint、checkpoint 兼容图、参考训练模型
  deployment/                     二值 PYNQ 运行时、权重、单张/10/1000 入口
  hardware/                       V1 最终 bit/HWH/XSA 与资源、时序、功耗、DRC 报告
  data/                           固定 1000 张图像/标签/索引（与 V1 完全一致）
  reference/v1_formal/            V1 正式 1000 张冻结记录（只读复制）
  reference/software/             二值/三值软件参考 logits、预测、指标
  reports/                        中文审计、兼容性、资源功耗、对比、上板日志
  scripts/                        权重导出、软件验证、Notebook 生成
  notebooks/                      可直接运行的 PYNQ Notebook
  results/                        板端结果（single/ten/subset1000）
  rtl/ sim/                       V1 适配 RTL、仿真与 Vivado 构建脚本（复用参考）
```

## 3. 模型来源与兼容性（论文必须说明）

- 二值 checkpoint：`model/binary_ria_pruned_816.pth`
  - SHA256 `6ee6a084f61b7b20c4730a1a8ab043079bbd38342bd422ccd32436562b6bd7ad`
  - 顶层字段：`state_dict`、`config`、`ria_nm="8:16"`、`source_checkpoint`、`model_source`、`spike_mode="binary"`
  - 224 个 state key；20 个 RIA mask；6,488,064 个 RIA 权重，3,244,032 个保留，**50.000%**，每组严格 8-of-16；`weight_orig` 已按 mask 置零。
- **不能使用** `spikformer-main/cifar10/model.py` 直接加载该 checkpoint：
  - 该文件的 SHA256 为 `2fd22031...`，定义的是 `q_linear/proj_linear/fc1_linear/fc2_linear` 与 SPS `rpe_conv`，参数名与 shape 均不匹配。
  - `model_binary.py` 的 SHA256 为 `a91c849b...`，虽然文件名含 binary，但实际定义的是 **三值** LIF（`TernarySpikeFunction`），不能用于本实验。
- 可用的语义参考模型：`model/reference_training_model.py`
  - SHA256 `2bc9ac76ba83fb2d2ccd1e6b338c236c5721dd05e6346b1b432d2150a8dbf73b`
  - 二值 0/1 `MultiStepLIFNode`、Q/K/V Conv1d、`attn_lif` 阈值 0.5、pool 在 proj2/proj3 之后；但属性名是 `proj*/proj1_*`，与 checkpoint 的 `block0..4` 键不同。
- 实际执行图：`model/binary_model_adapter.py`
  - 使用 checkpoint 的 `block0..4` 键名；与上述语义参考模型逐图 **bit-exact**（前 20 张 max_abs=0.0，预测 20/20 一致）。
  - 二值语义：`v = v + (x-v)/2`；`s = (v >= 1)`；硬重置 `v = v*(1-s)`；Attention LIF 阈值 0.5；attention scale 0.125；Q/K/V 只取 0/1。
- checkpoint 内部记录的 `model_source` 是 `/home/free/prj/finn/Spikingformer/cifar10/model.py`，本机不存在；本目录用上述可复现的兼容图实现，并在 `reports/PHASE2_BINARY_AUDIT.md` 中完整记录差异。

## 4. 硬件与分区

- 复用 V1 最终硬件，不重新综合，不使用 V11：
  - `hardware/exspike_migration_8_16.bit` SHA256 `92c8657baff4154ebf1c4339272d6b6f7d3c70ec0de1d8ad1561fd41a189b5a8`
  - `hardware/exspike_migration_8_16.hwh` SHA256 `3f3173d8a047be1a1c1ab80c78c50f33fdbb48f3c53836ec18c923d26dd5c043`
  - `hardware/exspike_migration_8_16_build.xsa` SHA256 `050ca2a4abfc00aeb0921ea3457ae078f9f38d92a796fee3249f5e5a249098ec`
- 板上实际环境为 **PynqLinux 2.7.0 / Linux 5.4.0-xilinx-v2020.2 / armv7l**（不是 V1 报告中的 PYNQ 3.1）。已实测 `Overlay` 能解析 V1 HWH，`exspike_0` @ `0x40000000`、`attention_0` @ `0x40001000` 均存在；`allocate/flush/invalidate/freebuffer` 均可用。
- PL 分区（与 V1 相同）：
  - 30 次矩阵核：5 个 tokenizer Conv、4 个 block 的 Q/K/V/proj 与 MLP1/MLP2、最后 head。
  - 4 次 Attention 核：QK^T、Attention×V、×0.125、二值 hard-reset LIF（阈值 0.5）。
- ARM/PS：im2col、全部 BN、所有 LIF、Pooling、残差、reshape、动态 int16 输入量化与反量化。
- 二值模型只把 Q/K/V LIF 从 V1 的三值 soft-reset 改为二值 hard-reset；硬件接收的 Q/K/V 严格为 0/1。运行时会拒绝任何 −1 值，因此没有把三值脉冲送进硬件。Attention 核的三值符号通路对 0/1 输入退化为精确二值点积；矩阵核是 int16 激活 × int8 权重，与脉冲是三值还是二值无关。
- **资源与功耗的边界**：本实验复用 V1 实现，**没有独立的二值综合**。因此 LUT/FF/BRAM/DSP、WNS/TNS、DRC 与 V1 完全相同；`1.444 W` 是 V1 的 Vivado vectorless 片上估算，不是二值工作负载的独立功耗估算，也不是板端实测。详见 `reports/RESOURCE_AND_POWER.md`。

## 5. 数据

- 官方 CIFAR-10 test split，固定分层 1000 张，每类 100 张，顺序固定，与 V1 完全一致。
- 文件与 SHA256：
  - images `b1ade992f818f678a138e97a334d3134e1535c313acb0d2e816770abb76a26ba`
  - labels `998b571dc076fcb72fe5d9e6de50e89c958acc5b2779b9fade559026536868a8`
  - indices `54c4a168d718fdf1b5ea1273d95805a44f12254fcb9a5972a3885dffdf2e6610`
- 预处理：uint8 / 255，再按 mean `[0.4914,0.4822,0.4465]`、std `[0.247,0.2435,0.2616]` 归一化；板上不再预处理。
- 前 10 个索引：6764, 4767, 4069, 8000, 6610, 833, 7532, 6866, 9838, 2002。

## 6. 运行方法

### 6.1 板端环境

- 板端目录：`/home/xilinx/jupyter_notebooks/board_test_exspike_binary_ria_8_16`
- Python：`/usr/local/share/pynq-venv/bin/python3`
- `sudo` 需要密码；本实验使用默认 `xilinx`（可通过 `PYNQ_PASSWORD` 覆盖）。Overlay 加载与 PYNQ 缓冲区分配必须在 sudo 下执行。

### 6.2 Phase A 单张

```bash
cd /home/xilinx/jupyter_notebooks/board_test_exspike_binary_ria_8_16
sudo -S env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -u \
  deployment/run_single.py --position 0
```

输出 `results/single/single.json`。要求：`status=PASS`、`max_abs_logit_error_numpy_vs_pl <= 1e-5`、`numpy_prediction == hardware_prediction`、`kernel_calls/matrix_calls/attention_calls = 34/30/4`。

### 6.3 Phase B 10 张

```bash
cd /home/xilinx/jupyter_notebooks/board_test_exspike_binary_ria_8_16
sudo -S env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -u \
  deployment/run_10.py --fresh
```

输出 `results/ten/predictions.csv`、`progress.json`、`results.json`。`run_10.py` 使用 `os.execv` 直接替换为 `board_runner.py`；在 PYNQ 2.7 上，如果用一个 Python 父进程通过 `subprocess` 再启动 runner，会在 block1 输入缓冲区出现 XRT CMA 分配失败，因此不要改回 wrapper 形式。

10 张完成后可生成汇总：

```bash
/usr/local/share/pynq-venv/bin/python3 deployment/summarize_ten.py --output-dir results/ten
```

### 6.4 Phase C 1000 张

正式 1000 张已于 2026-01-03 01:22:02 用修复后的运行时从 0 重启（PID 15998，`results/subset1000/`）。第一次运行在 33/1000 因 Attention 缓冲区 CMA 泄漏停止，33 张快照保存在 `results/progress/snapshot_0033/`，**不进入最终 1000 张结果**。复现/恢复命令：

```bash
cd /home/xilinx/jupyter_notebooks/board_test_exspike_binary_ria_8_16
sudo -S env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -u \
  deployment/run_1000.py --confirm-1000 \
  --output-dir results/subset1000 --save-interval 10
```

- `run_1000.py` 同样用 `os.execv` 直接执行 runner；`--confirm-1000` 是必需的显式确认。
- 结果每 10 张原子保存；断点续跑按 `dataset_index` 恢复；开始前可加 `--fresh` 归档旧结果。
- 进度：`results/subset1000/progress.json`；最终：`results/subset1000/results.json` 与 `predictions.csv`。
- 正式路径**没有 CPU 回退**；`PynqBackend` 缺失、34/30/4 调用不符、非有限 logits、超时都会直接报错退出。

### 6.5 Notebook

`notebooks/binary_ria_8_16_pynq_z2.ipynb` 提供：包哈希检查、单张、10 张、1000 张启动、进度和最终统计。**当 1000 张 runner 正在运行时，Notebook 会拒绝再跑单张/10 张**，只允许看进度。若在 Jupyter 内核中启动 1000 张遇到 XRT 分配问题，请改用上面的 SSH 命令；本实验的正式 1000 张就是通过 SSH 直接启动的。

## 7. 结果

### 7.1 软件参考

| 模型 | 1000 张软件 Top-1 | 说明 |
|---|---:|---|
| 三值 V1（同一子集） | **90.20%**（902/1000） | 与 V1 板端 90.40% 有 948/1000 预测一致；差值来自板上 int8/int16 量化 |
| 二值（本实验） | **88.50%**（885/1000） | 115 个错误；macro precision 0.88829、recall 0.88500、F1 0.88482 |

### 7.2 板端门禁

| 阶段 | 样本 | 正确 | Top-1 | 平均 E2E | 平均 Kernel | 矩阵核 | Attention 核 | 调用 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Phase A（2 张单图门禁） | 2 | 2 | 100% | 20.18–21.75 s | 7.36–7.53 s | 6.75–6.92 s | 0.618 s | 34/30/4 |
| Phase B（10 张） | 10 | **10** | **100%** | **17.3415 s** | **7.4506 s** | **6.8327 s** | **0.6180 s** | 34/30/4 |
| Phase C（1000 张） | 运行中 | — | — | — | — | — | — | 34/30/4（runner 强制） |

> 10 张均值只作为功能门禁，不能替代 1000 张正式结果；V1 的正式结果是 1000 张。
>
> 修复 Attention 共享缓冲区后的独立 10 张探针：**10/10**，平均 E2E **16.9841 s/图**、Kernel **7.4510 s/图**；运行中 CmaFree 稳定约 79 MB。正式 1000 张使用修复后运行时。

### 7.3 与三值 V1 的对照（正式二值 1000 张完成后回填）

| 指标 | 三值 V1 | 二值（本实验） |
|---|---:|---:|
| 脉冲类型 | −1/0/+1（Q/K/V） | 0/1（全部站点） |
| 可训练参数 | 9,326,266 | 9,326,266 |
| RIA 层 / 权重 / 保留 | 20 / 6,488,064 / 3,244,032（50%） | 20 / 6,488,064 / 3,244,032（50%） |
| 软件 Top-1（同子集） | 90.20% | 88.50% |
| 板端 Top-1（1000 张） | **90.40%**（904/1000） | **待完成** |
| 平均端到端（1000 张） | 16848.0378 ms | **待完成** |
| 平均 Kernel（1000 张） | 7121.1221 ms | **待完成** |
| 矩阵核 / Attention 核 | 6503.1392 / 617.9829 ms | **待完成** |
| 吞吐率 | 0.059354 img/s | **待完成** |
| LUT / FF / BRAM / DSP | 5519 / 3622 / 13.5 / 8 | 同 V1（复用，未独立综合） |
| WNS / TNS | +0.218 ns / 0.000 ns | 同 V1 |
| DRC | 0 error / 57 warning | 同 V1 |
| Vivado 片上功耗估算 | 1.444 W（vectorless） | 同 V1 实现；二值独立估算未做 |
| 整板实测功耗 | 未测量 | 未测量 |

## 8. 复现与校验

- 权重导出：`scripts/export_binary_weights.py`，输出 `deployment/binary_ria_8_16_weights.npz`，SHA256 `7972f820b767e72465e89228a0cc93f4b54733cfd081b31172fbb4c6c10eaec9`；30 层、18,566,688 字节 packed。
- 软件验证：`scripts/validate_binary_software.py`（需 `sy2/model/.conda_spikformer` 环境），结果写入 `reference/software/`。
- 整数后端门禁：`scripts/validate_numpy_backend.py`，前 20 张 18/20 正确、20/20 与软件参考预测一致。
- RTL 仿真：`sim/run_sim.py`（Icarus）与 V1 的 10 个矩阵用例 + Attention 用例；复用 V1 结论，未重新综合。
- 包完整性：`SHA256SUMS.txt`；V1 正式记录在 `reference/v1_formal/`，其哈希与源冻结副本一致。

## 9. 限制与注意事项

1. **V1 正式 1000 张记录的位置**：V1 目录自身的 `results/subset1000_in_progress` 只有 10/1000 的旧快照，不是最终结果。正式 1000 张记录被冻结归档在 `board_test_exspike_main2_8_16_migration_v2_perfopt/baseline_v1_readonly/raw_results`，本目录复制到 `reference/v1_formal/`；已独立复算 1000 行、904/1000=90.40%。
2. **V1 构建日志**：V1 根目录 `vivado.log` 中仍有早期 WNS=-2.519 的失败构建记录；最终 `timing_summary.rpt` 为 WNS +0.218/TNS 0。失败构建归档在 `validation/failed_board_gate_before_index_fix/`，未部署。
3. **模型来源不一致**：用户指定的 `spikformer-main/cifar10/model.py` 与二值 checkpoint 参数不兼容；`model_binary.py` 实际是三值。论文中必须说明本实验使用的是 checkpoint 键名兼容的 Conv1d/Conv2d 二值图，并给出 `model_source` 的记录值。
4. **硬件复用**：二值实验没有重新综合 bitstream；资源、时序、功耗估算与 V1 相同。若论文要求“独立二值硬件综合”，需要用同一 RTL 重新跑 Vivado，资源不会变化，但应单独报告构建日期与哈希。
5. **功耗**：`1.444 W` 是 V1 的 Vivado vectorless 片上估算，不是整板实测；二值工作负载的活动率不同，不能直接把它当作二值功耗。整板功耗需要仪表实测。
6. **1000 张未完成前**：不要把 `progress.json` 的 running accuracy、10 张均值或软件 88.50% 写成 FPGA 1000 张最终结果。
7. **第一次 1000 张运行**：在 33/1000 因 PYNQ 2.7 的 Attention 缓冲区 CMA 泄漏停止（CmaFree 10.9 MB）；进程退出后恢复 127.6 MB。修复为共享 q/k/v/out 缓冲区后，10 张探针 CmaFree 稳定约 79 MB；正式 1000 张从 0 重启。33 张快照仅作诊断，不进入最终结果。

## 10. 关键文件哈希

```text
binary_ria_pruned_816.pth                 6ee6a084f61b7b20c4730a1a8ab043079bbd38342bd422ccd32436562b6bd7ad
binary_ria_8_16_weights.npz               7972f820b767e72465e89228a0cc93f4b54733cfd081b31172fbb4c6c10eaec9
exspike_migration_8_16.bit                92c8657baff4154ebf1c4339272d6b6f7d3c70ec0de1d8ad1561fd41a189b5a8
exspike_migration_8_16.hwh                3f3173d8a047be1a1c1ab80c78c50f33fdbb48f3c53836ec18c923d26dd5c043
cifar10_subset1000_images.npy             b1ade992f818f678a138e97a334d3134e1535c313acb0d2e816770abb76a26ba
cifar10_subset1000_labels.npy             998b571dc076fcb72fe5d9e6de50e89c958acc5b2779b9fade559026536868a8
cifar10_subset1000_indices.npy            54c4a168d718fdf1b5ea1273d95805a44f12254fcb9a5972a3885dffdf2e6610
```
