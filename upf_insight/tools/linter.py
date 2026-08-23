"""UPF/Tcl linter - deterministic whitespace, case, and structure normalization.

Every issue carries a line number and a stable rule string so findings stay
traceable, matching the engine's provenance philosophy. Structural problems
(unbalanced braces/brackets) are reported but never auto-fixed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

CANONICAL_COMMANDS: frozenset[str] = frozenset({
    "upf_version",
    "set_design_top",
    "load_upf",
    "create_power_domain",
    "set_scope",
    "create_supply_port",
    "create_supply_net",
    "connect_supply_net",
    "set_domain_supply_net",
    "create_power_switch",
    "set_isolation",
    "set_isolation_control",
    "set_level_shifter",
    "set_retention",
    "set_retention_control",
    "add_power_state",
    "create_pst",
    "add_pst_state",
    "add_port_state",
    "set_port_attributes",
    "map_power_model",
    "map_isolation_cell",
    "map_level_shifter",
    "map_retention_cell",
    "use_interface_cell",
    "set_related_supply_net",
})

_TAB_RE = re.compile(r"\t")
_COMMA_RE = re.compile(r",(?=\S)")
_LEADING_TOKEN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_:]*)")


@dataclass(frozen=True)
class LintIssue:
    """One lint finding with source provenance."""

    line: int
    rule: str
    message: str


@dataclass
class LintResult:
    """Outcome of linting one file."""

    path: Path
    issues: List[LintIssue] = field(default_factory=list)
    changed: bool = False
    cleaned_text: str = ""


def _detect_unbalanced(text: str) -> List[LintIssue]:
    issues: List[LintIssue] = []
    brace = 0
    bracket = 0
    dq = False
    escape = False
    comment = False
    line = 1
    prev = ""
    min_brace_line: int | None = None
    min_bracket_line: int | None = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            dq = False
            escape = False
            comment = False
            prev = "\n"
            i += 1
            continue
        if comment:
            prev = ch
            i += 1
            continue
        if escape:
            escape = False
            prev = ch
            i += 1
            continue
        if ch == "\\":
            if dq:
                escape = True
            prev = ch
            i += 1
            continue
        if ch == '"':
            dq = not dq
            prev = ch
            i += 1
            continue
        if dq:
            prev = ch
            i += 1
            continue
        if ch == "#" and (prev == "" or prev in (" ", "\t", "{", "[", ";")):
            comment = True
            prev = ch
            i += 1
            continue
        if ch == "{":
            brace += 1
        elif ch == "}":
            brace -= 1
            if brace < 0 and min_brace_line is None:
                min_brace_line = line
                brace = 0
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket -= 1
            if bracket < 0 and min_bracket_line is None:
                min_bracket_line = line
                bracket = 0
        prev = ch
        i += 1
    if min_brace_line is not None:
        issues.append(LintIssue(min_brace_line, "unbalanced-brace",
                                "unexpected '}' with no matching '{'"))
    if min_bracket_line is not None:
        issues.append(LintIssue(min_bracket_line, "unbalanced-bracket",
                                "unexpected ']' with no matching '['"))
    last_line = text.count("\n") + 1
    if brace > 0:
        issues.append(LintIssue(last_line, "unbalanced-brace",
                                f"{brace} unclosed '{{' at end of file"))
    if bracket > 0:
        issues.append(LintIssue(last_line, "unbalanced-bracket",
                                f"{bracket} unclosed '[' at end of file"))
    return issues


def _collapse_blank_lines(lines: List[str],
                          issues: List[LintIssue]) -> List[str]:
    out: List[str] = []
    prev_blank = False
    for idx, ln in enumerate(lines, 1):
        blank = ln == ""
        if blank and prev_blank:
            issues.append(LintIssue(idx, "blank-lines",
                                    "multiple consecutive blank lines"))
            continue
        out.append(ln)
        prev_blank = blank
    return out


def lint_text(text: str) -> tuple[str, list[LintIssue]]:
    """Normalize UPF/Tcl text and report issues deterministically."""
    issues: List[LintIssue] = []
    raw_lines = text.split("\n")
    out_lines: List[str] = []
    for idx, ln in enumerate(raw_lines, 1):
        new = _TAB_RE.sub("    ", ln)
        if new != ln:
            issues.append(LintIssue(idx, "tab-character",
                                    "tab replaced with 4 spaces"))
        stripped = new.rstrip()
        if stripped != new:
            issues.append(LintIssue(idx, "trailing-whitespace",
                                    "trailing whitespace removed"))
        fixed_comma = _COMMA_RE.sub(", ", stripped)
        if fixed_comma != stripped:
            issues.append(LintIssue(idx, "comma-space",
                                    "missing space after comma"))
        match = _LEADING_TOKEN_RE.match(fixed_comma)
        if match is not None:
            token = match.group(1)
            lowered = token.lower()
            if lowered in CANONICAL_COMMANDS and token != lowered:
                fixed_comma = (fixed_comma[:match.start(1)] + lowered
                               + fixed_comma[match.end(1):])
                issues.append(LintIssue(
                    idx, "keyword-case",
                    f"command '{token}' normalized to '{lowered}'"))
        out_lines.append(fixed_comma)

    out_lines = _collapse_blank_lines(out_lines, issues)
    while out_lines and out_lines[-1] == "":
        out_lines.pop()
    cleaned = "\n".join(out_lines)
    if cleaned:
        cleaned += "\n"
        if not text.endswith("\n"):
            issues.append(LintIssue(len(out_lines), "missing-final-newline",
                                    "missing final newline added"))

    issues.extend(_detect_unbalanced(cleaned))
    issues.sort(key=lambda i: (i.line, i.rule, i.message))
    return cleaned, issues


def lint_file(path: str | Path, check_only: bool = False,
              fix: bool = False) -> LintResult:
    """Lint a file; optionally rewrite it in place when changes exist."""
    p = Path(path)
    original = p.read_text(encoding="utf-8", errors="replace")
    cleaned, issues = lint_text(original)
    changed = cleaned != original
    result = LintResult(path=p, issues=issues, changed=changed,
                        cleaned_text=cleaned)
    if fix and changed and not check_only:
        p.write_text(cleaned, encoding="utf-8", newline="")
    return result


__all__ = ["CANONICAL_COMMANDS", "LintIssue", "LintResult",
           "lint_file", "lint_text"]
