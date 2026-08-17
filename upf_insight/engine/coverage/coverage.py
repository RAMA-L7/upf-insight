"""Power-intent coverage analysis.

Mirrors the sdc-tools `coverage` module: answers "is every power domain /
supply / strategy family accounted for?".

Coverage is *structural* evidence, distinct from rule findings:
- domain coverage: every domain has a primary supply and (where switchable)
  the expected strategy families;
- supply coverage: every declared supply is referenced by at least one domain
  or PST;
- strategy coverage: retention domains have retention, etc.

No coverage claim implies correctness - it reports what the intent *touches*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ...model.power_model import PowerIntentModel

DIM_COVERAGE = "COVERAGE"


@dataclass
class DomainCoverage:
    domain: str
    has_primary_supply: bool = False
    is_switchable: bool = False
    has_isolation: bool = False
    has_retention: bool = False
    has_level_shifter: bool = False
    has_repeater: bool = False
    covered: bool = False
    gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "has_primary_supply": self.has_primary_supply,
            "is_switchable": self.is_switchable,
            "has_isolation": self.has_isolation,
            "has_retention": self.has_retention,
            "has_level_shifter": self.has_level_shifter,
            "has_repeater": self.has_repeater,
            "covered": self.covered,
            "gaps": self.gaps,
        }


@dataclass
class CoverageResult:
    domains: List[DomainCoverage] = field(default_factory=list)
    referenced_supplies: List[str] = field(default_factory=list)
    declared_supplies: List[str] = field(default_factory=list)
    unreferenced_supplies: List[str] = field(default_factory=list)
    domain_coverage: float = 0.0
    supply_coverage: float = 0.0

    def to_dict(self) -> dict:
        return {
            "domains": [d.to_dict() for d in self.domains],
            "referenced_supplies": self.referenced_supplies,
            "declared_supplies": self.declared_supplies,
            "unreferenced_supplies": self.unreferenced_supplies,
            "domain_coverage": self.domain_coverage,
            "supply_coverage": self.supply_coverage,
        }


def _switchable_outputs(model: PowerIntentModel) -> set:
    return {sw.output_supply for sw in model.switches.values() if sw.output_supply}


def _domain_primary_power(model: PowerIntentModel, dom) -> Optional[str]:
    if "primary_power_net" in dom.primary_supply_sets:
        return dom.primary_supply_sets["primary_power_net"]
    if "primary" in dom.primary_supply_sets:
        return dom.primary_supply_sets["primary"]
    for key, val in dom.primary_supply_sets.items():
        if key.lower() == "power":
            return val
    return None


def _collect_supplies(model: PowerIntentModel) -> set:
    names = set()
    for table in (model.supply_nets, model.supply_sets, model.supply_ports):
        for obj in table.values():
            names.add(obj.name)
    return names


def _referenced_supplies(model: PowerIntentModel) -> set:
    refs = set()
    for dom in model.domains.values():
        primary = _domain_primary_power(model, dom)
        if primary:
            refs.add(primary)
    for ss in model.supply_sets.values():
        for func in ss.functions.values():
            refs.add(func.strip("{}"))
    for pst in model.psts.values():
        for st in pst.states:
            refs.update(st.supply_states.keys())
    for iso in model.isolation:
        if iso.isolation_supply:
            refs.add(iso.isolation_supply)
    for ret in model.retentions:
        if ret.retention_supply:
            refs.add(ret.retention_supply)
    for rep in model.repeaters:
        if rep.repeater_supply:
            refs.add(rep.repeater_supply)
    for sw in model.switches.values():
        if sw.input_supply:
            refs.add(sw.input_supply)
        if sw.output_supply:
            refs.add(sw.output_supply)
    for eq in model.equivalences:
        refs.update(eq["names"])
    return refs


def analyze_coverage(model: PowerIntentModel) -> CoverageResult:
    """Compute structural power-intent coverage for a model."""
    result = CoverageResult()
    switched = _switchable_outputs(model)

    iso_domains = {iso.domain for iso in model.isolation}
    ret_domains = {ret.domain for ret in model.retentions}
    ls_domains = {ls.domain for ls in model.level_shifters}
    rep_domains = {rep.domain for rep in model.repeaters}

    for key, dom in model.domains.items():
        primary = _domain_primary_power(model, dom)
        dc = DomainCoverage(domain=dom.name,
                            has_primary_supply=primary is not None,
                            is_switchable=primary in switched)
        dc.has_isolation = dom.name in iso_domains
        dc.has_retention = dom.name in ret_domains
        dc.has_level_shifter = dom.name in ls_domains
        dc.has_repeater = dom.name in rep_domains

        if not dc.has_primary_supply:
            dc.gaps.append("no primary supply")
        if dc.is_switchable and not dc.has_isolation:
            dc.gaps.append("switchable but no isolation strategy")
        if dc.is_switchable and not dc.has_level_shifter:
            dc.gaps.append("switchable but no level-shifter strategy")
        dc.covered = not dc.gaps
        result.domains.append(dc)

    declared = _collect_supplies(model)
    referenced = _referenced_supplies(model)
    result.declared_supplies = sorted(declared)
    result.referenced_supplies = sorted(referenced & declared)
    result.unreferenced_supplies = sorted(declared - referenced)

    if result.domains:
        result.domain_coverage = round(
            sum(1 for d in result.domains if d.covered) / len(result.domains), 2)
    if declared:
        result.supply_coverage = round(len(referenced & declared) / len(declared), 2)
    return result


__all__ = ["DomainCoverage", "CoverageResult", "analyze_coverage"]