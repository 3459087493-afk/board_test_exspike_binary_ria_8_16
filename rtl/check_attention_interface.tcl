set script_dir [file normalize [file dirname [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
create_project -in_memory -part xc7z020clg400-1
set_property source_mgmt_mode All [current_project]
add_files -norecurse [file join $root_dir rtl ternary_attention_top.v]
create_bd_design interface_check
create_bd_cell -type module -reference ternary_attention_top attention_0
puts "INTERFACE_PINS=[get_bd_intf_pins -of_objects [get_bd_cells attention_0]]"
puts "PLAIN_PINS=[get_bd_pins -of_objects [get_bd_cells attention_0]]"
close_project
exit
