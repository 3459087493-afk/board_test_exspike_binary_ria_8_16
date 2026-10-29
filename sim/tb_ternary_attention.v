`timescale 1ns/1ps
module tb_ternary_attention;
reg clk=0,rst_n=0;always #5 clk=~clk;
wire [31:0] awaddr,araddr;wire [7:0] awlen,arlen;wire [2:0] awsize,arsize;
wire [1:0] awburst,arburst;wire awlock,arlock;wire [3:0] awcache,arcache;
wire [2:0] awprot,arprot;wire [3:0] awqos,arqos;wire awvalid,arvalid;
reg awready=1,arready=1;wire [63:0] wdata;wire [7:0] wstrb;wire wlast,wvalid;
reg wready=1;reg [1:0] bresp=0;reg bvalid=0;wire bready;
reg [63:0] rdata=0;reg [1:0] rresp=0;reg rlast=0,rvalid=0;wire rready;
reg [7:0] c_awaddr=0,c_araddr=0;reg c_awvalid=0,c_wvalid=0,c_arvalid=0;
wire c_awready,c_wready,c_bvalid,c_arready,c_rvalid;reg c_bready=1,c_rready=1;
reg [31:0] c_wdata=0;reg [3:0] c_wstrb=4'hf;wire [1:0] c_bresp,c_rresp;wire [31:0] c_rdata;
reg [7:0] mem[0:8191];integer n,g,tok,dim,errors=0;
reg [31:0] read_addr;integer read_left;
reg [31:0] write_addr;

ternary_attention_top dut(
 .ap_clk(clk),.ap_rst_n(rst_n),
 .m_axi_AWADDR(awaddr),.m_axi_AWLEN(awlen),.m_axi_AWSIZE(awsize),.m_axi_AWBURST(awburst),
 .m_axi_AWLOCK(awlock),.m_axi_AWCACHE(awcache),.m_axi_AWPROT(awprot),.m_axi_AWQOS(awqos),
 .m_axi_AWVALID(awvalid),.m_axi_AWREADY(awready),.m_axi_WDATA(wdata),.m_axi_WSTRB(wstrb),
 .m_axi_WLAST(wlast),.m_axi_WVALID(wvalid),.m_axi_WREADY(wready),.m_axi_BRESP(bresp),
 .m_axi_BVALID(bvalid),.m_axi_BREADY(bready),
 .m_axi_ARADDR(araddr),.m_axi_ARLEN(arlen),.m_axi_ARSIZE(arsize),.m_axi_ARBURST(arburst),
 .m_axi_ARLOCK(arlock),.m_axi_ARCACHE(arcache),.m_axi_ARPROT(arprot),.m_axi_ARQOS(arqos),
 .m_axi_ARVALID(arvalid),.m_axi_ARREADY(arready),.m_axi_RDATA(rdata),.m_axi_RRESP(rresp),
 .m_axi_RLAST(rlast),.m_axi_RVALID(rvalid),.m_axi_RREADY(rready),
 .s_axi_control_AWADDR(c_awaddr),.s_axi_control_AWVALID(c_awvalid),.s_axi_control_AWREADY(c_awready),
 .s_axi_control_WDATA(c_wdata),.s_axi_control_WSTRB(c_wstrb),.s_axi_control_WVALID(c_wvalid),
 .s_axi_control_WREADY(c_wready),.s_axi_control_BRESP(c_bresp),.s_axi_control_BVALID(c_bvalid),
 .s_axi_control_BREADY(c_bready),.s_axi_control_ARADDR(c_araddr),.s_axi_control_ARVALID(c_arvalid),
 .s_axi_control_ARREADY(c_arready),.s_axi_control_RDATA(c_rdata),.s_axi_control_RRESP(c_rresp),
 .s_axi_control_RVALID(c_rvalid),.s_axi_control_RREADY(c_rready));

task ctrl_write;input [7:0] addr;input [31:0] value;begin
 @(posedge clk);c_awaddr<=addr;c_wdata<=value;c_awvalid<=1;c_wvalid<=1;
 while(!(c_awready&&c_wready))@(posedge clk);
 @(posedge clk);c_awvalid<=0;c_wvalid<=0;
 while(!c_bvalid)@(posedge clk);
end endtask

always @(posedge clk)begin
 if(arvalid&&arready&&!rvalid)begin read_addr<=araddr;read_left<=arlen+1;rvalid<=1;end
 else if(rvalid&&rready)begin
  if(read_left==1)begin rvalid<=0;rlast<=0;end
  else begin read_addr<=read_addr+8;read_left<=read_left-1;end
 end
 if((arvalid&&arready&&!rvalid)||(rvalid&&rready&&read_left>1))begin
  rdata<={mem[((arvalid&&arready&&!rvalid)?araddr:read_addr+8)+7],
          mem[((arvalid&&arready&&!rvalid)?araddr:read_addr+8)+6],
          mem[((arvalid&&arready&&!rvalid)?araddr:read_addr+8)+5],
          mem[((arvalid&&arready&&!rvalid)?araddr:read_addr+8)+4],
          mem[((arvalid&&arready&&!rvalid)?araddr:read_addr+8)+3],
          mem[((arvalid&&arready&&!rvalid)?araddr:read_addr+8)+2],
          mem[((arvalid&&arready&&!rvalid)?araddr:read_addr+8)+1],
          mem[((arvalid&&arready&&!rvalid)?araddr:read_addr+8)]};
  rlast<=((arvalid&&arready&&!rvalid)?(arlen==0):(read_left==2));
 end
 if(awvalid&&awready)write_addr<=awaddr;
 if(wvalid&&wready)begin
  for(n=0;n<8;n=n+1)if(wstrb[n])mem[write_addr+n]<=wdata[n*8+:8];
  bvalid<=1;
 end else if(bvalid&&bready)bvalid<=0;
end

initial begin
 for(n=0;n<8192;n=n+1)mem[n]=0;
 // Eight non-identical tokens catch narrow-shift address aliasing. K and V
 // are +1; Q alternates +1/-1 by token, so even tokens spike and odd do not.
 for(g=0;g<4;g=g+1)for(tok=0;tok<8;tok=tok+1)for(dim=0;dim<32;dim=dim+1)begin
  mem[16'h0000+g*256+tok*32+dim]=(tok%2==0)?8'h01:8'hff;
  mem[16'h0400+g*256+tok*32+dim]=8'h01;
  mem[16'h0800+g*256+tok*32+dim]=8'h01;
 end
 repeat(8)@(posedge clk);rst_n=1;
 ctrl_write(8'h10,32'h00000000);ctrl_write(8'h1c,32'h00000400);
 ctrl_write(8'h28,32'h00000800);ctrl_write(8'h34,32'h00000c00);
 ctrl_write(8'h40,4);ctrl_write(8'h48,8);ctrl_write(8'h50,32);
 ctrl_write(8'h00,1);
 wait(dut.state==20);@(posedge clk);
 for(g=0;g<4;g=g+1)for(n=0;n<256;n=n+1)begin
  if(mem[16'h0c00+g*256+n]!==(((n/32)%2==0)?8'h01:8'h00))begin
   $display("MISMATCH g=%0d n=%0d got=%02x",g,n,mem[16'h0c00+g*64+n]);errors=errors+1;
  end
 end
 if(dut.qk_terms!==64'd8192)begin $display("QK_COUNT_BAD %0d",dut.qk_terms);errors=errors+1;end
 if(dut.av_terms!==64'd8192)begin $display("AV_COUNT_BAD %0d",dut.av_terms);errors=errors+1;end
 if(errors==0)$display("TERNARY_ATTENTION_RTL_PASS signed_nonidentical_tokens_temporal_state counters");
 else $display("TERNARY_ATTENTION_RTL_FAIL errors=%0d",errors);
 $finish;
end
initial begin #2000000;$display("TIMEOUT state=%0d",dut.state);$finish;end
endmodule
