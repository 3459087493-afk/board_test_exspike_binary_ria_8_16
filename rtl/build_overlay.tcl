set script_dir [file normalize [file dirname [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set project_dir [file join $script_dir exspike_migration_8_16_vivado]
set rtl_dir [file join $root_dir rtl]
set board_repo [file normalize [file join $root_dir .. board_test_8_16 third_party pynq-supported-board-file]]
set design_name exspike_migration_8_16_design
set output_dir $root_dir

set_param board.repoPaths [list $board_repo]
create_project exspike_migration_8_16_vivado $project_dir -part xc7z020clg400-1 -force
set_property board_part tul.com.tw:pynq-z2:part0:1.0 [current_project]
add_files -norecurse [glob [file join $rtl_dir *.v]]
add_files -norecurse [glob [file join $rtl_dir exspike *.v]]
update_compile_order -fileset sources_1

create_bd_design $design_name
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 processing_system7_0
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} \
    [get_bd_cells processing_system7_0]
set_property -dict [list \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP1 {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100.000000} \
] [get_bd_cells processing_system7_0]

create_bd_cell -type module -reference exspike_z2_top exspike_0
create_bd_cell -type module -reference ternary_attention_top attention_0
apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
    -config {Master "/processing_system7_0/M_AXI_GP0" Slave "/exspike_0/s_axi_control" Clk_master "/processing_system7_0/FCLK_CLK0 (100 MHz)" Clk_slave "/processing_system7_0/FCLK_CLK0 (100 MHz)" Clk_xbar "/processing_system7_0/FCLK_CLK0 (100 MHz)" intc_ip "New AXI Interconnect" master_apm "0"} \
    [get_bd_intf_pins exspike_0/s_axi_control]

apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
    -config {Master "/processing_system7_0/M_AXI_GP0" Slave "/attention_0/s_axi_control" Clk_master "/processing_system7_0/FCLK_CLK0 (100 MHz)" Clk_slave "/processing_system7_0/FCLK_CLK0 (100 MHz)" Clk_xbar "/processing_system7_0/FCLK_CLK0 (100 MHz)" intc_ip "New AXI Interconnect" master_apm "0"} \
    [get_bd_intf_pins attention_0/s_axi_control]

apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
    -config {Master "/exspike_0/m_axi" Slave "/processing_system7_0/S_AXI_HP0" Clk_master "/processing_system7_0/FCLK_CLK0 (100 MHz)" Clk_slave "/processing_system7_0/FCLK_CLK0 (100 MHz)" Clk_xbar "/processing_system7_0/FCLK_CLK0 (100 MHz)" intc_ip "New AXI Interconnect" master_apm "0"} \
    [get_bd_intf_pins processing_system7_0/S_AXI_HP0]

apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
    -config {Master "/attention_0/m_axi" Slave "/processing_system7_0/S_AXI_HP1" Clk_master "/processing_system7_0/FCLK_CLK0 (100 MHz)" Clk_slave "/processing_system7_0/FCLK_CLK0 (100 MHz)" Clk_xbar "/processing_system7_0/FCLK_CLK0 (100 MHz)" intc_ip "New AXI Interconnect" master_apm "0"} \
    [get_bd_intf_pins processing_system7_0/S_AXI_HP1]

assign_bd_address
validate_bd_design
save_bd_design

set bd_file [get_files ${design_name}.bd]
make_wrapper -files $bd_file -top
set wrappers [glob -nocomplain [file join $project_dir *.gen sources_1 bd $design_name hdl *_wrapper.v]]
if {[llength $wrappers] != 1} { error "Expected one BD wrapper, got: $wrappers" }
add_files -norecurse [lindex $wrappers 0]
set_property top ${design_name}_wrapper [current_fileset]
update_compile_order -fileset sources_1

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
set impl_status [get_property STATUS [get_runs impl_1]]
if {![string match "write_bitstream Complete*" $impl_status]} {
    error "Implementation did not complete: $impl_status"
}
open_run impl_1

report_utilization -file [file join $output_dir utilization.rpt]
report_utilization -hierarchical -file [file join $output_dir utilization_hierarchical.rpt]
report_timing_summary -delay_type max -report_unconstrained -check_timing_verbose \
    -max_paths 10 -file [file join $output_dir timing_summary.rpt]
report_drc -file [file join $output_dir drc.rpt]
report_power -file [file join $output_dir power.rpt]
set worst_slack [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
if {$worst_slack < 0} { error "Timing failed at100MHz: WNS=$worst_slack; do not deploy this build" }

set bit_files [glob -nocomplain [file join $project_dir *.runs impl_1 ${design_name}_wrapper.bit]]
set hwh_files [glob -nocomplain [file join $project_dir *.gen sources_1 bd $design_name hw_handoff ${design_name}.hwh]]
if {[llength $bit_files] != 1 || [llength $hwh_files] != 1} {
    error "BIT/HWH discovery failed: bit=$bit_files hwh=$hwh_files"
}
file copy -force [lindex $bit_files 0] [file join $output_dir exspike_migration_8_16.bit]
file copy -force [lindex $hwh_files 0] [file join $output_dir exspike_migration_8_16.hwh]
# Keep the build archive stem different from the runtime .bit/.hwh stem.
# PYNQ 3.1 otherwise treats a same-stem companion XSA as the Overlay input.
write_hw_platform -fixed -include_bit -force -file [file join $output_dir exspike_migration_8_16_build.xsa]
puts "BUILD_COMPLETE part=[get_property PART [current_project]] bit=[file join $output_dir exspike_migration_8_16.bit] hwh=[file join $output_dir exspike_migration_8_16.hwh]"
exit
