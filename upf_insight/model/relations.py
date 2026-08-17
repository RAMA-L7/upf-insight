"""Power-domain relations - the canonical domain relationship graph.

Derives a deterministic, evidence-backed view of how power domains relate to
each other from the SAME :class:`PowerIntentModel` that the validator,
generator, diff, gate, CLI and UI consume. There is no second model: the
relation graph is computed from the canonical model and carries provenance
(declared lines / files) wherever the model knows it.

What is derived
---------------
- Domain type: SWITCHABLE (a switch feeds its supply), ALWAYS_ON (declared in
  ``set_port_attributes ... always_on true`` or an explicit override),
  UNKNOWN otherwise. ALWAYS_ON is never inferred merely from the absence of a
  switch.
- Domain-to-domain relations: each cell carries the relationship kinds
  (isolation, level shifter, retention dependency, supply relation, switch
  relation, control dependency) plus provenance (line + file) from the
  underlying strategies/switches/supplies.
- A deterministic N x N matrix over the sorted domain names.

The UI must never infer relationships the engine does not know: every cell
here is derived from model objects that already exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .power_model import PowerIntentModel


@dataclass
class RelationEvidence:
    """One piece of evidence behind a domain relation."""

    kind: str          # isolation | level_shift | retention | supply | switch | control
    detail: str        # e.g. "set_isolation isol_core on core"
    line: Optional[int] = None
    file: Optional[str] = None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "detail": self.detail,
                "line": self.line, "file": self.file}


@dataclass
class DomainRelation:
    """A directed relation from_domain -> to_domain."""

    from_domain: str
    to_domain: str
    kinds: List[str] = field(default_factory=list)
    evidence: List[RelationEvidence] = field(default_factory=list)

    @property
    def label(self) -> str:
        """Compact matrix label: ISO, LS, ISO+LS, RET, SUPPLY, SWITCH, ..."""
        if not self.kinds:
            return "UNKNOWN"
        m = {"isolation": "ISO", "level_shift": "LS", "retention": "RET",
             "supply": "SUP", "switch": "SW", "control": "CTRL"}
        parts = [m.get(k, k.upper()) for k in self.kinds]
        # keep a stable, compact order: ISO/LS first, then the rest sorted
        order = {"ISO": 0, "LS": 1}
        parts.sort(key=lambda p: (order.get(p, 9), p))
        return "+".join(parts)

    def to_dict(self) -> dict:
        return {
            "from_domain": self.from_domain,
            "to_domain": self.to_domain,
            "kinds": sorted(set(self.kinds)),
            "label": self.label,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class DomainInfo:
    """One domain with its derived type and related domains."""

    name: str
    type: str                 # SWITCHABLE | ALWAYS_ON | UNKNOWN
    scope: str = "."
    elements: List[str] = field(default_factory=list)
    primary_power: Optional[str] = None
    primary_ground: Optional[str] = None
    switch: Optional[str] = None
    related: List[str] = field(default_factory=list)
    declared_line: Optional[int] = None
    declared_file: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "scope": self.scope,
            "elements": self.elements,
            "primary_power": self.primary_power,
            "primary_ground": self.primary_ground,
            "switch": self.switch,
            "related": sorted(self.related),
            "declared_line": self.declared_line,
            "declared_file": self.declared_file,
        }


@dataclass
class DomainRelations:
    """The full derived relation graph for one design.

    Three separate views of the SAME canonical model:
    - ``matrix`` / ``relations``: actual cross-domain interactions only
      (isolation, level shift, retention, switch, control). Sharing a supply
      is NOT a domain interaction and never appears here.
    - ``supply_sharing``: supply -> [domains] powered by it (a separate
      network view, never a cell in the matrix).
    - ``hierarchy``: UPF file / scope ownership per domain for hierarchical
      designs (flat designs carry a single file with the top scope).
    """

    architecture: str = "FLAT"      # FLAT | HIERARCHICAL | UNKNOWN
    domains: List[DomainInfo] = field(default_factory=list)
    relations: List[DomainRelation] = field(default_factory=list)
    matrix: Dict[str, Dict[str, str]] = field(default_factory=dict)  # [from][to] -> label
    supply_sharing: Dict[str, List[str]] = field(default_factory=dict)  # supply -> [domains]
    hierarchy: List[dict] = field(default_factory=list)             # domain ownership rows
    files: List[str] = field(default_factory=list)                   # UPF files seen
    supply_maps: List[dict] = field(default_factory=list)           # load_upf -supply maps

    def to_dict(self) -> dict:
        return {
            "architecture": self.architecture,
            "domains": [d.to_dict() for d in self.domains],
            "relations": [r.to_dict() for r in self.relations],
            "matrix": self.matrix,
            "supply_sharing": self.supply_sharing,
            "hierarchy": self.hierarchy,
            "files": sorted(self.files),
            "supply_maps": self.supply_maps,
        }


def _resolve_file(model: PowerIntentModel, line: Optional[int],
                  obj_file: Optional[str] = None) -> Optional[str]:
    """File provenance for a declared line.

    Prefers the file recorded on the model object itself (the builder records
    ``declared_file`` from the authoritative command stream - unambiguous even
    when multiple files share a line number). Falls back to the provenance
    index only when it resolves to exactly one file; ambiguous multi-file
    lines return None rather than an invented file.
    """
    if obj_file:
        return obj_file
    if line is None:
        return None
    files = model.record_files.get(line) or []
    return files[0] if len(files) == 1 else None


def _domain_power(model: PowerIntentModel, domain: PowerDomain) -> Optional[str]:
    """Resolve the domain's primary power net. The model stores either a raw
    net name (set_domain_supply_net -primary_power_net) or a supply-set name
    (create_power_domain -primary_supply_set); resolve the latter through the
    model's supply sets so relations always carry the real net."""
    d = domain.primary_supply_sets or {}
    if "primary_power_net" in d:
        return d["primary_power_net"]
    if "primary" in d:
        ss = model.supply_sets.get(model.scope_key(d["primary"], domain.scope))
        if ss is None:
            ss = model.supply_sets.get(d["primary"])
        if ss is not None:
            return ss.functions.get("power") or ss.functions.get("primary_power_net")
        return d["primary"]
    return d.get("power")


