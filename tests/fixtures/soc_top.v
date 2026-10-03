// soc_top.v - small deterministic RTL used for the Yosys -> netlist -> UPF
// design-aware validation case. Two switchable leaf blocks plus an always-on
// top, so power-domain elements, isolation controls and retention controls all
// have real design objects to resolve against.
module soc_top (
    input        clk,
    input        reset_n,
    input  [7:0] data_in,
    output [7:0] data_out,
    output       iso_en_cpu,
    output       ret_en_cpu
);

    wire [7:0] cpu_q;
    wire [7:0] sram_q;
    wire       busy;

    cpu_block  u_cpu (
        .clk   (clk),
        .rst_n (reset_n),
        .din   (data_in),
        .dout  (cpu_q)
    );

    sram_block u_sram (
        .clk   (clk),
        .din   (cpu_q),
        .dout  (sram_q)
    );

    assign data_out     = sram_q;
    assign iso_en_cpu   = busy;
    assign ret_en_cpu   = busy;

endmodule


module cpu_block (
    input        clk,
    input        rst_n,
    input  [7:0] din,
    output [7:0] dout
);
    reg [7:0] state;
    always @(posedge clk) begin
        if (!rst_n)
            state <= 8'b0;
        else
            state <= din + 1;
    end
    assign dout = state;
endmodule


module sram_block (
    input        clk,
    input  [7:0] din,
    output [7:0] dout
);
    reg [7:0] mem;
    always @(posedge clk)
        mem <= din;
    assign dout = mem;
endmodule