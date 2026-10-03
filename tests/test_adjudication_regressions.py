"""Regressions for defects found by adjudicating real open-source UPF findings.

Every test here corresponds to a defect discovered by
`scripts/adjudicate.py` against the AnyCore RISC-V power intent, after the
grammar layer had already been fixed. These are **semantic** defects — the
engine parsed the file correctly and then drew a wrong conclusion, or drew a
correct conclusion from wrong intermediate state.

Both defects share a shape worth stating: the tool was internally consistent
and its own fixtures agreed with it. Only foreign UPF exposed them.

  * UPF-087 treated every Verilog bus bit-select as a wildcard.
  * `add_pst_state` read positional `-state` entries as (supply, state) pairs,
    which cascaded into UPF-025/030/031/034.
"""

from __future__ import annotations

from upf_insight.engine.analysis.wildcard_analyzer import (
    _has_wildcard,
    analyze_wildcards,
    score_pattern,
)
from upf_insight.engine.engine import validate_records
from upf_insight.model.builder import build_model
from upf_insight.preprocess.upf_preprocess import preprocess


def build(text: str):
    return build_model(preprocess(text, file="t.upf"))


def _codes(text: str) -> set:
    return {f.rule for f in validate_records(preprocess(text, "<t>")).check.findings}


# ---------------------------------------------------------------------------
# UPF-087: bus bit-selects are not wildcards
# ---------------------------------------------------------------------------

def test_numeric_bit_select_is_not_a_wildcard():
    """`inst[3]` names one array element; it has no pattern semantics.

    IEEE 1801 element lists name design objects. A Verilog array reference is
    a bit select that resolves to exactly one object. Treating every '[' as a
    glob made UPF-087 fire on every bus in a design.
    """
    assert _has_wildcard("INST_LOOP[0].ram_instance") is False
    assert _has_wildcard("alPartitionActive_i[2]") is False
    assert _has_wildcard("counter_gen[0]") is False
    assert _has_wildcard("SW_PG_LSU_1/vout") is False


def test_real_globs_are_still_wildcards():
    """Negative control: genuine patterns must still be detected."""
    assert _has_wildcard("inst*") is True
    assert _has_wildcard("u_mem?") is True
    assert _has_wildcard("[abc]_reg_*") is True
    assert _has_wildcard("core/*") is True


def test_character_class_glob_is_still_a_wildcard():
    """`[abc]` is a glob character class even though it has no * or ?."""
    assert _has_wildcard("reg[abc]") is True


def test_bit_select_scores_as_a_literal():
    """A bit-select must score as fully specific with zero risk."""
    specificity, risk, level = score_pattern("INST_LOOP[0].ram_instance")
    assert (specificity, risk, level) == (1.0, 0, "LOW")


def test_upf_087_silent_on_bus_indexed_elements():
    """The end-to-end symptom: no UPF-087 for bus-indexed element lists.

    Reduced from AnyCore RamPartitioned.upf, which produced 12 findings here.
    """
    text = (
        "upf_version 2.1\n"
        "create_power_domain PD_RAM -include_scope\n"
        "create_power_domain PD_PART1 -elements {INST_LOOP[1].ram_inst}\n"
        "create_power_domain PD_PART2 -elements {INST_LOOP[2].ram_inst}\n"
    )
    assert "UPF-087" not in _codes(text)


def test_upf_087_silent_on_scoped_supply_with_bus_index():
    """A scoped supply name carrying an array index is not a wildcard either.

    AnyCore writes `connect_supply_net ... -ports {INST_LOOP[0].cam/VDD}`.
    """
    text = (
        "upf_version 2.1\n"
        "create_power_domain PD -elements {INST_LOOP[0].cam_instance}\n"
        "set_scope sub\n"
        "create_power_domain PD2 -elements {counter_gen[0].counterTable}\n"
    )
    assert "UPF-087" not in _codes(text)


def test_upf_087_still_fires_on_a_real_wildcard():
    """Negative control: a genuine low-specificity wildcard must be reported.

    Guards against 'fixing' UPF-087 by disabling it.
    """
    text = (
        "upf_version 2.1\n"
        "create_power_domain PD -elements {top/sram/reg*}\n"
    )
    assert "UPF-087" in _codes(text)


def test_wildcard_analysis_ignores_bit_selects():
    model = build(
        """
        upf_version 2.1
        create_power_domain d1 -elements {inst[0].sub}
        create_power_domain d2 -elements {inst[1].sub}
        """
    )
    assert analyze_wildcards(model).assessments == []


def test_wildcard_analysis_still_sees_real_wildcards():
    model = build(
        """
        upf_version 2.1
        create_power_domain d1 -elements {inst[0].sub}
        create_power_domain d2 -elements {core/*}
        """
    )
    patterns = [a.pattern for a in analyze_wildcards(model).assessments]
    assert patterns == ["core/*"]


