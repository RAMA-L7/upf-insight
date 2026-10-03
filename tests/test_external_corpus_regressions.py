"""Regressions for defects found by validating real open-source UPF.

Every test here corresponds to a defect observed in production UPF that
UPF-Insight did not write — primarily the AnyCore RISC-V power intent
(`anycore/anycore-riscv-src`, `power_spec/*.upf`, commit 419cc6c), measured
with `scripts/validate_external.py`. The UPF snippets below are reduced from
the real files; the constructs, not the surrounding content, are what the
engine got wrong.

These are hard assertions. A defect that reappears fails the suite rather
than being absorbed by an `xfail`.
"""

from __future__ import annotations

import pytest

from upf_insight.engine.engine import validate, validate_records
from upf_insight.model.builder import _pair_role, _pair_value
from upf_insight.preprocess.upf_preprocess import preprocess


def _codes(text: str) -> set:
    result = validate_records(preprocess(text, "<test>"))
    return {f.rule for f in result.check.findings}


def _messages(text: str, rule: str) -> list:
    result = validate_records(preprocess(text, "<test>"))
    return [f.message for f in result.check.findings if f.rule == rule]


# ---------------------------------------------------------------------------
# Tcl line continuation inside braces
# ---------------------------------------------------------------------------

def test_backslash_continuation_inside_braces_is_whitespace():
    """A backslash before EOL is a continuation even inside braces.

    AnyCore writes multi-line port lists this way:

        connect_supply_net VSS -ports {VSS  \\
                                    dom0/VSS  \\
                                    dom1/VSS}

    The backslash stands for whitespace and contributes nothing to the
    argument value. Preserving it put a literal '\\' in the port list, which
    surfaced as "unknown target '\\'" (UPF-024) once per continuation.
    """
    text = (
        "upf_version 2.1\n"
        "create_supply_net VSS\n"
        "connect_supply_net VSS -ports {VSS  \\\n"
        "                              dom0/VSS  \\\n"
        "                              dom1/VSS }\n"
    )
    records = preprocess(text, "<test>")
    # One logical command for the multi-line list (3 total: version, net, connect).
    assert len(records) == 3
    assert "\\" not in records[2].text
    # Every element is preserved (regression: list must not lose members).
    model = validate_records(records).check.model
    assert sorted(model.supply_nets["VSS"].connected_to) == [
        "VSS", "dom0/VSS", "dom1/VSS"]


def test_backslash_followed_by_space_then_newline_is_still_a_continuation():
    """Some files emit "… \\ " with a trailing space *after* the backslash.

    AnyCore does exactly this in Decode.upf / Fetch1Fetch2.upf. The backslash
    still abuts the newline in Tcl terms — the intervening spaces are the
    whitespace the continuation introduces.
    """
    text = (
        "upf_version 2.1\n"
        "create_supply_net VSS\n"
        "connect_supply_net VSS -ports {a/VSS  \\ \n"
        "                              b/VSS}\n"
    )
    records = preprocess(text, "<test>")
    assert len(records) == 3
    assert "\\" not in records[2].text
    model = validate_records(records).check.model
    assert sorted(model.supply_nets["VSS"].connected_to) == ["a/VSS", "b/VSS"]


def test_multiline_list_preserves_every_element():
    """A brace group spanning lines keeps all members (target: no data loss)."""
    names = " ".join(f"inst{i}" for i in range(6))
    text = (
        "upf_version 2.1\n"
        f"create_power_domain PD -elements {{\n  {names}\n}}\n"
    )
    model = validate_records(preprocess(text, "<test>")).check.model
    assert sorted(model.domains["PD"].elements) == sorted(
        f"inst{i}" for i in range(6))


# ---------------------------------------------------------------------------
# Tcl that is not UPF
# ---------------------------------------------------------------------------

def test_plain_tcl_is_not_reported_as_unknown_upf_command():
    """A .upf file is a Tcl script and legitimately contains Tcl.

    AnyCore's FetchStage1.upf builds scope with:

        set CURRENT_SCOPE [set_scope btb]
        load_upf BTB.upf
        set_scope ${CURRENT_SCOPE}

    Reporting `set` as "Unknown UPF command" invents an error on a valid file.
    """
    text = (
        "upf_version 2.1\n"
        "set CURRENT_SCOPE [set_scope btb]\n"
        "create_power_domain PD_BPU0\n"
        "source ./common_defs.upf\n"
        "foreach x {a b} { puts $x }\n"
    )
    assert "UPF-001" not in _codes(text)
    # The UPF commands in the same file must still be modelled.
    model = validate_records(preprocess(text, "<test>")).check.model
    assert "PD_BPU0" in model.domains


def test_genuinely_unknown_command_is_still_reported():
    """Skipping Tcl must not blind us to a real unknown UPF command."""
    text = "upf_version 2.1\ncreate_power_domain PD\nfrobnicate_widget PD x\n"
    assert "UPF-001" in _codes(text)


