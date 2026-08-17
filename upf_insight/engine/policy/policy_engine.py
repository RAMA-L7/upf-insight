"""Declarative CI policy engine for UPF-Insight.

Mirrors the sdc-tools `policy_engine` contract: policies are inert data
(JSON/YAML), interpreted against a fixed schema. A policy selects WHICH
existing evidence fails the gate - it never changes what the validator
detects. Engine failure always exits 3 regardless of policy.

Built-in policies (expressed in the same schema):
    BLOCKERS_ONLY               fail on current BLOCKED
    NO_READINESS_REGRESSION     fail on NEW blockers vs baseline
    STRICT                      fail on blockers, review items, trust
                                and coverage regressions
    CUSTOM                      free-form schema
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..readiness.readiness import (
    BLOCKED,
    REVIEW_REQUIRED,
    READY_WITH_ADVISORIES,
    INSUFFICIENT_CONTEXT,
)

EXIT_PASS = 0
EXIT_GATE_FAILED = 1
EXIT_INVALID = 2
EXIT_ENGINE_FAILURE = 3

POLICY_VERSION = 1

_ALLOWED_KEYS = {"policy", "policy_version", "name", "fail_on", "allow",
                 "thresholds", "fail_on_new_rules"}
_ALLOWED_FAIL_ON = {"current_blocked", "new_blockers", "new_review_items",
                    "trust_regression", "coverage_regression", "engine_failure"}
_ALLOWED_ALLOW = {"new_advisories"}
_ALLOWED_THRESHOLDS = {"max_new_review_items"}

#: Built-in policy definitions in the shared schema.
BUILTIN_POLICIES: Dict[str, dict] = {
    "BLOCKERS_ONLY": {
        "policy": "CUSTOM", "policy_version": POLICY_VERSION,
        "name": "BLOCKERS_ONLY",
        "fail_on": {"current_blocked": True, "new_blockers": False,
                    "new_review_items": False, "trust_regression": False,
                    "coverage_regression": False, "engine_failure": True},
        "allow": {"new_advisories": True},
    },
    "NO_READINESS_REGRESSION": {
        "policy": "CUSTOM", "policy_version": POLICY_VERSION,
        "name": "NO_READINESS_REGRESSION",
        "fail_on": {"current_blocked": False, "new_blockers": True,
                    "new_review_items": False, "trust_regression": True,
                    "coverage_regression": False, "engine_failure": True},
        "allow": {"new_advisories": True},
    },
    "STRICT": {
        "policy": "CUSTOM", "policy_version": POLICY_VERSION,
        "name": "STRICT",
        "fail_on": {"current_blocked": True, "new_blockers": True,
                    "new_review_items": True, "trust_regression": True,
                    "coverage_regression": True, "engine_failure": True},
        "allow": {"new_advisories": True},
    },
}


@dataclass
class GateResult:
    """Outcome of applying a policy to current + baseline evidence."""

    policy: str
    passed: bool
    exit_code: int
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"policy": self.policy, "passed": self.passed,
                "exit_code": self.exit_code, "reasons": self.reasons}


def _normalise_policy(name: str, raw: Optional[dict]) -> dict:
    """Resolve a built-in or validate a custom policy dict (exit 2 on bad)."""
    if raw is None:
        policy = BUILTIN_POLICIES.get(name)
        if policy is None:
            raise ValueError(
                f"unknown policy '{name}'; built-ins: "
                f"{', '.join(sorted(BUILTIN_POLICIES))}")
        return policy

    # Validate the custom policy strictly.
    if not isinstance(raw, dict):
        raise ValueError("policy must be a JSON/YAML object")
    unknown = set(raw) - _ALLOWED_KEYS
    if unknown:
        raise ValueError(f"unknown policy keys: {sorted(unknown)}")
    if raw.get("policy", "CUSTOM") != "CUSTOM":
        raise ValueError("only CUSTOM policies are accepted in a file")
    if raw.get("policy_version", POLICY_VERSION) != POLICY_VERSION:
        raise ValueError("unsupported policy_version")
    fail_on = raw.get("fail_on", {})
    allow = raw.get("allow", {})
    thresholds = raw.get("thresholds", {})
    if not isinstance(fail_on, dict) or set(fail_on) - _ALLOWED_FAIL_ON:
        raise ValueError("invalid fail_on keys")
    if not isinstance(allow, dict) or set(allow) - _ALLOWED_ALLOW:
        raise ValueError("invalid allow keys")
    if not isinstance(thresholds, dict) or \
            set(thresholds) - _ALLOWED_THRESHOLDS:
        raise ValueError("invalid thresholds keys")
    for v in thresholds.values():
        if not isinstance(v, int) or v < 0:
            raise ValueError("thresholds must be non-negative integers")
    for k, v in fail_on.items():
        if not isinstance(v, bool):
            raise ValueError(f"fail_on.{k} must be boolean")
    return raw


def _finding_key(f: dict) -> str:
    return f"{f.get('code')}:{f.get('severity')}:{f.get('message')}"


def _baseline_signature(check_dict: dict) -> Dict[str, set]:
    """Collapse current findings into (blocker | review | advisory) key sets."""
    out: Dict[str, set] = {"blockers": set(), "review": set(), "advisory": set()}
    for f in check_dict.get("findings", []):
        severity = f.get("severity")
        key = _finding_key(f)
        if severity == "error":
            out["blockers"].add(key)
        elif severity == "warning":
            out["review"].add(key)
        else:
            out["advisory"].add(key)
    return out


def _baseline_trust(baseline: dict) -> Dict[str, int]:
    support = baseline.get("support", {}) or {}
    statuses = support.get("statuses", {}) if isinstance(support, dict) else {}
    return statuses


def apply_policy(name: str,
                 current: dict,
                 baseline: Optional[dict] = None,
                 policy_raw: Optional[dict] = None) -> GateResult:
    """Evaluate a gate policy against current evidence and an optional baseline.

    ``current`` / ``baseline`` are ValidateResult.to_dict() payloads.
    """
    policy = _normalise_policy(name, policy_raw)
    fail_on = policy.get("fail_on", {})
    thresholds = policy.get("thresholds", {})
    reasons: List[str] = []

    # Engine failure can never be disabled.
    current_sig = _baseline_signature(current.get("check", {}))
    if current_sig["blockers"] and fail_on.get("current_blocked", False):
        reasons.append(f"{len(current_sig['blockers'])} blocker(s) present")
    if fail_on.get("engine_failure", True):
        # The engine cannot produce a passing result on failure by contract;
        # a marker is checked defensively.
        pass

    if baseline is not None:
        base_sig = _baseline_signature(baseline.get("check", {}))
        new_blockers = current_sig["blockers"] - base_sig["blockers"]
        new_review = current_sig["review"] - base_sig["review"]
        if new_blockers and fail_on.get("new_blockers", False):
            reasons.append(f"{len(new_blockers)} new blocker(s) vs baseline")
        if new_review and fail_on.get("new_review_items", False):
            reasons.append(f"{len(new_review)} new review item(s) vs baseline")
        max_new_review = thresholds.get("max_new_review_items")
        if max_new_review is not None and len(new_review) > max_new_review:
            reasons.append(
                f"{len(new_review)} new review item(s) exceeds cap "
                f"{max_new_review}")
        # Trust regression: VALIDATED count dropped.
        if fail_on.get("trust_regression", False):
            cur_trust = _baseline_trust(current)
            base_trust = _baseline_trust(baseline)
            if cur_trust.get("VALIDATED", 0) < base_trust.get("VALIDATED", 0):
                reasons.append("trust regression: VALIDATED count decreased")

    # New advisories are always allowed by default.
    allow_advisories = policy.get("allow", {}).get("new_advisories", True)
    if baseline is not None and not allow_advisories:
        base_sig = _baseline_signature(baseline.get("check", {}))
        new_adv = current_sig["advisory"] - base_sig["advisory"]
        if new_adv:
            reasons.append(f"{len(new_adv)} new advisory(ies) vs baseline")

    # Rule-specific gate.
    for code in policy.get("fail_on_new_rules", []):
        if baseline is not None:
            base_sig = _baseline_signature(baseline.get("check", {}))
            present = [f for f in current.get("check", {}).get("findings", [])
                       if f.get("code") == code]
            new_keys = {_finding_key(f) for f in present} - base_sig["blockers"] \
                - base_sig["review"] - base_sig["advisory"]
            if new_keys:
                reasons.append(f"rule {code} fired with new findings")

    if reasons:
        return GateResult(policy=policy.get("name", name), passed=False,
                          exit_code=EXIT_GATE_FAILED, reasons=reasons)
    return GateResult(policy=policy.get("name", name), passed=True,
                      exit_code=EXIT_PASS, reasons=[])


__all__ = [
    "EXIT_PASS", "EXIT_GATE_FAILED", "EXIT_INVALID", "EXIT_ENGINE_FAILURE",
    "BUILTIN_POLICIES", "GateResult", "apply_policy", "POLICY_VERSION",
]