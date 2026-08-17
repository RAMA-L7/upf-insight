"""Declarative CI policy engine - gates over readiness + baseline evidence."""

from .policy_engine import (
    EXIT_PASS,
    EXIT_GATE_FAILED,
    EXIT_INVALID,
    EXIT_ENGINE_FAILURE,
    BUILTIN_POLICIES,
    GateResult,
    apply_policy,
)

__all__ = [
    "EXIT_PASS", "EXIT_GATE_FAILED", "EXIT_INVALID", "EXIT_ENGINE_FAILURE",
    "BUILTIN_POLICIES", "GateResult", "apply_policy",
]