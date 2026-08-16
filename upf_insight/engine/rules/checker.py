"""UPF rule checker.

Deterministic rule engine that validates a PowerIntentModel and produces
findings with severity, rule code, message, and source provenance (file:line).
Mirrors the sdc-tools `checker.py` contract: every finding traces to evidence.

Severity model (mirrors sdc-tools): error / warning / info.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ...model.power_model import PowerIntentModel
from . import rules_registry
from .finding import Finding
from .upf_rules import (
    build_rule_handlers,
    RULE_HANDLERS,
)


@dataclass
class CheckResult:
    """Aggregate result of a UPF validation run."""

    findings: List[Finding] = field(default_factory=list)
    model: Optional[PowerIntentModel] = None
    support_boundary: Dict[str, int] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "info")

    @property
    def clean(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "counts": {
                "errors": self.error_count,
                "warnings": self.warning_count,
                "infos": self.info_count,
            },
            "support_boundary": self.support_boundary,
            "clean": self.clean,
        }


def check_model(model: PowerIntentModel, rules: Optional[List[str]] = None) -> CheckResult:
    """Run the deterministic rule set against a power-intent model.

    ``rules`` optionally restricts execution to a subset of rule codes.
    """
    result = CheckResult(model=model)
    for rule in rules_registry.registered_rules():
        if rules and rule.code not in rules:
            continue
        handler = RULE_HANDLERS.get(rule.code)
        if handler is None:
            continue
        try:
            findings = handler(model)
        except Exception as exc:  # a rule must never crash the whole run
            findings = [
                Finding(
                    rule=rule.code,
                    severity="error",
                    message=f"internal rule error: {exc}",
                    support="VALIDATED",
                )
            ]
        for f in findings:
            f.rule = f.rule or rule.code
            f.severity = f.severity or rule.severity
            result.findings.append(f)
    _resolve_finding_files(model, result.findings)
    return result


def _resolve_finding_files(model: PowerIntentModel, findings) -> None:
    """Populate ``Finding.file`` from the authoritative record provenance index.

    The engine knows the source filename for every command line; findings that
    carry a ``line`` can therefore resolve their file. When the same line
    number appears in more than one file (multi-file runs with colliding line
    numbers), the provenance is ambiguous and the field is left empty rather
    than invented.
    """
    if not model:
        return
    index = model.record_files or {}
    for f in findings:
        if f.file or not f.line:
            continue
        files = index.get(f.line)
        if files and len(files) == 1:
            f.file = files[0]


def check_records(records, model: Optional[PowerIntentModel] = None,
                  rules: Optional[List[str]] = None) -> CheckResult:
    """Build model from records (if not supplied) and run the checker."""
    from ..model.builder import build_model

    m = model or build_model(records)
    return check_model(m, rules=rules)


__all__ = ["CheckResult", "check_model", "check_records"]