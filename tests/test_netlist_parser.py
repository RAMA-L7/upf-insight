"""Netlist parser tests - structural Verilog into DesignContext."""

from upf_insight.engine.design.design_context import DesignContext
from upf_insight.engine.design.netlist_parser import load_design, parse_verilog

CPU_V = "tests/fixtures/cpu.v"
MALFORMED_V = "tests/fixtures/malformed.v"


def test_parse_ports_and_buses():
    context, issues = parse_verilog(CPU_V)
    assert not issues
    assert "clk" in context.ports
    assert "reset_n" in context.ports
    assert "data_in[0]" in context.ports
    assert "data_in[7]" in context.ports
    assert "data_out[3]" in context.ports
    assert "io_pad" in context.ports
    dirs = context.port_directions
    assert dirs["clk"] == "input"
    assert dirs["data_in[2]"] == "input"
    assert dirs["data_out[3]"] == "output"
    assert dirs["io_pad"] == "inout"


def test_parse_instances_and_sequential_heuristic():
    context, issues = parse_verilog(CPU_V)
    assert not issues
    assert set(context.instances) == {"u_alu", "u_ff", "u_io"}
    assert context.instances["u_io"].module == "io_block"
    assert context.instances["u_ff"].module == "dffb"
    assert context.instances["u_ff"].sequential
    assert context.instances["u_alu"].sequential
    assert not context.instances["u_io"].sequential


def test_parse_hierarchy_children():
    context, _issues = parse_verilog(CPU_V)
    children = context.children
    assert sorted(children["cpu_top"]) == ["u_alu", "u_ff", "u_io"]
    assert set(children) == {"cpu_top"}


def test_parse_signals_connectivity():
    context, _issues = parse_verilog(CPU_V)
    alu_q = context.signals["alu_q"]
    assert alu_q["driver"] == "u_alu"
    assert "u_io" in alu_q["receivers"]
    busy = context.signals["busy"]
    assert busy["driver"] == ""
    assert busy["receivers"] == ["u_ff"]
    assert context.has_signal("data_in")
    assert context.has_signal("data_in[7]")


def test_malformed_verilog_does_not_raise():
    context, issues = parse_verilog(MALFORMED_V)
    assert isinstance(context, DesignContext)
    assert len(issues) >= 1


def test_missing_file_does_not_raise():
    context, issues = parse_verilog("tests/fixtures/does_not_exist.v")
    assert isinstance(context, DesignContext)
    assert issues and issues[0]["kind"] == "io"


def test_load_design_dispatch_json():
    import json

    path = None
    tmp = json.dumps({
        "instances": {"u1": {"module": "core", "sequential": True}},
        "ports": ["clk", "rst"],
        "signals": {},
        "pg_pins": {},
    })
    p = write_temp(tmp, ".json")
    path = p
    context = load_design(path)
    assert context.instances["u1"].sequential
    assert context.ports == ["clk", "rst"]


def test_load_design_dispatch_verilog():
    context = load_design(CPU_V)
    assert "u_ff" in context.instances
    assert "clk" in context.ports


def test_load_design_never_raises_on_garbage():
    p = write_temp("not json at all {{{", ".json")
    context = load_design(p)
    assert isinstance(context, DesignContext)


def write_temp(content: str, suffix: str) -> str:
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path