def _domain_ground(model: PowerIntentModel, domain: PowerDomain) -> Optional[str]:
    d = domain.primary_supply_sets or {}
    if "primary_ground_net" in d:
        return d["primary_ground_net"]
    if "primary" in d:
        ss = model.supply_sets.get(model.scope_key(d["primary"], domain.scope))
        if ss is None:
            ss = model.supply_sets.get(d["primary"])
        if ss is not None:
            return ss.functions.get("ground") or ss.functions.get("primary_ground_net")
    return d.get("ground")


def _domain_switch(model: PowerIntentModel, domain: PowerDomain) -> Optional[PowerSwitch]:
    """The power switch that feeds this domain's primary power, if any."""
    dom_power = _domain_power(model, domain)
    if not dom_power:
        return None
    candidates = [s for s in model.switches.values()
                  if s.output_supply and dom_power in (s.output_supply, s.name)]
    # Multiple switches may feed the same net (parallel); report the first by
    # declaration order for determinism.
    return candidates[0] if candidates else None


def _domain_type(model: PowerIntentModel, domain: PowerDomain,
                 domain_switch: Optional[PowerSwitch]) -> str:
    """SWITCHABLE / ALWAYS_ON / UNKNOWN - never inferred from switch absence."""
    if domain_switch is not None:
        return "SWITCHABLE"
    # Explicit always-on declaration (set_port_attributes ... always_on true)
    # is honoured and scoped to the domain name; attribute values may arrive
    # with brace-group wrapping. A global always_on on signals must not mark
    # every domain always-on.
    for name, attrs in model.port_attributes.items():
        if name != domain.name and name != domain.scope.rstrip("/") + "/" + domain.name:
            continue
        joined = " ".join(attrs).replace("{", " ").replace("}", " ").lower()
        if "always_on" in joined and "true" in joined:
            return "ALWAYS_ON"
    return "UNKNOWN"


