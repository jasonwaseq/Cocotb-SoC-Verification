module uart_axi
  #(parameter example_p = 0)
  (input [0:0] clk_i // 12 MHz clock
  ,input [0:0] reset_i

  ,input [0:0] rx_serial_i
  ,output [0:0] tx_serial_o

  ,input [3:0] buttons_i // Read these
  ,output [5:1] led_o // Turn these on/off
   );

  wire        dbg_awvalid;
  wire [31:0] dbg_awaddr;
  wire [3:0]  dbg_awid;
  wire [7:0]  dbg_awlen;
  wire [1:0]  dbg_awburst;
  wire        dbg_awready;
  
  wire        dbg_wvalid;
  wire [31:0] dbg_wdata;
  wire [3:0]  dbg_wstrb;
  wire        dbg_wlast;
  wire        dbg_wready;
  
  wire        dbg_bvalid;
  wire [1:0]  dbg_bresp;
  wire [3:0]  dbg_bid;
  wire        dbg_bready;
  
  wire        dbg_arvalid;
  wire [31:0] dbg_araddr;
  wire [3:0]  dbg_arid;
  wire [7:0]  dbg_arlen;
  wire [1:0]  dbg_arburst;
  wire        dbg_arready;
  
  wire        dbg_rvalid;
  wire [31:0] dbg_rdata;
  wire [1:0]  dbg_rresp;
  wire [3:0]  dbg_rid;
  wire        dbg_rlast;
  wire        dbg_rready;

  wire        ram_awready;
  wire        ram_wready;
  wire        ram_bvalid;
  wire [1:0]  ram_bresp;
  wire [3:0]  ram_bid;
  wire        ram_arready;
  wire        ram_rvalid;
  wire [31:0] ram_rdata;
  wire [1:0]  ram_rresp;
  wire [3:0]  ram_rid;
  wire        ram_rlast;

  wire [31:0] gpio_inputs;
  wire [31:0] gpio_outputs;

  // check if accessing RAM (0x0000_0000 - 0x0000_0FFF)
  wire accessing_ram = (dbg_awaddr[31:12] == 20'h0) || (dbg_araddr[31:12] == 20'h0);

  assign gpio_inputs = {28'b0, buttons_i};
  assign led_o = gpio_outputs[4:0];  
  
  assign dbg_awready = accessing_ram ? ram_awready : 1'b1;
  assign dbg_wready = accessing_ram ? ram_wready : 1'b1;
  assign dbg_bvalid = accessing_ram ? ram_bvalid : 1'b0;
  assign dbg_bresp = accessing_ram ? ram_bresp : 2'b00;
  assign dbg_bid = accessing_ram ? ram_bid : 4'h0;
  
  assign dbg_arready = accessing_ram ? ram_arready : 1'b1;
  assign dbg_rvalid = accessing_ram ? ram_rvalid : 1'b0;
  assign dbg_rdata = accessing_ram ? ram_rdata : 32'h0;
  assign dbg_rresp = accessing_ram ? ram_rresp : 2'b00;
  assign dbg_rid = accessing_ram ? ram_rid : 4'h0;
  assign dbg_rlast = accessing_ram ? ram_rlast : 1'b1;

  dbg_bridge #(
    .CLK_FREQ(12000000),
    .UART_SPEED(115200),
    .AXI_ID(4'd0),
    .GPIO_ADDRESS(32'hf0000000),
    .STS_ADDRESS(32'hf0000004)
  )
  u_dbg_bridge (
    .clk_i(clk_i),
    .rst_i(reset_i),
    
    // UART interface
    .uart_rxd_i(rx_serial_i),
    .uart_txd_o(tx_serial_o),
    
    // AXI Write Address 
    .mem_awvalid_o(dbg_awvalid),
    .mem_awaddr_o(dbg_awaddr),
    .mem_awid_o(dbg_awid),
    .mem_awlen_o(dbg_awlen),
    .mem_awburst_o(dbg_awburst),
    .mem_awready_i(dbg_awready),
    
    // AXI Write Data
    .mem_wvalid_o(dbg_wvalid),
    .mem_wdata_o(dbg_wdata),
    .mem_wstrb_o(dbg_wstrb),
    .mem_wlast_o(dbg_wlast),
    .mem_wready_i(dbg_wready),
    
    // AXI Write Response
    .mem_bvalid_i(dbg_bvalid),
    .mem_bresp_i(dbg_bresp),
    .mem_bid_i(dbg_bid),
    .mem_bready_o(dbg_bready),
    
    // AXI Read Address 
    .mem_arvalid_o(dbg_arvalid),
    .mem_araddr_o(dbg_araddr),
    .mem_arid_o(dbg_arid),
    .mem_arlen_o(dbg_arlen),
    .mem_arburst_o(dbg_arburst),
    .mem_arready_i(dbg_arready),
    
    // AXI Read Data 
    .mem_rvalid_i(dbg_rvalid),
    .mem_rdata_i(dbg_rdata),
    .mem_rresp_i(dbg_rresp),
    .mem_rid_i(dbg_rid),
    .mem_rlast_i(dbg_rlast),
    .mem_rready_o(dbg_rready),
    
    // GPIO
    .gpio_inputs_i(gpio_inputs),
    .gpio_outputs_o(gpio_outputs)
  );

  // AXI RAM - 4KB memory at address 0x0000_0000
  axi_ram #(
    .DATA_WIDTH(32),
    .ADDR_WIDTH(12),  // 2^12 = 4KB
    .STRB_WIDTH(4),
    .ID_WIDTH(4),
    .PIPELINE_OUTPUT(0)
  )
  u_axi_ram (
    .clk(clk_i),
    .rst(reset_i),
    
    // AXI Write Address
    .s_axi_awid(dbg_awid),
    .s_axi_awaddr(dbg_awaddr[11:0]),
    .s_axi_awlen(dbg_awlen),
    .s_axi_awsize(3'b010),
    .s_axi_awburst(dbg_awburst),
    .s_axi_awlock(1'b0),
    .s_axi_awcache(4'b0000),
    .s_axi_awprot(3'b000),
    .s_axi_awvalid(dbg_awvalid & accessing_ram),
    .s_axi_awready(ram_awready),
    
    // AXI Write Data
    .s_axi_wdata(dbg_wdata),
    .s_axi_wstrb(dbg_wstrb),
    .s_axi_wlast(dbg_wlast),
    .s_axi_wvalid(dbg_wvalid & accessing_ram),
    .s_axi_wready(ram_wready),
    
    // AXI Write Response 
    .s_axi_bid(ram_bid),
    .s_axi_bresp(ram_bresp),
    .s_axi_bvalid(ram_bvalid),
    .s_axi_bready(dbg_bready),
    
    // AXI Read Address
    .s_axi_arid(dbg_arid),
    .s_axi_araddr(dbg_araddr[11:0]),
    .s_axi_arlen(dbg_arlen),
    .s_axi_arsize(3'b010), 
    .s_axi_arburst(dbg_arburst),
    .s_axi_arlock(1'b0),
    .s_axi_arcache(4'b0000),
    .s_axi_arprot(3'b000),
    .s_axi_arvalid(dbg_arvalid & accessing_ram),
    .s_axi_arready(ram_arready),
    
    // AXI Read Data 
    .s_axi_rid(ram_rid),
    .s_axi_rdata(ram_rdata),
    .s_axi_rresp(ram_rresp),
    .s_axi_rlast(ram_rlast),
    .s_axi_rvalid(ram_rvalid),
    .s_axi_rready(dbg_rready)
  );

endmodule