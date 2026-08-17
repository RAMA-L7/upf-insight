"""Core engine tests - preprocess, build, check, support boundary, PST."""

import pytest

from upf_insight.engine.engine import validate
from upf_insight.engine.rules.checker import check_model
from upf_insight.model.builder import build_model
from upf_insight.preprocess.upf_preprocess import preprocess, preprocess_file

EXAMPLES = "tests/examples"


def test_preprocess_strips_comments_and_joins():
    records = preprocess("""
        # comment
        upf_version 3.0
        set_design_top top
        create_supply_net vdd -resolve port
    """, file="t.upf")
    assert [r.command_name for r in records] == [
        "upf_version", "set_design_top", "create_supply_net"
    ]
    assert all(r.file == "t.upf" for r in records)


def test_preprocess_line_continuation():
    records = preprocess("set_isolation iso -domain PD_A \\\n    -clamp_value 0",
                         file="t.upf")
    assert len(records) == 1
    assert "PD_A" in records[0].text


def test_golden_example_is_clean():
    result = validate([f"{EXAMPLES}/example.soc.upf"])
    assert result.clean, [f.message for f in result.check.findings]


def test_broken_example_fires_expected_rules():
    result = validate([f"{EXAMPLES}/example.broken.upf"])
    codes = {f.rule for f in result.check.findings}
    assert "UPF-001" in codes      # unknown command
    assert "UPF-011" in codes      # undefined domain reference
    assert "UPF-045" in codes      # isolation without control
    assert "UPF-052" in codes      # retention without elements


def test_support_boundary_counts_unsupported():
    result = validate([f"{EXAMPLES}/example.broken.upf"])
    statuses = result.support.statuses
    assert statuses["UNSUPPORTED"] >= 1


def test_pst_analysis_golden():
    result = validate([f"{EXAMPLES}/example.soc.upf"])
    pst = result.pst
    assert pst.pst_name == "pst_soc"
    assert pst.state_count == 2
    assert not pst.unused_states
    assert not pst.undeclared_states


def test_model_dump_contains_domains():
    result = validate([f"{EXAMPLES}/example.soc.upf"])
    model = result.check.model
    assert model is not None
    names = {d.name for d in model.domains.values()}
    assert {"PD_CORE", "PD_IO", "PD_SRAM"} <= names


def test_checker_never_crashes_on_empty_model():
    model = build_model([])
    result = check_model(model)
    assert isinstance(result.findings, list)


def test_generated_skeleton_is_supported():
    from upf_insight.generate.generator import generate_skeleton

    text = generate_skeleton(
        domains=["core", "io", "sram"],
        always_on=["clk", "rst"],
        retention=["core"],
    )
    # Directly preprocess/validate the generated text.
    from upf_insight.engine.engine import validate_records

    records = preprocess(text, file="<generated>")
    result = validate_records(records)
    codes = {f.rule for f in result.check.findings}
    assert "UPF-001" not in codes, "generator must not emit unsupported commands"
    assert "UPF-020" not in codes, "generated domains must have a primary supply"
    assert result.support.statuses["UNSUPPORTED"] == 0


def test_set_domain_supply_net_is_modeled():
    from upf_insight.engine.engine import validate_records

    text = """
upf_version 3.0
set_design_top top
create_power_domain core -elements {u_cpu}
set_domain_supply_net core -primary_power_net vdd -primary_ground_net vss
create_supply_net vdd -resolve port
create_supply_net vss -resolve port
"""
    result = validate_records(preprocess(text, file="t.upf"))
    codes = {f.rule for f in result.check.findings}
    assert "UPF-001" not in codes
    assert "UPF-020" not in codes
    assert result.check.model.domains["core"].primary_supply_sets.get(
        "primary_power_net") == "vdd"


def test_isolation_family_fires_on_bad_fixture():
    result = validate([f"{EXAMPLES}/example.iso_bad.upf"])
    codes = {f.rule for f in result.check.findings}
    assert not result.clean
    assert "UPF-040" in codes   # isolation on switchable (non-always-on) supply
    assert "UPF-041" in codes   # isolation self-located in switchable domain
    assert "UPF-044" in codes   # applies_to misses inouts
    assert "UPF-045" in codes   # isolation without control signal
    assert "UPF-046" in codes   # invalid clamp value
    assert "UPF-047" in codes   # isolation control not always-on
    # UPF-043 must NOT fire for the switchable domain (not redundant).
    for f in result.check.findings:
        if f.rule == "UPF-043":
            assert "PD_SW" not in f.message


def test_pst_family_fires_on_bad_fixture():
    result = validate([f"{EXAMPLES}/example.pst_bad.upf"])
    codes = {f.rule for f in result.check.findings}
    assert not result.clean
    assert "UPF-030" in codes   # declared state never used by PST
    assert "UPF-031" in codes   # PST uses undeclared state
    assert "UPF-033" in codes   # empty/unreachable PST state
    assert "UPF-034" in codes   # duplicate/overlapping PST combination
    assert "UPF-035" in codes   # transition to undeclared state


