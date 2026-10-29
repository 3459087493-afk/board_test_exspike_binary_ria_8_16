# 硬件资源与时序

数据来自 Vivado 2022.2 对 xc7z020clg400-1 的实现后报告。

| 项目 | 已验证基线 | Attention migration V1 | V1 占器件 |
|---|---:|---:|---:|
| Slice LUT | 3,047 | 5,519 | 10.37% |
| Slice FF | 2,144 | 3,622 | 3.40% |
| DSP48 | 8 | 8 | 3.64% |
| BRAM tile | 10.5 | 13.5 | 9.64% |
| PL clock | 100 MHz | 100 MHz | — |
| WNS | 基线通过 | +0.218 ns | — |
| TNS | 基线通过 | 0.000 ns | — |

增量为 2,472 LUT、1,478 FF、0 DSP、3 BRAM tile。层次报告中 `attention_0` 使用 2,121 LUT、967 FF、3 RAMB36、0 DSP；其余增量包含第二条 AXI HP 数据路径和互连。所有用户时序约束满足。

DRC 为 0 error；保留的 warning 主要是原矩阵核 DSP 未全流水、BRAM 地址控制异步 reset，以及互连无负载网，不应隐瞒，详见 `drc.rpt`。
