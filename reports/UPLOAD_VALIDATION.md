# 板上文件与包清单校验

## 1. 已上传到板上的文件

上传目录：`/home/xilinx/jupyter_notebooks/board_test_exspike_binary_ria_8_16`

- `README.md`
- `notebooks/binary_ria_8_16_pynq_z2.ipynb`
- `reports/PHASE1_V1_AUDIT.md`
- `reports/PHASE2_BINARY_AUDIT.md`
- `reports/HARDWARE_COMPATIBILITY.md`
- `reports/RESOURCE_AND_POWER.md`
- `reports/BINARY_VS_TERNARY.md`
- `reports/BOARD_TEST_LOG.md`
- `reports/UPLOAD_VALIDATION.md`
- `reference/v1_formal/v1_formal_results.json`
- `reference/v1_formal/v1_formal_predictions.csv`
- `deployment/board_runtime.py`（修复 Attention 共享缓冲区后的运行时）

## 2. 哈希核验

- 板上 `deployment/board_runtime.py` SHA256：`c359c89b2af4d0d047aca6786ddaef25eaac46fb5815d7345d5124914786ccff`
- 与主机一致：**PASS**
- 文档/Notebook/V1 正式记录逐文件 `sha256sum` 与主机 `hashlib.sha256` 比较：**0 不匹配**（上传时核验）。

## 3. 包清单

- `SHA256SUMS_package.txt`：覆盖 model/deployment/hardware/data/reference/reports/scripts/notebooks/rtl/sim/README，不包含运行中的 `results/`。
- 使用方式：`sha256sum -c SHA256SUMS_package.txt`。
- 关键产物哈希：
  - `binary_ria_pruned_816.pth` `6ee6a084f61b7b20c4730a1a8ab043079bbd38342bd422ccd32436562b6bd7ad`
  - `binary_ria_8_16_weights.npz` `7972f820b767e72465e89228a0cc93f4b54733cfd081b31172fbb4c6c10eaec9`
  - `.bit` `92c8657baff4154ebf1c4339272d6b6f7d3c70ec0de1d8ad1561fd41a189b5a8`
  - `.hwh` `3f3173d8a047be1a1c1ab80c78c50f33fdbb48f3c53836ec18c923d26dd5c043`
  - images `b1ade992f818f678a138e97a334d3134e1535c313acb0d2e816770abb76a26ba`
  - labels `998b571dc076fcb72fe5d9e6de50e89c958acc5b2779b9fade559026536868a8`
  - indices `54c4a168d718fdf1b5ea1273d95805a44f12254fcb9a5972a3885dffdf2e6610`
  - `board_runtime.py` `c359c89b2af4d0d047aca6786ddaef25eaac46fb5815d7345d5124914786ccff`

## 4. 最终清单

正式 1000 张完成、`results/subset1000/` 取回后，运行：

```bash
cd /home/cym/prj2/finn/notebooks/end2end_example/sy2/spikformer-main/cifar10/board_test_exspike_binary_ria_8_16
python3 -I scripts/finalize_results.py
```

该脚本会：
- 校验 1000 行、序列/索引/标签、34/30/4 调用、最终正确率；
- 生成 `reports/FINAL_RESULTS.md`、`reports/FINAL_COMPARISON.csv`；
- 生成包含结果目录的 `SHA256SUMS.txt`；
- 生成 `board_test_exspike_binary_ria_8_16_package.zip`。
