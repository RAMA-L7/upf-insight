"""UPF-Insight engine orchestration.

Top-level API tying preprocess → model build → check → support boundary →
PST analysis → readiness → coverage together, and the entry points for the
`model`, `pst`, and `report` commands. Mirrors the sdc-tools
`checker.check_sdc()` orchestration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional

from .rules.checker import CheckResult, check_model
from .trust.support_boundary import SupportReport, compute_support_boundary
from .pst.analyzer import PstAnalysis, analyze_pst
from .readiness.readiness import ReadinessResult, compute_readiness
from .coverage.coverage import CoverageResult, analyze_coverage
from ..model.builder import build_model
from ..model.power_model import PowerIntentModel
from ..preprocess.upf_preprocess import CommandRecord, preprocess_many


@dataclass
class ValidateResult:
    """Aggregate result of a full UPF validation run."""

    check: CheckResult = field(default_factory=CheckResult)
    support: Optional[SupportReport] = None
    pst: Optional[PstAnalysis] = None
    readiness: Optional[ReadinessResult] = None
    coverage: Optional[CoverageResult] = None
    file_count: int = 0
    command_count: int = 0

    @property
    def clean(self) -> bool:
        return self.check.clean

    def to_dict(self) -> dict:
        model = self.check.model.to_dict() if self.check.model else None
        return {
            "check": self.check.to_dict(),
            "support": self.support.to_dict() if self.support else None,
            "pst": self.pst.to_dict() if self.pst else None,
            "readiness": self.readiness.to_dict() if self.readiness else None,
            "coverage": self.coverage.to_dict() if self.coverage else None,
            "model": model,
            "file_count": self.file_count,
            "command_count": self.command_count,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


def _run(records: List[CommandRecord], paths: List[str],
         rules: Optional[List[str]] = None,
         netlist: Optional[str] = None) -> ValidateResult:
    model: PowerIntentModel = build_model(records)
    if netlist:
        from .design.design_context import load_optional

        model.design = load_optional(netlist)
    check: CheckResult = check_model(model, rules=rules)
    support: SupportReport = compute_support_boundary(model)
    pst: PstAnalysis = analyze_pst(model)
    readiness: ReadinessResult = compute_readiness(model, check)
    coverage: CoverageResult = analyze_coverage(model)
    return ValidateResult(
        check=check,
        support=support,
        pst=pst,
        readiness=readiness,
        coverage=coverage,
        file_count=len(paths),
        command_count=model.commands_seen,
    )


def validate(paths: List[str], rules: Optional[List[str]] = None,
             netlist: Optional[str] = None) -> ValidateResult:
    """Preprocess, build, check, and bound a set of UPF files in load order.

    ``netlist`` optionally points at a JSON design context; when present the
    design-aware rules (UPF-080…084) become active.
    """
    records: List[CommandRecord] = preprocess_many(paths)
    return _run(records, paths, rules=rules, netlist=netlist)


def validate_records(records: List[CommandRecord],
                     rules: Optional[List[str]] = None,
                     design=None) -> ValidateResult:
    """Validate from already-preprocessed records (used by tests and web API)."""
    result = _run(records, [r.file for r in records], rules=rules)
    if design is not None:
        if result.check.model is not None:
            if isinstance(design, dict):
                # The web API passes a raw JSON dict; the design-aware rules
                # (UPF-080…084) and readiness consult DesignContext methods,
                # so normalize the dict into the typed context. Without this
                # the design-aware layer silently degrades (rules no-op) while
                # readiness crashes on attribute access.
                from .design.design_context import DesignContext

                design = DesignContext.from_dict(design)
            result.check.model.design = design
            result.check = check_model(result.check.model, rules=rules)
            # Design context changes the support boundary and the DESIGN_CONTEXT
            # readiness dimension — recompute both so the web UI is honest.
            result.support = compute_support_boundary(result.check.model)
            result.readiness = compute_readiness(result.check.model, result.check)
    return result


__all__ = ["ValidateResult", "validate", "validate_records"]