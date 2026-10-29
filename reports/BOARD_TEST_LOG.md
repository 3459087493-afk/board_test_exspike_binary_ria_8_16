# 上板测试日志（阶段性）

## 2026-01-03 环境预检

- 板：PYNQ-Z2，PynqLinux 2.7.0，Linux 5.4.0-xilinx-v2020.2，armv7l。
- `Overlay` 成功解析 V1 bit/HWH；`exspike_0` @ 0x40000000，`attention_0` @ 0x40001000。
- `allocate/flush/invalidate/freebuffer` 全部可用；`CmaTotal=128 MB`。
- V1 bit/HWH/weights/data 哈希与清单一致。

## Phase A：单张

### position 0

- dataset_index 6764，label 5
- NumPy 整数参考预测 5；PL 预测 5；软件参考 5
- 10 个 logits 的 `max_abs_logit_error_numpy_vs_pl = 0.0`
- 调用 34 / 30 / 4
- E2E 21751.1999 ms；Kernel 7534.1775 ms；矩阵 6916.2405 ms；Attention 617.9370 ms
- event_count 46,301,136；selected_mac 289,223,485
- Attention QK/AV 各 25,165,824

### position 1

- dataset_index 4767，label 6
- NumPy/PL 预测均 6；max_abs 0.0
- E2E 20184.9656 ms；Kernel 7364.7274 ms；矩阵 6746.7595 ms；Attention 617.9679 ms
- event_count 42,946,200；selected_mac 261,606,797

**结论：PASS**。二值 0/1 Q/K/V 进入 PL，NumPy 整数参考与真实 PL 位精确一致；无超时、无驱动错误。

## Phase B：10 张

- 10/10 正确；10/10 与软件参考预测一致；调用 34/30/4。
- 平均 E2E 17341.5368 ms；Kernel 7450.6219 ms；矩阵 6832.6575 ms；Attention 617.9644 ms。
- 逐图记录：`results/ten/predictions.csv`；汇总：`results/ten/ten_summary.json`。

### 分配问题记录与修复

- 多次 10 张尝试在 tokenizer block1 的 3.5 MB 输入缓冲区出现 `RuntimeError: Allocate failed: 4294967295`。
- CMA 仍有 128 MB；1/4/8/16/32 MB 探针均成功；单张/直接 runner 可成功。
- 修复 1：`PynqBackend` 初始化时分配共享输入 8M int16（16 MB）和共享输出 2M int32（8 MB），所有矩阵调用复用；不再每层申请大块 CMA。
- 修复 1 后 10 张 **PASS**。

## 第一次 1000 张运行（已停止，仅作诊断）

- 启动：2026-01-03 01:05:49 UTC，PID 14668。
- 快照：01:08:49 10/1000（10 正确）；01:11:42 20/1000（18 正确）；01:14:35 30/1000（28 正确）。
- 01:15:27 停止：**33/1000，31 正确**，running 93.94%；均值 E2E 17349.5178 ms、Kernel 7428.9819 ms、矩阵 6811.0075 ms、Attention 617.9744 ms。
- `CmaFree` 从启动时约 63 MB 降到 **10.9 MB**，约 1.5 MB/图；进程退出后恢复 **127.6 MB**。
- 结论：`PynqBackend.attention` 每次调用新建 q/k/v/out 缓冲区，`freebuffer()` 在 PYNQ 2.7 上未真正释放 CMA。继续运行会在约 80 张附近失败。
- 33 张记录已保存到主机 `results/progress/snapshot_0033/`；板上 `--fresh` 重启时归档，不进入最终 1000 张结果。

## 修复与 10 张探针

- 修复 2：Attention 的 q/k/v/out 也改为**共享持久缓冲区**，首次调用分配，后续复用；不再 `freebuffer`。
- 修复后运行时 SHA256：`c359c89b2af4d0d047aca6786ddaef25eaac46fb5815d7345d5124914786ccff`。
- 10 张探针：**10/10**，平均 E2E **16984.1112 ms**、Kernel **7451.0354 ms**、矩阵 **6833.0689 ms**、Attention **617.9665 ms**。
- 运行中 `CmaFree` 采样：首图后稳定在约 **79.2 MB**（t=30..160 s 基本不变）；探针退出后 129.1 MB。无逐图下降。

## 正式 1000 张重启

- 启动：**2026-01-03 01:22:02 UTC**
- PID：**15998**
- 输出：`results/subset1000/`
- 运行时：修复后的 `board_runtime.py`（Attention 共享缓冲区）
- 命令：`run_1000.py --confirm-1000 --output-dir results/subset1000 --save-interval 10 --fresh`
- `--fresh` 已将第一次 33 张运行归档；正式运行从 0 开始。
- 结果策略：每 10 张原子保存 `predictions.csv` / `progress.json` / `results.json`；断点续跑按 dataset_index；无 CPU 回退；每图强制 34/30/4。
- 01:24:59 UTC 首 10 张：**10/10 正确**，10/10 与软件参考预测一致；34/30/4；均值 E2E 16995.7968 ms、Kernel 7452.6296 ms、矩阵 6834.6562 ms、Attention 617.9734 ms；CmaFree 78.8 MB（稳定）。
- 01:30:36 UTC 快照：**30/1000，28 正确**，running 93.33%；均值 E2E 16911.7106 ms、Kernel 7424.4761 ms、矩阵 6806.5084 ms、Attention 617.9677 ms；CmaFree 79.16 MB（稳定）；预计剩余 4.56 h。该快照不是最终 Top-1。
- 02:18:34 UTC 快照：**200/1000，175 正确**，running 87.5%；均值 E2E 16917.4260 ms、Kernel 7431.3865 ms、矩阵 6813.4210 ms、Attention 617.9655 ms；检查时 CmaFree 38.3 MB；预计剩余 3.76 h。CSV 200 行通过序列/索引/标签/34-30-4 校验，190/200 与软件参考一致。该快照不是最终 Top-1。
- 02:29:53 UTC 快照：**240/1000，212 正确**，running 88.33%；均值 E2E 16924.9741 ms、Kernel 7431.7857 ms、矩阵 6813.8171 ms、Attention 617.9686 ms；检查时 CmaFree 37.8 MB；预计剩余 3.57 h。CSV 240 行通过序列/索引/标签/34-30-4 校验，225/240 与软件参考一致。该快照不是最终 Top-1。
- CMA 监视器记录过 **15.98 MB 和 7.91 MB 两次瞬时低点**（约 200、240 张时），runner 均未中断、继续推进；已改为不在瞬时低点退出的长期 CMA 日志器。若 RUNNER 状态变为 failed/interrupted 或 CmaFree 低于 1 MB，将保存现场后断点恢复，不使用 `--fresh`。
- 当前状态：**运行中**（预计剩余 4.67 h）；最终数字从 `results/subset1000/results.json` 读取，完成前不得作为最终 Top-1。

> 启动脚本的 SSH `stdout.read()` 曾超时，是因为后台 `setsid/sudo` 持有通道；任务本身已启动。后续版本把内层日志重定向放在 root `bash -c` 中，外层 `setsid/sudo` 重定向到 `/tmp`，避免权限错误和通道悬挂。
