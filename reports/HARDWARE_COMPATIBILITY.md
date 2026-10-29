# 硬件兼容性与上板适配

## 1. 复用对象

复用 V1 最终实现，不使用 V11，也不使用 V1 的失败构建：

- `hardware/exspike_migration_8_16.bit`：`92c8657baff4154ebf1c4339272d6b6f7d3c70ec0de1d8ad1561fd41a189b5a8`
- `hardware/exspike_migration_8_16.hwh`：`3f3173d8a047be1a1c1ab80c78c50f33fdbb48f3c53836ec18c923d26dd5c043`
- `hardware/exspike_migration_8_16_build.xsa`：`050ca2a4abfc00aeb0921ea3457ae078f9f38d92a796fee3249f5e5a249098ec`

V1 的失败构建（WNS −2.519）在 `validation/failed_board_gate_before_index_fix/`，未进入本目录。

## 2. 板上环境核验

- 实际板：PynqLinux **2.7.0**，Linux `5.4.0-xilinx-v2020.2`，armv7l。
- V1 报告写的是 PYNQ 3.1 / Linux 6.6.10；这是本实验发现的环境差异。V1 的 HWH 在 PYNQ 2.7 上仍可解析。
- 只读预检：
  - `Overlay("exspike_migration_8_16.bit")` 成功；
  - `ip_dict` 包含 `exspike_0`、`attention_0`、`processing_system7_0`；
  - `exspike_0` @ `0x40000000`，`attention_0` @ `0x40001000`；
  - `pynq.allocate` 可用，`flush` / `invalidate` / `freebuffer` 均存在；
  - `CmaTotal=128 MB`，1/4/8/16/32 MB 分配探针均成功。

## 3. 二值数据是否真的进入硬件

- 运行时 `PynqBackend.attention` 与 `NumpyBackend.attention` 都断言 `q/k/v ∈ {0,1}`，否则抛错；V1 的三值 helper 已从本目录运行时移除。
- 二值模型所有 LIF 都走 `lif()`（hard reset、0/1）；Q/K/V 不再使用 `ternary_lif()`。
- Attention 核的 `dot_ternary8` 对 0/1 输入：
  - 两个非零 → 乘积 +1；
  - 任一为零 → 0；
  - 符号位恒为 0，不会产生 −1。
  因此得到的是精确二值点积。
- AV 的 `av_product` 对 0/1 V 退化为 `score` 或 0；LIF 仍是 `w/2 + 8A`、阈值 64（0.5）、hard reset，与二值模型一致。
- 矩阵核接收的是 BN 后的 int16 量化激活，不是三值脉冲；脉冲类型只影响零/非零事件选择，不改变数值语义。
- 板端 Phase A 用 NumPy 整数参考对比 PL，10 个 logits **完全一致**；这不是 CPU 回退，PL 的 34/30/4 调用和计数器均被 runner 检查。

## 4. 二值模型与 V1 的差异

| 项目 | V1 三值 | 本实验二值 |
|---|---|---|
| Q/K/V LIF | 三值 soft reset，阈值 1.0 | 二值 hard reset，阈值 1.0 |
| 其他 LIF | 二值 hard reset | 二值 hard reset |
| Attention LIF | 二值，阈值 0.5 | 二值，阈值 0.5 |
| attention scale | 0.125 | 0.125 |
| 图形状 | 30 matrix + 4 attention | 30 matrix + 4 attention |
| 硬件 | V1 bit/HWH | 同 V1 bit/HWH（复用） |

唯一需要改的 ARM 侧语义是 Q/K/V LIF；硬件 Attention 核天然接受 0/1 子集，矩阵核与脉冲类型无关。

## 5. PYNQ 2.7 XRT 分配问题与修复

板上多次 10 张测试在 tokenizer block1 的 3.5 MB 输入缓冲区出现：

```text
RuntimeError: Allocate failed: 4294967295
```

- CMA 仍有 128 MB，4/8/16/32 MB 探针均成功；
- 单张 `run_single.py`、直接 `board_runner.py --limit 1/2` 可成功；
- 在 `subprocess` 父 Python 进程中启动 runner 时更容易复现；
- 6 次指数退避重试仍不能保证通过。

最终修复：`PynqBackend` 在初始化时**一次性分配共享输入/输出缓冲区**，所有 30 个矩阵调用复用：

- 输入：8M 个 int16（16 MB），覆盖最大 block2 tokenizer 的 4096×864；
- 输出：2M 个 int32（8 MB），覆盖最大 4096×192；
- 每次 `matmul` 只写共享缓冲区的前 `transfer.size` 个元素，`flush` 后启动核；
- 权重仍按层缓存，Attention 的 q/k/v/out 仍按调用分配（尺寸小）。

修复后 10 张测试 **10/10、34/30/4、无分配错误**。正式 1000 张 runner 使用同一运行时。

## 6. 风险与边界

- 共享缓冲区 `flush/invalidate` 覆盖整块 16 MB/8 MB，可能比精确缓冲区多少量时间；已在 10 张均值中体现（17.34 s/图），1000 张以最终结果为准。
- 运行中若出现 XRT 分配失败，`_allocate` 会重试 6 次；仍失败则 runner 直接退出，不会伪造结果。
- 1000 张 runner 没有 CPU 回退；`PynqBackend` 是唯一执行路径。
- V1 bitstream 未重新综合；如果审稿要求独立二值构建，可用同一 RTL 重跑 Vivado，资源不变，但需单独记录构建时间、WNS/TNS、DRC 和哈希。
