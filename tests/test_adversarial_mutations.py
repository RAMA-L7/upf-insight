"""Adversarial UPF validation - mutation tests.

Proves UPF-Insight catches intentionally broken power intent, not merely that
it accepts generated designs. Each test starts from the clean generated
baseline, applies ONE deliberate semantic defect (a mutation), and asserts the
validator reports the expected finding (or at least does NOT report clean).

Mutation detection rate is the metric: every mutated defect must produce a
finding. A clean baseline + every mutation caught = the validation engine
actually understands the power-intent semantics, not just the keywords.
"""

import hashlib

import pytest

from upf_insight.engine.engine import validate_records
from upf_insight.generate.generator import (
    UPFParams,
    DomainParam,
    SwitchParam,
    IsolationParam,
    LevelShifterParam,
    RetentionParam,
    generate_upf,
)
from upf_insight.preprocess.upf_preprocess import preprocess


def _clean_baseline() -> str:
    """The known-good generated design: switchable core on a switched supply,
    isolation + level shifter at parent, retention with elements, and a PST
    with a real ALL_ON + sw.off state."""
    p = UPFParams(
        design_top="top",
        domains=[
            DomainParam("core", elements="u_core", primary_power="vdd_sw_out",
                        voltage="0.8", domain_type="switchable"),
            DomainParam("io", elements="u_io", voltage="1.0",
                        domain_type="always_on"),
            DomainParam("sram", elements="u_sram", voltage="1.0",
                        domain_type="always_on"),
        ],
        switches=[SwitchParam("sw_core", "core", "vdd", "vdd_sw_out", "pwr_en")],
        isolation=[IsolationParam("core", clamp_value="0", signal="iso_en")],
        level_shifters=[LevelShifterParam("core", rule="low_to_high",
                                          threshold="0.8")],
        retention=[RetentionParam("core", elements="regA regB")],
        always_on=["clk", "rst", "save", "restore", "iso_en", "pwr_en"],
    )
    return generate_upf(p)


def _check(text: str):
    return validate_records(preprocess(text, file="<mutated>"))


def _errors(text: str) -> set:
    return {f.rule for f in _check(text).check.findings if f.severity == "error"}


def _all_rules(text: str) -> set:
    return {f.rule for f in _check(text).check.findings}


def test_clean_baseline_has_no_errors():
    text = _clean_baseline()
    errors = [f.rule for f in _check(text).check.findings if f.severity == "error"]
    assert errors == [], f"clean baseline must have 0 errors, got {errors}"


def test_m1_break_switched_supply():
    """core's primary supply is `vdd`, not the switch output `vdd_sw_out`."""
    text = _clean_baseline().replace(
        "-primary_power_net vdd_sw_out", "-primary_power_net vdd")
    assert "UPF-073" in _errors(text)


def test_m2_disconnect_switch_output():
    """vdd_sw_out is declared but no domain consumes it."""
    text = _clean_baseline().replace(
        "-primary_power_net vdd_sw_out", "-primary_power_net vdd_other")
    assert "UPF-073" in _errors(text)


def test_m3_wrong_level_shifter_rule():
    """core (0.8V) -> io (1.0V) needs low_to_high, not high_to_low."""
    text = _clean_baseline().replace("-rule low_to_high", "-rule high_to_low")
    assert "UPF-062" in _errors(text)


def test_m4_remove_level_shifter():
    """0.8V core and 1.0V io cross without any level-shifter strategy."""
    text = _clean_baseline().replace(
        "set_level_shifter ls_core \\\n"
        "    -domain core \\\n"
        "    -location parent \\\n"
        "    -threshold 0.8 \\\n"
        "    -applies_to both \\\n"
        "    -rule low_to_high\n", "")
    assert "UPF-061" in _errors(text)


def test_m5_isolation_at_self():
    """Isolation located `self` inside a switchable domain loses power."""
    text = _clean_baseline().replace(
        "-applies_to outputs \\\n    -location parent",
        "-applies_to outputs \\\n    -location self")
    assert "UPF-041" in _errors(text)


def test_m6_remove_retention_elements():
    """set_retention exists but names no elements to retain."""
    text = _clean_baseline().replace("\\\n    -elements {regA regB}", "")
    assert "UPF-052" in _all_rules(text)


def test_m7_save_restore_same_sense():
    """save and restore driven by the same signal with the same sense can
    never sequence - the polarity semantics are broken."""
    text = _clean_baseline().replace(
        "-save_signal {save high} \\\n    -restore_signal {restore low}",
        "-save_signal {ret_en high} \\\n    -restore_signal {ret_en high}")
    assert "UPF-053" in _errors(text)


def test_m8_impossible_pst():
    """A PST row declares the switch output ON while its input VDD is OFF."""
    text = _clean_baseline().replace(
        "add_pst_state ALL_ON \\\n"
        "    -pst pst_top \\\n"
        "    -state {vdd ON vss ON vdd_sw_out ON}",
        "add_pst_state BROKEN \\\n"
        "    -pst pst_top \\\n"
        "    -state {vdd OFF vss ON vdd_sw_out ON}")
    assert "UPF-039" in _errors(text)


def test_m9_remove_always_on():
    """save/restore control no longer declared always-on - REVIEW_REQUIRED."""
    text = _clean_baseline().replace(
        "set_port_attributes clk, rst, save, restore, iso_en, pwr_en "
        "-attribute {always_on true}",
        "set_port_attributes clk, rst -attribute {always_on true}")
    assert "UPF-051" in _all_rules(text)


def test_determinism_sha256_identical():
    """The exact same input must produce byte-identical UPF every time."""
    digests = set()
    for _ in range(3):
        digests.add(hashlib.sha256(_clean_baseline().encode("utf-8")).hexdigest())
    assert len(digests) == 1


MUTATIONS = [
    ("break switched supply", test_m1_break_switched_supply),
    ("disconnect switch output", test_m2_disconnect_switch_output),
    ("wrong LS rule", test_m3_wrong_level_shifter_rule),
    ("remove level shifter", test_m4_remove_level_shifter),
    ("isolation at self", test_m5_isolation_at_self),
    ("no retention elements", test_m6_remove_retention_elements),
    ("save/restore same sense", test_m7_save_restore_same_sense),
    ("impossible PST", test_m8_impossible_pst),
    ("remove always-on", test_m9_remove_always_on),
]


def test_mutation_detection_rate():
    """Every intended semantic defect is detected - the headline metric."""
    detected = 0
    for name, fn in MUTATIONS:
        try:
            fn()
            detected += 1
        except AssertionError as exc:
            raise AssertionError(f"mutation NOT detected: {name}: {exc}")
    assert detected == len(MUTATIONS), \
        f"detected {detected}/{len(MUTATIONS)}"
