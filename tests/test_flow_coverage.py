"""Tests for the industry UPF design-flow coverage expansion.

Phases A (strategy-control pairing), B (repeaters), C (hierarchical
promote/demote), D (switch state fidelity), E (supply equivalence + library
mapping). Every new rule family must fire on its fixture and stay silent on
clean intent, and the generator must round-trip through the validator.
"""

import pytest

from upf_insight.engine.engine import validate, validate_records
from upf_insight.engine.rules.checker import check_model
from upf_insight.engine.rules.rules_registry import registered_rules
from upf_insight.engine.rules.upf_rules import RULE_HANDLERS
from upf_insight.model.builder import build_model
from upf_insight.preprocess.upf_preprocess import preprocess


def _single(text: str) -> str:
    """Join Tcl line continuations (trailing backslash) into logical lines."""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        while line.endswith("\\") and i + 1 < len(lines):
            i += 1
            line = line[:-1].strip() + " " + lines[i].strip()
        out.append(line)
        i += 1
    return "\n".join(out)


def _check(text):
    return validate_records(preprocess(text, file="t.upf"))


def _codes(text):
    return {f.rule for f in _check(text).check.findings}


def _errors(text):
    return [f.rule for f in _check(text).check.findings if f.severity == "error"]


def _check_files(*specs):
    """Validate several files as one command stream.

    Mirrors how ``preprocess_many`` concatenates files in load order, so
    cross-file state (notably scope) can be exercised. ``specs`` are
    ``(file_name, text)`` pairs.
    """
    recs = []
    for name, text in specs:
        recs.extend(preprocess(text, file=name))
    return validate_records(recs)


def _domains_files(*specs):
    return set(_check_files(*specs).check.model.domains)


def _codes_files(*specs):
    return {f.rule for f in _check_files(*specs).check.findings}


SUPPLY_HEADER = """upf_version 3.0
set_design_top top
create_supply_port vdd -direction in
create_supply_net vdd -resolve port
connect_supply_net vdd -ports vdd
create_supply_port vss -direction in
create_supply_net vss -resolve port
connect_supply_net vss -ports vss
create_supply_set primary -function {power vdd} -function {ground vss}
"""


def test_every_registered_rule_has_a_handler():
    for rule in registered_rules():
        assert rule.code in RULE_HANDLERS, rule.code


def test_registry_grew_for_new_families():
    codes = {r.code for r in registered_rules()}
    for code in ("UPF-054", "UPF-064", "UPF-074", "UPF-090", "UPF-091",
                 "UPF-092", "UPF-093", "UPF-094", "UPF-095", "UPF-096",
                 "UPF-097", "UPF-098"):
        assert code in codes


# ── Phase A: strategy-control pairing ───────────────────────────────────────

def test_isolation_control_command_satisfies_upf045():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_isolation iso -domain PD -clamp_value 0
set_isolation_control iso -domain PD -isolation_signal iso_en
"""
    assert "UPF-045" not in _codes(text)
    model = build_model(preprocess(text, file="t.upf"))
    assert model.isolation[0].control_signal == "iso_en"


def test_retention_without_control_fires_upf054():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_retention ret -domain PD -retention_supply primary
"""
    assert "UPF-054" in _codes(text)


def test_retention_control_command_satisfies_upf054():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_retention ret -domain PD -retention_supply primary
set_retention_control ret -domain PD -retention_signal ret_en
"""
    assert "UPF-054" not in _codes(text)
    model = build_model(preprocess(text, file="t.upf"))
    assert model.retentions[0].control_signal == "ret_en"


def test_level_shifter_control_always_on_rule():
    # Not marked always-on -> UPF-064 warning.
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_level_shifter ls -domain PD
set_level_shifter_control ls -domain PD -level_shifter_signal ls_en
"""
    codes = _codes(text)
    assert "UPF-064" in codes
    assert "UPF-064" not in {f.rule for f in
                             _check(text + "set_port_attributes ls_en -attribute {always_on true}"
                                   ).check.findings}


def test_control_binding_works_when_control_precedes_strategy():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_isolation_control iso -domain PD -isolation_signal iso_en
set_isolation iso -domain PD -clamp_value 0
"""
    assert "UPF-045" not in _codes(text)


# ── Phase D: switch state fidelity ──────────────────────────────────────────

def test_switch_state_triples_are_parsed():
    text = SUPPLY_HEADER + """
