# Vivado 片上功耗估算

最终修复版实现后 `report_power` 给出：总片上功耗 1.444 W、动态 1.308 W、器件静态 0.136 W、结温 41.7°C、环境温度假设 25°C、置信度 Medium。没有 SAIF/VCD，`Simulation Activity File` 为 `---`，采用 vectorless 活动传播；报告还警告高扇出 reset 活动可能使估算不准确。

因此 1.444 W 只能作为 Vivado 片上估算，不能视为 PYNQ-Z2 整板功耗。优化前使用同口径的 Vivado 功耗报告未在本任务中重建，功耗变化百分比待补。整板空闲、推理平均/峰值和单图能量必须按 `power_measurement_protocol.md` 实测，目前为待测。
