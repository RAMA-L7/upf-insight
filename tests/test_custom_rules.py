"""Tests for user-defined declarative custom rules (YAML rulesets)."""

from __future__ import annotations

import os

import pytest

from upf_insight.engine.policy.custom_rules import (
    CustomRule,
    apply_custom_rules,
    load_custom_rules,
)
from upf_insight.preprocess.upf_preprocess import CommandRecord

EXAMPLE = os.path.join("examples", "policies", "custom_rules_example.yaml")


@pytest.fixture()
def records() -> list:
    return [
        CommandRecord(text="set_isolation iso_core -domain core "
                           "-applies_to outputs",
                      file="top.upf", line=10),
        CommandRecord(text="set_isolation iso_io -domain io -isolation_supply vdd_iso",
                      file="top.upf", line=14),
        CommandRecord(text="create_power_switch sw_core -domain core "
                           "-input_supply_port in vdd",
                      file="top.upf", line=20),
        CommandRecord(text="add_pst pst_top",
                      file="top.upf", line=30),
    ]


def test_load_example_yaml_yields_three_rules():
    rules = load_custom_rules(EXAMPLE)
    assert [r.id for r in rules] == ["CUST-001", "CUST-002", "CUST-003"]
    assert [r.severity for r in rules] == ["error", "warning", "info"]
    for rule in rules:
        assert isinstance(rule, CustomRule)
        assert rule.message


def test_apply_produces_expected_codes_severities_lines(records):
    rules = load_custom_rules(EXAMPLE)
    findings = apply_custom_rules(records, rules)
    got = [(f.rule, f.severity, f.line) for f in findings]
    assert ("CUST-001", "error", 10) in got
    assert ("CUST-002", "warning", 20) in got
    assert ("CUST-003", "info", 30) in got
    assert all(f.file == "top.upf" for f in findings)


def test_deterministic_order_rules_then_records():
    records = [
        CommandRecord(text="set_isolation a", file="a.upf", line=1),
        CommandRecord(text="set_isolation b", file="a.upf", line=2),
    ]
    rules = [
        CustomRule(id="CUST-001", severity="error", message="m1",
                   match_command="set_isolation"),
        CustomRule(id="CUST-002", severity="info", message="m2",
                   match_command="set_isolation"),
    ]
    findings = apply_custom_rules(records, rules)
    assert [(f.rule, f.line) for f in findings] == \
        [("CUST-001", 1), ("CUST-001", 2), ("CUST-002", 1), ("CUST-002", 2)]


def test_option_filter_requires_presence(records):
    rules = load_custom_rules(EXAMPLE)
    findings = {f.line: f.rule for f in apply_custom_rules(records, rules)}
    assert findings.get(14) is None


def test_non_matching_regex_yields_nothing():
    rules = [CustomRule(id="CUST-004", severity="info", message="never",
                        match_command="set_isolation",
                        match_pattern=r"-clamp_value\s+zzz")]
    records = [CommandRecord(text="set_isolation x -clamp_value 0",
                             file="f.upf", line=5)]
    assert apply_custom_rules(records, rules) == []


def test_invalid_id_raises_value_error(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text("rules:\n  - id: CUSTOM-1\n    severity: error\n"
                 "    match:\n      command: set_isolation\n"
                 "    message: bad id\n", encoding="utf-8")
    with pytest.raises(ValueError, match="CUST"):
        load_custom_rules(str(p))


def test_invalid_severity_and_bad_regex_raise(tmp_path):
    p1 = tmp_path / "sev.yaml"
    p1.write_text("rules:\n  - id: CUST-001\n    severity: fatal\n"
                  "    match:\n      command: '*'\n    message: m\n",
                  encoding="utf-8")
    with pytest.raises(ValueError, match="severity"):
        load_custom_rules(str(p1))
    p2 = tmp_path / "re.yaml"
    p2.write_text("rules:\n  - id: CUST-002\n    severity: info\n"
                  "    match:\n      command: '*'\n      pattern: '([unclosed'\n"
                  "    message: m\n", encoding="utf-8")
    with pytest.raises(ValueError, match="regex"):
        load_custom_rules(str(p2))


def test_unknown_keys_raise_and_stream_loading_works(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("rules:\n  - id: CUST-005\n    severity: info\n"
                 "    bogus: true\n    match:\n      command: '*'\n"
                 "    message: m\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown keys"):
        load_custom_rules(str(p))
    with open(EXAMPLE, encoding="utf-8") as fh:
        assert len(load_custom_rules(fh)) == 3