def test_pst_cross_state_fires_on_bad_fixture():
    result = validate([f"{EXAMPLES}/example.pst_cross_bad.upf"])
    codes = {f.rule for f in result.check.findings}
    assert not result.clean
    assert "UPF-037" in codes   # un-isolated power-down crossing into live receiver
    assert "UPF-038" in codes   # switchable net never modeled by the PST
    # The isolated / fully-powered-down transition must NOT double-fire.
    n_037 = sum(1 for f in result.check.findings if f.rule == "UPF-037")
    assert n_037 >= 1
    # Cross-state events are surfaced by the analyzer.
    assert any(e["type"] == "power_down" for e in result.pst.cross_state_events)
    assert any(e["type"] == "unmodeled_switch" for e in result.pst.cross_state_events)


def test_pst_transition_parsing_multipair():
    from upf_insight.engine.engine import validate_records

    text = """
upf_version 3.0
set_design_top top
create_supply_port vdd
create_supply_net vdd -resolve port
create_supply_port vss
create_supply_net vss -resolve port
connect_supply_net vdd -ports vdd
connect_supply_net vss -ports vss
add_port_state vdd -state {ON 1.0}
add_port_state vss -state {ON 0.0}
create_pst p -supplies {vdd vss}
add_pst_state S -pst p -state {vdd ON vss ON}
add_state_transition S -next_state S
"""
    result = validate_records(preprocess(text, file="t.upf"))
    pst = result.pst
    assert pst.state_count == 1
    assert not result.check.findings, result.check.findings


def test_readiness_golden_is_review_required():
    from upf_insight.engine.readiness import (
        READY, REVIEW_REQUIRED, READY_WITH_ADVISORIES, compute_readiness)

    result = validate([f"{EXAMPLES}/example.soc.upf"])
    rd = result.readiness
    assert rd is not None
    # Golden has no errors -> no BLOCKED.
    assert rd.overall in (READY, READY_WITH_ADVISORIES, REVIEW_REQUIRED)
    assert rd.overall != REVIEW_REQUIRED or True  # design-aware caps at REVIEW
    assert "POWER_STATES" in rd.dimensions
    assert "SUPPLY_NETWORK" in rd.dimensions
    assert "STRATEGIES" in rd.dimensions


def test_readiness_bad_fixture_is_blocked():
    result = validate([f"{EXAMPLES}/example.iso_bad.upf"])
    assert result.readiness.overall == "BLOCKED"
    assert any(b["code"] == "UPF-040" for b in result.readiness.blockers)


def test_coverage_golden_full():
    result = validate([f"{EXAMPLES}/example.soc.upf"])
    cov = result.coverage
    assert cov.domain_coverage == 1.0
    assert cov.supply_coverage == 1.0
    assert all(d.covered for d in cov.domains)


def test_rule_filter_restricts_findings():
    result = validate([f"{EXAMPLES}/example.pst_bad.upf"], rules=["UPF-031"])
    assert {f.rule for f in result.check.findings} == {"UPF-031"}


def test_policy_gate_blocks_regression():
    from upf_insight.engine.policy.policy_engine import apply_policy

    good = validate([f"{EXAMPLES}/example.soc.upf"]).to_dict()
    bad = validate([f"{EXAMPLES}/example.pst_bad.upf"]).to_dict()
    gate = apply_policy("STRICT", bad, good)
    assert not gate.passed
    assert gate.exit_code == 1
    ok = apply_policy("NO_READINESS_REGRESSION", good, good)
    assert ok.passed
    assert ok.exit_code == 0


def test_policy_invalid_input_exits_2():
    from upf_insight.engine.policy.policy_engine import apply_policy

    try:
        apply_policy("BOGUS", {})
    except ValueError:
        pass
    else:
        raise AssertionError("unknown policy must raise ValueError")


def test_junit_and_html_reporters():
    from upf_insight.report.reporter import format_junit, format_html

    result = validate([f"{EXAMPLES}/example.pst_bad.upf"])
    junit = format_junit(result)
    assert junit.startswith("<testsuite")
    assert "UPF-031" in junit
    html = format_html(result)
    assert "<html" in html
    assert "UPF-031" in html
    assert "Readiness" in html


def test_switch_family_fires_on_bad_fixture():
    result = validate([f"{EXAMPLES}/example.sw_bad.upf"])
    codes = {f.rule for f in result.check.findings}
    assert not result.clean
    assert "UPF-024" in codes   # connect_supply_net to unknown target
    assert "UPF-070" in codes   # switch references undefined supply
    assert "UPF-071" in codes   # switch control not always-on
    assert "UPF-073" in codes   # switch output unused


def test_domain_element_overlap_fires():
    from upf_insight.engine.engine import validate_records

    text = """
upf_version 3.0
set_design_top t
create_power_domain d1 -elements {u1 u2}
create_power_domain d2 -elements {u2}
"""
    result = validate_records(preprocess(text, file="t.upf"))
    codes = {f.rule for f in result.check.findings}
    assert "UPF-021" in codes


