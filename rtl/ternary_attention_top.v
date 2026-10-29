`timescale 1ns/1ps
// Exact integer attention path for the deployed ternary Spikformer.
//
// Input layout is head-major [head][time=4][token][dim=32], signed INT8
// with values restricted to {-1,0,+1}.  For each group this block computes
//   score = Q * K^T
//   value = score * V
// and folds the model's value/8 scale plus binary LIF into an integer update:
//   membrane_scaled = membrane_scaled/2 + 8*value; threshold_scaled = 64.
// membrane_scaled represents 128*v, which is exact for all four time steps.
// Output is one byte per element, 0 or 1, in the same head-major layout.
module ternary_attention_top(
 (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ap_clk CLK", X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF m_axi:s_axi_control, ASSOCIATED_RESET ap_rst_n, FREQ_HZ 100000000" *)
 input wire ap_clk,
 (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 ap_rst_n RST", X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
 input wire ap_rst_n,
 output wire [31:0] m_axi_AWADDR,output wire [7:0] m_axi_AWLEN,
 output wire [2:0] m_axi_AWSIZE,output wire [1:0] m_axi_AWBURST,
 output wire m_axi_AWLOCK,output wire [3:0] m_axi_AWCACHE,
 output wire [2:0] m_axi_AWPROT,output wire [3:0] m_axi_AWQOS,
 output wire m_axi_AWVALID,input wire m_axi_AWREADY,
 output wire [63:0] m_axi_WDATA,output wire [7:0] m_axi_WSTRB,
 output wire m_axi_WLAST,output wire m_axi_WVALID,input wire m_axi_WREADY,
 input wire [1:0] m_axi_BRESP,input wire m_axi_BVALID,output wire m_axi_BREADY,
 output wire [31:0] m_axi_ARADDR,output wire [7:0] m_axi_ARLEN,
 output wire [2:0] m_axi_ARSIZE,output wire [1:0] m_axi_ARBURST,
 output wire m_axi_ARLOCK,output wire [3:0] m_axi_ARCACHE,
 output wire [2:0] m_axi_ARPROT,output wire [3:0] m_axi_ARQOS,
 output wire m_axi_ARVALID,input wire m_axi_ARREADY,
 input wire [63:0] m_axi_RDATA,input wire [1:0] m_axi_RRESP,
 input wire m_axi_RLAST,input wire m_axi_RVALID,output wire m_axi_RREADY,
 input wire [7:0] s_axi_control_AWADDR,input wire s_axi_control_AWVALID,
 output wire s_axi_control_AWREADY,input wire [31:0] s_axi_control_WDATA,
 input wire [3:0] s_axi_control_WSTRB,input wire s_axi_control_WVALID,
 output wire s_axi_control_WREADY,output wire [1:0] s_axi_control_BRESP,
 output wire s_axi_control_BVALID,input wire s_axi_control_BREADY,
 input wire [7:0] s_axi_control_ARADDR,input wire s_axi_control_ARVALID,
 output wire s_axi_control_ARREADY,output wire [31:0] s_axi_control_RDATA,
 output wire [1:0] s_axi_control_RRESP,output wire s_axi_control_RVALID,
 input wire s_axi_control_RREADY
);
wire clk=ap_clk,rst_n=ap_rst_n;

// AXI-Lite register file. Physical CMA addresses on Zynq-7020 are 32 bit.
reg aw_hold,w_hold,bvalid,rvalid,start_pulse,done;
reg [7:0] aw_addr; reg [31:0] w_data,rdata; reg [3:0] w_strobe;
reg [31:0] qbase,kbase,vbase,obase,groups,tokens,dims,error_code;
reg [63:0] cycles,read_beats,write_beats,qk_terms,av_terms;
reg [5:0] state;
localparam IDLE=0,LQ_REQ=1,LQ_DATA=2,LK_REQ=3,LK_DATA=4,
 LP_REQ=5,LP_DATA=6,QK_INIT=7,QK_FETCH=8,QK_DOT=9,QK_RUN=10,
 AV_INIT=11,AV_FETCH=12,AV_RUN=13,AV_FINISH=14,LIF_STORE=15,
 WR_AW=16,WR_W=17,WR_B=18,ADVANCE=19,DONE=20;
wire ctrl_read=s_axi_control_ARVALID&&s_axi_control_ARREADY&&s_axi_control_ARADDR==0;
assign s_axi_control_AWREADY=!aw_hold&&!bvalid;
assign s_axi_control_WREADY=!w_hold&&!bvalid;
assign s_axi_control_BVALID=bvalid; assign s_axi_control_BRESP=0;
assign s_axi_control_ARREADY=!rvalid; assign s_axi_control_RVALID=rvalid;
assign s_axi_control_RDATA=rdata; assign s_axi_control_RRESP=0;
always @(posedge clk) begin
 if(!rst_n) begin
  aw_hold<=0;w_hold<=0;bvalid<=0;rvalid<=0;start_pulse<=0;done<=0;
  qbase<=0;kbase<=0;vbase<=0;obase<=0;groups<=0;tokens<=0;dims<=0;
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
    8'h10:qbase<=w_data; 8'h1c:kbase<=w_data; 8'h28:vbase<=w_data;
    8'h34:obase<=w_data; 8'h40:groups<=w_data;
    8'h48:tokens<=w_data; 8'h50:dims<=w_data;
   endcase
  end
  if(rvalid&&s_axi_control_RREADY)rvalid<=0;
  if(s_axi_control_ARVALID&&s_axi_control_ARREADY)begin
   rvalid<=1;
   case(s_axi_control_ARADDR)
    8'h00:rdata<={28'b0,(state==IDLE),(state==IDLE),done,1'b0};
    8'h10:rdata<=qbase;8'h1c:rdata<=kbase;8'h28:rdata<=vbase;8'h34:rdata<=obase;
    8'h40:rdata<=groups;8'h48:rdata<=tokens;8'h50:rdata<=dims;
    8'h58:rdata<=cycles[31:0];8'h5c:rdata<=cycles[63:32];
    8'h60:rdata<=read_beats[31:0];8'h64:rdata<=write_beats[31:0];
    8'h68:rdata<=error_code;
    8'h6c:rdata<=qk_terms[31:0];8'h70:rdata<=qk_terms[63:32];
    8'h74:rdata<=av_terms[31:0];8'h78:rdata<=av_terms[63:32];
    default:rdata<=0;
   endcase
  end
 end
end

// One head/time slice occupies at most 64*32 bytes = 256 AXI beats.
reg [63:0] qmem[0:255]; reg [63:0] kmem[0:255]; reg [63:0] vmem[0:255];
reg signed [7:0] score_mem[0:4095];
reg signed [15:0] lif_mem[0:2047];
reg [31:0] group_id,group_bytes,q_group_addr,k_group_addr,v_group_addr,o_group_addr;
reg [8:0] load_word,load_total;
reg [7:0] burst_left,burst_len;
reg [31:0] rd_addr;
wire read_request=(state==LQ_REQ||state==LK_REQ||state==LP_REQ);
wire read_data=(state==LQ_DATA||state==LK_DATA||state==LP_DATA);
wire [8:0] words_remaining=load_total-load_word;
wire [7:0] next_burst=(words_remaining>16)?16:words_remaining[7:0];
assign m_axi_ARADDR=rd_addr; assign m_axi_ARLEN=next_burst-1'b1;
assign m_axi_ARSIZE=3;assign m_axi_ARBURST=1;assign m_axi_ARLOCK=0;
assign m_axi_ARCACHE=4'b0011;assign m_axi_ARPROT=0;assign m_axi_ARQOS=0;
assign m_axi_ARVALID=read_request;assign m_axi_RREADY=read_data;

reg [6:0] qi,qj; reg [2:0] qkg; reg signed [15:0] qk_acc;
reg [63:0] q_word_reg,k_word_reg; reg signed [15:0] qk_dot_reg;
reg [6:0] ai; reg [5:0] ad; reg [6:0] aj; reg signed [23:0] av_acc;
reg signed [7:0] av_score_reg,av_v_reg;
reg [63:0] out_pack; reg [31:0] wr_addr; reg [63:0] wr_value;
reg signed [24:0] lif_candidate_reg;

function signed [15:0] dot_ternary8;
 input [63:0] a; input [63:0] b;
 reg signed [7:0] a0,a1,a2,a3,a4,a5,a6,a7;
 reg signed [7:0] b0,b1,b2,b3,b4,b5,b6,b7;
 reg signed [1:0] p0,p1,p2,p3,p4,p5,p6,p7;
 reg signed [2:0] s0,s1,s2,s3;
 reg signed [3:0] t0,t1;
 begin
  a0=$signed(a[7:0]);a1=$signed(a[15:8]);a2=$signed(a[23:16]);a3=$signed(a[31:24]);
  a4=$signed(a[39:32]);a5=$signed(a[47:40]);a6=$signed(a[55:48]);a7=$signed(a[63:56]);
  b0=$signed(b[7:0]);b1=$signed(b[15:8]);b2=$signed(b[23:16]);b3=$signed(b[31:24]);
  b4=$signed(b[39:32]);b5=$signed(b[47:40]);b6=$signed(b[55:48]);b7=$signed(b[63:56]);
  p0=(a0==0||b0==0)?0:((a0[7]^b0[7])?-1:1);
  p1=(a1==0||b1==0)?0:((a1[7]^b1[7])?-1:1);
  p2=(a2==0||b2==0)?0:((a2[7]^b2[7])?-1:1);
  p3=(a3==0||b3==0)?0:((a3[7]^b3[7])?-1:1);
  p4=(a4==0||b4==0)?0:((a4[7]^b4[7])?-1:1);
  p5=(a5==0||b5==0)?0:((a5[7]^b5[7])?-1:1);
  p6=(a6==0||b6==0)?0:((a6[7]^b6[7])?-1:1);
  p7=(a7==0||b7==0)?0:((a7[7]^b7[7])?-1:1);
  s0=p0+p1;s1=p2+p3;s2=p4+p5;s3=p6+p7;
  t0=s0+s1;t1=s2+s3;dot_ternary8=t0+t1;
 end
endfunction
// Explicit concatenation widens token indices before shifting.  Keeping the
// shift in the original 7-bit qi/ai width aliases tokens (e.g. ai<<6 wraps
// every two tokens in score_mem) after synthesis.
wire [63:0] q_word=qmem[{qi,2'b00}+qkg];
wire [63:0] k_word=kmem[{qj,2'b00}+qkg];
wire signed [15:0] qk_dot=dot_ternary8(q_word_reg,k_word_reg);
wire signed [7:0] av_score=score_mem[{ai,6'b000000}+aj];
wire [63:0] av_vword=vmem[{aj,2'b00}+(ad>>3)];
wire signed [7:0] av_v=$signed(av_vword[(ad[2:0]*8)+:8]);
wire signed [15:0] av_product=(av_v_reg==0)?16'sd0:(av_v_reg[7]?-av_score_reg:av_score_reg);
wire signed [23:0] av_sum=av_acc+av_product;
wire signed [15:0] prior_lif=(group_id[1:0]==0)?16'sd0:$signed(lif_mem[{ai,5'b00000}+ad]);
wire signed [24:0] lif_candidate=($signed(prior_lif)>>>1)+($signed(av_acc)<<<3);
wire lif_spike=(lif_candidate_reg>=25'sd64);

assign m_axi_AWADDR=wr_addr;assign m_axi_AWLEN=0;assign m_axi_AWSIZE=3;
assign m_axi_AWBURST=1;assign m_axi_AWLOCK=0;assign m_axi_AWCACHE=4'b0011;
assign m_axi_AWPROT=0;assign m_axi_AWQOS=0;assign m_axi_AWVALID=(state==WR_AW);
assign m_axi_WDATA=wr_value;assign m_axi_WSTRB=8'hff;assign m_axi_WLAST=1;
assign m_axi_WVALID=(state==WR_W);assign m_axi_BREADY=(state==WR_B);

always @(posedge clk)begin
 if(!rst_n)begin
  state<=IDLE;error_code<=0;cycles<=0;read_beats<=0;write_beats<=0;qk_terms<=0;av_terms<=0;
  group_id<=0;group_bytes<=0;q_group_addr<=0;k_group_addr<=0;v_group_addr<=0;o_group_addr<=0;
  load_word<=0;load_total<=0;burst_left<=0;burst_len<=0;rd_addr<=0;
  qi<=0;qj<=0;qkg<=0;qk_acc<=0;q_word_reg<=0;k_word_reg<=0;qk_dot_reg<=0;
  ai<=0;ad<=0;aj<=0;av_acc<=0;
  av_score_reg<=0;av_v_reg<=0;
  lif_candidate_reg<=0;out_pack<=0;wr_addr<=0;wr_value<=0;
 end else begin
  if(state!=IDLE)cycles<=cycles+1;
  case(state)
   IDLE:if(start_pulse)begin
    error_code<=0;cycles<=0;read_beats<=0;write_beats<=0;qk_terms<=0;av_terms<=0;group_id<=0;
    group_bytes<=tokens<<5;q_group_addr<=qbase;k_group_addr<=kbase;
    v_group_addr<=vbase;o_group_addr<=obase;load_word<=0;load_total<=tokens<<2;
    if(groups==0||groups>64||tokens==0||tokens>64||dims!=32)begin error_code<=1;state<=DONE;end
    else begin rd_addr<=qbase;state<=LQ_REQ;end
   end
   LQ_REQ:if(m_axi_ARREADY)begin burst_len<=next_burst;burst_left<=next_burst;state<=LQ_DATA;end
   LQ_DATA:if(m_axi_RVALID)begin
    qmem[load_word]<=m_axi_RDATA;load_word<=load_word+1;read_beats<=read_beats+1;
    burst_left<=burst_left-1;
    if(m_axi_RRESP!=0)begin error_code<=32'h100|m_axi_RRESP;state<=DONE;end
    else if(m_axi_RLAST)begin
     if(load_word+1==load_total)begin load_word<=0;rd_addr<=k_group_addr;state<=LK_REQ;end
     else begin rd_addr<=rd_addr+(burst_len<<3);state<=LQ_REQ;end
    end
   end
   LK_REQ:if(m_axi_ARREADY)begin burst_len<=next_burst;burst_left<=next_burst;state<=LK_DATA;end
   LK_DATA:if(m_axi_RVALID)begin
    kmem[load_word]<=m_axi_RDATA;load_word<=load_word+1;read_beats<=read_beats+1;burst_left<=burst_left-1;
    if(m_axi_RRESP!=0)begin error_code<=32'h100|m_axi_RRESP;state<=DONE;end
    else if(m_axi_RLAST)begin
     if(load_word+1==load_total)begin load_word<=0;rd_addr<=v_group_addr;state<=LP_REQ;end
     else begin rd_addr<=rd_addr+(burst_len<<3);state<=LK_REQ;end
    end
   end
   LP_REQ:if(m_axi_ARREADY)begin burst_len<=next_burst;burst_left<=next_burst;state<=LP_DATA;end
   LP_DATA:if(m_axi_RVALID)begin
    vmem[load_word]<=m_axi_RDATA;load_word<=load_word+1;read_beats<=read_beats+1;burst_left<=burst_left-1;
    if(m_axi_RRESP!=0)begin error_code<=32'h100|m_axi_RRESP;state<=DONE;end
    else if(m_axi_RLAST)begin
     if(load_word+1==load_total)state<=QK_INIT;
     else begin rd_addr<=rd_addr+(burst_len<<3);state<=LP_REQ;end
    end
   end
   QK_INIT:begin qi<=0;qj<=0;qkg<=0;qk_acc<=0;state<=QK_FETCH;end
   QK_FETCH:begin q_word_reg<=q_word;k_word_reg<=k_word;state<=QK_DOT;end
   QK_DOT:begin qk_dot_reg<=qk_dot;state<=QK_RUN;end
   QK_RUN:begin
    qk_terms<=qk_terms+8;
    if(qkg==3)begin
     score_mem[{qi,6'b000000}+qj]<=qk_acc+qk_dot_reg;qkg<=0;qk_acc<=0;
     if(qj+1<tokens)begin qj<=qj+1;state<=QK_FETCH;end
     else begin qj<=0;if(qi+1<tokens)begin qi<=qi+1;state<=QK_FETCH;end else state<=AV_INIT;end
    end else begin qk_acc<=qk_acc+qk_dot_reg;qkg<=qkg+1;state<=QK_FETCH;end
   end
   AV_INIT:begin ai<=0;ad<=0;aj<=0;av_acc<=0;out_pack<=0;state<=AV_FETCH;end
   AV_FETCH:begin
    av_score_reg<=av_score;av_v_reg<=av_v;state<=AV_RUN;
   end
   AV_RUN:begin
    av_terms<=av_terms+1;
    if(aj+1<tokens)begin av_acc<=av_sum;aj<=aj+1;state<=AV_FETCH;end
    else begin av_acc<=av_sum;aj<=0;state<=AV_FINISH;end
   end
   // Register the accumulator result and the LIF arithmetic separately.  This
   // removes the former RAM -> signed add -> LIF add/compare -> output path.
   AV_FINISH:begin lif_candidate_reg<=lif_candidate;state<=LIF_STORE;end
   LIF_STORE:begin
     lif_mem[{ai,5'b00000}+ad]<=lif_spike?16'sd0:lif_candidate_reg[15:0];
     out_pack[ad[2:0]*8+:8]<=lif_spike?8'h01:8'h00;
     av_acc<=0;aj<=0;
     if(ad[2:0]==7)begin
      wr_addr<=o_group_addr+({25'd0,ai}<<5)+(ad-7);
      wr_value<={(lif_spike?8'h01:8'h00),out_pack[55:0]};state<=WR_AW;
     end else begin ad<=ad+1;state<=AV_FETCH;end
   end
   WR_AW:if(m_axi_AWREADY)state<=WR_W;
   WR_W:if(m_axi_WREADY)state<=WR_B;
   WR_B:if(m_axi_BVALID)begin
    write_beats<=write_beats+1;
    if(m_axi_BRESP!=0)begin error_code<=32'h200|m_axi_BRESP;state<=DONE;end
    else state<=ADVANCE;
   end
   ADVANCE:begin
    out_pack<=0;
    if(ad+1<32)begin ad<=ad+1;state<=AV_FETCH;end
    else begin
     ad<=0;
     if(ai+1<tokens)begin ai<=ai+1;state<=AV_FETCH;end
     else if(group_id+1<groups)begin
      group_id<=group_id+1;ai<=0;load_word<=0;
      q_group_addr<=q_group_addr+group_bytes;k_group_addr<=k_group_addr+group_bytes;
      v_group_addr<=v_group_addr+group_bytes;o_group_addr<=o_group_addr+group_bytes;
      rd_addr<=q_group_addr+group_bytes;state<=LQ_REQ;
     end else state<=DONE;
    end
   end
   DONE:state<=IDLE;
   default:state<=IDLE;
  endcase
 end
end
endmodule
