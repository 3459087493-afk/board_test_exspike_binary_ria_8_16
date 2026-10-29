#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
unset DEBUG
exec /tools/Xilinx/Vivado/2022.2/bin/vivado -mode batch -source "$SCRIPT_DIR/build_overlay.tcl"