# ---------------------------------------------------------------------------
# create_power_domain argument order
# ---------------------------------------------------------------------------

def test_include_scope_before_name_does_not_become_the_domain_name():
    """`-include_scope` may precede the domain name (target: no phantom domain).

    AnyCore writes `create_power_domain -include_scope PD_RAM`. Taking
    args[0] blindly named the domain "-include_scope" and lost PD_RAM
    entirely, so every later rule looked at a domain that does not exist.
    """
    text = "upf_version 2.1\ncreate_power_domain -include_scope PD_RAM\n"
    model = validate_records(preprocess(text, "<test>")).check.model
    assert "-include_scope" not in model.domains
    assert "PD_RAM" in model.domains


def test_domain_name_after_options_is_still_parsed_with_elements():
    """Flag-first ordering must not cost us the elements list."""
    text = (
        "upf_version 2.1\n"
        "create_power_domain -include_scope PD -elements {u1 u2}\n"
    )
    model = validate_records(preprocess(text, "<test>")).check.model
    assert "PD" in model.domains
    assert sorted(model.domains["PD"].elements) == ["u1", "u2"]


# ---------------------------------------------------------------------------
# {role signal} pairs
# ---------------------------------------------------------------------------

def test_control_port_pair_yields_the_signal_not_the_brace_literal():
    """`-control_port {ctrl en}` names a role and a signal; rules need the signal.

    AnyCore: `-control_port {ctrl alPartitionActive_i[2]      }`. Keeping the
    braced pair intact made every control-signal lookup miss and produced
    findings quoting '{ctrl alPartitionActive_i[2]      }' as a signal name.
    """
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "create_supply_net VDD_SW -domain PD\n"
        "create_power_switch SW -domain PD -output_supply_port {vout VDD_SW} "
        "-input_supply_port {vin VDD} -control_port {ctrl en0} "
        "-on_state {on_s vin {ctrl}} -off_state {off_s {!ctrl}}\n"
    )
    model = validate_records(preprocess(text, "<test>")).check.model
    sw = next(iter(model.switches.values()))
    assert sw.control_port == "en0"
    assert sw.control_port_role == "ctrl"


def test_bare_control_port_still_works():
    """A single-word -control_port has no role half and must pass through."""
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "create_supply_net VDD_SW -domain PD\n"
        "create_power_switch SW -domain PD -input_supply VDD "
        "-output_supply VDD_SW -control_port pwr_en "
        "-on_state {on VDD {pwr_en}} -off_state {off {!pwr_en}}\n"
    )
    model = validate_records(preprocess(text, "<test>")).check.model
    sw = next(iter(model.switches.values()))
    assert sw.control_port == "pwr_en"
    assert sw.control_port_role is None


def test_pair_helpers_directly():
    assert _pair_value("{ctrl en0}") == "en0"
    assert _pair_value("{vin VDD}") == "VDD"
    assert _pair_value("en0") == "en0"
    assert _pair_value("{solo}") == "solo"
    assert _pair_value(None) is None
    assert _pair_role("{ctrl en0}") == "ctrl"
    assert _pair_role("en0") is None


def test_on_state_may_reference_the_control_role_not_the_signal():
    """A switch may key its state to the port *role*; that is not a defect.

    `-control_port {ctrl en}` with `-on_state {on_s vin {ctrl}}` is how
    AnyCore writes every power switch. Flagging it would be a false positive.
    """
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "create_supply_net VDD_SW -domain PD\n"
        "create_power_switch SW -domain PD -input_supply_port {vin VDD} "
        "-output_supply_port {vout VDD_SW} -control_port {ctrl en0} "
        "-on_state {on_s vin {ctrl}} -off_state {off_s {!ctrl}}\n"
    )
    assert "UPF-074" not in _codes(text)


# ---------------------------------------------------------------------------
# Relative scope composition
# ---------------------------------------------------------------------------

def test_relative_set_scope_composes_onto_the_loading_scope():
    """A relative set_scope descends; it must not discard the parent prefix.

    AnyCore's Core_OOO_Hier.upf loads children into named scopes and the
    children then descend further:

        set_scope /fs1
        load_upf FetchStage1.upf     # child enters /fs1
        # inside the child:
        set_scope btb                 # -> /fs1/btb

    Assigning absolutely keyed the child's supplies 'btb/VDD' while the
    parent referenced 'fs1/btb/VDD' — a UPF-024 false positive on every
    hierarchically loaded block.
    """
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "set_scope /fs1\n"
        "set_scope btb\n"
        "create_supply_net VDD\n"
        "create_supply_port VDD\n"
    )
    model = validate_records(preprocess(text, "<test>")).check.model
    # The leading '/' is preserved verbatim in the key.
    assert "/fs1/btb/VDD" in model.supply_nets
    assert model.current_scope == "/fs1/btb"


