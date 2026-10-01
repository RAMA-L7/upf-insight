"""Real-world corpus regression tests.

`engine/quality.py` proves the engine catches defects the same author injected.
It cannot prove the engine does not invent findings on foreign UPF. These tests
close that gap against `tests/corpus/`, which includes a hand-written file
using the legal IEEE 1801 option spellings the v0.3.0 grammar rejected.

The corpus is expected to be CLEAN. Findings here are tool defects unless a
test says otherwise — see docs/validation/REAL_WORLD_REPORT.md.

The P0 grammar work has landed: every former `xfail` marker is inverted to a
hard assertion. Syntax-layer rules (UPF-001/002/003/024) must stay silent on
this legal UPF; the semantic advisories that remain are real and are pinned by
`test_semantic_checks_still_fire_on_real_upf`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CORPUS = Path(__file__).resolve().parent / "corpus"


def _codes(name: str):
    """Run the CLI over a corpus file and return (codes, by_severity)."""
    import json

    proc = subprocess.run(
        [sys.executable, "scripts/validate_corpus.py", "--json", str(CORPUS / name)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    payload = json.loads(proc.stdout)
    entry = payload["results"][0]
    return entry


def test_corpus_is_present():
    """The validation corpus must ship with the repo, not live on one laptop."""
    files = sorted(p.name for p in CORPUS.glob("*.upf"))
    assert files, "tests/corpus is empty — real-world validation would be skipped"


def test_legal_option_forms_are_not_rejected():
    """IEEE 1801 defines these options; UPF-002 must not fire on them.

    Recorded as false positives at v0.3.0 (38 of 53 corpus FPs).
    """
    from upf_insight.engine.engine import validate

    result = validate([str(CORPUS / "ieee1801_upf21_forms.upf")])
    messages = " | ".join(f.message for f in result.check.findings)

    illegal = [
        "-include_scope", "-input_supply ", "-output_supply ",
        "-isolation_power_net", "-isolation_ground_net",
        "-retention_power_net", "-retention_ground_net",
    ]
    for opt in illegal:
        offending = [
            f for f in result.check.findings
            if f.rule == "UPF-002" and opt in f.message
        ]
        assert not offending, (
            f"UPF-002 rejects legal IEEE 1801 option {opt!r}: "
            f"{offending[0].message if offending else ''}"
        )
    # -domain / -location are shared names; assert via the specific rules only.
    assert "Illegal option '-domain' for command 'create_power_switch'" not in messages


def test_map_power_switch_is_known():
    """map_power_switch is defined by the standard and must not be UPF-001."""
    from upf_insight.engine.engine import validate

    result = validate([str(CORPUS / "ieee1801_upf21_forms.upf")])
    unknown = [f.message for f in result.check.findings
               if f.rule == "UPF-001" and "map_power_switch" in f.message]
    assert not unknown, f"map_power_switch reported as unknown: {unknown}"


def test_brace_group_ports_are_expanded():
    """`-ports { VDD_TOP }` is one port, not a literal brace token.

    Recorded as a false positive at v0.3.0 (UPF-024 'unknown target').
    """
    from upf_insight.engine.engine import validate

    result = validate([str(CORPUS / "ieee1801_upf21_forms.upf")])
    brace_fps = [f.message for f in result.check.findings
                 if f.rule == "UPF-024" and "{" in f.message]
    assert not brace_fps, f"brace group not expanded: {brace_fps}"


def test_switches_are_connected_to_supplies():
    """A switch parsed with null supplies means the grammar dropped options.

    That disconnection is what made UPF-076 ('the domain can never power
    down') a false positive on a design that does declare an off-state.
    """
    from upf_insight.engine.engine import validate

    result = validate([str(CORPUS / "ieee1801_upf21_forms.upf")])
    switches = result.check.model.switches
    assert switches, "no switch modeled"
    for name, sw in switches.items():
        assert sw.input_supply, f"switch {name} has no input_supply (option dropped)"
        assert sw.output_supply, f"switch {name} has no output_supply (option dropped)"
        assert sw.off_state, f"switch {name} has no off_state"


def test_semantic_checks_still_fire_on_real_upf():
    """The false positives above must not be 'fixed' by disabling real checks.

    Guards the value the tool exists to provide: it must still report
    always-on control questions and bidirectional crossings on legal UPF.
    """
    from upf_insight.engine.engine import validate

    result = validate([str(CORPUS / "ieee1801_upf21_forms.upf")])
    codes = {f.rule for f in result.check.findings}
    for rule in ("UPF-044", "UPF-047", "UPF-051"):
        assert rule in codes, (
            f"{rule} stopped firing on corpus UPF — semantic checks regressed"
        )


def test_false_positive_rate_is_reported():
    """The harness must always emit a rate, so regressions are visible."""
    payload = _codes("ieee1801_upf21_forms.upf")
    assert "false_positive_rate" in payload
    assert payload["findings"] > 0

def test_multiline_element_list_is_one_command():
    """A brace group spanning lines is ONE command, not N+1.

    Real UPF writes element lists across lines:
        create_power_domain PD -elements {
        inst0
        inst1
        }
    The v0.3.0 preprocessor splits at every newline regardless of brace depth,
    so the closing brace and each instance path become phantom commands and the
    domain's element list is lost entirely. Measured: 505 spurious UPF-001 and
    138 empty-element domains across the 37-file AnyCore corpus.
    """
    from upf_insight.preprocess.upf_preprocess import preprocess

    text = (
        "upf_version 3.0\n"
        "create_power_domain PD -elements {\n"
        "inst0\n"
        "inst1\n"
        "}\n"
    )
    records = preprocess(text, file="t.upf")
    commands = [r.text for r in records]

    assert "}" not in commands, "closing brace leaked as its own command"
    assert "inst0" not in commands, "element path leaked as its own command"
    assert any("PD" in c and "inst0" in c for c in commands), (
        f"element list was not kept with its command: {commands}"
    )


def test_multiline_domain_keeps_its_elements():
    """The domain must retain its instance list, not parse as empty."""
    from upf_insight.engine.engine import validate_records
    from upf_insight.preprocess.upf_preprocess import preprocess

    text = (
        "upf_version 3.0\n"
        "create_supply_port VDD -direction in\n"
        "create_supply_net VDD -resolve port\n"
        "connect_supply_net VDD -ports VDD\n"
        "create_supply_port VSS -direction in\n"
        "create_supply_net VSS -resolve port\n"
        "connect_supply_net VSS -ports VSS\n"
        "create_supply_set primary -function {power VDD} -function {ground VSS}\n"
        "create_power_domain PD -elements {\n"
        "u_core\n"
        "u_cache\n"
        "} -primary_supply_set primary\n"
    )
    result = validate_records(preprocess(text, file="t.upf"))
    dom = result.check.model.domains.get("PD")
    assert dom is not None and dom.elements, (
        "multi-line -elements list was lost; element-based checks are blind"
    )


def test_supply_port_pair_is_split():
    """`-input_supply_port {vin VDD}` is a pair, not one supply named '{vin VDD}'."""
    from upf_insight.engine.engine import validate_records
    from upf_insight.preprocess.upf_preprocess import preprocess

    text = (
        "upf_version 3.0\n"
        "create_supply_port VDD -direction in\n"
        "create_supply_net VDD -resolve port\n"
        "connect_supply_net VDD -ports VDD\n"
        "create_supply_set primary -function {power VDD}\n"
        "create_power_switch SW -input_supply_port {vin VDD} \\n"
        "    -output_supply_port {vout VDD_SW} -control_port en \\n"
        "    -on_state {ON VDD {en}} -off_state {OFF {!en}}\n"
        "create_supply_net VDD_SW -resolve net\n"
        "create_power_domain PD -elements {u_core} -primary_supply_set primary\n"
    )
    result = validate_records(preprocess(text, file="t.upf"))
    messages = " | ".join(f.message for f in result.check.findings)
    assert "{vin VDD}" not in messages, (
        "supply-port pair used verbatim as a supply name"
    )
