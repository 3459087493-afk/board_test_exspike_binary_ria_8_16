# 当前 ARM/FPGA 划分与 migration_v1 变化

## 基线

基线每图30次PL矩阵调用：5个tokenizer Conv、每个Encoder的Q/K/V/projection和2个MLP、最后head。ARM执行im2col、BN、二值/三值LIF、pooling、QK、Attention×V、残差、reshape、动态量化和反量化。既有实测为16.53 s/image，其中矩阵Kernel累计6.64 s，差值9.89 s。

每次矩阵调用均由ARM准备CMA输入，写AXI-Lite，PL经HP0读取输入/权重并写INT32输出，ARM invalidate/copy后反量化。中间结果在多数层返回PS DDR/ARM。

## migration_v1

新增 `ternary_attention_top`，通过独立AXI-Lite控制和PS7 HP1访问DDR。每个Encoder中，Q/K/V投影、BN和三值LIF后得到 `[T=4,B=1,H=12,N=64,D=32]` 的INT8三值张量；ARM仅进行布局复制到CMA，PL执行：

```text
Q @ K^T -> score @ V -> ×0.125 -> binary LIF(tau=2, threshold=0.5, hard reset)
```

输出为INT8 0/1，再交给原projection矩阵核。单图调用数预计从30变为34，因此本版本迁移了真实计算，但没有减少启动次数；是否端到端加速只能由板端实测判定。

仍在ARM：im2col、全部BN、Q/K/V三值LIF、tokenizer/MLP/projection前后的普通LIF、pooling、残差、reshape、量化/反量化和最终均值。仍存在Q/K/V与Attention核之间的DDR/CMA传输。

## 真实公式证据

`nm8_16.py` 的顺序为Q/K/V三值化、`q @ k.transpose`、`attn @ v`、乘 `attn_scale`、reshape、`attn_lif`。checkpoint参数为T=4、C=384、heads=12、attn_scale=0.125、score_norm=none；训练构造器未覆盖默认0.125。软件等价性结果见 `attention_software_validation.json`。
