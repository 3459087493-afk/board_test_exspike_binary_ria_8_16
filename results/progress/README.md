# 1000 张进度快照

- 板端权威进度：`/home/xilinx/jupyter_notebooks/board_test_exspike_binary_ria_8_16/results/subset1000/progress.json`
- 本目录的 `snapshot_XXXX/` 是从板上只读取回的中间快照，包含 `progress.json`、`results.json`、`predictions.csv`、`summary.json`。
- 快照用于进度记录和中间校验；**不是最终 Top-1 或最终延迟**。
- 最终结果以 `results/subset1000/results.json` 和 `predictions.csv` 为准，并由 `scripts/finalize_results.py` 生成 `reports/FINAL_RESULTS.md`、`SHA256SUMS.txt` 与压缩包。
