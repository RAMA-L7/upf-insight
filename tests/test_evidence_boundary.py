"""Evidence-boundary tests - UNKNOWN is not FALSE, and never a defect.

The trust boundary the product commits to:

    READY != SIGNOFF
    COVERAGE != CORRECTNESS
    UNKNOWN != DEFECT
    NO RELATION != PROOF OF NO PHYSICAL CONNECTION

These tests pin that boundary down:

1. A fact that can only be established with a netlist (does a signal actually
   cross between two domains?) is reported as a NETLIST_REQUIRED warning or
   left unknown - never as a definitive error. UNKNOWN is not FALSE.
2. A missing netlist never becomes a fabricated defect: no finding across
   every fixture and every adversarial mutation carries support=
   NETLIST_REQUIRED at error severity.
3. Findings grounded in *declared* UPF facts (declared voltages, declared
   commands) keep their severity - honesty cuts both ways.
4. The support boundary itself is honest: an empty file is NOT_VALIDATED,
   never VALIDATED, and unsupported commands are counted, not hidden.
"""

import glob

import pytest

from upf_insight.engine.engine import validate
from upf_insight.engine.rules.checker import CheckResult, _enforce_evidence_boundary
from upf_insight.engine.rules.finding import Finding
from upf_insight.generate.generator import (
    UPFParams, DomainParam, SwitchParam, IsolationParam,
    LevelShifterParam, RetentionParam, generate_upf,
)
from upf_insight.preprocess.upf_preprocess import preprocess
from upf_insight.engine.engine import validate_records

ALL_FIXTURES = (
    sorted(glob.glob("tests/fixtures/**/*.upf", recursive=True))
    + sorted(glob.glob("tests/examples/**/*.upf", recursive=True))
)


def _gen_baseline() -> str:
    """Known-good generated design (same intent as the adversarial suites)."""
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


BASE = _gen_baseline()


# ── 1. UNKNOWN is not FALSE ────────────────────────────────────────────────

def test_unknown_crossing_is_not_an_error():
    """Without a netlist the engine says 'may cross', never 'does cross'."""
    res = validate_records(preprocess(BASE, file="<gen>"))
    for f in res.check.findings:
        if f.rule == "UPF-072":  # always-on signal into switchable domain
            assert f.severity == "warning"
            assert f.support == "NETLIST_REQUIRED"
            assert "may cross" in f.message
            assert "confirm" in f.message


def test_missing_isolation_is_warning_not_error():
    """UPF-042 flags crossing risk as NETLIST_REQUIRED warning, not error."""
    text = BASE.replace("set_isolation", "set_isolation_removed_", 1)
    # If the replace did nothing, generate a variant with isolation omitted.
    if text == BASE:
        p = UPFParams(
            design_top="top",
            domains=[
                DomainParam("core", elements="u_core",
                            primary_power="vdd_sw_out", voltage="0.8",
                            domain_type="switchable"),
                DomainParam("io", elements="u_io", voltage="1.0",
                            domain_type="always_on"),
            ],
            switches=[SwitchParam("sw_core", "core", "vdd", "vdd_sw_out",
                                  "pwr_en")],
            level_shifters=[LevelShifterParam("core", rule="low_to_high",
                                              threshold="0.8")],
            always_on=["iso_en", "pwr_en"],
        )
        text = generate_upf(p)
    res = validate_records(preprocess(text, file="<iso-removed>"))
    for f in res.check.findings:
        if f.rule == "UPF-042":
            assert f.severity == "warning"
            assert f.support == "NETLIST_REQUIRED"


def test_no_netlist_required_error_in_any_fixture():
    """A fact needing a netlist is never reported as an error."""
    for path in ALL_FIXTURES:
        res = validate([path])
        for f in res.check.findings:
            assert not (f.severity == "error"
                        and f.support == "NETLIST_REQUIRED"), \
                f"{path}: {f.rule} fabricated an error from netlist evidence"


