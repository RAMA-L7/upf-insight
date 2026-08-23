"""Tests for wildcard-specificity analysis (UPF-087 input analysis)."""

from __future__ import annotations

from upf_insight.engine.analysis.wildcard_analyzer import (
    ELABORATION_NOTE,
    analyze_wildcards,
    score_pattern,
)
from upf_insight.model.builder import build_model
from upf_insight.preprocess.upf_preprocess import preprocess


def build(text: str):
    return build_model(preprocess(text, file="t.upf"))


def test_wildcard_heavy_domain_element_is_high_risk():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        create_power_domain d1 -elements {inst*}
        """
    )
    result = analyze_wildcards(model)
    assert result.summary["total"] == 1
    assert result.summary["high"] == 1
    a = result.assessments[0]
    assert a.pattern == "inst*"
    assert a.context == "power_domain:d1"
    assert a.risk_level == "HIGH"
    assert ELABORATION_NOTE in a.notes
    assert 4 <= a.risk_score <= 10
    assert 0.0 <= a.specificity <= 1.0


def test_no_wildcard_model_yields_empty_result():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        create_power_domain d1 -elements {u_cpu}
        create_supply_net vdd -resolve port
        """
    )
    result = analyze_wildcards(model)
    assert result.assessments == []
    assert result.summary == {"total": 0, "high": 0, "medium": 0, "low": 0}
    assert result.notes == []


def test_leading_wildcard_scores_higher_than_trailing():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        create_power_domain d1 -elements {*inst}
        create_power_domain d2 -elements {inst*}
        """
    )
    result = analyze_wildcards(model)
    by_context = {a.context: a for a in result.assessments}
    leading = by_context["power_domain:d1"]
    trailing = by_context["power_domain:d2"]
    assert leading.risk_score > trailing.risk_score
    assert leading.specificity < trailing.specificity


def test_strategy_elements_are_collected():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        set_isolation iso1 -domain PD_A -elements {u_mem?} -clamp_value 0
        """
    )
    result = analyze_wildcards(model)
    contexts = {(a.pattern, a.context) for a in result.assessments}
    assert ("u_mem?", "isolation:PD_A") in contexts


def test_risk_levels_are_bounded_and_ordered():
    for pattern, level in [
        ("u_cpu", "LOW"),
        ("u_cp?", "LOW"),
        ("a??b", "MEDIUM"),
        ("*", "HIGH"),
        ("[abc]_reg_*", "HIGH"),
    ]:
        specificity, risk, got = score_pattern(pattern)
        assert got == level, pattern
        if not any(c in pattern for c in "*?["):
            assert specificity == 1.0 and risk == 0
        else:
            assert 0.0 <= specificity <= 1.0
            assert 0 <= risk <= 10


def test_summary_counts_match_assessments():
    model = build(
        """
        upf_version 3.0
        set_design_top t
        create_power_domain d1 -elements {u_a}
        create_power_domain d2 -elements {b*}
        create_power_domain d3 -elements {c?x}
        """
    )
    result = analyze_wildcards(model)
    levels = [a.risk_level for a in result.assessments]
    assert result.summary["total"] == len(levels)
    assert result.summary["high"] == levels.count("HIGH")
    assert result.summary["medium"] == levels.count("MEDIUM")
    assert result.summary["low"] == levels.count("LOW")


def test_to_dict_determinism():
    text = """
        upf_version 3.0
        set_design_top t
        create_power_domain d1 -elements {inst* u_clk}
        create_power_domain d2 -elements {mem_[2-7]*}
    """
    first = analyze_wildcards(build(text)).to_dict()
    second = analyze_wildcards(build(text)).to_dict()
    assert first == second
