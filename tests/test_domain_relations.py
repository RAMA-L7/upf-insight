"""Domain-relations tests - canonical relation graph, matrix, generator
relations, hierarchical projects, and determinism.

The relation graph must always be derived from the canonical model: no
UI-side inference, no fabricated relationships. UNKNOWN cells are the honest
answer when the model has no evidence.
"""

import json

from upf_insight.engine.engine import validate
from upf_insight.generate.generator import (
    UPFParams,
    DomainParam,
    SwitchParam,
    IsolationParam,
    LevelShifterParam,
    RelationParam,
    generate_upf,
    generate_project,
)
from upf_insight.model.relations import derive_domain_relations
from upf_insight.preprocess.upf_preprocess import preprocess

EXAMPLES = "tests/examples"


def _gen(params: UPFParams):
    return validate([_tmp_write(params)])


def _tmp_write(params: UPFParams) -> str:
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".upf")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(generate_upf(params))
    return path


# ── Domain types ──────────────────────────────────────────────────────────

def test_domain_type_never_inferred_from_switch_absence():
    """A domain without a switch must be UNKNOWN, not ALWAYS_ON."""
    p = UPFParams(design_top="top",
                  domains=[DomainParam("core"), DomainParam("mem")])
    rel = _gen(p).relations
    types = {d.name: d.type for d in rel.domains}
    assert types == {"core": "UNKNOWN", "mem": "UNKNOWN"}


def test_domain_type_switchable_from_switch():
    """A domain fed by a power switch output is SWITCHABLE."""
    p = UPFParams(
        design_top="top",
        domains=[DomainParam("core", primary_power="vdd_sw", domain_type="switchable"),
                 DomainParam("aon", primary_power="vdd", domain_type="always_on")],
        switches=[SwitchParam("sw_core", "core", "vdd", "vdd_sw", "pwr_ok")],
    )
    rel = _gen(p).relations
    types = {d.name: d.type for d in rel.domains}
    assert types["core"] == "SWITCHABLE"
    assert types["aon"] == "ALWAYS_ON"


def test_domain_type_always_on_explicit_declaration():
    """ALWAYS_ON only when explicitly declared - never a default."""
    p = UPFParams(design_top="top",
                  domains=[DomainParam("aon", domain_type="always_on"),
                           DomainParam("core")])
    rel = _gen(p).relations
    types = {d.name: d.type for d in rel.domains}
    assert types["aon"] == "ALWAYS_ON"
    assert types["core"] == "UNKNOWN"


# ── Relations / matrix ────────────────────────────────────────────────────

def test_cpu_subsys_relations_have_switch_and_level_shift_evidence():
    result = validate([f"{EXAMPLES}/cpu_subsys/cpu_subsys_v1.upf"])
    rel = result.relations
    labels = {(r.from_domain, r.to_domain): r.label for r in rel.relations}
    assert ("PD_AO", "PD_CPU") in labels
    assert labels[("PD_AO", "PD_CPU")] == "SW"
    # PD_IO level-shifts toward every other domain (different supplies)
    assert labels.get(("PD_IO", "PD_CPU")) == "LS"
    # every relation carries provenance
    for r in rel.relations:
        assert r.evidence, f"relation {r.from_domain}->{r.to_domain} has no evidence"
        assert r.evidence[0].line, "evidence must carry a source line"


def test_matrix_is_square_deterministic_and_sorted():
    result = validate([f"{EXAMPLES}/cpu_subsys/cpu_subsys_v1.upf"])
    rel = result.relations
    names = [d.name for d in rel.domains]
    assert names == sorted(names)
    assert set(rel.matrix.keys()) == set(names)
    for f in names:
        assert set(rel.matrix[f].keys()) == set(names)
        assert rel.matrix[f][f] == "-"
    # serialization is deterministic across runs
    again = validate([f"{EXAMPLES}/cpu_subsys/cpu_subsys_v1.upf"])
    assert json.dumps(rel.to_dict(), sort_keys=True) == json.dumps(
        again.relations.to_dict(), sort_keys=True)


def test_matrix_empty_cells_are_honest():
    """Cells without proven interaction stay empty ("") - sharing a supply
    is NOT a domain interaction, so untouched pairs must not read SUP or
    UNKNOWN as if they were a relationship."""
    result = validate([f"{EXAMPLES}/cpu_subsys/cpu_subsys_v1.upf"])
    rel = result.relations
    for r in rel.relations:
        assert rel.matrix[r.from_domain][r.to_domain] == r.label
    # PD_SRAM and PD_CPU share ground VSS but have no crossing evidence
    assert rel.matrix["PD_SRAM"]["PD_CPU"] == ""
    # supply sharing is a separate view, never a cell
    assert "SUP" not in {r.label for r in rel.relations}
    assert "vss" in rel.supply_sharing
    assert "PD_SRAM" in rel.supply_sharing["vss"]
    assert "PD_CPU" in rel.supply_sharing["vss"]


