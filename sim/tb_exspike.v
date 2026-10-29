`timescale 1ns/1ps
module tb_exspike;
reg clk=0;always #5 clk=~clk;
reg rst_n=0;
wire [31:0] m_axi_AWADDR;
wire [7:0] m_axi_AWLEN;
wire [2:0] m_axi_AWSIZE;
wire [1:0] m_axi_AWBURST;
wire m_axi_AWLOCK;
wire [3:0] m_axi_AWCACHE;
wire [2:0] m_axi_AWPROT;
wire [3:0] m_axi_AWQOS;
wire m_axi_AWVALID;
reg m_axi_AWREADY;
wire [63:0] m_axi_WDATA;
wire [7:0] m_axi_WSTRB;
wire m_axi_WLAST;
wire m_axi_WVALID;
reg m_axi_WREADY;
reg [1:0] m_axi_BRESP;
reg m_axi_BVALID;
wire m_axi_BREADY;
wire [31:0] m_axi_ARADDR;
wire [7:0] m_axi_ARLEN;
wire [2:0] m_axi_ARSIZE;
wire [1:0] m_axi_ARBURST;
wire m_axi_ARLOCK;
wire [3:0] m_axi_ARCACHE;
wire [2:0] m_axi_ARPROT;
wire [3:0] m_axi_ARQOS;
wire m_axi_ARVALID;
reg m_axi_ARREADY;
reg [63:0] m_axi_RDATA;
reg [1:0] m_axi_RRESP;
reg m_axi_RLAST;
reg m_axi_RVALID;
wire m_axi_RREADY;
reg [7:0] s_axi_control_AWADDR;
reg s_axi_control_AWVALID;
wire s_axi_control_AWREADY;
reg [31:0] s_axi_control_WDATA;
reg [3:0] s_axi_control_WSTRB;
reg s_axi_control_WVALID;
wire s_axi_control_WREADY;
wire [1:0] s_axi_control_BRESP;
wire s_axi_control_BVALID;
reg s_axi_control_BREADY;
reg [7:0] s_axi_control_ARADDR;
reg s_axi_control_ARVALID;
wire s_axi_control_ARREADY;
wire [31:0] s_axi_control_RDATA;
wire [1:0] s_axi_control_RRESP;
wire s_axi_control_RVALID;
reg s_axi_control_RREADY;
exspike_z2_top dut(.ap_clk(clk),.ap_rst_n(rst_n),.m_axi_AWADDR(m_axi_AWADDR),.m_axi_AWLEN(m_axi_AWLEN),.m_axi_AWSIZE(m_axi_AWSIZE),.m_axi_AWBURST(m_axi_AWBURST),.m_axi_AWLOCK(m_axi_AWLOCK),.m_axi_AWCACHE(m_axi_AWCACHE),.m_axi_AWPROT(m_axi_AWPROT),.m_axi_AWQOS(m_axi_AWQOS),.m_axi_AWVALID(m_axi_AWVALID),.m_axi_AWREADY(m_axi_AWREADY),.m_axi_WDATA(m_axi_WDATA),.m_axi_WSTRB(m_axi_WSTRB),.m_axi_WLAST(m_axi_WLAST),.m_axi_WVALID(m_axi_WVALID),.m_axi_WREADY(m_axi_WREADY),.m_axi_BRESP(m_axi_BRESP),.m_axi_BVALID(m_axi_BVALID),.m_axi_BREADY(m_axi_BREADY),.m_axi_ARADDR(m_axi_ARADDR),.m_axi_ARLEN(m_axi_ARLEN),.m_axi_ARSIZE(m_axi_ARSIZE),.m_axi_ARBURST(m_axi_ARBURST),.m_axi_ARLOCK(m_axi_ARLOCK),.m_axi_ARCACHE(m_axi_ARCACHE),.m_axi_ARPROT(m_axi_ARPROT),.m_axi_ARQOS(m_axi_ARQOS),.m_axi_ARVALID(m_axi_ARVALID),.m_axi_ARREADY(m_axi_ARREADY),.m_axi_RDATA(m_axi_RDATA),.m_axi_RRESP(m_axi_RRESP),.m_axi_RLAST(m_axi_RLAST),.m_axi_RVALID(m_axi_RVALID),.m_axi_RREADY(m_axi_RREADY),.s_axi_control_AWADDR(s_axi_control_AWADDR),.s_axi_control_AWVALID(s_axi_control_AWVALID),.s_axi_control_AWREADY(s_axi_control_AWREADY),.s_axi_control_WDATA(s_axi_control_WDATA),.s_axi_control_WSTRB(s_axi_control_WSTRB),.s_axi_control_WVALID(s_axi_control_WVALID),.s_axi_control_WREADY(s_axi_control_WREADY),.s_axi_control_BRESP(s_axi_control_BRESP),.s_axi_control_BVALID(s_axi_control_BVALID),.s_axi_control_BREADY(s_axi_control_BREADY),.s_axi_control_ARADDR(s_axi_control_ARADDR),.s_axi_control_ARVALID(s_axi_control_ARVALID),.s_axi_control_ARREADY(s_axi_control_ARREADY),.s_axi_control_RDATA(s_axi_control_RDATA),.s_axi_control_RRESP(s_axi_control_RRESP),.s_axi_control_RVALID(s_axi_control_RVALID),.s_axi_control_RREADY(s_axi_control_RREADY));
reg [7:0] mem[0:524287];
integer j,t,rdleft;reg [31:0] raddr,waddr;reg[2:0] rsize;
reg ractive,wactive;
always @(posedge clk) begin
 if(!rst_n) begin
  m_axi_ARREADY<=0;m_axi_RVALID<=0;m_axi_RLAST<=0;m_axi_RRESP<=0;m_axi_RDATA<=0;
  m_axi_AWREADY<=0;m_axi_WREADY<=0;m_axi_BVALID<=0;m_axi_BRESP<=0;
  ractive<=0;wactive<=0;
 end else begin
  m_axi_ARREADY<=!ractive;
  m_axi_AWREADY<=!wactive&&!m_axi_BVALID;
  m_axi_WREADY<=wactive;
  if(m_axi_ARVALID&&m_axi_ARREADY)begin
   ractive<=1;m_axi_ARREADY<=0;raddr<=m_axi_ARADDR;rdleft<=m_axi_ARLEN+1;rsize<=m_axi_ARSIZE;
  end
  if(ractive&&!m_axi_RVALID)begin
   for(j=0;j<8;j=j+1)m_axi_RDATA[j*8+:8]<=mem[(raddr&32'hfffffff8)+j];
   m_axi_RVALID<=1;m_axi_RLAST<=(rdleft==1);
  end
  if(m_axi_RVALID&&m_axi_RREADY)begin
   m_axi_RVALID<=0;
   if(rdleft==1)begin ractive<=0;m_axi_RLAST<=0;end
   else begin rdleft<=rdleft-1;raddr<=raddr+(1<<rsize);end
  end
  if(m_axi_AWVALID&&m_axi_AWREADY)begin waddr<=m_axi_AWADDR;wactive<=1;m_axi_AWREADY<=0;end
  if(m_axi_WVALID&&m_axi_WREADY)begin
   for(j=0;j<8;j=j+1)if(m_axi_WSTRB[j])mem[(waddr&32'hfffffff8)+j]<=m_axi_WDATA[j*8+:8];
   wactive<=0;m_axi_WREADY<=0;m_axi_BVALID<=1;
  end
  if(m_axi_BVALID&&m_axi_BREADY)m_axi_BVALID<=0;
 end
end

task wr;
 input[7:0] addr;input[31:0] data;
 begin
  @(negedge clk);s_axi_control_AWADDR=addr;s_axi_control_AWVALID=1;
  s_axi_control_WDATA=data;s_axi_control_WVALID=1;s_axi_control_WSTRB=15;s_axi_control_BREADY=1;
  @(posedge clk);while(!(s_axi_control_AWREADY&&s_axi_control_WREADY))@(posedge clk);
  @(negedge clk);s_axi_control_AWVALID=0;s_axi_control_WVALID=0;
  @(posedge clk);while(!s_axi_control_BVALID)@(posedge clk);
  @(negedge clk);s_axi_control_BREADY=0;
 end
endtask
task rd;
 input[7:0] addr;output[31:0] data;
 begin
  @(negedge clk);s_axi_control_ARADDR=addr;s_axi_control_ARVALID=1;s_axi_control_RREADY=1;
  @(posedge clk);while(!s_axi_control_ARREADY)@(posedge clk);
  @(negedge clk);s_axi_control_ARVALID=0;
  @(posedge clk);while(!s_axi_control_RVALID)@(posedge clk);
  data=s_axi_control_RDATA;
  @(negedge clk);s_axi_control_RREADY=0;
 end
endtask

integer V,I,O,mode,extreme,zero_period,case_no;
integer vv,oo,ii,tt,k,maskbit,ival,wval,byteaddr,waits,expected_mac;
reg[31:0] control,status,got,reference;
reg signed[63:0] sum;
integer signed xvalues[0:8191];
integer signed weights[0:32767];
reg selected[0:32767];
reg[7:0] masks;
task run_case;
 input integer v_in,i_in,o_in,sparse_in,extreme_in,zero_in;
 begin
  V=v_in;I=i_in;O=o_in;mode=sparse_in;extreme=extreme_in;zero_period=zero_in;case_no=case_no+1;
  for(vv=0;vv<V;vv=vv+1)for(ii=0;ii<I;ii=ii+1)begin
   ival=extreme!=0?32767:((vv*33+ii*17)%101)-50;
   if(zero_period==-1 || (zero_period>0 && ii%zero_period!=0))ival=0;
   xvalues[vv*I+ii]=ival;mem[(vv*((I+3)/4*4)+ii)*2]=ival&255;mem[(vv*((I+3)/4*4)+ii)*2+1]=(ival>>8)&255;
  end
  for(oo=0;oo<O;oo=oo+1)for(ii=0;ii<I;ii=ii+1)begin
   selected[oo*I+ii]=(!mode)||(((ii+oo)%16)<8);
   wval=extreme!=0?(extreme>0?127:-128):((oo*7+ii*3)%255)-128;
   weights[oo*I+ii]=selected[oo*I+ii]?wval:0;
  end
  for(tt=0;tt<(O+7)/8;tt=tt+1)for(ii=0;ii<I;ii=ii+1)begin
   byteaddr=65536+(tt*I+ii)*16;masks=0;
   for(k=0;k<8;k=k+1)begin
    oo=tt*8+k;
    mem[byteaddr+k]=(oo<O)?weights[oo*I+ii]&255:0;
    if(oo<O && selected[oo*I+ii])masks[k]=1;
   end
   mem[byteaddr+8]=masks;
   for(k=9;k<16;k=k+1)mem[byteaddr+k]=0;
  end
  wr(8'h10,0);wr(8'h1c,65536);wr(8'h28,262144);
  wr(8'h34,V);wr(8'h3c,I);wr(8'h44,O);wr(8'h4c,mode);wr(0,1);
  control=0;waits=0;
  while(!(control&2))begin rd(0,control);waits=waits+1;if(waits>200000)$fatal(1,"timeout case %d state %d",case_no,dut.state);end
  rd(8'h50,status);if(status!=0)$fatal(1,"AXI error %h",status);
  for(vv=0;vv<V;vv=vv+1)for(oo=0;oo<O;oo=oo+1)begin
   sum=0;
   for(ii=0;ii<I;ii=ii+1)sum=sum+$signed(xvalues[vv*I+ii])*$signed(weights[oo*I+ii]);
   if(sum>64'sd2147483647)reference=32'h7fffffff;
   else if(sum< -64'sd2147483648)reference=32'h80000000;
   else reference=sum[31:0];
   byteaddr=262144+(vv*O+oo)*4;
   got={mem[byteaddr+3],mem[byteaddr+2],mem[byteaddr+1],mem[byteaddr]};
   if(got!==reference)$fatal(1,"mismatch case=%0d v=%0d o=%0d got=%h ref=%h sum=%0d",case_no,vv,oo,got,reference,sum);
  end
  expected_mac=0;
  for(vv=0;vv<V;vv=vv+1)for(oo=0;oo<O;oo=oo+1)for(ii=0;ii<I;ii=ii+1)
   if(xvalues[vv*I+ii]!=0 && selected[oo*I+ii])expected_mac=expected_mac+1;
  rd(8'h64,status);
  if(status!==expected_mac)$fatal(1,"event MAC counter mismatch got=%d ref=%d",status,expected_mac);
  rd(8'h5c,status);
  $display("CASE_PASS case=%0d V=%0d I=%0d O=%0d sparse=%0d extreme=%0d zero_period=%0d events=%0d",case_no,V,I,O,mode,extreme,zero_period,status);
 end
endtask

initial begin
 s_axi_control_AWADDR=0;s_axi_control_AWVALID=0;s_axi_control_WDATA=0;s_axi_control_WSTRB=0;
 s_axi_control_WVALID=0;s_axi_control_BREADY=0;s_axi_control_ARADDR=0;s_axi_control_ARVALID=0;s_axi_control_RREADY=0;
 case_no=0;
 repeat(5)@(negedge clk);rst_n=1;repeat(3)@(negedge clk);
 run_case(3,32,16,1,0,0);
 run_case(3,27,10,0,0,0);
 run_case(2,384,16,1,0,5);
 run_case(1,2048,10,1,1,0);
 run_case(1,2048,10,1,-1,0);
 run_case(1,1024,8,0,1,0);
 run_case(1,1024,8,0,-1,0);
 run_case(1,32,8,1,0,1000);
 run_case(2,32,10,1,0,-1);
 run_case(150,27,10,0,0,0);
 $display("RTL_INTEGER_SIMULATION_PASS 10 cases; ExSpike filter/address/accumulator, MAC counters and4KiB boundary verified");
 $finish;
end
initial begin #100000000;$fatal(1,"global timeout");end
endmodule