create_power_switch sw -input_supply_port vdd -output_supply_port vdd_sw \\
    -control_port en -on_state {on vdd {en}} -off_state {off vdd {!en}}
"""
    sw = next(iter(build_model(preprocess(text, file="t.upf")).switches.values()))
    assert sw.on_state == "on"
    assert sw.off_state == "off"
    assert sw.on_state_supply == "vdd"
    assert sw.on_state_condition == ["en"]
    assert sw.off_state_condition == ["!en"]


def test_switch_condition_without_control_fires_upf074():
    text = SUPPLY_HEADER + """
create_power_switch sw -input_supply_port vdd -output_supply_port vdd_sw \\
    -control_port en -on_state {on vdd {other}} -off_state {off vdd {!other}}
"""
    assert "UPF-074" in _codes(text)


def test_switch_condition_referencing_control_is_silent():
    text = SUPPLY_HEADER + """
create_power_switch sw -input_supply_port vdd -output_supply_port vdd_sw \\
    -control_port en -on_state {on vdd {en}} -off_state {off vdd {!en}}
"""
    assert "UPF-074" not in _codes(text)


# ── Phase B: repeater strategies ────────────────────────────────────────────

def test_repeater_happy_path_modeled():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
create_supply_net vdd_rep -resolve net
set_repeater rep -domain PD -repeater_supply vdd_rep -location self \\
    -driver_type minimal -repeater_signal rep_en
"""
    model = build_model(preprocess(text, file="t.upf"))
    assert len(model.repeaters) == 1
    assert model.repeaters[0].domain == "PD"
    assert model.repeaters[0].repeater_supply == "vdd_rep"
    assert model.repeaters[0].signal == "rep_en"
    # no errors (UPF-090 emits only a PARTIAL warning when the supply exists)
    assert "UPF-001" not in _codes(text)
    assert "UPF-090" in _codes(text)  # PARTIAL always-on confirmation


def test_repeater_undefined_supply_fires_upf090_error():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_repeater rep -domain PD -repeater_supply ghost -repeater_signal rep_en
"""
    assert "UPF-090" in _errors(text)


def test_repeater_self_in_switchable_domain():
    text = SUPPLY_HEADER + """
create_supply_net vdd_sw -resolve net
create_power_switch sw -input_supply_port vdd -output_supply_port vdd_sw \\
    -control_port en -on_state {on vdd {en}} -off_state {off vdd {!en}}
create_power_domain PD -elements {u1} -primary_supply_set primary
set_domain_supply_net PD -primary_power_net vdd_sw
set_repeater rep -domain PD -location self -repeater_signal rep_en
"""
    assert "UPF-092" in _errors(text)


def test_repeater_without_elements_fires_upf093():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_repeater rep -domain PD -repeater_signal rep_en
"""
    assert "UPF-093" in _codes(text)


def test_repeater_without_control_fires_upf094():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_repeater rep -domain PD -elements {u1}
"""
    assert "UPF-094" in _errors(text)


def test_repeater_control_not_always_on_fires_upf091():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_repeater rep -domain PD -elements {u1} -repeater_signal rep_en
"""
    assert "UPF-091" in _codes(text)


def test_repeater_generator_round_trip():
    from upf_insight.generate.generator import (
        UPFParams, DomainParam, RepeaterParam, generate_upf)

    text = generate_upf(UPFParams(
        domains=[DomainParam("core", "u_core"), DomainParam("io", "u_io")],
        repeaters=[RepeaterParam("io", repeater_supply="vdd_rep", signal="rep_en")],
    ))
    flat = _single(text)
    assert "set_repeater rep_io -domain io -repeater_supply vdd_rep" in flat
    assert "-repeater_signal rep_en" in flat
    res = _check(text)
    assert "UPF-001" not in {f.rule for f in res.check.findings}
    assert not [f for f in res.check.findings if f.severity == "error"]
    assert len(res.check.model.repeaters) == 1