# ── Generator relations ───────────────────────────────────────────────────

def test_generate_with_relations_is_deterministic():
    p = UPFParams(
        design_top="top",
        domains=[DomainParam("core", primary_power="vdd_sw", domain_type="switchable"),
                 DomainParam("mem", primary_power="vdd"),
                 DomainParam("aon", primary_power="vdd", domain_type="always_on")],
        switches=[SwitchParam("sw_core", "core", "vdd", "vdd_sw", "pwr_ok")],
        relations=[RelationParam("aon", "core", "switch"),
                   RelationParam("core", "mem", "isolation,level_shift")],
    )
    a = generate_upf(p)
    b = generate_upf(p)
    assert a == b
    assert "# relation aon -> core: switch" in a
    assert "# relation core -> mem: isolation, level_shift" in a
    # The relation editor now synthesizes the REAL strategy commands that
    # make each selected semantics true: set_isolation / set_level_shifter
    # for the isolation,level_shift relation, and the switch is already
    # generated from the switch parameters.
    assert "set_isolation iso_core_to_mem -domain core -isolation_supply vdd " in a
    assert "set_level_shifter ls_core_to_mem -domain core -location parent " in a
    # relations survive the round trip into the canonical model: the switch
    # makes aon -> core a real cross-domain interaction, the synthesized
    # level shifter makes core -> mem a real level-shift interaction, and
    # sharing vdd alone is NOT a relation (supply sharing is separate).
    rel = _gen(p).relations
    pairs = {(r.from_domain, r.to_domain) for r in rel.relations}
    assert ("aon", "core") in pairs
    assert ("core", "mem") in pairs  # real LS evidence, not shared supply
    assert "vdd" in rel.supply_sharing
    assert set(rel.supply_sharing["vdd"]) >= {"mem", "aon"}
    assert "SUP" not in {r.label for r in rel.relations}


def test_generate_rejects_unknown_relation_domains():
    p = UPFParams(design_top="top",
                  domains=[DomainParam("core")],
                  relations=[RelationParam("ghost", "core", "switch")])
    try:
        generate_upf(p)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "unknown from-domain" in str(exc)


# ── Hierarchical generation ───────────────────────────────────────────────

def test_hierarchical_project_files_and_determinism():
    p = UPFParams(design_top="top", primary_power="vdd", primary_ground="vss",
                  domains=[DomainParam("core_a", elements="core_a"),
                           DomainParam("core_b", elements="core_b")],
                  architecture="hierarchical", hierarchy=["core_a", "core_b"])
    proj = generate_project(p)
    assert set(proj.keys()) == {"top.upf", "core_a.upf", "core_b.upf"}
    assert "load_upf core_a.upf -scope core_a" in proj["top.upf"]
    assert "load_upf core_b.upf -scope core_b" in proj["top.upf"]
    # each child owns its own domain in its own scope - no shared first-domain
    # fallback, no duplicate definitions across files
    assert "create_power_domain core_a -elements {core_a}" in proj["core_a.upf"]
    assert "create_power_domain core_b -elements {core_b}" in proj["core_b.upf"]
    assert "set_scope core_a" in proj["core_a.upf"]
    assert "set_scope core_b" in proj["core_b.upf"]
    # deterministic
    assert generate_project(p) == proj
    # round-trips: architecture reported as HIERARCHICAL with 3 files, per-file
    # ownership resolved from the load order
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as td:
        for name, text in proj.items():
            with open(os.path.join(td, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        result = validate([os.path.join(td, "top.upf"),
                           os.path.join(td, "core_a.upf"),
                           os.path.join(td, "core_b.upf")])
        assert result.relations.architecture == "HIERARCHICAL"
        assert len(result.relations.files) == 3
        # child domains keep their own names (scoped keys) and own files -
        # no shared first-domain fallback, ownership resolved from load order
        names = {d.name for d in result.relations.domains}
        assert names >= {"core_a/core_a", "core_b/core_b"}
        rows = {h["domain"]: h for h in result.relations.hierarchy}
        assert rows["core_a/core_a"]["upf_file"] == "core_a.upf"
        assert rows["core_b/core_b"]["upf_file"] == "core_b.upf"


# ── API / to_dict exposure ────────────────────────────────────────────────

def test_relations_exposed_in_result_dict():
    result = validate([f"{EXAMPLES}/cpu_subsys/cpu_subsys_v1.upf"])
    d = result.to_dict()
    assert "relations" in d
    assert d["relations"]["architecture"] == "FLAT"
    assert len(d["relations"]["domains"]) == 4


def test_derive_domain_relations_none_model():
    rel = derive_domain_relations(None)
    assert rel.domains == [] and rel.relations == []
    assert rel.to_dict()["architecture"] == "FLAT"
