// cpu.v - small structural CPU-ish top for netlist parser tests.
module cpu_top (
    input        clk,
    input        reset_n,
    input  [7:0] data_in,
    output [7:0] data_out,
    output       iso_en,
    inout        io_pad
);
    wire [7:0] alu_q;
    wire       busy;

    alu_unit u_alu (
        .clk   (clk),
        .rst_n (reset_n),
        .din   (data_in),
        .dout  (alu_q)
    );

    dffb u_ff (
        .clk (clk),
        .d   (busy),
        .q   (iso_en)
    );

    io_block u_io (
        .pad  (io_pad),
        .core (alu_q),
        .clk  (clk)
    );

    assign data_out = alu_q;

endmodule

module alu_unit (
    input clk,
    input rst_n,
    input [7:0] din,
    output reg [7:0] dout
);
    always @(posedge clk) begin
        if (!rst_n) begin
            dout <= 8'b0;
        end else begin
            dout <= din + 1;
        end
    end
endmodule

module dffb (
    input clk,
    input d,
    output q
);
    reg qi;
    always @(posedge clk) q <= qi;
endmodule

module io_block (
    inout pad,
    input [7:0] core,
    input clk
);
    assign pad = core[0];
endmodule