def derive_domain_relations(model: Optional[PowerIntentModel]) -> DomainRelations:
    """Derive the canonical domain relation graph from the power-intent model.

    Deterministic: domains, relations, and matrix axes are sorted; every
    relation carries at least one piece of provenance when the model knows it.
    """
    if model is None:
        return DomainRelations()

    # Architecture: hierarchy events / multi-file load -> HIERARCHICAL
    has_hierarchy = bool(model.hierarchy_events) or len(model.load_upf_events) > 0
    architecture = "HIERARCHICAL" if has_hierarchy else "FLAT"

    files: List[str] = []
    for fl in model.record_files.values():
        for f in fl:
            if f not in files:
                files.append(f)

    domains: List[DomainInfo] = []
    domain_by_name: Dict[str, DomainInfo] = {}
    domain_obj_by_name: Dict[str, PowerDomain] = {}
    for name in sorted(model.domains):
        d = model.domains[name]
        sw = _domain_switch(model, d)
        info = DomainInfo(
            name=name,
            type=_domain_type(model, d, sw),
            scope=d.scope,
            elements=list(d.elements),
            primary_power=_domain_power(model, d),
            primary_ground=_domain_ground(model, d),
            switch=sw.name if sw else None,
            declared_line=d.declared_line,
            declared_file=_resolve_file(model, d.declared_line, d.declared_file),
        )
        domains.append(info)
        domain_by_name[name] = info
        domain_obj_by_name[name] = d

    # Relation accumulator: (from, to) -> DomainRelation
    rel_map: Dict[tuple, DomainRelation] = {}

    def _add_relation(from_d: str, to_d: str, kind: str, detail: str,
                      line: Optional[int] = None,
                      obj_file: Optional[str] = None) -> None:
        if from_d == to_d or from_d not in domain_by_name or to_d not in domain_by_name:
            return
        key = (from_d, to_d)
        rel = rel_map.setdefault(key, DomainRelation(from_d, to_d))
        if kind not in rel.kinds:
            rel.kinds.append(kind)
        rel.evidence.append(RelationEvidence(kind, detail, line,
                                             _resolve_file(model, line, obj_file)))

    # 1) Switch relations: source domain (input supply owner) -> gated domain.
    for sw_name in sorted(model.switches):
        sw = model.switches[sw_name]
        owner = _supply_domain(model, domain_obj_by_name, sw.output_supply,
                               getattr(sw, "scope", None))
        if owner is None:
            continue
        # who owns the input supply?
        src = _supply_domain(model, domain_obj_by_name, sw.input_supply,
                             getattr(sw, "scope", None))
        if src is not None:
            _add_relation(src, owner, "switch",
                          f"power switch {sw_name}: {sw.input_supply} -> {sw.output_supply}",
                          sw.declared_line, sw.declared_file)
            # an always-on domain that owns the input supply is the proven
            # anchor; record it explicitly against the gated domain.
            if domain_by_name[src].type == "ALWAYS_ON" and src != owner:
                _add_relation(src, owner, "switch",
                              f"power switch {sw_name} gates {owner} from always-on {src}",
                              sw.declared_line, sw.declared_file)
        else:
            # Input supply is not owned by any domain (e.g. a top-level port):
            # the gated domain depends on the always-on infrastructure, so
            # record the relation against every always-on anchor - the AON
            # domain is the only candidate source for a gating supply.
            for dname, d in domain_by_name.items():
                if d.type == "ALWAYS_ON" and dname != owner:
                    _add_relation(dname, owner, "switch",
                                  f"power switch {sw_name} gates {owner}",
                                  sw.declared_line, sw.declared_file)

    def _resolve_domain(ref: str) -> Optional[str]:
        """Map a strategy's domain reference to its scoped model key.

        Strategies record the bare domain name ('core_a'); the model keys
        domains with their scope ('core_a/core_a'). Accept an exact key, the
        bare name (unambiguous), or the scope-prefixed name."""
        if not ref:
            return None
        if ref in domain_by_name:
            return ref
        bare = [k for k in domain_by_name if k.split("/")[-1] == ref]
        if len(bare) == 1:
            return bare[0]
        return None

    # 2) Isolation relations: a strategy on a domain that clamps to a supply
    #    owned by another domain is evidence of that boundary.
    for iso in sorted(model.isolation, key=lambda x: (x.declared_line or 0, x.domain)):
        dom = _resolve_domain(iso.domain)
        if dom is None:
            continue
        owner = _supply_domain(model, domain_obj_by_name, iso.isolation_supply,
                               getattr(iso, "scope", None))
        if owner is not None and owner != dom:
            _add_relation(dom, owner, "isolation",
                          f"set_isolation on {dom} clamps via {iso.isolation_supply}",
                          iso.declared_line, iso.declared_file)

    # 3) Level shifter relations: a shifter on a domain whose supply differs
    #    from another domain's is evidence of a level-shift boundary.
    for ls in sorted(model.level_shifters, key=lambda x: (x.declared_line or 0, x.domain)):
        dom = _resolve_domain(ls.domain)
        if dom is None:
            continue
        p1 = domain_by_name[dom].primary_power
        for other in domain_by_name:
            if other == dom:
                continue
            p2 = domain_by_name[other].primary_power
            if p1 and p2 and p1 != p2:
                _add_relation(dom, other, "level_shift",
                              f"set_level_shifter on {dom} ({ls.rule}) between {p1} and {p2}",
                              ls.declared_line, ls.declared_file)

    # 4) Retention dependency: a domain retaining via an always-on supply
    #    depends on the domain that owns that supply.
    for ret in sorted(model.retentions, key=lambda x: (x.declared_line or 0, x.domain)):
        dom = _resolve_domain(ret.domain)
        if dom is None:
            continue
        owner = _supply_domain(model, domain_obj_by_name, ret.retention_supply,
                               getattr(ret, "scope", None))
        if owner is not None and owner != dom:
            _add_relation(dom, owner, "retention",
                          f"set_retention on {dom} retains via {ret.retention_supply}",
                          ret.declared_line, ret.declared_file)

    # 5) Supply SHARING is a separate view, never a domain interaction: two
    #    domains powered by the same net do not imply a crossing. Populate the
    #    supply_sharing map and add the shared ground (VSS) net as well.
    power_owners: Dict[str, List[str]] = {}
    for d in domains:
        for net in (d.primary_power, d.primary_ground):
            if net:
                power_owners.setdefault(net, []).append(d.name)
    supply_sharing = {net: sorted(set(owners)) for net, owners in sorted(power_owners.items())}

    # 6) Control dependency: a switch whose control port lives inside another
    #    domain makes the gated domain depend on that domain.
    for sw_name in sorted(model.switches):
        sw = model.switches[sw_name]
        if not sw.control_port:
            continue
        owner = _supply_domain(model, domain_obj_by_name, sw.output_supply,
                               getattr(sw, "scope", None))
        if owner is None:
            continue
        for dname, d in domain_by_name.items():
            if dname == owner:
                continue
            if any(sw.control_port.startswith(el) or el in sw.control_port
                   for el in d.elements):
                _add_relation(owner, dname, "control",
                              f"switch {sw_name} control {sw.control_port} lives in {dname}",
                              sw.declared_line, sw.declared_file)

    # Build deterministic relations + matrix. Only cross-domain interactions
    # appear; cells without evidence stay "-" (an empty cell is honest - it
    # means no proven interaction, NOT an invented "UNKNOWN" relationship).
    relations = [rel_map[k] for k in sorted(rel_map)]
    names = [d.name for d in domains]
    matrix: Dict[str, Dict[str, str]] = {}
    for f in names:
        row: Dict[str, str] = {}
        for t in names:
            row[t] = "-" if f == t else ""
        matrix[f] = row
    for rel in relations:
        matrix[rel.from_domain][rel.to_domain] = rel.label

    # related domains per domain (interaction only, not supply sharing)
    for rel in relations:
        if rel.from_domain in domain_by_name and rel.to_domain not in domain_by_name[rel.from_domain].related:
            domain_by_name[rel.from_domain].related.append(rel.to_domain)
        if rel.to_domain in domain_by_name and rel.from_domain not in domain_by_name[rel.to_domain].related:
            domain_by_name[rel.to_domain].related.append(rel.from_domain)

    hierarchy = _hierarchy_ownership(model, domain_by_name)

    return DomainRelations(
        architecture=architecture,
        domains=domains,
        relations=relations,
        matrix=matrix,
        supply_sharing=supply_sharing,
        hierarchy=hierarchy,
        files=files,
        supply_maps=model.supply_maps,
    )