def test_no_netlist_required_error_in_clean_baseline():
    """The generated clean baseline emits zero errors at all."""
    res = validate_records(preprocess(BASE, file="<gen>"))
    assert res.check.error_count == 0
    for f in res.check.findings:
        assert f.support != "NETLIST_REQUIRED" or f.severity != "error"


def test_enforce_evidence_boundary_downgrades_mistagged_error():
    """Even a mis-tagged rule cannot leak a netlist-dependent error through."""
    result = CheckResult()
    result.findings.append(Finding(
        rule="UPF-999", severity="error", support="NETLIST_REQUIRED",
        message="would-be fabricated error"))
    result.findings.append(Finding(
        rule="UPF-998", severity="error", support="VALIDATED",
        message="declared fact stays an error"))
    _enforce_evidence_boundary(result)
    by_rule = {f.rule: f for f in result.findings}
    assert by_rule["UPF-999"].severity == "warning"
    assert by_rule["UPF-999"].message.startswith("[netlist required]")
    assert by_rule["UPF-998"].severity == "error"


# ── 2. Declared facts stay honest (severity preserved) ────────────────────

def test_declared_voltage_facts_remain_errors():
    """UPF-061/062 errors rest on declared voltages - not on netlist guesses.

    The voltages come from create_power_domain / supply-state declarations in
    the UPF text itself, so they are established facts. Removing the level
    shifter from a declared voltage-different design is a real defect.
    """
    text = BASE.replace(
        "set_level_shifter ls_core \\\n    -domain core \\\n"
        "    -location parent \\\n    -rule low_to_high \\\n"
        "    -threshold 0.8\n", "")
    if text == BASE:
        # Fallback: strip any line starting with set_level_shifter.
        text = "\n".join(
            ln for ln in BASE.splitlines()
            if not ln.startswith("set_level_shifter")) + "\n"
    res = validate_records(preprocess(text, file="<ls-removed>"))
    assert any(f.rule == "UPF-061" and f.severity == "error"
               for f in res.check.findings)


# ── 3. Support boundary honesty ────────────────────────────────────────────

def test_empty_file_is_not_validated_not_validated():
    """No commands parsed -> NOT_VALIDATED, never VALIDATED credit."""
    res = validate_records(preprocess("", file="<empty>"))
    statuses = res.support.statuses
    assert statuses["NOT_VALIDATED"] >= 1
    assert statuses["VALIDATED"] == 0


def test_unsupported_commands_are_counted_not_hidden():
    """A broken command is an honest UNSUPPORTED finding, not silence."""
    text = "upf_version 3.0\nset_design_top top\nmake_banana foo\n"
    res = validate_records(preprocess(text, file="<unsupported>"))
    statuses = res.support.statuses
    assert statuses["UNSUPPORTED"] >= 1
    assert any(f.rule == "UPF-001" for f in res.check.findings)


def test_support_boundary_notes_explain_partial_strength():
    """When switches exist without a PST the boundary says so out loud."""
    text = "\n".join(
        ln for ln in BASE.splitlines()
        if not ln.startswith(("create_pst", "add_pst_state"))) + "\n"
    res = validate_records(preprocess(text, file="<no-pst>"))
    notes = " ".join(res.support.notes).lower()
    assert any("switch" in n for n in res.support.notes)


# ── 4. UNKNOWN domain type stays UNKNOWN ───────────────────────────────────

def test_domain_type_never_inferred_from_supply_name():
    """A domain on a VDD_xxx supply is still UNKNOWN without switch evidence."""
    p = UPFParams(
        design_top="top",
        domains=[
            DomainParam("pd_a", elements="u_a", primary_power="VDD_CORE"),
            DomainParam("pd_b", elements="u_b", primary_power="VDD_IO"),
        ],
    )
    text = generate_upf(p)
    res = validate_records(preprocess(text, file="<no-evidence>"))
    rel = res.relations
    types = {d.name: d.type for d in rel.domains}
    assert types["pd_a"] == "UNKNOWN"
    assert types["pd_b"] == "UNKNOWN"
