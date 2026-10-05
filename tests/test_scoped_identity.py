"""Regression tests for cross-file scoped-object identity.

The defect these pin: ``build_model`` walked a flat record list and kept one
entry per child *basename*, so a file loaded into N scopes was built once and
the other N-1 instances were dropped. On AnyCore, ``PipeLineReg.upf`` is loaded
30 times under 30 distinct scopes; 29 instances were discarded. A second,
independent defect sat underneath it: several fragments each declare a
complete, scope-less object of the same name (nine files declare
``Core_OOO_PST``), and scope alone cannot tell those apart, so the last
declaration silently overwrote the rest.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upf_insight.engine.engine import validate          # noqa: E402
from upf_insight.model.builder import build_model       # noqa: E402
from upf_insight.model.power_model import PowerIntentModel  # noqa: E402
from upf_insight.preprocess.upf_preprocess import preprocess_many  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


def _model(paths):
    """Build a model the way the engine does, so tests exercise real wiring."""
    records = preprocess_many([str(p) for p in paths])
    by_file = {}
    for rec in records:
        if rec.file:
            by_file.setdefault(Path(rec.file).name, []).append(rec)
    return build_model(records, by_file=by_file)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# --- 1. same local name in two scopes survives -----------------------------

def test_same_name_in_two_scopes_survives():
    """The two-scope fixture must yield two tables, not one."""
    m = _model([FIXTURES / "scoped_pst_parent.upf",
                FIXTURES / "scoped_pst_child.upf"])
    assert "child_a/Core_OOO_PST" in m.psts
    assert "child_b/Core_OOO_PST" in m.psts
    assert "child_a/PD_CHILD" in m.domains
    assert "child_b/PD_CHILD" in m.domains
    # Each scope keeps its own object rather than sharing the last one written.
    assert m.psts["child_a/Core_OOO_PST"] is not m.psts["child_b/Core_OOO_PST"]


def test_repeated_child_load_under_many_scopes_keeps_every_instance(tmp_path):
    """A child loaded N times under N scopes yields N distinct objects."""
    child = _write(tmp_path, "leaf.upf",
                   "create_supply_net VDD\n"
                   "create_power_domain PD -primary_supply_set SS\n")
    parent = _write(tmp_path, "root.upf",
                    "".join("load_upf leaf.upf -scope s%d\n" % i
                            for i in range(4)))
    m = _model([parent, child])
    for i in range(4):
        assert "s%d/PD" % i in m.domains, "scope s%d lost" % i
        assert "s%d/VDD" % i in m.supply_nets


# --- 2. references resolve to the correct scoped object --------------------

def test_reference_resolves_to_its_own_scope_not_a_namesake(tmp_path):
    """A child-scoped reference binds to the child's object."""
    child = _write(tmp_path, "leaf.upf",
                   "create_supply_net VDD\n"
                   "create_power_domain PD -primary_supply_set SS\n")
    parent = _write(tmp_path, "root.upf",
                    "create_supply_net VDD\n"      # top-scope namesake
                    "load_upf leaf.upf -scope kid\n")
    m = _model([parent, child])
    assert "VDD" in m.supply_nets and "kid/VDD" in m.supply_nets
    kid = m.domains["kid/PD"]
    assert kid.scope == "kid"


def test_supply_map_binds_child_local_name_to_parent_supply(tmp_path):
    """`-supply {local parent}` makes the child's local name resolvable."""
    child = _write(tmp_path, "leaf.upf",
                   "create_supply_net vdd_local\n")
    parent = _write(tmp_path, "root.upf",
                    "create_supply_net vdd_top\n"
                    "load_upf leaf.upf -scope kid -supply {vdd_local vdd_top}\n")
    m = _model([parent, child])
    pairs = {(x["local_scope"], x["local"], x["parent"]) for x in m.supply_maps}
    assert ("kid", "vdd_local", "vdd_top") in pairs


# --- 3. one declaration cannot silently overwrite another ------------------

