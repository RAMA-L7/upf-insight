"""Flat + hierarchical power-intent sprint regression tests.

Covers the sprint acceptance criteria: flat multi-domain generation with
AON/switchable classification, hierarchical generation with per-child domain
ownership and load_upf supply mapping, round-trip into the canonical model,
supply-map validation rules, report exposure and determinism.
"""

import json
import os
import tempfile

from upf_insight.engine.engine import validate
from upf_insight.generate.generator import (
    UPFParams,
    DomainParam,
    SwitchParam,
    RelationParam,
    generate_upf,
    generate_project,
)
from upf_insight.report.reporter import format_html, format_text

EXAMPLES = "tests/examples"


def _validate_fixture(*files):
    return validate([os.path.join(EXAMPLES, f) for f in files])


# ── Fixture 2: flat multi-domain (AON + A/B/C switchable + SRAM) ──────────

def test_flat_multidomain_fixture_types_and_relations():
    rel = _validate_fixture("flat_multidomain/flat_multidomain.upf").relations
    assert rel.architecture == "FLAT"
    types = {d.name: d.type for d in rel.domains}
    assert types == {"PD_AON": "ALWAYS_ON", "PD_A": "SWITCHABLE",
                     "PD_B": "SWITCHABLE", "PD_C": "SWITCHABLE",
                     "PD_SRAM": "ALWAYS_ON"}
    labels = {(r.from_domain, r.to_domain): r.label for r in rel.relations}
    # switch relations: AON anchors each gated domain
    assert labels[("PD_AON", "PD_A")] == "SW"
    assert labels[("PD_AON", "PD_B")] == "SW"
    assert labels[("PD_AON", "PD_C")] == "SW"
    # isolation relations clamp via the always-on AON supply
    assert "ISO" in labels[("PD_A", "PD_AON")]
    assert "ISO" in labels[("PD_B", "PD_AON")]
    # every relation carries provenance
    for r in rel.relations:
        assert r.evidence and r.evidence[0].line


def test_flat_multidomain_fixture_no_errors():
    result = _validate_fixture("flat_multidomain/flat_multidomain.upf")
    errors = [x for x in result.check.findings if x.severity == "error"]
    assert not errors, [e.message for e in errors]


def test_flat_multidomain_fixture_supply_sharing_separate_from_relations():
    rel = _validate_fixture("flat_multidomain/flat_multidomain.upf").relations
    # vss is shared infrastructure - a supply network row, never a matrix cell
    assert "vss" in rel.supply_sharing
    assert set(rel.supply_sharing["vss"]) == {"PD_A", "PD_AON", "PD_B",
                                              "PD_C", "PD_SRAM"}
    labels = {r.label for r in rel.relations}
    assert "SUP" not in labels


# ── Fixture 3: hierarchical project (top + children + supply maps) ────────

def test_hierarchical_fixture_architecture_and_ownership():
    rel = _validate_fixture("hierarchical/top.upf",
                            "hierarchical/core_a.upf",
                            "hierarchical/core_b.upf",
                            "hierarchical/sram.upf").relations
    assert rel.architecture == "HIERARCHICAL"
    types = {d.name: d.type for d in rel.domains}
    assert types["PD_AON"] == "ALWAYS_ON"
    assert types["core_a/PD_A"] == "SWITCHABLE"
    assert types["core_b/PD_B"] == "SWITCHABLE"
    assert types["sram/PD_SRAM"] == "ALWAYS_ON"
    # per-file ownership resolves from the load order
    rows = {h["domain"]: h for h in rel.hierarchy}
    assert rows["core_a/PD_A"]["upf_file"] == "core_a.upf"
    assert rows["core_b/PD_B"]["upf_file"] == "core_b.upf"
    assert rows["sram/PD_SRAM"]["upf_file"] == "sram.upf"
    # load_upf supply maps are recorded
    assert len(rel.supply_maps) == 6
    assert {"local": "vdd_aon", "parent": "vdd_aon"} in [
        {k: m[k] for k in ("local", "parent")} for m in rel.supply_maps
    ]
    # switch relations cross the AON anchor into each gated child domain
    labels = {(r.from_domain, r.to_domain) for r in rel.relations}
    assert ("PD_AON", "core_a/PD_A") in labels
    assert ("PD_AON", "core_b/PD_B") in labels


