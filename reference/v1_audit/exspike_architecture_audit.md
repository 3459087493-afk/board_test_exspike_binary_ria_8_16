# ExSpike-main2 架构审计（migration_v1）

日期：2026-10-21；原目录仅以只读方式检查。

## 源码事实

- 原顶层 `SCNN_TOP_PCIE` 面向 `xc7v2000tfhg1761-2`，依赖 XDMA PCIe、MIG DDR3、原板时钟和管脚，不能直接用于 Zynq-7020。
- 可见 RTL 的完整主链为 `EVENT_PROCESSOR_TOP -> NEURAL_PROC -> SPARSE_PROCESSING/WEIGHT_TOP/READ_MEMBRANE_P/READ_MP_BIAS`。
- `SPARSE_PROCESSING` 包含 512-bit 二值事件图、42-bit event FIFO 和 overlap/XOR 控制；它没有三值符号通道，不能直接用于当前 −1/0/+1 事件。
- `FAST_FILTER` 用 `x & (x-1)` 清除最低置位并输出 one-hot；`INDEX2ABS_SUB_0` 将128-bit one-hot解码成9-bit地址；二者可在保留符号旁路的条件下复用。
- `MP_ACC` 是16-bit条件加法寄存器；当前矩阵核将它参数化为48 bit并实例化8 lane。
- `WEIGHT_TOP`、`READ_MEMBRANE_P`、`READ_MP_BIAS` 强耦合9位置卷积、16-bit膜电位、专用BRAM和二值阈值，不能直接保持当前模型语义。
- 公开目录没有可直接综合的完整 Attention Core RTL/EDIF。论文描述不能替代可复现源码，因此 migration_v1 的Attention核是依据 `nm8_16.py` 重新实现，不宣称直接复用了原Attention Core。

## 复用边界

| 分类 | 模块 | migration_v1处理 |
|---|---|---|
| 直接/参数化复用 | FAST_FILTER | 512位算法缩为16位事件组 |
| 直接复用 | INDEX2ABS_SUB_0 | 16位one-hot零扩展到128位，解码逻辑不变 |
| 参数化复用 | MP_ACC | 16位扩展为48位、8 lane |
| 思想参考 | SPARSE_PROCESSING/FIFO | 暂未迁移；三值overlap语义未证明 |
| 不直接移植 | SCNN_TOP_PCIE/XDMA/MIG | 改用PS7 GP0控制及HP0/HP1数据口 |
| 新实现 | ternary_attention_top | 三值QK、AV、固定0.125及后续二值LIF |

完整原始ExSpike约使用312.5 BRAM tile，超过PYNQ-Z2的140，因此不能整体照搬。