def test_absolute_set_scope_replaces_the_prefix():
    """A leading '/' is absolute and still replaces the current scope."""
    text = (
        "upf_version 2.1\n"
        "set_scope /fs1\n"
        "set_scope /other\n"
        "create_supply_net VDD\n"
    )
    model = validate_records(preprocess(text, "<test>")).check.model
    assert "/other/VDD" in model.supply_nets
    assert "/fs1/other/VDD" not in model.supply_nets


def test_restating_the_current_scope_is_idempotent():
    """A child restating its own scope must not compose to 'a/a'.

    The generator emits `set_scope core_a` at the top of core_a.upf, which is
    loaded with `-scope core_a`. That restates the scope; it is not a descent.
    """
    text = (
        "upf_version 2.1\n"
        "set_scope core_a\n"
        "set_scope core_a\n"
        "create_supply_net vdd\n"
    )
    model = validate_records(preprocess(text, "<test>")).check.model
    assert "core_a/vdd" in model.supply_nets
    assert "core_a/core_a/vdd" not in model.supply_nets


# ---------------------------------------------------------------------------
# Legal IEEE 1801 option spellings found in the wild
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    # create_supply_net -domain / -reuse / -exclude (AnyCore, 543 occurrences)
    "upf_version 2.1\ncreate_supply_net VDD -domain TOP\n"
    "create_supply_net VSS -domain TOP -reuse\n"
    "create_supply_net VDD2 -domain TOP -exclude\n",
    # create_power_domain -scope (AnyCore BPU.upf)
    "upf_version 2.1\ncreate_power_domain PD -elements {u1} -scope u1\n",
    # set_isolation -diff_supply_only (AnyCore ActiveList.upf, 71 occurrences)
    "upf_version 2.1\ncreate_power_domain PD\n"
    "set_isolation ISO -domain PD -isolation_power_net VDD "
    "-isolation_ground_net VSS -diff_supply_only TRUE\n",
    # isolation control -location / _power_net forms
    "upf_version 2.1\ncreate_power_domain PD\n"
    "set_isolation_control ISO -domain PD -isolation_signal iso_en "
    "-location parent\n",
    # retention _power_net / _ground_net forms
    "upf_version 2.1\ncreate_power_domain PD\n"
    "set_retention RET -domain PD -retention_power_net VDD "
    "-retention_ground_net VSS\n",
])
def test_legal_option_forms_are_accepted(text):
    """Options defined by IEEE 1801 must not be reported as UPF-002."""
    assert "UPF-002" not in _codes(text)


def test_isolation_power_net_is_modelled_not_just_accepted():
    """Accepting -isolation_power_net must also *use* it (regression: silent)."""
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "create_power_domain PD\n"
        "set_isolation ISO -domain PD -isolation_power_net VDD "
        "-isolation_ground_net VSS\n"
    )
    model = validate_records(preprocess(text, "<test>")).check.model
    assert model.isolation[0].isolation_supply == "VDD"


def test_create_power_switch_accepts_both_supply_spellings():
    """UPF 2.1/3.0 use -input_supply; UPF 3.1+ uses -input_supply_port."""
    for spelling in ("-input_supply VDD -output_supply VDD_SW",
                     "-input_supply_port {vin VDD} -output_supply_port {vout VDD_SW}"):
        text = (
            "upf_version 2.1\n"
            "create_supply_net VDD\n"
            "create_supply_net VDD_SW -domain PD\n"
            f"create_power_switch SW -domain PD {spelling} -control_port pwr_en "
            "-on_state {on VDD {pwr_en}} -off_state {off {!pwr_en}}\n"
        )
        codes = _codes(text)
        assert "UPF-003" not in codes, spelling


# ---------------------------------------------------------------------------
# Whole-corpus invariants
# ---------------------------------------------------------------------------

def test_corpus_files_remain_free_of_syntax_layer_findings():
    """No UPF-001/002/003 on legal UPF — the grammar layer must be silent."""
    result = validate(["tests/corpus/ieee1801_upf21_forms.upf"])
    syntax = {f.rule for f in result.check.findings
              if f.rule in ("UPF-001", "UPF-002", "UPF-003", "UPF-024")}
    assert not syntax, sorted(syntax)


def test_semantic_checks_still_fire_after_normalization_fixes():
    """Guard rule A: none of the above may be bought by weakening checks."""
    text = (
        "upf_version 2.1\n"
        "create_supply_net VDD\n"
        "create_supply_net VSS\n"
        "create_power_domain PD_A -elements {u_a}\n"
        "create_power_domain PD_B -elements {u_b}\n"
        "set_isolation ISO -domain PD_A -isolation_signal iso_en\n"
        "set_retention RET -domain PD_A -save_signal {save high}\n"
    )
    codes = _codes(text)
    # Real semantic questions must still be raised.
    assert "UPF-047" in codes or "UPF-044" in codes or "UPF-051" in codes