def test_hierarchical_fixture_no_errors():
    result = _validate_fixture("hierarchical/top.upf",
                               "hierarchical/core_a.upf",
                               "hierarchical/core_b.upf",
                               "hierarchical/sram.upf")
    errors = [x for x in result.check.findings if x.severity == "error"]
    assert not errors, [e.message for e in errors]


# ── Unknown-evidence fixture (spec fixture 5): nothing inferred ───────────

def test_unknown_evidence_domains_are_unknown():
    p = UPFParams(design_top="top",
                  domains=[DomainParam("PD_A"), DomainParam("PD_B")])
    result = validate([_tmp_write(p)])
    types = {d.name: d.type for d in result.relations.domains}
    assert types == {"PD_A": "UNKNOWN", "PD_B": "UNKNOWN"}
    # no relations can be proven without switch/strategy evidence
    assert result.relations.relations == []


def _tmp_write(params: UPFParams) -> str:
    fd, path = tempfile.mkstemp(suffix=".upf")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(generate_upf(params))
    return path


# ── Generation round-trips ────────────────────────────────────────────────

def test_flat_generation_round_trip_matrix():
    """Acceptance A/D: generated flat intent round-trips and the matrix shows
    the declared interactions without confusing shared supplies."""
    p = UPFParams(
        design_top="top", primary_power="vdd_aon", primary_ground="vss",
        domains=[
            DomainParam("PD_AON", elements="u_aon", primary_power="vdd_aon",
                        domain_type="always_on"),
            DomainParam("PD_A", elements="u_a", primary_power="vdd_a_sw",
                        domain_type="switchable"),
            DomainParam("PD_SRAM", elements="u_sram", primary_power="vdd_mem",
                        domain_type="always_on"),
        ],
        switches=[SwitchParam("PSW_A", "PD_A", "vdd_aon", "vdd_a_sw",
                              "a_pwr_en")],
        relations=[RelationParam("PD_A", "PD_SRAM", "isolation,level_shift")],
    )
    rel = validate([_tmp_write(p)]).relations
    labels = {(r.from_domain, r.to_domain): r.label for r in rel.relations}
    assert labels[("PD_A", "PD_SRAM")] == "ISO+LS"
    assert labels[("PD_AON", "PD_A")] == "SW"
    # generated UPF must not carry duplicate definitions or self-located
    # boundary strategies in switchable domains
    result = validate([_tmp_write(p)])
    rules = {x.rule for x in result.check.findings}
    assert "UPF-013" not in rules
    assert "UPF-041" not in rules
    assert "UPF-063" not in rules


