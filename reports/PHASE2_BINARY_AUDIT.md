# 第二阶段：二值模型审计与软件验证

## 1. checkpoint

- 文件：`model/binary_ria_pruned_816.pth`
- SHA256：`6ee6a084f61b7b20c4730a1a8ab043079bbd38342bd422ccd32436562b6bd7ad`
- 顶层：`state_dict`、`config`、`ria_nm="8:16"`、`source_checkpoint`、`model_source`、`spike_mode="binary"`
- 224 个 state key；20 个 `weight_mask`；6,488,064 个 RIA 权重，保留 3,244,032，**50.000%**，每组严格 8-of-16。
- `weight_orig` 在保存前已乘 mask：mask 外非零数为 0；mask 内非零数为 3,244,032。
- `source_checkpoint` 记录为 `/home/free/prj/finn/Spikingformer/cifar10/output/train/20261007-201525-vitsnn-32/model_best.pth.tar`；`model_source` 记录为 `/home/free/prj/finn/Spikingformer/cifar10/model.py`。这两个路径本机不存在，只作溯源记录。

## 2. 模型来源不一致（必须在论文中说明）

| 文件 | SHA256 | 实际内容 | 能否直接加载 checkpoint |
|---|---|---|---|
| `spikformer-main/cifar10/model.py` | `2fd22031...` | `q_linear/proj_linear/fc1_linear/fc2_linear`、SPS `rpe_conv` | **不能**；参数名与 shape 不匹配 |
| `spikformer-main/cifar10/model_binary.py` | `a91c849b...` | `TernarySpikeFunction`、三值 LIF | **不能**；它是三值模型 |
| `sy2/model/spikingformer-cml/cifar10/model.py` | `2bc9ac76...` | 二值 0/1 LIF、Conv1d Q/K/V、pool 在 proj2/proj3 之后 | 语义参考；属性名是 `proj*`，**不能按 checkpoint 键 strict load** |
| `model/binary_model_adapter.py` | 本目录实现 | 使用 checkpoint 的 `block0..4` 键名，二值 0/1 LIF | **可以**；strict key 覆盖无 missing/unexpected |

- 用户指定的 `spikformer-main/cifar10/model.py` 不是这个 checkpoint 的模型；不能为了“用上 model.py”而丢弃/重命名参数。
- `model_binary.py` 文件名容易误导，实际是三值；本实验没有使用它。
- 实际执行图是 `binary_model_adapter.py`；它与 `sy2/model/.../model.py` 的语义参考逐图 bit-exact：
  - 前 20 张 max_abs = 0.0
  - 预测一致 20/20
  - strict load：adapter 与 reference 均无 missing/unexpected（reference 用 `block* → proj*` 映射）
- 映射关系：`patch_embed.block0_conv/bn → proj_conv/bn`，`block1..4_conv/bn → proj1..4_conv/bn`；`block.i.*` 不变。

## 3. 二值脉冲语义

- 全部站点：0/1 脉冲，`v = v + (x−v)/2`，`s = (v ≥ 1)`，`v = v·(1−s)`（hard reset）。
- `attn_lif`：阈值 **0.5**，hard reset。
- attention scale：0.125。
- Q/K/V：二值 0/1，不是三值；运行时会拒绝任何 −1 值。
- 与 V1 的唯一语义差异：V1 的 Q/K/V 是三值 soft-reset，本实验是二值 hard-reset。

## 4. 软件 1000 张

在固定 V1 1000 张子集上：

| 指标 | 值 |
|---|---:|
| 样本 | 1000 |
| 正确 | 885 |
| Top-1 | **88.50%** |
| 错误 | 115 |
| macro precision | 0.8882913 |
| macro recall | 0.8850000 |
| macro F1 | 0.8848163 |
| 与已有二值 logits 对比 | max_abs = 0.0，1000/1000 预测一致 |
| 与 V1 三值软件同子集对比 | 90.20% → 88.50%，−1.70 pp |

- 前 20 张与 NumPy 整数后端：18/20 正确、20/20 与软件参考预测一致（同一份 20 张）。
- 参数：9,326,266 个可训练参数（二值/三值相同）；RIA 权重 6,488,064，保留 3,244,032；非 RIA conv/linear 权重 2,792,976；BN affine 14,928；norm 3,072；bias 27,226。

## 5. 与 V1 硬件的兼容性结论

- 图形状完全相同：30 次矩阵 + 4 次 Attention；T=4、12 heads、N=64、head_dim=32。
- 矩阵核：int16 动态量化激活 × int8 per-output-channel 权重，与脉冲是三值还是二值无关；二值 0/1 激活直接进入同一引擎。
- Attention 核：V1 的 `dot_ternary8` 对 0/1 输入退化为精确二值点积；`av_product` 对 0/1 V 退化为“score 或 0”；attention LIF 本来就是二值 0.5 hard reset；×0.125 一致。运行时会断言 Q/K/V 只含 0/1，三值符号通路从未被激活。
- 因此 V1 的 bit/HWH 可以复用，但必须通过板端门禁；己完成 Phase A（2 张，max_abs=0.0）、Phase B（10 张，10/10），Phase C 1000 张运行中。
- 硬件复用不等于“用三值计算冒充二值”：板端收到的 Q/K/V 是 0/1；NumPy 整数参考与 PL 逐 logit 一致；没有 −1 进入 Attention 核。

## 6. 板端门禁摘要

- Phase A：position 0（dataset_index 6764，label 5），NumPy/PL 预测均 5，10 个 logits max_abs **0.0**，34/30/4，Attention QK/AV 各 25,165,824。
- Phase A：position 1（dataset_index 4767，label 6），max_abs **0.0**，预测均 6。
- Phase B：10/10 正确，10/10 与软件参考一致，34/30/4；平均 E2E 17.3415 s、Kernel 7.4506 s（矩阵 6.8327 s、Attention 0.6180 s）。
- Phase C：1000 张，运行中；以 `results/subset1000/progress.json` 为准。

## 7. 重要限制

- checkpoint 的 `model_source` 与本机文件不一致；本实验的可执行图是键名兼容适配器，不是直接加载 `spikformer-main/cifar10/model.py`。
- 二值板端 1000 张完成前，88.50% 只能标为“软件参考”，不能标为“FPGA 实测”。
- 二值硬件复用 V1 bitstream，没有独立综合；资源/功耗与 V1 相同，详见 `RESOURCE_AND_POWER.md`。
