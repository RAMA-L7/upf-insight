"""Adversarial coverage matrix - 12 semantic categories, 42 mutations.

The corpus (clean baseline + one-defect-per-mutation texts) lives in
``upf_insight/engine/quality.py`` - the SAME corpus the CLI ``quality``
report consumes. These tests assert the corpus contract: every mutation is
detected by its expected rule, the clean baseline stays error-free, and the
metrics stay at 100% detection with zero false positives.

The headline metric: mutations detected / mutations attempted. The clean
baseline carries only review-level advisory warnings (trust boundary), and
every intended defect produces at least one additional finding.

Determinism is verified by SHA-256 over repeated generation.
"""

import hashlib

import pytest

from upf_insight.engine.quality import (
    BASE, MUTATIONS, CATEGORIES, clean_baseline, run_quality_report,
)
from upf_insight.preprocess.upf_preprocess import preprocess
from upf_insight.engine.engine import validate_records


def _msgset(text: str) -> set:
    res = validate_records(preprocess(text, file="<mutated>"))
    return {(f.rule, f.severity, f.message) for f in res.check.findings}


def _added_rules(text: str, base: set) -> set:
    return {r for r, s, m in _msgset(text) - base}


def _errors(text: str) -> set:
    return {f.rule for f in validate_records(preprocess(text, file="<mutated>"))
            .check.findings if f.severity == "error"}


def test_clean_baseline_has_zero_errors():
    errors = [f.rule for f in validate_records(preprocess(BASE, file="<x>"))
              .check.findings if f.severity == "error"]
    assert errors == [], f"clean baseline must have 0 errors, got {errors}"


def test_every_mutation_detected_with_expected_rule():
    """The headline metric: every intended defect is detected, each by its
    expected rule (not merely by cascade noise)."""
    base = _msgset(BASE)
    missed = []
    for category, name, mutated, expected in MUTATIONS:
        added = _added_rules(mutated, base)
        if expected not in added:
            missed.append((category, name, expected, sorted(added)))
    assert missed == [], (
        f"{len(missed)} mutation(s) not detected by expected rule:\n" +
        "\n".join(f"  [{c}] {n}: expected {e}, added {a}" for c, n, e, a in missed))


def test_mutation_detection_rate():
    base = _msgset(BASE)
    detected = sum(1 for _, _, mutated, _ in MUTATIONS if _added_rules(mutated, base))
    assert detected == len(MUTATIONS), f"detected {detected}/{len(MUTATIONS)}"
    assert detected == 42


def test_no_false_positive_on_clean_baseline():
    """The clean baseline must not carry any mutation-specific rule."""
    base_rules = {r for r, s, m in _msgset(BASE)}
    mutation_rules = {e for _, _, _, e in MUTATIONS}
    assert base_rules & mutation_rules == set(), (
        f"clean baseline already carries mutation rules: "
        f"{sorted(base_rules & mutation_rules)}")


def test_every_category_has_mutations():
    seen = {c for c, _, _, _ in MUTATIONS}
    assert seen == set(CATEGORIES), (
        f"category coverage mismatch: missing {set(CATEGORIES) - seen}")


def test_per_category_detection():
    base = _msgset(BASE)
    for cat in CATEGORIES:
        in_cat = [(n, m, e) for c, n, m, e in MUTATIONS if c == cat]
        assert len(in_cat) >= 2, f"category '{cat}' needs >= 2 mutations"
        for name, mutated, expected in in_cat:
            added = _added_rules(mutated, base)
            assert expected in added, (
                f"[{cat}] '{name}': expected {expected}, added {sorted(added)}")


def test_determinism_sha256_identical():
    """Same input must produce byte-identical UPF every run."""
    digests = set()
    for _ in range(3):
        digests.add(hashlib.sha256(clean_baseline().encode("utf-8")).hexdigest())
    assert len(digests) == 1


def test_each_mutation_actually_changes_the_text():
    """Guard against no-op mutations (string drift breaking the suite)."""
    for category, name, mutated, _ in MUTATIONS:
        assert mutated != BASE, f"[{category}] '{name}' is a no-op mutation"


def test_error_severity_of_mutation_rules():
    """Structural/blocking defects must be errors, not advisories."""
    error_rules = {e for _, _, _, e in MUTATIONS}
    for rule in ("UPF-073", "UPF-039", "UPF-075", "UPF-076", "UPF-077",
                 "UPF-078", "UPF-065", "UPF-061", "UPF-062", "UPF-041",
                 "UPF-053", "UPF-031", "UPF-013"):
        assert rule in error_rules


# ── Quality-report contract (shared corpus, shared metric) ────────────────

def test_quality_report_full_detection_zero_baseline_false_positives():
    """The CLI report and the regression suite agree on the same corpus."""
    report = run_quality_report()
    assert report.total_mutations == len(MUTATIONS) == 42
    assert report.detected == 42
    assert report.missed == []
    assert report.baseline_errors == 0
    assert report.baseline_false_positives == 0
    assert report.detection_rate == 1.0


def test_quality_report_json_is_structured_and_deterministic():
    """The JSON form carries the same numbers and is stable across runs."""
    import json

    a = json.dumps(run_quality_report().to_dict(), sort_keys=True)
    b = json.dumps(run_quality_report().to_dict(), sort_keys=True)
    assert a == b
    d = json.loads(a)
    assert d["detection_rate"] == 1.0
    assert d["baseline_false_positives"] == 0
    assert len(d["per_category"]) == len(CATEGORIES)
