"""Design coverage tests - netlist-aware port coverage analysis."""

from upf_insight.engine.design.design_coverage import analyze_design_coverage
from upf_insight.engine.design.netlist_parser import parse_verilog
from upf_insight.model.builder import build_model
from upf_insight.model.power_model import PowerIntentModel
from upf_insight.preprocess.upf_preprocess import preprocess

CPU_V = "tests/fixtures/cpu.v"


def _model(upf_text: str) -> PowerIntentModel:
    return build_model(preprocess(upf_text, file="t.upf"))


def _soc_model() -> PowerIntentModel:
    return _model("""
        upf_version 3.0
        set_design_top cpu_top
        create_power_domain PD_TOP -include_scope
        create_power_domain PD_CPU -elements {u_alu}
        set_port_attributes clk -attribute {always_on true}
        set_port_attributes reset_n, iso_en -attribute {always_on true}
        set_port_attributes data_in[0] -attribute {always_on true}
    """)


def test_insufficient_context_path():
    model = _soc_model()
    result = analyze_design_coverage(model, None)
    assert result.status == "INSUFFICIENT_CONTEXT"
    assert "insufficient_context" in result.notes
    d = result.to_dict()
    assert d["coverage_is_not_correctness"] is True
    assert sum(d["input_ports"].values()) == 0


def test_buckets_constrained_and_unconstrained():
    model = _soc_model()
    context, issues = parse_verilog(CPU_V)
    assert not issues
    result = analyze_design_coverage(model, context)
    inp = result.input_ports
    out = result.output_ports
    assert inp["CONSTRAINED"] >= 2          # clk, reset_n (+ data_in[0])
    assert inp["UNCONSTRAINED"] >= 1
    assert out["CONSTRAINED"] >= 1          # iso_en
    assert "data_in[7]" in result.unconstrained_inputs
    assert "clk" not in result.unconstrained_inputs
    assert "iso_en" not in result.unconstrained_outputs
    assert "data_out[7]" in result.unconstrained_outputs
    assert result.ratios["input_port_coverage"] > 0.0
    assert result.ratios["output_port_coverage"] < 1.0


def test_partial_via_domain_binding():
    model = _soc_model()
    context, _issues = parse_verilog(CPU_V)
    result = analyze_design_coverage(model, context)
    by_port = {p.port: p for p in result.ports}
    assert by_port["reset_n"].status == "CONSTRAINED"
    assert "set_port_attributes" in by_port["reset_n"].evidence


def test_not_applicable_for_upf_ports_missing_from_design():
    model = _soc_model()
    context, _issues = parse_verilog(CPU_V)
    result = analyze_design_coverage(model, context)
    statuses = {p.port: p.status for p in result.ports}
    assert all(statuses[p] != "NOT_APPLICABLE" for p in statuses if p in context.ports)


def test_to_dict_is_deterministic():
    model = _soc_model()
    context, _issues = parse_verilog(CPU_V)
    r1 = analyze_design_coverage(model, context).to_dict()
    r2 = analyze_design_coverage(model, context).to_dict()
    assert r1 == r2
    assert r1["coverage_is_not_correctness"] is True
    assert r1["domain_count"] == len(model.domains)
    ports = [p["port"] for p in r1["ports"]]
    assert ports == sorted(ports)