def test_hierarchical_generation_round_trip_ownership():
    """Acceptance B/C: generated hierarchical project round-trips with correct
    architecture, per-child ownership and file provenance."""
    p = UPFParams(
        design_top="top", primary_power="vdd_aon", primary_ground="vss",
        architecture="hierarchical", hierarchy=["core_a", "core_b"],
        domains=[
            DomainParam("PD_AON", elements="u_aon", primary_power="vdd_aon",
                        domain_type="always_on"),
            DomainParam("PD_A", elements="core_a", primary_power="vdd_a_sw",
                        domain_type="switchable"),
            DomainParam("PD_B", elements="core_b", primary_power="vdd_b_sw",
                        domain_type="switchable"),
        ],
        switches=[SwitchParam("PSW_A", "PD_A", "vdd_aon", "vdd_a_sw",
                              "a_pwr_en"),
                  SwitchParam("PSW_B", "PD_B", "vdd_aon", "vdd_b_sw",
                              "b_pwr_en")],
    )
    proj = generate_project(p)
    assert set(proj) == {"top.upf", "core_a.upf", "core_b.upf"}
    assert "load_upf core_a.upf -scope core_a" in proj["top.upf"]
    assert "load_upf core_b.upf -scope core_b" in proj["top.upf"]
    assert "create_power_domain PD_A -elements {core_a}" in proj["core_a.upf"]
    assert "create_power_domain PD_B -elements {core_b}" in proj["core_b.upf"]
    assert "create_power_domain PD_AON" in proj["top.upf"]
    # deterministic: identical project bytes across runs
    assert generate_project(p) == proj
    with tempfile.TemporaryDirectory() as td:
        for name, text in proj.items():
            with open(os.path.join(td, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        result = validate([os.path.join(td, "top.upf"),
                           os.path.join(td, "core_a.upf"),
                           os.path.join(td, "core_b.upf")])
        rel = result.relations
        assert rel.architecture == "HIERARCHICAL"
        rows = {h["domain"]: h for h in rel.hierarchy}
        assert rows["core_a/PD_A"]["upf_file"] == "core_a.upf"
        assert rows["core_b/PD_B"]["upf_file"] == "core_b.upf"
        types = {d.name: d.type for d in rel.domains}
        assert types["core_a/PD_A"] == "SWITCHABLE"
        assert types["core_b/PD_B"] == "SWITCHABLE"
        assert types["PD_AON"] == "ALWAYS_ON"
        # supply maps from the generated load_upf lines
        assert len(rel.supply_maps) == 4


# ── Validation rules: supply map + loaded file ────────────────────────────

def test_supply_map_rule_fires_for_undefined_parent():
    upf = (
        "upf_version 3.0\n"
        "set_design_top top\n"
        "create_supply_net vdd -resolve port\n"
        "set_scope child\n"
        "load_upf child.upf -scope child -supply {vdd_missing vdd_ghost}\n"
        "set_scope .\n"
    )
    result = validate([_tmp_text(upf)])
    f099 = [x for x in result.check.findings if x.rule == "UPF-099"]
    assert f099, "UPF-099 must fire when a supply-map side is undefined"
    assert f099[0].severity == "error"
    assert f099[0].line


def test_loaded_upf_missing_rule():
    upf = (
        "upf_version 3.0\n"
        "set_design_top top\n"
        "set_scope child\n"
        "load_upf child.upf -scope child\n"
        "set_scope .\n"
    )
    result = validate([_tmp_text(upf)])
    f100 = [x for x in result.check.findings if x.rule == "UPF-100"]
    assert f100 and f100[0].severity == "warning"
    assert "child.upf" in f100[0].message


def _tmp_text(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".upf")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


# ── Report / CLI exposure ─────────────────────────────────────────────────

def test_report_text_exposes_architecture_and_relations():
    result = _validate_fixture("flat_multidomain/flat_multidomain.upf")
    text = format_text(result)
    assert "Architecture : FLAT" in text
    assert "always-on" in text and "switchable" in text
    assert "Supply sharing:" in text
    assert "Hierarchy     :" in text


def test_report_html_includes_relations_matrix_and_supply():
    result = _validate_fixture("flat_multidomain/flat_multidomain.upf")
    html = format_html(result)
    assert "Power-domain relations" in html
    assert "Domain relation matrix" in html
    assert "Supply network" in html
    assert "Domain ownership" in html
    assert "PD_AON" in html


def test_relations_json_deterministic():
    a = _validate_fixture("flat_multidomain/flat_multidomain.upf")
    b = _validate_fixture("flat_multidomain/flat_multidomain.upf")
    assert json.dumps(a.relations.to_dict(), sort_keys=True) == json.dumps(
        b.relations.to_dict(), sort_keys=True)
    d = a.to_dict()["relations"]
    assert "supply_maps" in d
    assert "hierarchy" in d
    assert "matrix" in d


# ── Hierarchical round-trip: scoped switches, strategies, load_upf ────────

def _build_hier_project():
    p = UPFParams(
        design_top="top", primary_power="vdd", primary_ground="vss",
        architecture="hierarchical",
        hierarchy=["core_a", "core_b", "sram"],
        domains=[
            DomainParam("core_a", elements="u_a", primary_power="vdd_core_sw",
                        domain_type="switchable"),
            DomainParam("core_b", elements="u_b", primary_power="vdd_core_sw",
                        domain_type="switchable"),
            DomainParam("sram", elements="u_sram", primary_power="vdd_sram",
                        domain_type="always_on"),
        ],
        switches=[
            SwitchParam("sw_a", "core_a", "vdd_aon", "vdd_core_sw", "pg_en"),
            SwitchParam("sw_b", "core_b", "vdd_aon", "vdd_core_sw", "pg_en"),
        ],
        relations=[
            RelationParam("core_a", "sram", "isolation,level_shift"),
            RelationParam("core_b", "sram", "isolation"),
        ],
    )
    return generate_project(p)


def test_hierarchical_scoped_switch_relations_never_cross_resolve():
    """Same-named switched supplies in sibling scopes must resolve to their
    own domains - regression for the suffix-match cross-resolution bug where
    sw_b's output vdd_core_sw resolved to core_a."""
    proj = _build_hier_project()
    with tempfile.TemporaryDirectory() as td:
        for name, text in proj.items():
            with open(os.path.join(td, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        rel = validate([os.path.join(td, "top.upf"),
                        os.path.join(td, "core_a.upf"),
                        os.path.join(td, "core_b.upf"),
                        os.path.join(td, "sram.upf")]).relations
        labels = {(r.from_domain, r.to_domain): r.label for r in rel.relations}
        # each gated domain is anchored by the always-on infrastructure
        assert labels.get(("sram/sram", "core_a/core_a")) == "SW"
        assert labels.get(("sram/sram", "core_b/core_b")) == "SW"
        # cross-domain strategies: core_a->sram ISO+LS, core_b->sram ISO
        assert labels.get(("core_a/core_a", "sram/sram")) == "ISO+LS"
        assert labels.get(("core_b/core_b", "sram/sram")) == "ISO"


def test_hierarchical_load_upf_from_top_scope_no_false_undefined():
    """load_upf runs in the top scope and -supply maps resolve against the
    top-level supplies - regression for false UPF-010 errors when set_scope
    preceded load_upf."""
    proj = _build_hier_project()
    assert "set_scope core_a" not in proj["top.upf"].split("load_upf")[0]
    with tempfile.TemporaryDirectory() as td:
        for name, text in proj.items():
            with open(os.path.join(td, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        result = validate([os.path.join(td, "top.upf"),
                           os.path.join(td, "core_a.upf"),
                           os.path.join(td, "core_b.upf"),
                           os.path.join(td, "sram.upf")])
        errors = [x for x in result.check.findings if x.severity == "error"]
        assert not errors, [e.message for e in errors]
        # supply maps carry the child scope and the parent-scope reference
        maps = result.relations.supply_maps
        assert any(m["local_scope"] == "core_a" and m["parent"] == "vdd_aon"
                   for m in maps)


def test_hierarchical_strategy_scope_attribution():
    """Strategies declared in child scopes carry that scope, and supply
    lookups resolve in it - regression for lookups using the model's final
    current scope."""
    proj = _build_hier_project()
    with tempfile.TemporaryDirectory() as td:
        for name, text in proj.items():
            with open(os.path.join(td, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        res = validate([os.path.join(td, "top.upf"),
                        os.path.join(td, "core_a.upf"),
                        os.path.join(td, "core_b.upf"),
                        os.path.join(td, "sram.upf")])
        m = res.check.model
        scopes = {i.domain: i.scope for i in m.isolation}
        assert scopes == {"core_a": "core_a", "core_b": "core_b"}
        # the isolation supply (sram's power) resolves across scopes for the
        # relation derivation
        rel = res.relations
        labels = {(r.from_domain, r.to_domain): r.label for r in rel.relations}
        assert labels.get(("core_a/core_a", "sram/sram")) == "ISO+LS"