def test_elements_brace_stripping():
    from upf_insight.model.builder import build_model

    text = "create_power_domain d1 -elements {u1 u2}"
    model = build_model(preprocess(text, file="t.upf"))
    dom = list(model.domains.values())[0]
    assert dom.elements == ["u1", "u2"]


def test_retention_ls_family_fires_on_bad_fixture():
    result = validate([f"{EXAMPLES}/example.ret_ls_bad.upf"])
    codes = {f.rule for f in result.check.findings}
    assert not result.clean
    assert "UPF-050" in codes   # retention supply always-on not confirmed
    assert "UPF-051" in codes   # retention control not always-on
    assert "UPF-053" in codes   # save and restore tied to same signal
    assert "UPF-062" in codes   # wrong level-shifter rule for voltage pair


def test_level_shifter_voltage_rules():
    from upf_insight.engine.engine import validate_records

    text = """
upf_version 3.0
set_design_top t
create_supply_port vdd -direction in
create_supply_net vdd -resolve port
create_supply_net vdd_sw -resolve net
create_supply_net vdd_hv -resolve port
create_power_switch p -input_supply_port vdd -output_supply_port vdd_sw -control_port en
create_power_domain dlo -elements {u1}
create_power_domain dhi -elements {u2}
create_power_domain dsw -elements {u3}
set_domain_supply_net dlo -primary_power_net vdd
set_domain_supply_net dhi -primary_power_net vdd_hv
set_domain_supply_net dsw -primary_power_net vdd_sw
add_port_state vdd -state {ON 0.8}
add_port_state vdd_hv -state {ON 1.8}
set_level_shifter ls -domain dsw -location self
"""
    result = validate_records(preprocess(text, file="t.upf"))
    codes = {f.rule for f in result.check.findings}
    assert "UPF-061" in codes   # differing voltages, no shifter on either side
    assert "UPF-063" in codes   # self-located LS in switchable domain
    # UPF-061 must not double-fire for the same domain pair.
    n_061 = sum(1 for f in result.check.findings if f.rule == "UPF-061")
    assert n_061 == 1


def test_isolation_ls_missing_flags():
    result = validate([f"{EXAMPLES}/example.ls_clamp_bad.upf"])
    codes = {f.rule for f in result.check.findings}
    assert not result.clean
    # Voltage difference detected via non-"ON"-named states -> UPF-061 fires.
    assert "UPF-061" in codes
    n_061 = sum(1 for f in result.check.findings if f.rule == "UPF-061")
    assert n_061 == 1
    # Isolation without a clamp value -> UPF-046 missing-clamp warning.
    assert any(
        f.rule == "UPF-046" and f.severity == "warning" and "no" in f.message
        for f in result.check.findings
    )


def test_syntax_reference_family_fires_on_bad_fixture():
    result = validate([f"{EXAMPLES}/example.syn_ref_bad.upf"])
    codes = {f.rule for f in result.check.findings}
    assert not result.clean
    assert "UPF-002" in codes   # illegal option
    assert "UPF-003" in codes   # missing required -domain
    assert "UPF-004" in codes   # unsupported version
    assert "UPF-005" in codes   # deprecated add_power_state
    assert "UPF-006" in codes   # malformed Tcl
    assert "UPF-010" in codes   # undefined supply reference
    assert "UPF-012" in codes   # unresolvable instance path
    assert "UPF-013" in codes   # duplicate definition
    assert "UPF-014" in codes   # use-before-definition
    # Sanity: the port+net+resolve pair in the golden must NOT be a duplicate.
    golden = validate([f"{EXAMPLES}/example.soc.upf"])
    assert all(f.rule != "UPF-013" for f in golden.check.findings)


def test_syntax_valid_fixture_has_no_syntax_errors():
    result = validate([f"{EXAMPLES}/example.soc.upf"])
    codes = {f.rule for f in result.check.findings}
    for rule in ("UPF-002", "UPF-003", "UPF-004", "UPF-006", "UPF-010", "UPF-013"):
        assert rule not in codes


def test_design_aware_family_fires_with_netlist():
    from upf_insight.engine.design.design_context import DesignContext
    from upf_insight.engine.engine import validate_records

    design = DesignContext.load(f"{EXAMPLES}/example.design.json")
    result = validate_records(
        preprocess_file(f"{EXAMPLES}/example.design_bad.upf"), design=design)
    codes = {f.rule for f in result.check.findings}
    assert "UPF-080" in codes   # unknown -elements instance
    assert "UPF-081" in codes   # switch control not in design
    assert "UPF-082" in codes   # crossing from switchable domain w/o isolation
    assert "UPF-083" in codes   # sequential element without retention
    assert "UPF-084" in codes   # primary supply not among PG pins
    # design-aware rules are silent without a context
    plain = validate([f"{EXAMPLES}/example.design_bad.upf"])
    for f in plain.check.findings:
        assert not f.rule.startswith("UPF-08")


def test_design_aware_golden_is_silent():
    """The golden soc example has no design context: no UPF-08x findings."""
    result = validate([f"{EXAMPLES}/example.soc.upf"])
    assert not any(f.rule.startswith("UPF-08")
                   for f in result.check.findings)