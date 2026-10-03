"""Stage attribution and finding evidence.

A flat list of rule codes hides where a finding came from. A parser bug, a
normalization bug and a real design violation look identical unless you already
know the layer. These tests pin the stage taxonomy and the evidence contract.
"""

from __future__ import annotations

import pytest

from upf_insight.engine.engine import validate, validate_records
from upf_insight.engine.rules.finding import Finding
from upf_insight.engine.stages import (
    DESIGN,
    MODEL,
    NORMALIZATION,
    PARSE,
    SEMANTIC,
    STAGES,
    findings_by_stage,
    stage_for,
    stage_report,
)
from upf_insight.preprocess.upf_preprocess import preprocess


def _findings(text: str):
    return validate_records(preprocess(text, "<t>")).check.findings


# ---------------------------------------------------------------------------
# Stage attribution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rule,expected", [
    ("UPF-001", PARSE),        # unknown command
    ("UPF-002", PARSE),        # illegal option
    ("UPF-006", PARSE),        # unbalanced Tcl
    ("UPF-087", NORMALIZATION),  # wildcard / bit-select shape
    ("UPF-031", NORMALIZATION),  # PST state not mapped onto the IR
    ("UPF-010", MODEL),        # referenced but never defined
    ("UPF-013", MODEL),        # duplicate definition
    ("UPF-047", SEMANTIC),     # isolation control must be always-on
])
def test_stage_assignment(rule, expected):
    assert stage_for(rule) == expected


def test_netlist_required_is_a_design_stage_check():
    """A NETLIST_REQUIRED check exists *because* the design is absent."""
    assert stage_for("UPF-038", "NETLIST_REQUIRED") == DESIGN
    # The same rule without that support is a plain semantic check.
    assert stage_for("UPF-038", "VALIDATED") == SEMANTIC


def test_stages_cover_every_finding_exactly_once():
    findings = [
        Finding(rule="UPF-001", severity="error", message="x"),
        Finding(rule="UPF-047", severity="warning", message="y"),
        Finding(rule="UPF-038", severity="warning", message="z",
                support="NETLIST_REQUIRED"),
    ]
    counts = findings_by_stage(findings)
    assert sum(counts.values()) == len(findings)
    assert set(counts) == set(STAGES)


def test_clean_upf_reports_no_parse_findings():
    """The grammar layer must stay silent on legal UPF."""
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "create_power_domain PD -elements {u1}\n"
        "set_isolation ISO -domain PD -isolation_signal en\n"
    )
    report = stage_report(_findings(text))
    assert report["stages"][PARSE] == 0
    assert report["readable_ratio"] == 1.0


def test_stage_report_is_exposed_on_the_result():
    result = validate(["tests/fixtures/soc_top.upf"])
    stages = result.to_dict()["stages"]
    assert stages is not None
    assert stages["total"] == len(result.check.findings)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def test_every_finding_serialises_its_stage():
    d = Finding(rule="UPF-047", severity="warning", message="m").to_dict()
    assert d["stage"] == SEMANTIC
    assert d["evidence"] == []


def test_evidence_defaults_to_empty_not_invented():
    """A rule with nothing concrete to cite must claim nothing."""
    f = Finding(rule="UPF-047", severity="warning", message="m")
    assert f.evidence == []


def test_upf_038_cites_the_switch_it_checked():
    """A finding should carry the relationship it verified, not just a verdict.

    The evidence names the switch, its supplies, and the PST that was checked,
    so an engineer can confirm or refute the claim without re-reading the UPF.
    """
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "create_supply_net VDD_SW -domain PD_CPU\n"
        "create_power_domain PD_CPU -elements {u_cpu} -supply { primary VDD_SW }\n"
        "create_power_switch SW_CPU -domain PD_CPU "
        "-output_supply_port {vout VDD_SW} -input_supply_port {vin VDD} "
        "-control_port en -on_state {on_s vin {en}} -off_state {off_s {!en}}\n"
        "add_supply_state VDD_SW -state {ON 1.0} -state {OFF off}\n"
        "create_pst P -supplies { VDD }\n"
        "add_pst_state ON -pst P -state {ON}\n"
    )
    findings = [f for f in _findings(text) if f.rule == "UPF-038"]
    assert findings, "expected UPF-038 for an unmodeled switch output"
    joined = " | ".join(findings[0].evidence)
    assert "Power switch: SW_CPU" in joined
    assert "Input supply: VDD" in joined
    assert "VDD_SW" in joined
    # The port path the supply is also known by must be cited.
    assert "SW_CPU/vout" in joined


def test_evidence_is_json_serialisable():
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "create_power_domain PD -elements {u1}\n"
        "set_isolation ISO -domain PD -isolation_signal en\n"
    )
    payload = validate_records(preprocess(text, "<t>")).to_dict()
    assert "stages" in payload
    for f in payload["check"]["findings"]:
        assert isinstance(f["evidence"], list)
        assert "stage" in f