def test_repeater_shows_in_coverage():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
create_supply_net vdd_rep -resolve net
set_repeater rep -domain PD -repeater_supply vdd_rep -repeater_signal rep_en
"""
    cov = _check(text).coverage
    dom = next(d for d in cov.domains if d.domain == "PD")
    assert dom.has_repeater is True


# ── Phase C: hierarchical UPF ───────────────────────────────────────────────

def test_promote_undefined_fires_upf095():
    text = SUPPLY_HEADER + """
set_scope soc_top
upf_promote ghost_net -net ghost_net
"""
    assert "UPF-095" in _errors(text)


def test_promote_defined_supply_is_silent():
    text = SUPPLY_HEADER + """
create_supply_net vdd_core -resolve net
set_scope soc_top
upf_promote vdd_core -net vdd_core
"""
    assert "UPF-095" not in _codes(text)


def test_demote_fires_upf096():
    text = SUPPLY_HEADER + """
upf_demote vdd -net vdd
"""
    assert "UPF-096" in _codes(text)


def test_load_upf_composition_fires_upf097():
    text = SUPPLY_HEADER + """
set_scope soc_top
load_upf ip_block.upf
"""
    assert "UPF-097" in _codes(text)


# ── Phase E: supply equivalence + library mapping ───────────────────────────

def test_set_equivalent_undefined_fires_upf098():
    text = SUPPLY_HEADER + """
set_equivalent -nets {vdd ghost}
"""
    assert "UPF-098" in _errors(text)


def test_set_equivalent_declared_is_silent():
    text = SUPPLY_HEADER + """
create_supply_net vdd2 -resolve net
set_equivalent -nets {vdd vdd2}
"""
    assert "UPF-098" not in _codes(text)


def test_library_mapping_and_update_commands_recognized():
    text = SUPPLY_HEADER + """
create_supply_net vdd2 -resolve net
update_supply_net vdd2 -resolve net
update_supply_set primary -function {power vdd}
map_isolation_cell iso -domain top -lib_cells {ISOL_AND_0}
map_level_shifter_cell ls -domain top -lib_cells {LS_HL}
map_retention_cell ret -domain top -lib_cells {RET_DFF}
"""
    codes = _codes(text)
    assert "UPF-001" not in codes, "synthesis-flow commands must not be unknown"
    model = build_model(preprocess(text, file="t.upf"))
    assert len(model.library_mappings) == 3


def test_level_shifter_applies_to_is_legal():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_level_shifter ls -domain PD -applies_to inout
"""
    assert "UPF-002" not in _codes(text)
    ls = build_model(preprocess(text, file="t.upf")).level_shifters[0]
    assert ls.applies_to == "inout"

# ── Cross-file scope semantics ─────────────────────────────────────────────
#
# Scope is per-file state. A file that never issues `set_scope` starts at
# the top scope rather than inheriting the previous file's cursor, and a file
# pulled in by `load_upf <f> -scope <s>` starts in `<s>` — IEEE 1801 lets the
# child inherit the scope it is loaded into rather than repeat `set_scope`.
#
# These were latent: every hierarchical fixture repeats `set_scope` and every
# multi-file test call passes top.upf first, so neither the bleed nor the
# load_upf gap could surface.

_CHILD_WITH_SCOPE = """upf_version 3.0
set_scope core_a
create_power_domain PD_A -elements {core_a}
"""

_CHILD_WITHOUT_SCOPE = """upf_version 3.0
create_power_domain PD_SHUT -elements {u_shut}
"""


def test_scope_does_not_bleed_across_file_boundary():
    """A file that never issues set_scope starts at the top scope."""
    assert _domains_files(("core_a.upf", _CHILD_WITH_SCOPE),
                          ("top.upf", _CHILD_WITHOUT_SCOPE)) == {
        "core_a/PD_A", "PD_SHUT",
    }


def test_file_order_does_not_change_the_model():
    """Same files in either CLI order yield the same model and findings."""
    fwd = _check_files(("core_a.upf", _CHILD_WITH_SCOPE),
                       ("top.upf", _CHILD_WITHOUT_SCOPE))
    rev = _check_files(("top.upf", _CHILD_WITHOUT_SCOPE),
                       ("core_a.upf", _CHILD_WITH_SCOPE))
    assert set(fwd.check.model.domains) == set(rev.check.model.domains)
    assert {f.rule for f in fwd.check.findings} == {f.rule for f in rev.check.findings}


