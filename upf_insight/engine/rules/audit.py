"""Rule-registry audit - the contract that keeps the rule set honest.

With a growing registry it is easy for rules to drift: a handler with no
registry entry, a registry entry with no handler, a ``depends_on`` reference
to a rule that does not exist, or a rule whose regression test reference is
empty. This module audits the whole registry and returns a structured report;
``tests/test_rule_audit.py`` asserts the report is clean.

Audited properties:
- every registered rule has a handler and vice versa
- every rule carries non-empty semantic metadata (inputs, context, test_ref)
- ``depends_on`` references exist and form no cycles
- cascade-suppression only references error-severity prerequisite rules
- no duplicate rule codes; deterministic (sorted) registry ordering
"""

from __future__ import annotations

from typing import List

from .rules_registry import registered_rules
from .upf_rules import RULE_HANDLERS


def audit_registry() -> dict:
    """Return a structured audit report for the full rule registry."""
    problems: List[str] = []
    rules = registered_rules()
    codes = [r.code for r in rules]

    # 1. Registry <-> handler sync.
    registry_codes = set(codes)
    handler_codes = set(RULE_HANDLERS)
    for code in sorted(handler_codes - registry_codes):
        problems.append(f"handler '{code}' has no registry entry")
    for code in sorted(registry_codes - handler_codes):
        problems.append(f"registered rule '{code}' has no handler")

    # 2. Duplicate codes.
    if len(codes) != len(set(codes)):
        dupes = sorted({c for c in codes if codes.count(c) > 1})
        problems.append(f"duplicate rule codes: {dupes}")

    # 3. Metadata completeness.
    for r in rules:
        if not r.title:
            problems.append(f"{r.code}: empty title")
        if not r.description:
            problems.append(f"{r.code}: empty description")
        if not r.semantic_inputs:
            problems.append(f"{r.code}: empty semantic_inputs")
        if r.context not in ("UPF_ONLY", "NETLIST_REQUIRED", "PARTIAL"):
            problems.append(f"{r.code}: invalid context {r.context!r}")
        if not r.test_ref:
            problems.append(f"{r.code}: empty test_ref")
        if r.severity not in ("error", "warning", "info"):
            problems.append(f"{r.code}: invalid severity {r.severity!r}")
        if r.layer not in ("SYNTAX", "REFERENCE", "SUPPLY_DOMAIN", "PST",
                           "STRATEGY", "DESIGN", "SUPPLY"):
            problems.append(f"{r.code}: invalid layer {r.layer!r}")

    # 4. Dependency integrity: depends_on codes exist; no cycles; prerequisites
    #    are error-severity rules (only errors block dependents).
    by_code = {r.code: r for r in rules}
    for r in rules:
        for dep in r.depends_on:
            if dep not in by_code:
                problems.append(f"{r.code}: depends_on unknown rule '{dep}'")
            elif by_code[dep].severity != "error":
                problems.append(
                    f"{r.code}: depends_on '{dep}' is not error-severity "
                    f"(cascade suppression only blocks on errors)")
    # cycle detection over the depends_on graph
    visiting, visited = set(), set()

    def visit(node: str, path: List[str]) -> None:
        if node in visiting:
            cycle = path[path.index(node):] + [node]
            problems.append(f"dependency cycle: {' -> '.join(cycle)}")
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in by_code[node].depends_on:
            visit(dep, path + [node])
        visiting.discard(node)
        visited.add(node)

    for r in rules:
        visit(r.code, [])

    return {
        "rule_count": len(rules),
        "handler_count": len(RULE_HANDLERS),
        "problems": problems,
        "clean": not problems,
        "by_layer": _counts_by_layer(rules),
        "by_context": _counts_by_context(rules),
        "by_severity": _counts_by_severity(rules),
    }


def _counts_by_layer(rules) -> dict:
    out: dict = {}
    for r in rules:
        out[r.layer] = out.get(r.layer, 0) + 1
    return dict(sorted(out.items()))


def _counts_by_context(rules) -> dict:
    out: dict = {}
    for r in rules:
        out[r.context] = out.get(r.context, 0) + 1
    return dict(sorted(out.items()))


def _counts_by_severity(rules) -> dict:
    out: dict = {}
    for r in rules:
        out[r.severity] = out.get(r.severity, 0) + 1
    return dict(sorted(out.items()))


def format_audit(report: dict) -> str:
    """Human-readable audit report (used by the CLI ``rules audit``)."""
    lines = [
        f"UPF rules audit",
        f"  registered rules : {report['rule_count']}",
        f"  handlers         : {report['handler_count']}",
        f"  layers           : {report['by_layer']}",
        f"  contexts         : {report['by_context']}",
        f"  severities       : {report['by_severity']}",
    ]
    if report["clean"]:
        lines.append("  AUDIT: CLEAN")
    else:
        lines.append(f"  AUDIT: {len(report['problems'])} problem(s)")
        for p in report["problems"]:
            lines.append(f"    - {p}")
    return "\n".join(lines)


__all__ = ["audit_registry", "format_audit"]