# ---------------------------------------------------------------------------
# add_pst_state: IEEE 1801 positional -state mapping
# ---------------------------------------------------------------------------

def test_positional_state_maps_onto_create_pst_supplies():
    """`-state` entries map by POSITION onto `create_pst -supplies`.

    Reduced from AnyCore ActiveList.upf:

        create_pst Core_OOO_PST -supplies { VDD VSS sw2/vout sw3/vout }
        add_pst_state ALL_OFF -pst Core_OOO_PST -state {ACTIVE ACTIVE OFF OFF }

    Reading those four entries as (supply, state) pairs put state names in
    the supply slot, so every supply read as unreferenced.
    """
    model = build(
        """
        upf_version 2.1
        create_pst Core_OOO_PST -supplies { VDD VSS sw2/vout sw3/vout }
        add_pst_state ALL_OFF -pst Core_OOO_PST -state {ACTIVE ACTIVE OFF OFF}
        """
    )
    pst = next(iter(model.psts.values()))
    assert pst.supply_list == ["VDD", "VSS", "sw2/vout", "sw3/vout"]
    assert pst.states[0].supply_states == {
        "VDD": "ACTIVE", "VSS": "ACTIVE",
        "sw2/vout": "OFF", "sw3/vout": "OFF",
    }


def test_state_never_becomes_its_own_supply():
    """The self-referential signature of the old bug must be impossible.

    UPF-031 reported "state 'ACTIVE' on supply 'ACTIVE'", which no valid UPF
    can express.
    """
    model = build(
        """
        upf_version 2.1
        create_pst P -supplies { VDD VSS }
        add_pst_state ON -pst P -state {ACTIVE ACTIVE}
        """
    )
    pst = next(iter(model.psts.values()))
    for supply, state in pst.states[0].supply_states.items():
        assert supply != state, "supply and state must be distinct objects"


def test_upf_031_silent_on_a_correct_pst():
    """No 'undeclared state' when the PST names declared states."""
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "create_supply_net VSS\n"
        "add_port_state VDD -state {ACTIVE 1.1}\n"
        "add_port_state VSS -state {ACTIVE 0.0}\n"
        "create_pst P -supplies { VDD VSS }\n"
        "add_pst_state ON -pst P -state {ACTIVE ACTIVE}\n"
    )
    assert "UPF-031" not in _codes(text)


def test_referenced_states_are_not_reported_unused():
    """UPF-025 must not fire when the PST references the declared states."""
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "create_supply_net VSS\n"
        "add_port_state VDD -state {ACTIVE 1.1} -state {OFF off}\n"
        "add_port_state VSS -state {ACTIVE 0.0}\n"
        "create_pst P -supplies { VDD VSS }\n"
        "add_pst_state ALL_ON  -pst P -state {ACTIVE ACTIVE}\n"
        "add_pst_state ALL_OFF -pst P -state {OFF OFF}\n"
    )
    unused = [f.message for f in validate_records(
        preprocess(text, "<t>")).check.findings if f.rule == "UPF-025"]
    assert not unused, unused


def test_explicit_pair_form_still_supported():
    """The (supply state) spelling used by existing fixtures must keep working.

    Both forms are legal IEEE 1801; the positional fix must not break the
    explicit one.
    """
    model = build(
        """
        upf_version 2.1
        create_pst p -supplies { vdd vss }
        add_pst_state RUN -pst p -state {vdd ON vss ON}
        """
    )
    pst = next(iter(model.psts.values()))
    assert pst.states[0].supply_states == {"vdd": "ON", "vss": "ON"}


def test_pst_without_supplies_falls_back_without_inventing_keys():
    """A PST with no -supplies list must not fabricate supply names."""
    model = build(
        """
        upf_version 2.1
        create_pst p
        add_pst_state s0 -pst p -state {ON}
        """
    )
    pst = next(iter(model.psts.values()))
    assert pst.supply_list == []
    # Nothing is invented; the entry is simply unresolvable.
    assert pst.states[0].supply_states == {}


def test_positional_and_pair_forms_coexist_in_one_table():
    """A table may mix both spellings; each row resolves on its own terms."""
    model = build(
        """
        upf_version 2.1
        create_pst p -supplies { vdd vss }
        add_pst_state POS -pst p -state {ON OFF}
        add_pst_state PAIR -pst p -state {vdd ON vss ON}
        """
    )
    pst = next(iter(model.psts.values()))
    by_name = {s.name: s.supply_states for s in pst.states}
    assert by_name["POS"] == {"vdd": "ON", "vss": "OFF"}
    assert by_name["PAIR"] == {"vdd": "ON", "vss": "ON"}