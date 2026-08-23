"""User-defined custom rules for UPF-Insight (declarative YAML rulesets).

An analog of the declarative policy layer: a ruleset is inert data validated
against a fixed schema. Custom rules add team-specific lint findings on top of
the built-in registry - they never remove or weaken engine evidence.

Schema per rule:
    id:       must match CUST-<3 digits>
    severity: error | warning | info
    match:    command (required, UPF command name or *), option (optional
              Tcl option name, e.g. isolation_supply), pattern (optional
              regex applied to the raw record text)
    message:  required human-readable finding text
    why:      optional rationale

Application is deterministic: rules in file order, records in stream order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import IO, List, Optional, Union

import yaml

from ...preprocess.upf_preprocess import CommandRecord
from ..rules.finding import Finding

RULE_ID_PATTERN = re.compile(r"^CUST-\d{3}$")
_SEVERITIES = ("error", "warning", "info")
_ALLOWED_RULE_KEYS = {"id", "severity", "match", "message", "why"}
_ALLOWED_MATCH_KEYS = {"command", "option", "pattern"}


@dataclass(frozen=True)
class CustomRule:
    """One user-defined declarative rule."""

    id: str
    severity: str
    message: str
    match_command: str
    match_option: Optional[str] = None
    match_pattern: Optional[re.Pattern] = None
    why: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.match_pattern, str):
            object.__setattr__(self, "match_pattern", re.compile(self.match_pattern))


def _validate_rule(raw: object, index: int) -> CustomRule:
    where = f"rules[{index}]"
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: each rule must be a mapping")
    unknown = set(raw) - _ALLOWED_RULE_KEYS
    if unknown:
        raise ValueError(f"{where}: unknown keys {sorted(unknown)}; "
                         f"allowed: {sorted(_ALLOWED_RULE_KEYS)}")
    rid = raw.get("id")
    if not isinstance(rid, str) or not RULE_ID_PATTERN.match(rid):
        raise ValueError(
            f"{where}: 'id' must match CUST-\\d{{3}} (e.g. CUST-001), "
            f"got {rid!r}")
    severity = raw.get("severity")
    if severity not in _SEVERITIES:
        raise ValueError(f"{where}: 'severity' must be one of "
                         f"{list(_SEVERITIES)}, got {severity!r}")
    message = raw.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError(f"{where}: 'message' must be a non-empty string")
    why = raw.get("why", "")
    if not isinstance(why, str):
        raise ValueError(f"{where}: 'why' must be a string")
    match = raw.get("match")
    if not isinstance(match, dict) or not match:
        raise ValueError(f"{where}: 'match' must be a non-empty mapping")
    unknown_match = set(match) - _ALLOWED_MATCH_KEYS
    if unknown_match:
        raise ValueError(f"{where}: unknown match keys {sorted(unknown_match)}; "
                         f"allowed: {sorted(_ALLOWED_MATCH_KEYS)}")
    command = match.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError(f"{where}: match.command must be a non-empty "
                         f"command name or '*'")
    option = match.get("option")
    if option is not None and (not isinstance(option, str)
                               or not option.strip()):
        raise ValueError(f"{where}: match.option must be an option name string")
    pattern_raw = match.get("pattern")
    compiled: Optional[re.Pattern] = None
    if pattern_raw is not None:
        if not isinstance(pattern_raw, str) or not pattern_raw:
            raise ValueError(f"{where}: match.pattern must be a regex string")
        try:
            compiled = re.compile(pattern_raw)
        except re.error as exc:
            raise ValueError(
                f"{where}: invalid match.pattern regex {pattern_raw!r}: "
                f"{exc}") from exc
    return CustomRule(id=rid, severity=severity, message=message,
                      match_command=command.lower(), match_option=option,
                      match_pattern=compiled, why=why)


def load_custom_rules(path_or_stream: Union[str, IO[str]]) -> List[CustomRule]:
    """Load and schema-validate a YAML custom-rules file or open stream."""
    if hasattr(path_or_stream, "read"):
        text = path_or_stream.read()
    else:
        with open(path_or_stream, "r", encoding="utf-8") as fh:
            text = fh.read()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in custom rules: {exc}") from exc
    if isinstance(data, dict):
        unknown_top = set(data) - {"rules"}
        if unknown_top:
            raise ValueError(f"unknown top-level keys {sorted(unknown_top)}; "
                             f"expected {{'rules': [...]}}")
        items = data.get("rules")
    else:
        items = data
    if not isinstance(items, list):
        raise ValueError("custom rules document must be a list of rules or a "
                         "mapping with a 'rules' list")
    return [_validate_rule(item, i) for i, item in enumerate(items)]


def _has_option(text: str, option: str) -> bool:
    for token in text.split():
        if token.startswith("-") and token.lstrip("-").lower() == \
                option.lstrip("-").lower():
            return True
    return False


def apply_custom_rules(records: List[CommandRecord],
                       rules: List[CustomRule]) -> List[Finding]:
    """Apply custom rules to preprocessed records deterministically.

    Rules are applied in file order; within one rule, records are visited in
    stream order. Every hit yields a Finding with the record's provenance.
    """
    findings: List[Finding] = []
    for rule in rules:
        for record in records:
            if rule.match_command != "*" and \
                    record.command_name != rule.match_command:
                continue
            if rule.match_option is not None and \
                    not _has_option(record.text, rule.match_option):
                continue
            if rule.match_pattern is not None and \
                    rule.match_pattern.search(record.text) is None:
                continue
            findings.append(Finding(rule=rule.id, severity=rule.severity,
                                    message=rule.message, file=record.file,
                                    line=record.line))
    return findings


__all__ = ["CustomRule", "load_custom_rules", "apply_custom_rules",
           "RULE_ID_PATTERN"]