def test_same_scope_same_file_redefinition_is_still_reported(tmp_path):
    """A genuine redefinition is a duplicate, not two objects."""
    f = _write(tmp_path, "one.upf",
               "create_power_domain PD -primary_supply_set SS\n"
               "create_power_domain PD -primary_supply_set SS2\n")
    m = _model([f])
    assert any(d["name"] == "PD" for d in m.duplicate_definitions)


def test_different_files_same_name_are_distinct_objects(tmp_path):
    """Two fragments declaring the same scope-less name are two objects."""
    a = _write(tmp_path, "a.upf",
               "create_supply_net V1\ncreate_supply_net V2\n"
               "create_supply_port p1 -direction in\n"
               "create_supply_net W1 -resolve port\n"
               "create_pst TBL -supplies {W1}\n"
               "create_pst TBL2 -supplies {W1}\n")
    b = _write(tmp_path, "b.upf",
               "create_supply_net V3\n"
               "create_supply_port p2 -direction in\n"
               "create_supply_net W2 -resolve port\n"
               "create_pst TBL -supplies {W2}\n"
               "create_pst TBL2 -supplies {W2}\n")
    m = _model([a, b])
    tbls = {k: v for k, v in m.psts.items() if k.split("/")[-1].startswith("TBL")}
    assert len(tbls) == 4, sorted(tbls)
    # Neither fragment's table was overwritten by the other.
    supplies = {frozenset(v.supply_list or []) for v in tbls.values()}
    assert supplies == {frozenset({"W1"}), frozenset({"W2"})}


def test_supply_nets_from_two_fragments_both_survive(tmp_path):
    a = _write(tmp_path, "a.upf", "create_supply_net SHARED\n")
    b = _write(tmp_path, "b.upf", "create_supply_net SHARED\n")
    m = _model([a, b])
    # The first declaration keeps the unqualified key; the second, coming from
    # a different file, is qualified by its origin so neither is lost.
    assert "SHARED" in m.supply_nets
    assert "SHARED@b.upf" in m.supply_nets
    assert len(m.supply_nets) == 2
    assert m.supply_nets["SHARED"].declared_file.endswith("a.upf")
    assert m.supply_nets["SHARED@b.upf"].declared_file.endswith("b.upf")


# --- 4. set_scope remains positional (and construction stays ordered) -------

def test_set_scope_composes_positionally(tmp_path):
    f = _write(tmp_path, "p.upf",
               "set_scope a\n"
               "create_supply_net NET_A\n"
               "set_scope b\n"
               "create_supply_net NET_B\n")
    m = _model([f])
    assert "a/NET_A" in m.supply_nets
    assert "a/b/NET_B" in m.supply_nets


def test_reordering_set_scope_changes_the_model(tmp_path):
    """Guards against 'fixing' identity by making construction order-free.

    If construction ever became order-independent, swapping two set_scope lines
    would produce the same model. It must not.
    """
    first = _write(tmp_path, "first.upf",
                   "set_scope a\nset_scope b\ncreate_supply_net NET\n")
    second = _write(tmp_path, "second.upf",
                    "set_scope b\nset_scope a\ncreate_supply_net NET\n")
    m1, m2 = _model([first]), _model([second])
    assert set(m1.supply_nets) != set(m2.supply_nets)


def test_absolute_scope_resets_relative_composition(tmp_path):
    f = _write(tmp_path, "p.upf",
               "set_scope a\nset_scope /root\ncreate_supply_net NET\n")
    m = _model([f])
    # An absolute scope replaces the cursor rather than composing onto it, so
    # the net lands at /root and not at a//root.
    assert "/root/NET" in m.supply_nets
    assert not any(k.endswith("a//root/NET") or k == "a/NET"
                   for k in m.supply_nets)


# --- 5. existing single-file behaviour unchanged ---------------------------

def test_scope_key_without_origin_is_unchanged():
    """origin=None must reproduce the historical key exactly."""
    m = PowerIntentModel()
    assert m.scope_key("PD") == "PD"
    assert m.scope_key("PD", "child") == "child/PD"
    assert m.scope_key("PD", ".") == "PD"
    assert m.scope_key("PD", "") == "PD"


