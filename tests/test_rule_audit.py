"""Rule-registry audit regression tests.

Every registered rule must carry full semantic metadata, every handler must
have a registry entry and vice versa, ``depends_on`` references must resolve to
error-severity rules without cycles, and the registry must be deterministic
(same order every call). This keeps the growing rule set honest.
"""

import pytest

from upf_insight.engine.rules.audit import audit_registry
from upf_insight.engine.rules.rules_registry import registered_rules
from upf_insight.engine.rules.upf_rules import RULE_HANDLERS


def test_audit_is_clean():
    """The whole registry must pass the audit - no drift allowed."""
    report = audit_registry()
    assert report["clean"], "rule registry drift:\n" + "\n".join(
        f"  - {p}" for p in report["problems"])


def test_registry_handler_sync():
    """Every registered code has a handler and vice versa."""
    codes = {r.code for r in registered_rules()}
    assert codes == set(RULE_HANDLERS)


def test_all_rules_have_semantic_metadata():
    """Every rule carries semantic_inputs, context, and a test reference."""
    for r in registered_rules():
        assert r.semantic_inputs, f"{r.code}: empty semantic_inputs"
        assert r.context in ("UPF_ONLY", "NETLIST_REQUIRED", "PARTIAL"), \
            f"{r.code}: invalid context {r.context!r}"
        assert r.test_ref, f"{r.code}: empty test_ref"


def test_depends_on_targets_are_error_rules():
    """Cascade suppression only blocks on error-severity prerequisites."""
    by_code = {r.code: r for r in registered_rules()}
    for r in registered_rules():
        for dep in r.depends_on:
            target = by_code.get(dep)
            assert target is not None, f"{r.code}: depends_on unknown '{dep}'"
            assert target.severity == "error", \
                f"{r.code}: depends_on '{dep}' is not error-severity"


def test_registry_ordering_is_deterministic():
    """Registered rules come back in a stable, sorted order."""
    a = [r.code for r in registered_rules()]
    b = [r.code for r in registered_rules()]
    assert a == b
    assert a == sorted(a)


def test_cascade_suppression_rules_registered():
    """The primary-error cascade subjects are declared in the registry."""
    by_code = {r.code: r for r in registered_rules()}
    assert by_code["UPF-073"].depends_on == ("UPF-010",)
    assert by_code["UPF-070"].depends_on == ("UPF-010",)
    assert by_code["UPF-011"].depends_on == ()