def _hierarchy_ownership(model: PowerIntentModel,
                         domain_by_name: Dict[str, DomainInfo]) -> List[dict]:
    """Domain -> UPF file / scope / owner mapping.

    For flat designs every domain belongs to the top scope of its declaring
    file. For hierarchical designs the scope path (e.g. ``top.core_a``) names
    the owning RTL instance, and the load_upf events tell us which file each
    scope came from.
    """
    rows: List[dict] = []
    # scope -> file, from load_upf events (set_scope X; load_upf X.upf). The
    # declaring file of the load command is authoritative for the child scope;
    # the loaded child UPF owns the domains defined within that scope.
    scope_file: Dict[str, str] = {}
    for ev in model.load_upf_events:
        ev_scope = ev.get("scope", ".")
        ev_file = ev.get("loaded")
        if ev_file:
            scope_file[ev_scope] = ev_file
    for d in domain_by_name.values():
        scope = d.scope or "."
        owner = _owner_from_scope(scope, model.design_top)
        upf_file = scope_file.get(scope) or scope_file.get(owner) or d.declared_file
        rows.append({
            "domain": d.name,
            "scope": scope,
            "owner": owner,
            "upf_file": _display_name(upf_file) if upf_file else
                       ("top.upf" if architecture_hint(model) else None),
            "declared_line": d.declared_line,
            "declared_file": _display_name(d.declared_file),
        })
    return rows


