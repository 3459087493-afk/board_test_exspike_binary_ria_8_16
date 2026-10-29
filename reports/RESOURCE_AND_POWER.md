# 资源、时序、DRC 与功耗

## 1. 复用说明

本实验**复用 V1 最终 bitstream**，没有重新综合二值专用 bitstream。因此下列资源、时序、DRC 与功耗估算都属于同一物理实现；二值模型只改变 ARM 侧 LIF 语义和权重内容，不改变 PL 逻辑。若需要“独立二值综合”，必须用同一 RTL 重新跑 Vivado 并单独报告，但资源预计不变。

## 2. Vivado 2022.2 实现结果（xc7z020clg400-1）

| 项目 | 值 | 占器件 |
|---|---:|---:|
| Slice LUTs | 5,519 | 10.37% |
| Slice Registers | 3,622 | 3.40% |
| Block RAM Tile | 13.5 | 9.64% |
| DSP48 | 8 | 3.64% |
| PL clock | 100 MHz | — |
| WNS | **+0.218 ns** | — |
| TNS | **0.000 ns** | — |
| Failing endpoints | 0 | — |
| DRC | **0 error / 57 warning** | — |

原始报告：
- `hardware/reports/utilization.rpt`
- `hardware/reports/utilization_hierarchical.rpt`
- `hardware/reports/timing_summary.rpt`
- `hardware/reports/drc.rpt`
- `hardware/reports/power.rpt`

DRC warning 主要是 DSP 输入未全流水（DPIP-1 16、DPOP-2 8）、BRAM 异步控制（REQP-1839 20、REQP-1840 5）、LUT 方程项检查 6、无负载 1、报告上限 1；没有 error。

## 3. 功耗

Vivado `report_power`（vectorless，无 SAIF/VCD）：

| 项目 | 值 |
|---|---:|
| Total On-Chip Power | **1.444 W** |
| Dynamic | 1.308 W |
| Device Static | 0.136 W |
| Junction Temperature | 41.7 °C |
| Confidence | Medium |
| Simulation Activity File | --- |

这**不是**整板实测功耗，也**不是**二值工作负载的独立估算。二值模型的脉冲活动率与三值不同，事件选择/翻转率会不同；没有二值 SAIF 时，不能把 1.444 W 当作二值功耗。整板功耗需要外部仪表按 `hardware/reports/power_measurement_protocol.md` 测量；本实验未测量。

## 4. 资源与样本数量的关系

FPGA 资源由实际实现决定，与测试 1000 张还是 10000 张无关。本实验 1000 张与 V1 的 1000 张使用同一 bitstream，因此资源行相同；不能用样本数量推断资源变化。

## 5. 结论

- 二值实验的硬件资源/时序/DRC 与 V1 完全一致，因为物理实现未变。
- 功耗数字只能标为“Vivado 片上估算（V1 实现）”；二值独立估算未做，整板实测未做。
- 论文中必须区分：真实板端测量（准确率、延迟、调用次数、计数器）与工具估算（资源、WNS/TNS、功耗）。
