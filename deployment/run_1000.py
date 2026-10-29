#!/usr/bin/env python3
"""Phase C: the formal fixed 1000-image PYNQ-Z2 run.

The run must be explicitly confirmed.  Like ``run_10.py``, this entry uses
``os.execv`` so the board runner is the direct process under sudo; this avoids
the PYNQ 2.7 XRT CMA problem observed with a Python parent process.  The runner
is resumable by dataset index and writes progress and CSV rows every 10 images.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent
DEFAULT_OUTPUT = PACKAGE_ROOT / "results" / "subset1000"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-1000", action="store_true",
                        help="required explicit confirmation for the 1000-image run")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--save-interval", type=int, default=10)
    parser.add_argument("--fresh", action="store_true", help="archive existing results before starting")
    args = parser.parse_args()
    if not args.confirm_1000:
        print("REFUSED: pass --confirm-1000 only after the single-image and 10-image gates pass.")
        return 2
    active = subprocess.run(["pgrep", "-af", "[b]oard_runner.py"], capture_output=True, text=True)
    if active.stdout.strip():
        raise SystemExit("REFUSED: another board_runner.py is already active:\n" + active.stdout)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(HERE / "board_runner.py"),
               "--mode", "subset1000", "--output-dir", str(args.output_dir),
               "--save-interval", str(args.save_interval)]
    if args.fresh:
        command.append("--start-from-scratch")
    os.execv(sys.executable, command)


if __name__ == "__main__":
    raise SystemExit(main())
