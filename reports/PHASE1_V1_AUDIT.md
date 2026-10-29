# 第一阶段：V1 三值上板实验审计

审计对象：`board_test_exspike_main2_8_16_migration_v1`。只读检查，未修改 V1 任何文件。

## 1. 模型与权重

- checkpoint：`8_16.model_best.pth.tar`
  - SHA256 `4d2af5f76b758f4c7dcd3540c4e5cd24e4b71ecfa960c57d3886be0bca3c9531`
  - epoch 43，存储 metric 90.5，284 个 state key，strict load 无 missing/unexpected。
- 模型源码：`provenance/nm8_16.py`
  - SHA256 `d0fb5ebb62fcb49933ab02d673b2759bc70de3032f9669eeb6bcea56e803c85a`
  - T=4，C=384，12 heads，head_dim=32，N=64，patch_size=4。
- Q/K/V：三值 `{−1,0,+1}`，`MultiStepTernaryLIFNode`，tau=2，有效阈值 **1.0**（checkpoint 字段为 0.75，但训练构造器未覆盖默认值，实际训练/推理为 1.0），soft reset `v ← v − s·threshold`。
- 其余 LIF：二值 0/1，hard reset；`attn_lif` 阈值 0.5。
- Attention：`q @ k^T`、`attn @ v`、`×0.125`、reshape、二值 attention LIF。

## 2. RIA 8:16

- 20 个目标层：4 个 block 的 `q_conv/k_conv/v_conv/mlp1_conv/mlp2_conv`。
- 目标权重总数 6,488,064；保留 3,244,032；**50.000%** 结构稀疏。
- 每个 16 位置组严格保留 8 个位置；checkpoint 自带 mask。
- 导出 int8 时，保留位置的权重中有 783 个被量化为 0；这是权重 int8 量化的结果，不是 mask 变化。
- 未被剪枝的 `proj_conv`、tokenizer Conv、head 保持密集。

## 3. PL/PS 分区

- PL：
  - 30 次矩阵核：5 个 tokenizer Conv、4 个 block 的 Q/K/V/proj + MLP1/MLP2、head。
  - 4 次 Attention 核：QK^T、Attention×V、×0.125、二值 attention LIF。
- ARM/PS：im2col、BN、所有 LIF、Pooling、残差、reshape、动态 int16 量化/反量化、argmax、结果写入。
- 每图强制 34 次调用（30 matrix + 4 attention）；runner 对每图断言，否则中止。

## 4. 硬件

- 最终 bit：`exspike_migration_8_16.bit`
  - SHA256 `92c8657baff4154ebf1c4339272d6b6f7d3c70ec0de1d8ad1561fd41a189b5a8`
- HWH：`exspike_migration_8_16.hwh`
  - SHA256 `3f3173d8a047be1a1c1ab80c78c50f33fdbb48f3c53836ec18c923d26dd5c043`
  - `exspike_0` @ `0x40000000`（HP0），`attention_0` @ `0x40001000`（HP1）。
- XSA：`exspike_migration_8_16_build.xsa`
  - SHA256 `050ca2a4abfc00aeb0921ea3457ae078f9f38d92a796fee3249f5e5a249098ec`
- Vivado 2022.2，xc7z020clg400-1，100 MHz。
- 资源：LUT 5519（10.37%）、FF 3622（3.40%）、BRAM 13.5（9.64%）、DSP 8（3.64%）。
- 时序：WNS **+0.218 ns**，TNS **0.000 ns**，0 failing endpoints，所有用户约束满足。
- DRC：**0 error / 57 warning**（DSP 未全流水、BRAM 异步复位、互连无负载等）。
- Vivado vectorless 片上功耗：**1.444 W**（动态 1.308 W，静态 0.136 W，Medium confidence）；没有 SAIF/VCD；不是整板实测。

> 注意：V1 根目录 `vivado.log` 中仍保留早期失败构建的 WNS −2.519 记录；最终交付的是 `timing_summary.rpt` 的 +0.218 ns 版本。失败构建归档在 `validation/failed_board_gate_before_index_fix/`，不作为部署产物。

## 5. 数据

- 官方 CIFAR-10 test split，固定分层 1000 张，每类 100 张，固定顺序。
- images `b1ade992f818f678a138e97a334d3134e1535c313acb0d2e816770abb76a26ba`
- labels `998b571dc076fcb72fe5d9e6de50e89c958acc5b2779b9fade559026536868a8`
- indices `54c4a168d718fdf1b5ea1273d95805a44f12254fcb9a5972a3885dffdf2e6610`
- 预处理：uint8/255，mean `[0.4914,0.4822,0.4465]`，std `[0.247,0.2435,0.2616]`；板上不再预处理。
- 前 10 个索引：6764, 4767, 4069, 8000, 6610, 833, 7532, 6866, 9838, 2002。

## 6. 正式 1000 张记录与复算

V1 目录自身的 `results/subset1000_in_progress/` 是 **10/1000 的旧快照**，不是最终结果。正式 1000 张记录被只读冻结归档在：

`board_test_exspike_main2_8_16_migration_v2_perfopt/baseline_v1_readonly/raw_results/`

本目录复制到 `reference/v1_formal/`。独立复算结果：

| 项目 | 值 |
|---|---:|
| 行数 | 1000 |
| sequence_id | 0..999 精确 |
| dataset_index | 与固定子集完全一致 |
| label | 与固定子集完全一致 |
| 类别计数 | 每类 100 |
| 正确 | 904 |
| Top-1 | **90.40%** |
| 95% Wilson CI | [88.4165, 92.0743] |
| 错误 | 96 |
| 调用 | 每图 34 = 30 matrix + 4 attention |
| 平均 E2E | 16848.037835 ms/图 |
| 中位数 E2E | 16809.525040 ms/图 |
| P75 / P95 E2E | 16995.210849 / 17186.874521 ms/图 |
| 平均 Kernel | 7121.122130 ms/图 |
| 平均矩阵核 | 6503.139240 ms/图 |
| 平均 Attention 核 | 617.982890 ms/图 |
| 吞吐率 | 0.059354 img/s |

冻结文件哈希：
- `results.json` `43e207b30a2d8c28fd561fa695ddea8e0cdd99685c64a8eec8e79b7bebf27c86`
- `predictions.csv` `1b4a5d594eaadaf6c28872359365817852b8fa0cf47f442f1db9559bdcb87492`

## 7. 同子集软件参考

用 `nm8_16.py` + checkpoint + 20 个 RIA wrapper，在固定 1000 张上做 PyTorch 软件推理：

- 902/1000 = **90.20%**
- 与 V1 板端预测一致 948/1000
- 板端 90.40%，差 2 张净收益，来源是板上 int8/int16 量化与软件 float 的差异

## 8. 结论

V1 的模型、RIA、数据、分区、硬件和 1000 张正式记录均可复算；二值实验以 V1 的以下字段为固定对照：同一 1000 张、同一预处理、同一 34/30/4 调用图、同一 PL/ARM 分区、同一 V1 最终 bit/HWH。
