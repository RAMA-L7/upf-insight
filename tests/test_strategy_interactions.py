"""Tests for cross-strategy interaction analysis (UPF-085 / UPF-086)."""

from __future__ import annotations

from upf_insight.engine.analysis.strategy_interactions import (
    CODE_CONFLICT,
    CODE_DUPLICATE,
    CONFLICT,
    DUPLICATE,
    OVERRIDE,
    analyze_strategy_interactions,
)
from upf_insight.model.builder import build_model
from upf_insight.preprocess.upf_preprocess import preprocess


def build(text: str):
    return build_model(preprocess(text, file="t.upf"))


def kinds_by_code(result):
    return {(i.kind, i.code) for i in result.interactions}


def test_exact_duplicate_isolation_is_upf085_error():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        set_isolation iso1 -domain PD_A -elements {u1 u2} -clamp_value 0
        set_isolation iso2 -domain PD_A -elements {u2 u1} -clamp_value 0
        """
    )
    result = analyze_strategy_interactions(model)
    assert (DUPLICATE, CODE_DUPLICATE) in kinds_by_code(result)
    dup = next(i for i in result.interactions if i.kind == DUPLICATE)
    assert dup.finding is not None
    assert dup.finding.severity == "error"
    assert dup.subject == "isolation:PD_A"
    assert dup.evidence["earlier_line"] < dup.evidence["later_line"]


def test_differing_parameter_isolation_is_upf086_override():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        set_isolation iso1 -domain PD_A -elements {u1} -clamp_value 0
        set_isolation iso2 -domain PD_A -elements {u1} -clamp_value 1
        """
    )
    result = analyze_strategy_interactions(model)
    assert (OVERRIDE, CODE_CONFLICT) in kinds_by_code(result)
    ov = next(i for i in result.interactions if i.kind == OVERRIDE)
    assert ov.finding is not None
    assert ov.finding.severity == "warning"
    assert "clamp_value" in ov.evidence["differing_parameters"]
    assert (
        ov.evidence["differing_parameters"]["clamp_value"]["earlier"] == "0"
    )
    assert ov.evidence["differing_parameters"]["clamp_value"]["later"] == "1"


def test_overlapping_power_switch_outputs_conflict():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        create_supply_port vdd -direction in
        create_supply_net vdd -resolve port
        create_power_switch sw_a -input_supply_port vdd -output_supply_port vdd_sw
        create_power_switch sw_b -input_supply_port vdd -output_supply_port vdd_sw
        """
    )
    result = analyze_strategy_interactions(model)
    conflicts = [i for i in result.interactions if i.kind == CONFLICT]
    assert conflicts
    assert any(c.subject == "vdd_sw" for c in conflicts)
    ev = next(c for c in conflicts if c.subject == "vdd_sw").evidence
    assert {ev["switch_a"], ev["switch_b"]} == {"sw_a", "sw_b"}
    assert all(c.finding.severity == "warning" for c in conflicts)


def test_same_element_retention_twice_conflicts():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        set_retention ret1 -domain PD_SRAM -elements {u_sram}
        set_retention ret2 -domain PD_SRAM -elements {u_sram} \
            -retention_supply vdd_ret
        """
    )
    result = analyze_strategy_interactions(model)
    conf = [
        i
        for i in result.interactions
        if i.kind == CONFLICT and i.subject == "retention:PD_SRAM"
    ]
    assert len(conf) == 1
    assert "retention_supply" in conf[0].evidence["differing_parameters"]
    assert conf[0].finding.severity == "warning"


def test_identical_retention_is_duplicate_not_conflict():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        set_retention ret1 -domain PD_SRAM -elements {u_sram}
        set_retention ret2 -domain PD_SRAM -elements {u_sram}
        """
    )
    result = analyze_strategy_interactions(model)
    assert (DUPLICATE, CODE_DUPLICATE) in kinds_by_code(result)
    assert not [
        i for i in result.interactions
        if i.kind == CONFLICT and i.subject == "retention:PD_SRAM"
    ]


def test_location_contradiction_between_isolation_and_level_shifter():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        set_isolation iso1 -domain PD_A -location self -clamp_value 0
        set_level_shifter ls1 -domain PD_A -location parent
        """
    )
    result = analyze_strategy_interactions(model)
    conf = [
        i
        for i in result.interactions
        if i.kind == CONFLICT and i.subject == "PD_A"
    ]
    assert len(conf) == 1
    assert conf[0].evidence["isolation_location"] == "self"
    assert conf[0].evidence["level_shifter_location"] == "parent"


def test_matching_locations_do_not_conflict():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        set_isolation iso1 -domain PD_A -location self -clamp_value 0
        set_level_shifter ls1 -domain PD_A -location self
        """
    )
    result = analyze_strategy_interactions(model)
    assert not [i for i in result.interactions if i.subject == "PD_A"]


def test_clean_model_yields_no_interactions():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        set_isolation iso1 -domain PD_A -clamp_value 0
        """
    )
    result = analyze_strategy_interactions(model)
    assert result.interactions == []
    assert result.notes == []


def test_empty_model_never_raises():
    model = build("")
    result = analyze_strategy_interactions(model)
    assert result.interactions == []


def test_to_dict_determinism():
    text = """
        upf_version 3.0
        set_design_top t
        set_isolation iso1 -domain PD_A -clamp_value 0
        set_isolation iso2 -domain PD_A -clamp_value 1
        create_power_switch sw_a -input_supply_port vdd -output_supply_port vdd_sw
        create_power_switch sw_b -input_supply_port vdd -output_supply_port vdd_sw
    """
    first = analyze_strategy_interactions(build(text)).to_dict()
    second = analyze_strategy_interactions(build(text)).to_dict()
    assert first == second