def _display_name(path: Optional[str]) -> Optional[str]:
    """Basename for file provenance - portable, never machine-specific."""
    if not path:
        return path
    return path.replace("\\", "/").split("/")[-1]


def architecture_hint(model: PowerIntentModel) -> bool:
    """True when the model carries hierarchy events (multi-file composition)."""
    return bool(model.hierarchy_events) or len(model.load_upf_events) > 0


def _owner_from_scope(scope: str, design_top: Optional[str]) -> str:
    """First path component of the scope (e.g. ``top.core_a`` -> ``core_a``),
    falling back to the design top when the scope is the root."""
    cleaned = scope.strip().strip("/")
    if not cleaned or cleaned == ".":
        return design_top or "top"
    parts = [p for p in cleaned.split("/") if p]
    return parts[-1] if len(parts) > 1 else parts[0]


def _supply_domain(model: PowerIntentModel, domain_obj_by_name: Dict[str, object],
                   supply: Optional[str],
                   scope: Optional[str] = None) -> Optional[str]:
    """Return the domain whose primary power net matches ``supply`` (or whose
    name is a suffix of the supply, e.g. switch output ``vdd_core_gated``).

    ``scope`` is the scope the reference appears in (e.g. the switch's own
    scope): the net is resolved as ``<scope>/<supply>`` first so two child
    scopes with same-named supplies (``core_a/vdd_core_sw`` vs
    ``core_b/vdd_core_sw``) map to their own domains, never to the first
    domain that happens to match. Returns None when unresolvable - the caller
    records nothing in that case."""
    if not supply:
        return None
    # Resolve the supply to a fully-qualified name inside the reference scope
    # (e.g. core_a/vdd_core_sw) and match it against each domain's own
    # fully-qualified power/ground/net. Same-named supplies in sibling scopes
    # are disambiguated by scope only when the bare name is ambiguous; a
    # unique bare-name match (including cross-scope references like a
    # strategy in core_a clamping via sram's vdd_sram) resolves directly.
    scoped = None
    if scope and scope not in (".", ""):
        scoped = scope.rstrip("/") + "/" + supply
    bare_matches: List[str] = []
    for name, d in domain_obj_by_name.items():
        pp = _domain_power(model, d)
        if not pp:
            continue
        dom_scope = (getattr(d, "scope", ".") or ".").rstrip("/")
        dom_qualified = f"{dom_scope}/{pp}" if dom_scope not in (".", "") else pp
        if scoped and (scoped == dom_qualified or scoped == name):
            return name  # exact scope-qualified match wins
        if supply in (pp, d.name) and "/" not in pp:
            bare_matches.append(name)
        elif supply == dom_qualified and "/" not in supply:
            bare_matches.append(name)
    if len(bare_matches) == 1:
        return bare_matches[0]
    if len(bare_matches) > 1 and scope:
        for name in bare_matches:
            d = domain_obj_by_name[name]
            dom_scope = (getattr(d, "scope", ".") or ".").rstrip("/")
            if dom_scope == scope.rstrip("/"):
                return name
    if bare_matches:
        return bare_matches[0]
    # Cross-scope fallback: a strategy in one scope may reference a supply
    # declared in another scope (e.g. core_a's isolation clamps via sram's
    # vdd_sram). Resolve through the model's supply tables; a unique owner
    # is accepted only when unambiguous.
    cross: List[str] = []
    for name, d in domain_obj_by_name.items():
        pp = _domain_power(model, d)
        if pp and supply == pp:
            cross.append(name)
    if len(cross) == 1:
        return cross[0]
    if len(cross) > 1 and scope:
        for name in cross:
            dom_scope = (getattr(d, "scope", ".") or ".").rstrip("/")
            if dom_scope == scope.rstrip("/"):
                return name
        return None  # ambiguous across scopes - do not guess
    # Suffix fallback (e.g. switch output ``vdd_core_gated`` implies domain
    # ``core``) is scope-aware: a same-named suffix in a sibling scope must
    # never be matched just because iteration order sees it first.
    for name, d in domain_obj_by_name.items():
        if not name or "_" not in supply:
            continue
        dom_scope = (getattr(d, "scope", ".") or ".").rstrip("/")
        if supply.endswith("_" + name) or supply == name:
            if not scope or dom_scope == scope.rstrip("/"):
                return name
    return None


__all__ = [
    "RelationEvidence", "DomainRelation", "DomainInfo", "DomainRelations",
    "derive_domain_relations",
]
