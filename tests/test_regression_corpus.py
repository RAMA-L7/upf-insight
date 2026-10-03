"""Regression corpus: one tiny fixture per real-world defect found.

Each file under `tests/fixtures/upf/` is a minimal, self-contained reduction of
a construct that real open-source UPF used and that UPF-Insight previously got
wrong. The header of each fixture names the source it came from.

Why fixtures rather than inline strings in the test modules: a defect
regression should be readable by someone who has never read the test suite,
and should fail with a filename that says which construct broke. When a future
parser change reintroduces one of these bugs, this file names it directly.

Run `python -m pytest tests/test_regression_corpus.py -q`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from upf_insight.engine.engine import validate
from upf_insight.model.builder import build_model
from upf_insight.preprocess.upf_preprocess import preprocess

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "upf"


def _all_fixtures():
    return sorted(FIXTURES.glob("*.upf"))


def _build(name: str):
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return build_model(preprocess(text, str(FIXTURES / name)))


def _codes(name: str) -> set:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    result = validate([str(FIXTURES / name)])
    return {f.rule for f in result.check.findings}


def test_fixture_directory_is_populated():
    """A regression corpus that silently emptied protects nothing."""
    names = [p.name for p in _all_fixtures()]
    assert len(names) >= 10, names


@pytest.mark.parametrize("path", _all_fixtures(), ids=lambda p: p.stem)
def test_every_fixture_parses_without_syntax_findings(path):
    """No fixture may report UPF-001/002/003 — they are all legal UPF."""
    result = validate([str(path)])
    syntax = {f.rule for f in result.check.findings
              if f.rule in ("UPF-001", "UPF-002", "UPF-003", "UPF-006")}
    assert not syntax, [f.message for f in result.check.findings
                        if f.rule in syntax]


@pytest.mark.parametrize("path", _all_fixtures(), ids=lambda p: p.stem)
def test_every_fixture_is_deterministic(path):
    """Byte-identical findings across two runs."""
    a = validate([str(path)]).check.findings
    b = validate([str(path)]).check.findings
    assert [(f.rule, f.message, f.line) for f in a] == \
           [(f.rule, f.message, f.line) for f in b]


# ---------------------------------------------------------------------------
# Per-fixture expected outcome
# ---------------------------------------------------------------------------

def test_multiline_elements_keeps_every_member():
    """A brace group spanning lines is one command; no element may be lost."""
    model = _build("multiline_elements.upf")
    parts = model.domains["PD_PART1"]
    assert sorted(parts.elements) == [
        "INST_LOOP[1].ram_inst", "INST_LOOP[2].ram_inst",
        "INST_LOOP[3].ram_inst",
    ]


def test_backslash_continuation_yields_one_command_no_backslash():
    """The backslash is whitespace; it must not become a port named '\\'."""
    text = (FIXTURES / "backslash_continuation.upf").read_text(encoding="utf-8")
    records = preprocess(text, "backslash_continuation.upf")
    assert len(records) == 3
    model = build_model(records)
    targets = model.supply_nets["VSS"].connected_to
    assert "\\" not in " ".join(targets)
    assert sorted(targets) == [
        "VSS",
        "counter_gen[0].counterTable/VSS",
        "counter_gen[1].counterTable/VSS",
    ]


def test_include_scope_before_name_is_not_the_domain_name():
    """`create_power_domain -include_scope PD_RAM` names PD_RAM."""
    model = _build("include_scope.upf")
    assert "-include_scope" not in model.domains
    assert "PD_RAM" in model.domains


def test_array_bit_select_is_not_flagged_as_a_wildcard():
    """Bus indices are literals, not globs."""
    assert "UPF-087" not in _codes("array_bit_select.upf")


def test_control_port_pair_resolves_to_the_signal():
    """`{ctrl en0}` names a role and a signal; rules need the signal."""
    model = _build("control_port_pair.upf")
    sw = next(iter(model.switches.values()))
    assert sw.control_port == "en0"
    assert sw.control_port_role == "ctrl"


def test_control_port_role_reference_is_not_a_finding():
    """A condition naming the role is correct, not a defect."""
    assert "UPF-074" not in _codes("control_port_pair.upf")


def test_pst_positional_state_maps_onto_supplies():
    """`-state` entries map by position, not as (supply, state) pairs."""
    model = _build("pst_positional_state.upf")
    pst = next(iter(model.psts.values()))
    by_name = {s.name: s.supply_states for s in pst.states}
    assert by_name["ALL_OFF"] == {
        "VDD": "ACTIVE", "VSS": "ACTIVE",
        "sw2/vout": "OFF", "sw3/vout": "OFF",
    }


def test_pst_positional_state_is_not_reported_unused():
    assert "UPF-025" not in _codes("pst_positional_state.upf")


def test_pst_naming_the_switch_port_path_is_modeled():
    """`SW_CPU/vout` is a legal way to name a switched supply."""
    assert "UPF-038" not in _codes("pst_switch_port_path.upf")


def test_relative_scope_composes_onto_the_loading_scope():
    """`set_scope /fs1` then `set_scope btb` must land in /fs1/btb."""
    model = _build("relative_scope.upf")
    assert model.current_scope == "/fs1/btb"
    assert "/fs1/btb/VDD" in model.supply_nets


def test_plain_tcl_is_not_an_unknown_upf_command():
    """A .upf file is a Tcl script; `set`/`source`/`foreach` are not UPF."""
    assert "UPF-001" not in _codes("plain_tcl.upf")
    model = _build("plain_tcl.upf")
    assert "PD_BPU0" in model.domains


def test_legal_option_forms_are_all_accepted():
    """-domain, -reuse, -scope, -diff_supply_only, map_power_switch."""
    assert "UPF-002" not in _codes("legal_option_forms.upf")