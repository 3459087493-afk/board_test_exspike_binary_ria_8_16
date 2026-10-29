#!/usr/bin/env python3
"""Run real RTL/AXI testbench and retain stdout and a machine-readable result."""
import json
from pathlib import Path
import subprocess

B=Path(__file__).resolve().parent.parent
cmd=['iverilog','-g2012','-s','tb_exspike','-o','sim/tb_exspike.vvp',
     'rtl/exspike_z2_top.v','rtl/exspike_tile_ram.v','rtl/exspike/fast_filter.v',
     'rtl/exspike/index2abs_sub.v','rtl/exspike/mp_acc.v','sim/tb_exspike.v']
subprocess.run(cmd,cwd=B,check=True)
matrix=subprocess.run(['vvp','sim/tb_exspike.vvp'],cwd=B,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
attention_compile=['iverilog','-g2012','-s','tb_ternary_attention','-o','sim/tb_ternary_attention.vvp',
                   'rtl/ternary_attention_top.v','sim/tb_ternary_attention.v']
subprocess.run(attention_compile,cwd=B,check=True)
attention=subprocess.run(['vvp','sim/tb_ternary_attention.vvp'],cwd=B,text=True,
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
stdout=matrix.stdout+attention.stdout
(B/'sim/rtl_simulation.log').write_text(stdout)
print(stdout)
passed=(matrix.returncode==0 and attention.returncode==0 and
        'RTL_INTEGER_SIMULATION_PASS' in matrix.stdout and
        'TERNARY_ATTENTION_RTL_PASS' in attention.stdout)
(B/'rtl_simulation.json').write_text(json.dumps({'status':'PASS' if passed else 'FAIL',
    'simulator':'Icarus Verilog',
    'testbenches':['sim/tb_exspike.v','sim/tb_ternary_attention.v'],
    'matrix_cases':10,
    'attention_scope':'signed non-identical tokens, temporal LIF state, AXI and work counters',
    'scope':'actual RTL with AXI memory and register transactions; not HLS and not board inference',
    'stdout':stdout},indent=2)+'\n')
raise SystemExit(0 if passed else 1)
