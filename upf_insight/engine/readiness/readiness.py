"""Power-intent readiness - a categorical verdict on a validated UPF model.

Mirrors the sdc-tools `constraint_readiness` shape: readiness is *categorical*,
never a numeric score. Each dimension aggregates findings into a status, the
dimensions combine to one overall verdict:

    READY · READY_WITH_ADVISORIES · REVIEW_REQUIRED · BLOCKED · INSUFFICIENT_CONTEXT

The verdict is evidence-driven and deterministic. It is not a signoff: a READY
verdict means "no rule fired", never "power intent proven correct".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ...model.power_model import PowerIntentModel
from ..rules.checker import CheckResult, Finding

READY = "READY"
READY_WITH_ADVISORIES = "READY_WITH_ADVISORIES"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
BLOCKED = "BLOCKED"
INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
ALL_STATUSES = (READY, READY_WITH_ADVISORIES, REVIEW_REQUIRED, BLOCKED,
                INSUFFICIENT_CONTEXT)

DIM_POWER_STATES = "POWER_STATES"
DIM_SUPPLY_NETWORK = "SUPPLY_NETWORK"
DIM_STRATEGIES = "STRATEGIES"
DIM_CONSISTENCY = "CONSISTENCY"
DIM_DESIGN_CONTEXT = "DESIGN_CONTEXT"
DIMENSIONS = (DIM_POWER_STATES, DIM_SUPPLY_NETWORK, DIM_STRATEGIES,
              DIM_CONSISTENCY, DIM_DESIGN_CONTEXT)

#: rule -> dimension mapping (from the registry layer groupings).
_RULE_DIMENSION = {
    "UPF-001": DIM_CONSISTENCY, "UPF-002": DIM_CONSISTENCY,
    "UPF-003": DIM_CONSISTENCY, "UPF-004": DIM_CONSISTENCY,
    "UPF-005": DIM_CONSISTENCY, "UPF-006": DIM_CONSISTENCY,
    "UPF-010": DIM_SUPPLY_NETWORK, "UPF-011": DIM_STRATEGIES,
    "UPF-012": DIM_DESIGN_CONTEXT, "UPF-013": DIM_CONSISTENCY,
    "UPF-014": DIM_CONSISTENCY, "UPF-015": DIM_CONSISTENCY,
    "UPF-016": DIM_DESIGN_CONTEXT,
    "UPF-020": DIM_SUPPLY_NETWORK, "UPF-021": DIM_CONSISTENCY,
    "UPF-022": DIM_SUPPLY_NETWORK, "UPF-023": DIM_SUPPLY_NETWORK,
    "UPF-024": DIM_SUPPLY_NETWORK, "UPF-025": DIM_POWER_STATES,
    "UPF-030": DIM_POWER_STATES, "UPF-031": DIM_POWER_STATES,
    "UPF-032": DIM_POWER_STATES, "UPF-033": DIM_POWER_STATES,
    "UPF-034": DIM_POWER_STATES, "UPF-035": DIM_POWER_STATES,
    "UPF-036": DIM_STRATEGIES,
    "UPF-040": DIM_STRATEGIES, "UPF-041": DIM_STRATEGIES,
    "UPF-042": DIM_STRATEGIES, "UPF-043": DIM_STRATEGIES,
    "UPF-044": DIM_STRATEGIES, "UPF-045": DIM_STRATEGIES,
    "UPF-046": DIM_STRATEGIES, "UPF-047": DIM_STRATEGIES,
    "UPF-050": DIM_STRATEGIES, "UPF-051": DIM_STRATEGIES,
    "UPF-052": DIM_STRATEGIES, "UPF-053": DIM_STRATEGIES,
    "UPF-054": DIM_STRATEGIES,
    "UPF-060": DIM_STRATEGIES, "UPF-061": DIM_STRATEGIES,
    "UPF-062": DIM_STRATEGIES, "UPF-063": DIM_STRATEGIES,
    "UPF-064": DIM_STRATEGIES,
    "UPF-070": DIM_SUPPLY_NETWORK, "UPF-071": DIM_SUPPLY_NETWORK,
    "UPF-072": DIM_SUPPLY_NETWORK, "UPF-073": DIM_SUPPLY_NETWORK,
    "UPF-074": DIM_STRATEGIES,
    "UPF-080": DIM_DESIGN_CONTEXT, "UPF-081": DIM_DESIGN_CONTEXT,
    "UPF-082": DIM_DESIGN_CONTEXT, "UPF-083": DIM_DESIGN_CONTEXT,
    "UPF-084": DIM_DESIGN_CONTEXT,
    "UPF-090": DIM_STRATEGIES, "UPF-091": DIM_STRATEGIES,
    "UPF-092": DIM_STRATEGIES, "UPF-093": DIM_STRATEGIES,
    "UPF-094": DIM_STRATEGIES,
    "UPF-095": DIM_DESIGN_CONTEXT, "UPF-096": DIM_DESIGN_CONTEXT,
    "UPF-097": DIM_DESIGN_CONTEXT,
    "UPF-098": DIM_SUPPLY_NETWORK,
}

#: Rules that are deterministic blockers on their own.
BLOCKER_RULES = {
    "UPF-001", "UPF-002", "UPF-003", "UPF-006", "UPF-010", "UPF-011",
    "UPF-013", "UPF-020", "UPF-021", "UPF-023", "UPF-030", "UPF-031",
    "UPF-040", "UPF-041", "UPF-045", "UPF-046", "UPF-061", "UPF-062",
    "UPF-063", "UPF-070", "UPF-054", "UPF-090", "UPF-092", "UPF-094",
    "UPF-095", "UPF-098",
}

_DEFAULT_TIER = {"error": BLOCKED, "warning": REVIEW_REQUIRED,
                 "info": READY_WITH_ADVISORIES}


@dataclass
class ReadinessFinding:
    code: str
    severity: str
    message: str
    line: int = 0
    tier: str = ""
    dimension: str = ""

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "message": self.message, "line": self.line,
                "tier": self.tier, "dimension": self.dimension}


@dataclass
class DimensionEvidence:
    dimension: str
    status: str
    summary: str = ""
    findings: List[ReadinessFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"dimension": self.dimension, "status": self.status,
                "summary": self.summary,
                "findings": [f.to_dict() for f in self.findings]}


@dataclass
class ReadinessResult:
    overall: str = INSUFFICIENT_CONTEXT
    mode: str = "UPF_ONLY"
    dimensions: Dict[str, DimensionEvidence] = field(default_factory=dict)
    blockers: List[dict] = field(default_factory=list)
    review_items: List[dict] = field(default_factory=list)
    advisories: List[dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "mode": self.mode,
            "dimensions": {d: ev.to_dict() for d, ev in self.dimensions.items()},
            "blockers": self.blockers,
            "review_items": self.review_items,
            "advisories": self.advisories,
            "notes": self.notes,
        }


def _tier_for(code: str, severity: str) -> str:
    # A blocker rule only blocks when it fires at error severity; PARTIAL /
    # NETLIST_REQUIRED warnings on the same code are advisory/review.
    if code in BLOCKER_RULES and severity == "error":
        return BLOCKED
    return _DEFAULT_TIER.get(severity, REVIEW_REQUIRED)


def _aggregate(tiers: List[str]) -> str:
    if BLOCKED in tiers:
        return BLOCKED
    if REVIEW_REQUIRED in tiers:
        return REVIEW_REQUIRED
    if READY_WITH_ADVISORIES in tiers:
        return READY_WITH_ADVISORIES
    return READY


def _evidence_for_dimension(dim: str, findings: List[ReadinessFinding]) -> str:
    tiers = [f.tier for f in findings if f.dimension == dim]
    return _aggregate(tiers) if tiers else READY


def compute_readiness(model: PowerIntentModel, check: CheckResult) -> ReadinessResult:
    """Derive the categorical readiness verdict from findings + model shape."""
    rd = ReadinessResult(mode="UPF_ONLY")

    bucket: Dict[str, List[ReadinessFinding]] = {d: [] for d in DIMENSIONS}
    tiers: List[str] = []

    for f in check.findings:
        dim = _RULE_DIMENSION.get(f.rule, DIM_CONSISTENCY)
        tier = _tier_for(f.rule, f.severity)
        rf = ReadinessFinding(code=f.rule, severity=f.severity,
                              message=f.message, line=f.line or 0,
                              tier=tier, dimension=dim)
        bucket[dim].append(rf)
        tiers.append(tier)
        if tier == BLOCKED:
            rd.blockers.append(rf.to_dict())
        elif tier == REVIEW_REQUIRED:
            rd.review_items.append(rf.to_dict())
        else:
            rd.advisories.append(rf.to_dict())

    # Structural evidence that does not come from a rule finding.
    if not model.commands_seen:
        rd.overall = INSUFFICIENT_CONTEXT
        rd.notes.append("No UPF commands were parsed.")
    elif not model.psts and not model.supply_states:
        rd.notes.append("No power states and no PST - power-state readiness "
                        "cannot be assessed.")
    if not model.domains:
        rd.notes.append("No power domains were declared.")

    # Design-aware layer: present only when a design context was supplied.
    design_present = getattr(model, "design", None) is not None
    if design_present:
        rd.mode = "DESIGN_AWARE"
    if not design_present:
        bucket[DIM_DESIGN_CONTEXT].append(ReadinessFinding(
            code="UPF-080", severity="info", line=0,
            message="Design-aware readiness (UPF-080..084) requires a netlist/RTL "
                    "context, which was not supplied.",
            tier=REVIEW_REQUIRED, dimension=DIM_DESIGN_CONTEXT))
        tiers.append(REVIEW_REQUIRED)

    summaries = {
        DIM_POWER_STATES: _summarize_power_states(model),
        DIM_SUPPLY_NETWORK: _summarize_supply_network(model),
        DIM_STRATEGIES: _summarize_strategies(model),
        DIM_CONSISTENCY: _summarize_consistency(model),
        DIM_DESIGN_CONTEXT: (
            f"{len(design.instances)} instance(s), {len(design.ports)} port(s)"
            if (design := getattr(model, "design", None)) is not None
            else "netlist/RTL context not supplied; design-aware rules (UPF-080..084) did not run"
        ),
    }

    for dim in DIMENSIONS:
        findings = bucket[dim]
        status = _evidence_for_dimension(dim, findings)
        if not findings and status == READY:
            # A dimension with no findings is still evidence-based.
            status = _evidence_for_dimension(dim, findings)
        rd.dimensions[dim] = DimensionEvidence(
            dimension=dim, status=status, summary=summaries[dim],
            findings=findings)

    # Aggregate tiers only when commands were actually parsed. For empty
    # input, overall stays INSUFFICIENT_CONTEXT (its default) - reporting
    # REVIEW_REQUIRED for a file that was never analyzed would be dishonest.
    if model.commands_seen:
        rd.overall = _aggregate(tiers)
    return rd


def _summarize_power_states(model: PowerIntentModel) -> str:
    n_states = sum(len(p.states) for p in model.psts.values())
    n_trans = sum(len(p.transitions) for p in model.psts.values())
    n_declared = len(model.supply_states)
    if not model.psts:
        return f"{n_declared} supply state(s) declared, no PST."
    return f"{n_states} PST state(s), {n_trans} transition(s), " \
           f"{n_declared} declared supply state(s)."


def _summarize_supply_network(model: PowerIntentModel) -> str:
    return (f"{len(model.domains)} domain(s), {len(model.supply_nets)} "
            f"net(s), {len(model.supply_sets)} set(s), "
            f"{len(model.supply_ports)} port(s), {len(model.switches)} switch(es).")


def _summarize_strategies(model: PowerIntentModel) -> str:
    return (f"{len(model.isolation)} isolation, "
            f"{len(model.level_shifters)} level-shifter, "
            f"{len(model.retentions)} retention, "
            f"{len(model.repeaters)} repeater strategy(ies).")


def _summarize_consistency(model: PowerIntentModel) -> str:
    if not model.unsupported_commands:
        return "No unsupported commands parsed."
    return f"{len(model.unsupported_commands)} unsupported command(s) parsed."


__all__ = [
    "READY", "READY_WITH_ADVISORIES", "REVIEW_REQUIRED", "BLOCKED",
    "INSUFFICIENT_CONTEXT", "ALL_STATUSES",
    "DIM_POWER_STATES", "DIM_SUPPLY_NETWORK", "DIM_STRATEGIES",
    "DIM_CONSISTENCY", "DIM_DESIGN_CONTEXT", "DIMENSIONS",
    "ReadinessFinding", "DimensionEvidence", "ReadinessResult",
    "compute_readiness",
]