def test_load_upf_scope_establishes_child_scope():
    """IEEE 1801: a child loaded via `load_upf -scope` inherits that scope and
    need not repeat `set_scope`."""
    parent = "upf_version 3.0\nset_design_top top\nload_upf child.upf -scope core_a\n"
    child = "upf_version 3.0\ncreate_power_domain PD_A -elements {core_a}\n"
    assert "core_a/PD_A" in _domains_files(("top.upf", parent), ("child.upf", child))


def test_scope_reset_is_silent():
    """The scope fixes correct the model; they introduce no finding of their
    own and flag no finding the files do not already produce individually."""
    combined = _codes_files(("core_a.upf", _CHILD_WITH_SCOPE),
                            ("top.upf", _CHILD_WITHOUT_SCOPE))
    per_file = _codes_files(("core_a.upf", _CHILD_WITH_SCOPE)) | _codes_files(
        ("top.upf", _CHILD_WITHOUT_SCOPE))
    assert combined == per_file


# ── Rules previously asserted nowhere ───────────────────────────────────────
#
# UPF-015, UPF-016, UPF-025, UPF-032 and UPF-036 had no assertion anywhere in
# the suite — not directly, and not as an expected mutation code. Each gets a
# positive (fires) and a negative (stays quiet) case here.


def test_circular_supply_set_function_fires_upf015():
    """A supply set whose power function references itself is a hard cycle."""
    text = SUPPLY_HEADER + """
create_supply_set primary -function {power primary} -function {ground vss}
"""
    assert "UPF-015" in _codes(text)


def test_normal_supply_set_is_silent_upf015():
    assert "UPF-015" not in _codes(SUPPLY_HEADER)


def test_scope_target_needing_netlist_fires_upf016():
    """A non-top set_scope cannot be verified without design hierarchy."""
    text = SUPPLY_HEADER + """
set_scope core_a
create_power_domain PD -elements {u1} -primary_supply_set primary
"""
    assert "UPF-016" in _codes(text)


def test_top_scope_set_scope_is_silent_upf016():
    """set_scope to the design top is the resolved case, not a warning."""
    text = SUPPLY_HEADER + """
set_scope top
create_power_domain PD -elements {u1} -primary_supply_set primary
"""
    assert "UPF-016" not in _codes(text)


def test_unreferenced_supply_state_fires_upf025():
    """A supply state no PST and no supply-set function ever names."""
    text = SUPPLY_HEADER + """
add_supply_state PON -state {ON 1.0}
create_power_domain PD -elements {u1} -primary_supply_set primary
"""
    assert "UPF-025" in _codes(text)


def test_referenced_supply_state_is_silent_upf025():
    """The same state, referenced by a supply-set function, is not flagged."""
    text = SUPPLY_HEADER + """
add_supply_state PON -state {ON 1.0}
create_supply_set ss_set -function {power PON} -function {ground vss}
create_power_domain PD -elements {u1} -primary_supply_set primary
"""
    assert "UPF-025" not in _codes(text)


def test_supply_states_without_pst_fires_upf032():
    text = SUPPLY_HEADER + """
add_supply_state PON -state {ON 1.0}
create_power_domain PD -elements {u1} -primary_supply_set primary
"""
    assert "UPF-032" in _codes(text)


def test_supply_states_with_pst_is_silent_upf032():
    text = SUPPLY_HEADER + """
add_supply_state PON -state {ON 1.0}
create_power_domain PD -elements {u1} -primary_supply_set primary
create_pst pst -supplies {vdd vss}
add_pst_state s0 -pst pst -state {primary ON}
"""
    assert "UPF-032" not in _codes(text)


def test_strategy_without_pst_fires_upf036():
    """An isolation strategy with no PST to condition it on."""
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_isolation iso -domain PD -clamp_value 0
"""
    assert "UPF-036" in _codes(text)


def test_strategy_with_pst_is_silent_upf036():
    text = SUPPLY_HEADER + """
create_power_domain PD -elements {u1} -primary_supply_set primary
set_isolation iso -domain PD -clamp_value 0
create_pst pst -supplies {vdd vss}
add_pst_state s0 -pst pst -state {supply_set primary ON}
"""
    assert "UPF-036" not in _codes(text)
