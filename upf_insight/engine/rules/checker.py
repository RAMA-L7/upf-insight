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

    After execution, a cascade pass suppresses dependent findings: when a
    prerequisite rule (declared via ``Rule.depends_on``) produced an error on
    the same subject (e.g. UPF-010 undefined supply -> UPF-073 switch output
    unused), the dependent finding is downgraded to ``info`` and tagged with
    ``blocked_by`` so it reads as context, not as a definitive secondary
    error.
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
            # NOT_VALIDATED, not VALIDATED: a rule that crashed proved
            # nothing about the design. Tagging it VALIDATED would let an
            # engine bug read as a clean bill of health.
            findings = [
                Finding(
                    rule=rule.code,
                    severity="error",
                    message=f"internal rule error: {exc}",
                    support="NOT_VALIDATED",
                )
            ]
        for f in findings:
            f.rule = f.rule or rule.code
            f.severity = f.severity or rule.severity
            result.findings.append(f)
    _apply_cascade_suppression(result)
    _enforce_evidence_boundary(result)
    _resolve_finding_files(model, result.findings)
    # The field is serialized in to_dict(); populate it rather than leaving
    # every consumer an empty dict. Lazy import keeps the rule layer free of
    # a module-level dependency on the trust package.
    from ..trust.support_boundary import compute_support_boundary

    result.support_boundary = dict(compute_support_boundary(model).statuses)
    return result


def _apply_cascade_suppression(result: CheckResult) -> None:
    """Downgrade dependent findings whose prerequisite already errored.

    The registry declares dependencies via ``Rule.depends_on``.  A dependent
    finding on subject S is only suppressed when the prerequisite produced an
    *error* finding on the *same* subject S - so a clean run or a different
    subject is never touched.
    """
    by_code = {r.code: r for r in rules_registry.registered_rules()}
    blocking_errors: Dict[str, set] = {}
    for f in result.findings:
        if f.severity == "error" and f.subject:
            blocking_errors.setdefault(f.subject, set()).add(f.rule)
    for f in result.findings:
        rule = by_code.get(f.rule)
        if rule is None or not rule.depends_on:
            continue
        if not f.subject:
            continue
        fired = blocking_errors.get(f.subject, set())
        blockers = [b for b in rule.depends_on if b in fired]
        if not blockers:
            continue
        f.severity = "info"
        f.support = "BLOCKED"
        f.blocked_by = ",".join(blockers)
        f.message = (f"[blocked by {f.blocked_by}] " + f.message)


def _enforce_evidence_boundary(result: CheckResult) -> None:
    """Never let netlist-required evidence become a definitive error.

    A fact that can only be established with a netlist (e.g. whether a signal
    actually crosses between two domains) must never be reported as an error:
    UNKNOWN is not FALSE, and a missing netlist is not a proven defect. Any
    error finding carrying ``NETLIST_REQUIRED`` support is downgraded to a
    warning so the trust boundary holds even if a future rule mis-tags its
    finding. Findings grounded in declared UPF facts (``VALIDATED``,
    ``PARTIAL``, ``UNSUPPORTED``) keep their severity.
    """
    for f in result.findings:
        if f.severity == "error" and f.support == "NETLIST_REQUIRED":
            f.severity = "warning"
            f.message = ("[netlist required] " + f.message)


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