#!/usr/bin/env python3
"""Phase B: exactly ten fixed-subset images through the real PL.

This entry deliberately replaces its own process with ``board_runner.py`` via
``os.execv``.  On the PYNQ 2.7 board, launching the runner as a child of a
Python wrapper reproducibly caused an XRT CMA allocation failure at the block1
input buffer, while running the runner directly succeeded.  There is therefore
no parent Python process between sudo and the board runner.

Per-image CSV/progress are written by ``board_runner.py``.  Run
``summarize_ten.py`` afterwards to produce ``ten_summary.json``.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent
DEFAULT_OUTPUT = PACKAGE_ROOT / "results" / "ten"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fresh", action="store_true", help="archive existing ten-image outputs first")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(HERE / "board_runner.py"),
               "--mode", "subset1000", "--limit", "10",
               "--output-dir", str(args.output_dir), "--save-interval", "10"]
    if args.fresh:
        command.append("--start-from-scratch")
    os.execv(sys.executable, command)


if __name__ == "__main__":
    main()