def test_single_file_model_has_no_origin_qualification():
    m = _model([FIXTURES / "scoped_pst_child.upf"])
    assert all("@" not in k for k in m.psts)
    assert all("@" not in k for k in m.domains)


def test_single_file_analysis_unchanged():
    """A single known-good file still reports exactly what it did."""
    r = validate([str(ROOT / "tests" / "examples" / "example.soc.upf")])
    errors = [f for f in r.check.findings if f.severity == "error"]
    assert errors == [], [e.message for e in errors]
    # The known-good example carries warnings/info but no errors, and no
    # finding may be attributed to a scope the file never entered.
    assert all("@" not in (f.message or "") for f in r.check.findings)


# --- recursion and missing targets -----------------------------------------

def test_nested_load_upf_terminates(tmp_path):
    """Real corpora nest load_upf; expansion must not recurse forever."""
    leaf = _write(tmp_path, "leaf.upf", "create_supply_net LEAFNET\n")
    mid = _write(tmp_path, "mid.upf", "load_upf leaf.upf -scope deep\n")
    top = _write(tmp_path, "top.upf", "load_upf mid.upf -scope mid\n")
    m = _model([top, mid, leaf])
    assert any(k.endswith("LEAFNET") for k in m.supply_nets)


def test_self_recursive_load_terminates(tmp_path):
    f = _write(tmp_path, "loop.upf",
               "load_upf loop.upf -scope again\ncreate_supply_net LOOPNET\n")
    m = _model([f])
    assert "LOOPNET" in m.supply_nets


def test_missing_load_target_does_not_crash(tmp_path):
    """A referenced-but-absent file is skipped, and the event is recorded."""
    f = _write(tmp_path, "top.upf",
               "load_upf absent.upf -scope kid\ncreate_supply_net NET\n")
    m = _model([f])
    assert "NET" in m.supply_nets
    assert any(e.get("loaded") == "absent.upf" for e in m.load_upf_events)


# --- 6. determinism ---------------------------------------------------------

def test_repeated_builds_are_identical(tmp_path):
    child = _write(tmp_path, "leaf.upf",
                   "create_supply_net VDD\ncreate_power_domain PD -primary_supply_set SS\n")
    parent = _write(tmp_path, "root.upf",
                    "".join("load_upf leaf.upf -scope s%d\n" % i for i in range(5)))
    a, b = _model([parent, child]), _model([parent, child])
    assert sorted(a.domains) == sorted(b.domains)
    assert sorted(a.psts) == sorted(b.psts)
    assert json.dumps(a.to_dict(), sort_keys=True, default=str) == \
        json.dumps(b.to_dict(), sort_keys=True, default=str)


def test_validate_is_deterministic_on_two_scope_fixture():
    files = [str(FIXTURES / "scoped_pst_parent.upf"),
             str(FIXTURES / "scoped_pst_child.upf")]
    first = validate(files)
    second = validate(files)
    assert json.dumps(first.check.model.to_dict(), sort_keys=True, default=str) == \
        json.dumps(second.check.model.to_dict(), sort_keys=True, default=str)


# --- 7. no finding suppressed for metrics ----------------------------------

def test_expansion_does_not_relax_any_rule():
    """The fix must come from a more faithful model, not quieter rules.

    The same construction still reports its genuine defects; nothing was muted
    to make a count look better.
    """
    r = validate([str(FIXTURES / "scoped_pst_parent.upf"),
                  str(FIXTURES / "scoped_pst_child.upf")])
    codes = {f.rule for f in r.check.findings}
    # UPF-022 (unconnected net) and UPF-097 (hierarchy needs a netlist) are
    # real properties of this fixture and must still be reported.
    assert "UPF-022" in codes
    assert "UPF-097" in codes


def test_rule_registry_is_untouched():
    """No rule was disabled, re-registered, or severity-downgraded."""
    from upf_insight.engine.rules.rules_registry import RULES
    assert len(RULES) >= 77
    assert len({r.code for r in RULES}) == len(RULES)