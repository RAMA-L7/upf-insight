"""Strategy-interaction analysis over the built power-intent model.

Detects, deterministically:

- DUPLICATE (UPF-085, error): two strategies of the same type on the same
  domain/scope with identical essential parameters.
- OVERRIDE (UPF-086, warning): a later strategy of the same type on the same
  domain/scope silently overriding an earlier one; differing parameters are
  reported explicitly.
- CONFLICT (UPF-086, warning): concrete structural conflicts - two power
  switches driving the same output supply net, isolation/level-shifter pairs
  on the same domain with contradictory -location values, and retention
  strategies covering the same elements twice with different parameters.

Every finding traces to a declared line via the shared Finding type. The
analyzer never raises: per-strategy processing is wrapped defensively and
failures surface as notes in the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ...model.power_model import (
    IsolationStrategy,
    LevelShifterStrategy,
    PowerIntentModel,
    PowerSwitch,
    RetentionStrategy,
)
from ..rules.finding import Finding

DUPLICATE = "DUPLICATE"
OVERRIDE = "OVERRIDE"
CONFLICT = "CONFLICT"

CODE_DUPLICATE = "UPF-085"
CODE_CONFLICT = "UPF-086"


@dataclass
class Interaction:
    """One detected interaction between two (or more) model records."""

    kind: str
    code: str
    subject: str
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    finding: Optional[Finding] = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "code": self.code,
            "subject": self.subject,
            "message": self.message,
            "evidence": self.evidence,
            "finding": self.finding.to_dict() if self.finding is not None else None,
        }


@dataclass
class InteractionResult:
    """Deterministic strategy-interaction report."""

    interactions: List[Interaction] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "interactions": [i.to_dict() for i in self.interactions],
            "notes": list(self.notes),
        }


def _severity(kind: str) -> str:
    if kind == DUPLICATE:
        return "error"
    if kind in (OVERRIDE, CONFLICT):
        return "warning"
    return "info"


def _make_finding(
    kind: str,
    code: str,
    subject: str,
    message: str,
    evidence: Dict[str, Any],
) -> Finding:
    line = evidence.get("later_line") or evidence.get("line")
    file_name = evidence.get("later_file") or evidence.get("file") or ""
    return Finding(
        rule=code,
        severity=_severity(kind),
        message=message,
        file=str(file_name),
        line=int(line) if isinstance(line, int) else None,
        support="VALIDATED",
        subject=subject,
    )


def _iso_params(s: IsolationStrategy) -> Dict[str, Any]:
    return {
        "elements": sorted(s.elements),
        "clamp_value": s.clamp_value or "",
        "location": s.location or "self",
        "isolation_supply": s.isolation_supply or "",
        "applies_to": s.applies_to or "outputs",
    }


def _ls_params(s: LevelShifterStrategy) -> Dict[str, Any]:
    return {
        "elements": sorted(s.elements),
        "location": s.location or "self",
        "threshold": s.threshold,
        "rule": s.rule or "low_to_high",
        "applies_to": s.applies_to or "",
    }


def _ret_params(s: RetentionStrategy) -> Dict[str, Any]:
    return {
        "elements": sorted(s.elements),
        "retention_supply": s.retention_supply or "",
        "save_signal": s.save_signal or "",
        "restore_signal": s.restore_signal or "",
    }


def _diff_params(a: Dict[str, Any], b: Dict[str, Any]) -> List[str]:
    return sorted(k for k in a if a[k] != b.get(k))


def _detect_strategy_duplicates_and_overrides(
    model: PowerIntentModel,
) -> List[Interaction]:
    param_fn: Dict[str, Callable[[Any], Dict[str, Any]]] = {
        "isolation": _iso_params,
        "level_shifter": _ls_params,
        "retention": _ret_params,
    }
    interactions: List[Interaction] = []
    buckets: Dict[Tuple[str, str, str], List[Tuple[int, Any]]] = {}

    series: List[Tuple[str, Any]] = []
    for iso in model.isolation:
        series.append(("isolation", iso))
    for ls in model.level_shifters:
        series.append(("level_shifter", ls))
    for ret in model.retentions:
        series.append(("retention", ret))

    for stype, strat in series:
        key = (stype, getattr(strat, "scope", "."), getattr(strat, "domain", ""))
        buckets.setdefault(key, []).append((len(buckets[key]), strat))

    for key in sorted(buckets):
        stype, scope, domain = key
        items = sorted(buckets[key], key=lambda t: (t[1].declared_line or 0, id(t[1])))
        fn = param_fn[stype]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                earlier = items[i][1]
                later = items[j][1]
                try:
                    pa = fn(earlier)
                    pb = fn(later)
                except Exception as exc:
                    interactions.append(
                        Interaction(
                            kind="INFO",
                            code="",
                            subject=f"{stype}:{domain}",
                            message=f"comparison failed: {exc}",
                        )
                    )
                    continue
                differing = _diff_params(pa, pb)
                label = f"{stype} on domain '{domain}'"
                if not differing:
                    message = (
                        f"Exact duplicate {label}: identical essential parameters "
                        f"(scope '{scope}'); the later declaration at line "
                        f"{later.declared_line} is redundant."
                    )
                    evidence: Dict[str, Any] = {
                        "strategy_type": stype,
                        "domain": domain,
                        "scope": scope,
                        "earlier_line": earlier.declared_line,
                        "later_line": later.declared_line,
                    }
                    interactions.append(
                        Interaction(
                            kind=DUPLICATE,
                            code=CODE_DUPLICATE,
                            subject=f"{stype}:{domain}",
                            message=message,
                            evidence=evidence,
                            finding=_make_finding(
                                DUPLICATE, CODE_DUPLICATE,
                                f"{stype}:{domain}", message, evidence,
                            ),
                        )
                    )
                elif stype == "retention" and _retention_overlaps(pa, pb):
                    message = (
                        f"Conflicting {label}: same-element retention defined twice "
                        f"with different parameters ({', '.join(differing)}); "
                        f"line {later.declared_line} overrides line "
                        f"{earlier.declared_line}."
                    )
                    evidence = {
                        "strategy_type": stype,
                        "domain": domain,
                        "scope": scope,
                        "earlier_line": earlier.declared_line,
                        "later_line": later.declared_line,
                        "overlapping_elements": sorted(
                            set(pa["elements"]) & set(pb["elements"])
                        )
                        if pa["elements"] and pb["elements"]
                        else ["<whole-domain>"],
                        "differing_parameters": {
                            k: {"earlier": pa[k], "later": pb[k]} for k in differing
                        },
                    }
                    interactions.append(
                        Interaction(
                            kind=CONFLICT,
                            code=CODE_CONFLICT,
                            subject=f"{stype}:{domain}",
                            message=message,
                            evidence=evidence,
                            finding=_make_finding(
                                CONFLICT, CODE_CONFLICT,
                                f"{stype}:{domain}", message, evidence,
                            ),
                        )
                    )
                else:
                    message = (
                        f"Overriding {label}: later declaration at line "
                        f"{later.declared_line} silently overrides the one at line "
                        f"{earlier.declared_line}; differing parameters: "
                        f"{', '.join(differing)}."
                    )
                    evidence = {
                        "strategy_type": stype,
                        "domain": domain,
                        "scope": scope,
                        "earlier_line": earlier.declared_line,
                        "later_line": later.declared_line,
                        "differing_parameters": {
                            k: {"earlier": pa[k], "later": pb[k]} for k in differing
                        },
                    }
                    interactions.append(
                        Interaction(
                            kind=OVERRIDE,
                            code=CODE_CONFLICT,
                            subject=f"{stype}:{domain}",
                            message=message,
                            evidence=evidence,
                            finding=_make_finding(
                                OVERRIDE, CODE_CONFLICT,
                                f"{stype}:{domain}", message, evidence,
                            ),
                        )
                    )
    return interactions


def _retention_overlaps(pa: Dict[str, Any], pb: Dict[str, Any]) -> bool:
    ea: List[str] = pa["elements"]
    eb: List[str] = pb["elements"]
    if not ea or not eb:
        return True
    return bool(set(ea) & set(eb))


def _detect_switch_output_overlap(model: PowerIntentModel) -> List[Interaction]:
    # Keyed by (scope, output_supply), not by the bare net name. Two switches
    # in *different* scopes may each drive a same-named local net without
    # conflicting — that is the normal shape of composed hierarchical UPF,
    # where every child declares its own `vout`. Grouping them under the bare
    # name made every such pair look like a conflict.
    by_net: Dict[Tuple[str, str], List[PowerSwitch]] = {}
    for sw in model.switches.values():
        if sw.output_supply:
            by_net.setdefault(
                (getattr(sw, "scope", ".") or ".", sw.output_supply), []
            ).append(sw)
    interactions: List[Interaction] = []
    for scope, net in sorted(by_net):
        drivers = sorted(by_net[(scope, net)], key=lambda s: (s.name, s.scope))
        for i in range(len(drivers)):
            for j in range(i + 1, len(drivers)):
                a, b = drivers[i], drivers[j]
                message = (
                    f"Conflicting power switches: '{a.name}' and '{b.name}' both "
                    f"drive output supply net '{net}' in scope '{scope}'."
                )
                evidence = {
                    "switch_a": a.name,
                    "switch_b": b.name,
                    "output_supply": net,
                    "scope": scope,
                    "line": min(
                        d for d in (a.declared_line, b.declared_line) if d is not None
                    )
                    if any(d is not None for d in (a.declared_line, b.declared_line))
                    else None,
                }
                interactions.append(
                    Interaction(
                        kind=CONFLICT,
                        code=CODE_CONFLICT,
                        subject=model.scope_key(net, scope),
                        message=message,
                        evidence=evidence,
                        finding=_make_finding(
                            CONFLICT, CODE_CONFLICT,
                            model.scope_key(net, scope), message, evidence
                        ),
                    )
                )
    return interactions


def _detect_location_contradictions(model: PowerIntentModel) -> List[Interaction]:
    iso_by_domain: Dict[Tuple[str, str], List[IsolationStrategy]] = {}
    for iso in model.isolation:
        iso_by_domain.setdefault((iso.domain, iso.scope), []).append(iso)
    ls_by_domain: Dict[Tuple[str, str], List[LevelShifterStrategy]] = {}
    for ls in model.level_shifters:
        ls_by_domain.setdefault((ls.domain, ls.scope), []).append(ls)

    interactions: List[Interaction] = []
    seen: set = set()
    for dom_key in sorted(set(iso_by_domain) & set(ls_by_domain)):
        domain, scope = dom_key
        for iso in sorted(iso_by_domain[dom_key], key=lambda s: (s.declared_line or 0, id(s))):
            for ls in sorted(ls_by_domain[dom_key], key=lambda s: (s.declared_line or 0, id(s))):
                if (iso.location or "self") == (ls.location or "self"):
                    continue
                combo = (domain, scope, iso.location or "self", ls.location or "self")
                if combo in seen:
                    continue
                seen.add(combo)
                message = (
                    f"Contradictory boundary locations for domain '{domain}' "
                    f"(scope '{scope}'): isolation uses -location "
                    f"'{iso.location or 'self'}' while the level shifter uses "
                    f"-location '{ls.location or 'self'}'."
                )
                evidence = {
                    "domain": domain,
                    "scope": scope,
                    "isolation_location": iso.location or "self",
                    "level_shifter_location": ls.location or "self",
                    "isolation_line": iso.declared_line,
                    "level_shifter_line": ls.declared_line,
                    "line": min(
                        d
                        for d in (iso.declared_line, ls.declared_line)
                        if d is not None
                    )
                    if any(
                        d is not None
                        for d in (iso.declared_line, ls.declared_line)
                    )
                    else None,
                }
                interactions.append(
                    Interaction(
                        kind=CONFLICT,
                        code=CODE_CONFLICT,
                        subject=domain,
                        message=message,
                        evidence=evidence,
                        finding=_make_finding(
                            CONFLICT, CODE_CONFLICT, domain, message, evidence
                        ),
                    )
                )
    return interactions


def analyze_strategy_interactions(model: PowerIntentModel) -> InteractionResult:
    """Analyze the model for duplicate / overriding / conflicting strategies."""
    result = InteractionResult()
    detectors: List[Callable[[PowerIntentModel], List[Interaction]]] = [
        _detect_strategy_duplicates_and_overrides,
        _detect_switch_output_overlap,
        _detect_location_contradictions,
    ]
    for detector in detectors:
        try:
            result.interactions.extend(detector(model))
        except Exception as exc:
            result.notes.append(f"detector_failed:{detector.__name__}:{exc}")
    result.interactions.sort(key=lambda i: (i.code, i.kind, i.subject, i.message))
    result.notes.sort()
    return result


__all__ = [
    "DUPLICATE",
    "OVERRIDE",
    "CONFLICT",
    "CODE_DUPLICATE",
    "CODE_CONFLICT",
    "Interaction",
    "InteractionResult",
    "analyze_strategy_interactions",
]
