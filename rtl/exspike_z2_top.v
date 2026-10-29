`timescale 1ns/1ps
// PYNQ-Z2 wrapper around ExSpike's actual event selection, address and accumulator RTL.
module exspike_z2_top(
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ap_clk CLK", X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF m_axi:s_axi_control, ASSOCIATED_RESET ap_rst_n, FREQ_HZ 100000000" *)
    input wire ap_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 ap_rst_n RST", X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input wire ap_rst_n,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWADDR" *)
    output wire [31:0] m_axi_AWADDR,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWLEN" *)
    output wire [7:0] m_axi_AWLEN,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWSIZE" *)
    output wire [2:0] m_axi_AWSIZE,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWBURST" *)
    output wire [1:0] m_axi_AWBURST,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWLOCK" *)
    output wire m_axi_AWLOCK,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWCACHE" *)
    output wire [3:0] m_axi_AWCACHE,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWPROT" *)
    output wire [2:0] m_axi_AWPROT,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWQOS" *)
    output wire [3:0] m_axi_AWQOS,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWVALID" *)
    output wire m_axi_AWVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi AWREADY" *)
    input wire m_axi_AWREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi WDATA" *)
    output wire [63:0] m_axi_WDATA,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi WSTRB" *)
    output wire [7:0] m_axi_WSTRB,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi WLAST" *)
    output wire m_axi_WLAST,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi WVALID" *)
    output wire m_axi_WVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi WREADY" *)
    input wire m_axi_WREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi BRESP" *)
    input wire [1:0] m_axi_BRESP,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi BVALID" *)
    input wire m_axi_BVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi BREADY" *)
    output wire m_axi_BREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARADDR" *)
    output wire [31:0] m_axi_ARADDR,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARLEN" *)
    output wire [7:0] m_axi_ARLEN,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARSIZE" *)
    output wire [2:0] m_axi_ARSIZE,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARBURST" *)
    output wire [1:0] m_axi_ARBURST,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARLOCK" *)
    output wire m_axi_ARLOCK,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARCACHE" *)
    output wire [3:0] m_axi_ARCACHE,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARPROT" *)
    output wire [2:0] m_axi_ARPROT,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARQOS" *)
    output wire [3:0] m_axi_ARQOS,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARVALID" *)
    output wire m_axi_ARVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi ARREADY" *)
    input wire m_axi_ARREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi RDATA" *)
    input wire [63:0] m_axi_RDATA,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi RRESP" *)
    input wire [1:0] m_axi_RRESP,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi RLAST" *)
    input wire m_axi_RLAST,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi RVALID" *)
    input wire m_axi_RVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 m_axi RREADY" *)
    output wire m_axi_RREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control AWADDR" *)
    input wire [7:0] s_axi_control_AWADDR,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control AWVALID" *)
    input wire s_axi_control_AWVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control AWREADY" *)
    output wire s_axi_control_AWREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control WDATA" *)
    input wire [31:0] s_axi_control_WDATA,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control WSTRB" *)
    input wire [3:0] s_axi_control_WSTRB,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control WVALID" *)
    input wire s_axi_control_WVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control WREADY" *)
    output wire s_axi_control_WREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control BRESP" *)
    output wire [1:0] s_axi_control_BRESP,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control BVALID" *)
    output wire s_axi_control_BVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control BREADY" *)
    input wire s_axi_control_BREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control ARADDR" *)
    input wire [7:0] s_axi_control_ARADDR,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control ARVALID" *)
    input wire s_axi_control_ARVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control ARREADY" *)
    output wire s_axi_control_ARREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control RDATA" *)
    output wire [31:0] s_axi_control_RDATA,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control RRESP" *)
    output wire [1:0] s_axi_control_RRESP,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control RVALID" *)
    output wire s_axi_control_RVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi_control RREADY" *)
    input wire s_axi_control_RREADY
);

wire clk=ap_clk, rst_n=ap_rst_n;
// AXI-Lite: independent AW/W latches, no assumptions about their relative order.
reg aw_hold,w_hold,bvalid,rvalid; reg [7:0] aw_addr; reg [31:0] w_data,rdata;reg [3:0] w_strobe;
reg [31:0] xbase,wbase,ybase,vectors,in_features,out_features,sparse_mode;
reg start_pulse,done;
reg [7:0] state;
reg [31:0] error_code;
reg [63:0] cycles,events,mac_issues,read_beats;
localparam IDLE=0,WREQ=1,WDATA=2,XREQ=3,XDATA=4,CLEAR=5,MAP_LOAD=6,
           EVENT_REQ=7,EVENT_WAIT=8,EVENT_READ=9,EVENT_MUL=10,EVENT_ACC=11,
           YREQ=12,YWAIT=13,NEXT_VECTOR=14,DONE=15;
wire ctrl_read=s_axi_control_ARVALID && s_axi_control_ARREADY && s_axi_control_ARADDR==0;
assign s_axi_control_AWREADY=!aw_hold&&!bvalid;
assign s_axi_control_WREADY=!w_hold&&!bvalid;
assign s_axi_control_BVALID=bvalid;
assign s_axi_control_BRESP=0;
assign s_axi_control_ARREADY=!rvalid;
assign s_axi_control_RVALID=rvalid;
assign s_axi_control_RDATA=rdata;
assign s_axi_control_RRESP=0;
always @(posedge clk) begin
 if(!rst_n) begin
  aw_hold<=0;w_hold<=0;bvalid<=0;rvalid<=0;start_pulse<=0;done<=0;
  xbase<=0;wbase<=0;ybase<=0;vectors<=0;in_features<=0;out_features<=0;sparse_mode<=0;
 end else begin
  start_pulse<=0;
  if(ctrl_read)done<=0;
  if(state==DONE)done<=1;
  if(s_axi_control_AWVALID&&s_axi_control_AWREADY)begin aw_hold<=1;aw_addr<=s_axi_control_AWADDR;end
  if(s_axi_control_WVALID&&s_axi_control_WREADY)begin w_hold<=1;w_data<=s_axi_control_WDATA;w_strobe<=s_axi_control_WSTRB;end
  if(bvalid&&s_axi_control_BREADY)bvalid<=0;
  if(aw_hold&&w_hold&&!bvalid)begin
   aw_hold<=0;w_hold<=0;bvalid<=1;
   if(w_strobe==4'hf)case(aw_addr)
    8'h00:if(w_data[0]&&state==IDLE)begin start_pulse<=1;done<=0;end
    8'h10:xbase<=w_data;
    8'h1c:wbase<=w_data;
    8'h28:ybase<=w_data;
    8'h34:vectors<=w_data;
    8'h3c:in_features<=w_data;
    8'h44:out_features<=w_data;
    8'h4c:sparse_mode<=w_data;
   endcase
  end
  if(rvalid&&s_axi_control_RREADY)rvalid<=0;
  if(s_axi_control_ARVALID&&s_axi_control_ARREADY)begin
   rvalid<=1;
   case(s_axi_control_ARADDR)
    8'h00:rdata<={28'b0,(state==IDLE),(state==IDLE),done,1'b0};
    8'h10:rdata<=xbase;8'h1c:rdata<=wbase;8'h28:rdata<=ybase;
    8'h34:rdata<=vectors;8'h3c:rdata<=in_features;8'h44:rdata<=out_features;8'h4c:rdata<=sparse_mode;
    8'h50:rdata<=error_code;8'h54:rdata<=cycles[31:0];8'h58:rdata<=cycles[63:32];
    8'h5c:rdata<=events[31:0];8'h60:rdata<=events[63:32];
    8'h64:rdata<=mac_issues[31:0];8'h68:rdata<=mac_issues[63:32];8'h6c:rdata<=read_beats[31:0];
    default:rdata<=0;
   endcase
  end
 end
end

// Single outstanding AXI reader. Weights are 128-bit records (two64-bit beats).
reg [1:0] rs;reg [31:0] rd_addr;
wire rd_cmd=(state==WREQ||state==XREQ);
wire rd_ready=(rs==0);
reg [31:0] weight_tile_base,input_row_base,output_row_base;
wire [31:0] col_weight_address=weight_tile_base+(column<<4);
wire [31:0] col_input_address=input_row_base+(column<<1);
wire [31:0] words_left=(in_features-column+3)>>2;
wire [31:0] page_words=(4096-{20'b0,col_input_address[11:0]})>>3;
wire [31:0] limited_words=(words_left<16)?words_left:16;
wire [31:0] xburst_words=(limited_words<page_words)?limited_words:page_words;
reg [7:0] rd_len;reg [2:0] rd_size;
assign m_axi_ARADDR=rd_addr;
assign m_axi_ARLEN=rd_len;
assign m_axi_ARSIZE=rd_size;
assign m_axi_ARBURST=1;assign m_axi_ARLOCK=0;assign m_axi_ARCACHE=4'b0011;
assign m_axi_ARPROT=0;assign m_axi_ARQOS=0;
assign m_axi_ARVALID=(rs==1);assign m_axi_RREADY=(rs==2);
wire rd_valid=m_axi_RVALID&&m_axi_RREADY;
always @(posedge clk)begin
 if(!rst_n)begin rs<=0;rd_addr<=0;end else case(rs)
  0:if(rd_cmd)begin rd_addr<=(state==WREQ)?col_weight_address:col_input_address;rd_len<=(state==WREQ)?8'd1:xburst_words[7:0]-1'b1;rd_size<=3;rs<=1;end
  1:if(m_axi_ARREADY)rs<=2;
  2:if(rd_valid&&m_axi_RLAST)rs<=0;
 endcase
end

reg [31:0] vector_id,out_tile,column,group_base,lane_id;
reg weight_half;

reg [15:0] event_map[0:255];
wire [3:0] new_events={
 ((column+3<in_features)&&(m_axi_RDATA[63:48]!=0)),
 ((column+2<in_features)&&(m_axi_RDATA[47:32]!=0)),
 ((column+1<in_features)&&(m_axi_RDATA[31:16]!=0)),
 (m_axi_RDATA[15:0]!=0)};
wire [15:0] one_hot;
wire one_hot_valid,empty;
wire [8:0] absolute_addr;
wire absolute_valid;
FAST_FILTER #(.WIDTH(16)) U_EXSPIKE_FAST_FILTER(
 .clk(clk),.rst_n(rst_n),.neuron_spike(event_map[group_base>>4]),
 .neuron_spike_valid(state==MAP_LOAD),
 .generate_next_en(state==EVENT_REQ&&!empty),
 .spike_index(one_hot),.spike_index_valid(one_hot_valid),.no_valid_spike(empty));
// ExSpike's actual original address decoder, with the16-event group zero-extended.
INDEX2ABS_SUB_0 U_EXSPIKE_INDEX2ABS(
 .clk(clk),.rst_n(rst_n),.spike_index({112'b0,one_hot}),.spike_index_valid(one_hot_valid),
 .absolute_addr(absolute_addr),.absolute_addr_valid(absolute_valid),.generate_next_en(1'b1));

wire [63:0] current_weights;
wire [7:0] current_selected;
wire [63:0] current_input_word;
reg [1:0] current_input_lane;
wire signed [15:0] current_activation=current_input_word >> (current_input_lane*16);
wire [31:0] event_address=group_base+absolute_addr;
exspike_tile_ram #(.WIDTH(64),.ADDR_BITS(12)) U_WEIGHT_TILE(
 .clk(clk),.we(state==WDATA&&rd_valid&&!weight_half),.waddr(column[11:0]),.wdata(m_axi_RDATA),
 .re(state==EVENT_READ),.raddr(event_address[11:0]),.rdata(current_weights));
exspike_tile_ram #(.WIDTH(8),.ADDR_BITS(12)) U_SELECTED_TILE(
 .clk(clk),.we(state==WDATA&&rd_valid&&weight_half),.waddr(column[11:0]),.wdata(m_axi_RDATA[7:0]),
 .re(state==EVENT_READ),.raddr(event_address[11:0]),.rdata(current_selected));
exspike_tile_ram #(.WIDTH(64),.ADDR_BITS(10)) U_INPUT_TILE(
 .clk(clk),.we(state==XDATA&&rd_valid),.waddr(column[11:2]),.wdata(m_axi_RDATA),
 .re(state==EVENT_READ),.raddr(event_address[11:2]),.rdata(current_input_word));
reg signed [23:0] product[0:7];
wire [47:0] accum[0:7];
genvar g;
generate for(g=0;g<8;g=g+1)begin:lane
 always @(posedge clk)if(state==EVENT_MUL && current_selected[g])
  product[g] <= $signed(current_activation) * $signed(current_weights[g*8+:8]);
 wire [47:0] term={{24{product[g][23]}},product[g]};
 MP_ACC #(.WIDTH(48)) U_EXSPIKE_MP_ACC(
  .clk(clk),.acc_en(state==CLEAR || (state==EVENT_ACC&&current_selected[g])),
  .src_mp((state==CLEAR)?48'b0:accum[g]),
  .weight((state==CLEAR)?48'b0:term),.res(accum[g]));
end endgenerate

function [31:0] sat32;
 input signed [47:0] value;
 begin
  if(value>48'sd2147483647)sat32=32'h7fffffff;
  else if(value< -48'sd2147483648)sat32=32'h80000000;
  else sat32=value[31:0];
 end
endfunction
function [3:0] pop8;
 input [7:0] mask;integer i;
 begin pop8=0;for(i=0;i<8;i=i+1)pop8=pop8+mask[i];end
endfunction
// Single outstanding AXI writer, narrow32-bit output on the64-bit HP port.
reg [2:0] ws;reg [31:0] wr_addr,wr_value;
wire wr_ready=(ws==0);
wire wr_done=(ws==4&&m_axi_BVALID);
assign m_axi_AWADDR=wr_addr;assign m_axi_AWLEN=0;assign m_axi_AWSIZE=2;
assign m_axi_AWBURST=1;assign m_axi_AWLOCK=0;assign m_axi_AWCACHE=4'b0011;
assign m_axi_AWPROT=0;assign m_axi_AWQOS=0;assign m_axi_AWVALID=(ws==1);
assign m_axi_WDATA={32'b0,wr_value} << (wr_addr[2:0]*8);
assign m_axi_WSTRB=8'h0f << wr_addr[2:0];
assign m_axi_WLAST=1;assign m_axi_WVALID=(ws==2);assign m_axi_BREADY=(ws==4);
always @(posedge clk)begin
 if(!rst_n)begin ws<=0;wr_addr<=0;wr_value<=0;end else case(ws)
  0:if(state==YREQ)begin wr_addr<=output_row_base+((out_tile+lane_id)<<2);wr_value<=sat32($signed(accum[lane_id]));ws<=1;end
  1:if(m_axi_AWREADY)ws<=2;
  2:if(m_axi_WREADY)ws<=4;
  4:if(m_axi_BVALID)ws<=0;
 endcase
end

always @(posedge clk)begin
 if(!rst_n)begin state<=IDLE;error_code<=0;cycles<=0;events<=0;mac_issues<=0;read_beats<=0;
  vector_id<=0;out_tile<=0;column<=0;group_base<=0;lane_id<=0;weight_half<=0;
  weight_tile_base<=0;input_row_base<=0;output_row_base<=0;
 end else begin
  if(state!=IDLE)cycles<=cycles+1;
  if(rd_valid)read_beats<=read_beats+1;
  case(state)
   IDLE:if(start_pulse)begin
    error_code<=0;cycles<=0;events<=0;mac_issues<=0;read_beats<=0;
    out_tile<=0;column<=0;vector_id<=0;weight_half<=0;
    weight_tile_base<=wbase;input_row_base<=xbase;output_row_base<=ybase;
    if(in_features==0||in_features>4096||vectors==0||vectors>4096||out_features==0)begin error_code<=1;state<=DONE;end
    else state<=WREQ;
   end
   WREQ:if(rd_ready)state<=WDATA;
   WDATA:if(rd_valid)begin
    if(!weight_half)begin weight_half<=1;end
    else begin
weight_half<=0;
     if(column+1<in_features)begin column<=column+1;state<=WREQ;end
     else begin column<=0;state<=XREQ;end
    end
   end
   XREQ:if(rd_ready)state<=XDATA;
   XDATA:if(rd_valid)begin
    if(column[3:0]==0)event_map[column>>4]<={12'b0,new_events};
    else event_map[column>>4]<=event_map[column>>4]|({12'b0,new_events}<<column[3:0]);
    if(column+4>=in_features)begin group_base<=0;state<=CLEAR;end
    else begin column<=column+4;if(m_axi_RLAST)state<=XREQ;end
   end
   CLEAR:state<=MAP_LOAD;
   MAP_LOAD:state<=EVENT_REQ;
   EVENT_REQ:if(empty)begin
    if(group_base+16<in_features)begin group_base<=group_base+16;state<=MAP_LOAD;end
    else begin lane_id<=0;state<=YREQ;end
   end else state<=EVENT_WAIT;
   EVENT_WAIT:state<=EVENT_READ;
   EVENT_READ:begin
    current_input_lane<=event_address[1:0];
    state<=EVENT_MUL;
   end
   EVENT_MUL:state<=EVENT_ACC;
   EVENT_ACC:begin events<=events+1;mac_issues<=mac_issues+pop8(current_selected);state<=EVENT_REQ;end
   YREQ:if(wr_ready)state<=YWAIT;
   YWAIT:if(wr_done)begin
    if(lane_id+1<8 && out_tile+lane_id+1<out_features)begin lane_id<=lane_id+1;state<=YREQ;end
    else state<=NEXT_VECTOR;
   end
   NEXT_VECTOR:begin
    column<=0;
    if(vector_id+1<vectors)begin
     vector_id<=vector_id+1;input_row_base<=input_row_base+(((in_features+3)>>2)<<3);
     output_row_base<=output_row_base+(out_features<<2);state<=XREQ;
    end
    else if(out_tile+8<out_features)begin
     out_tile<=out_tile+8;vector_id<=0;weight_tile_base<=weight_tile_base+(in_features<<4);
     input_row_base<=xbase;output_row_base<=ybase;state<=WREQ;
    end
    else state<=DONE;
   end
   DONE:state<=IDLE;
  endcase
  if(rd_valid&&m_axi_RRESP!=0)begin error_code<=32'h100|m_axi_RRESP;state<=DONE;end
  if(wr_done&&m_axi_BRESP!=0)begin error_code<=32'h200|m_axi_BRESP;state<=DONE;end
 end
end
endmodule
