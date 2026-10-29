module exspike_tile_ram #(parameter WIDTH=64, ADDR_BITS=12)(
 input wire clk,we,re,
 input wire [ADDR_BITS-1:0] waddr,raddr,
 input wire [WIDTH-1:0] wdata,
 output reg [WIDTH-1:0] rdata
);
 (* ram_style="block" *) reg [WIDTH-1:0] memory[0:(1<<ADDR_BITS)-1];
 always @(posedge clk)begin
  if(we)memory[waddr]<=wdata;
  if(re)rdata<=memory[raddr];
 end
endmodule
