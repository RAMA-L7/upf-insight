"""Wildcard-specificity analysis over the built power-intent model.

Collects every name pattern containing a wildcard character (``*``, ``?``,
``[...]``) used for instances, ports, supply nets, switch controls, and
strategy element lists, then scores how specific each pattern is.

Specificity (0..1) is driven by the literal-character fraction with penalties
for leading wildcards and repeated stars; risk_score (0..10) combines
wildcard kind, position, breadth, and literal length into a coarse risk
bucket:

- LOW    (risk 0-1): narrow, near-literal patterns
- MEDIUM (risk 2-3): bounded patterns
- HIGH   (risk 4+): broad patterns; these carry an honest-boundary note that
  wildcard matching happens at elaboration time, so results may vary.

The analysis never raises and its output ordering is deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from ...model.power_model import PowerIntentModel

WILDCARD_CHARS = ("*", "?", "[")

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"

ELABORATION_NOTE = "wildcards_match_at_elaboration_time_results_may_vary"

_BRACKET_GROUP = re.compile(r"\[[^\]]*\]")


@dataclass
class WildcardAssessment:
    """One scored wildcard pattern in the context where it was used."""

    pattern: str
    context: str
    specificity: float
    risk_score: int
    risk_level: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "context": self.context,
            "specificity": self.specificity,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "notes": list(self.notes),
        }


@dataclass
class WildcardResult:
    """Deterministic wildcard-usage report."""

    assessments: List[WildcardAssessment] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "assessments": [a.to_dict() for a in self.assessments],
            "summary": dict(self.summary),
            "notes": list(self.notes),
        }


def _has_wildcard(pattern: str) -> bool:
    return any(c in pattern for c in WILDCARD_CHARS)


def _pattern_stats(pattern: str) -> Tuple[int, int, int, bool]:
    groups = len(_BRACKET_GROUP.findall(pattern))
    stripped = _BRACKET_GROUP.sub("", pattern)
    stars = stripped.count("*")
    questions = stripped.count("?")
    leading = bool(pattern) and pattern[0] in ("*", "?")
    return stars, questions, groups, leading


def score_pattern(pattern: str) -> Tuple[float, int, str]:
    """Return (specificity 0..1, risk_score 0..10, risk_level)."""
    if not _has_wildcard(pattern):
        return 1.0, 0, RISK_LOW

    stars, questions, groups, leading = _pattern_stats(pattern)
    literal_chars = len(
        _BRACKET_GROUP.sub(
            "", pattern.replace("*", "").replace("?", "")
        ).strip()
    )
    total_len = max(len(pattern), 1)

    specificity = len(pattern.replace("*", "").replace("?", "")) / total_len
    specificity -= 0.20 * groups
    if leading:
        specificity -= 0.15
    if stars > 1:
        specificity -= 0.05 * (stars - 1)
    specificity = round(max(0.0, min(1.0, specificity)), 4)

    risk = 0
    risk += min(4 * stars, 8)
    risk += min(questions, 3)
    risk += min(2 * groups, 4)
    if leading:
        risk += 2
    if stars >= 1 and literal_chars < 3:
        risk += 1
    risk = max(0, min(10, risk))

    if risk >= 4:
        level = RISK_HIGH
    elif risk >= 2:
        level = RISK_MEDIUM
    else:
        level = RISK_LOW
    return specificity, risk, level


def _collect(
    model: PowerIntentModel, errors: List[str]
) -> List[Tuple[str, str]]:
    found: Set[Tuple[str, str]] = set()

    def add(pattern: str, context: str) -> None:
        if pattern and _has_wildcard(pattern):
            found.add((pattern, context))

    try:
        for dom in model.domains.values():
            for el in dom.elements:
                add(el, f"power_domain:{dom.name}")
    except Exception as exc:
        errors.append(f"domains:{exc}")
    try:
        for name in model.port_attributes:
            add(name, "port_attributes")
    except Exception as exc:
        errors.append(f"port_attributes:{exc}")
    try:
        for sw in model.switches.values():
            if sw.control_port:
                add(sw.control_port, f"switch:{sw.name}")
    except Exception as exc:
        errors.append(f"switches:{exc}")
    try:
        for net in model.supply_nets.values():
            add(net.name, "supply_net")
    except Exception as exc:
        errors.append(f"supply_nets:{exc}")
    strategy_sources = [
        ("isolation", model.isolation),
        ("level_shifter", model.level_shifters),
        ("retention", model.retentions),
        ("repeater", model.repeaters),
    ]
    for label, strategies in strategy_sources:
        try:
            for strat in strategies:
                for el in getattr(strat, "elements", []) or []:
                    add(el, f"{label}:{getattr(strat, 'domain', '')}")
        except Exception as exc:
            errors.append(f"{label}:{exc}")

    return sorted(found)


def collect_wildcard_patterns(model: PowerIntentModel) -> List[Tuple[str, str]]:
    """Collect unique (pattern, context) pairs using wildcards, sorted."""
    return _collect(model, [])


def analyze_wildcards(model: PowerIntentModel) -> WildcardResult:
    """Assess every wildcard-bearing name pattern used across the model."""
    result = WildcardResult()
    errors: List[str] = []
    patterns = _collect(model, errors)

    for pattern, context in patterns:
        try:
            specificity, risk, level = score_pattern(pattern)
            notes: List[str] = []
            if level == RISK_HIGH:
                notes.append(ELABORATION_NOTE)
            result.assessments.append(
                WildcardAssessment(
                    pattern=pattern,
                    context=context,
                    specificity=specificity,
                    risk_score=risk,
                    risk_level=level,
                    notes=notes,
                )
            )
        except Exception as exc:
            result.notes.append(f"assessment_failed:{context}:{pattern}:{exc}")

    result.assessments.sort(key=lambda a: (a.pattern, a.context))
    summary: Dict[str, int] = {
        "total": len(result.assessments),
        "high": sum(1 for a in result.assessments if a.risk_level == RISK_HIGH),
        "medium": sum(1 for a in result.assessments if a.risk_level == RISK_MEDIUM),
        "low": sum(1 for a in result.assessments if a.risk_level == RISK_LOW),
    }
    result.summary = summary
    result.notes.extend(sorted(errors))
    result.notes.sort()
    return result


__all__ = [
    "WILDCARD_CHARS",
    "ELABORATION_NOTE",
    "WildcardAssessment",
    "WildcardResult",
    "score_pattern",
    "collect_wildcard_patterns",
    "analyze_wildcards",
]
