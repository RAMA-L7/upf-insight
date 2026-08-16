"""Regression tests for the realistic CPU-subsystem fixture.

Contract being proven (semantic, not formatting):

- V1 (known-good) is clean: 0 errors, PASS, domain/supply coverage 1.0,
  readiness not BLOCKED, in both UPF-only and design-aware modes.
- V2 (regressed) is blocked: UPF-061 fires for every voltage-differing
  domain pair (the level shifter on the 1.8 V I/O boundary was removed),
  readiness is BLOCKED, coverage reports the missing strategy.
- The regression is real and minimal: removing exactly that one construct
  flips V1 -> V2; re-adding it flips V2 -> V1.
- Diff identifies the removed level shifter.
- A STRICT / NO_READINESS_REGRESSION / BLOCKERS_ONLY gate blocks V2 vs the
  V1 baseline (exit 1); a gate over an unchanged baseline passes (exit 0).
- Findings carry accurate line numbers and stable, deterministic output.
"""

import json
import os

import pytest

from upf_insight.diff.differ import diff_files
from upf_insight.engine.engine import validate
from upf_insight.engine.policy.policy_engine import apply_policy
from upf_insight.preprocess.upf_preprocess import preprocess

EXAMPLES = "tests/examples/cpu_subsys"
V1 = f"{EXAMPLES}/cpu_subsys_v1.upf"
V2 = f"{EXAMPLES}/cpu_subsys_v2.upf"
DESIGN = f"{EXAMPLES}/cpu_subsys_design.json"


def _find_line(path: str, needle: str) -> int:
    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if needle in line:
                return i
    raise AssertionError(f"needle {needle!r} not found in {path}")


# ── V1: known-good ──────────────────────────────────────────────────────────

def test_v1_is_clean():
    result = validate([V1])
    assert result.check.error_count == 0
    assert result.clean
    assert not any(f.rule.startswith("UPF-06") and f.severity == "error"
                   for f in result.check.findings)


def test_v1_coverage_full():
    result = validate([V1])
    assert result.coverage.domain_coverage == 1.0
    assert result.coverage.supply_coverage == 1.0
    assert all(d.covered for d in result.coverage.domains)


def test_v1_readiness_not_blocked():
    result = validate([V1])
    assert result.readiness.overall != "BLOCKED"


def test_v1_design_aware_is_clean():
    result = validate([V1], netlist=DESIGN)
    assert result.check.error_count == 0
    # All instances/signals/PG pins resolve; no design-aware findings.
    assert not any(f.rule.startswith("UPF-08") for f in result.check.findings)
    # Readiness must now reflect that a design context WAS supplied.
    dim = result.readiness.dimensions["DESIGN_CONTEXT"]
    assert "not supplied" not in dim.summary
    assert "instance" in dim.summary


def test_v1_design_aware_retention_covers_sequential():
    """The retention strategies cover u_cpu/u_sram; UPF-083 must not fire."""
    result = validate([V1], netlist=DESIGN)
    assert not any(f.rule == "UPF-083" for f in result.check.findings)


# ── V2: regressed ───────────────────────────────────────────────────────────

def test_v2_fires_upf061_for_each_voltage_pair():
    result = validate([V2])
    errors = [f for f in result.check.findings
              if f.rule == "UPF-061" and f.severity == "error"]
    # PD_CPU(1.0) <-> PD_IO(1.8), PD_AO(1.0) <-> PD_IO(1.8),
    # PD_IO(1.8) <-> PD_SRAM(1.0): three differing pairs, all unshifted.
    assert len(errors) == 3
    assert all("1.8V" in f.message for f in errors)
    assert all("PD_IO" in f.message for f in errors)


def test_v2_is_blocked():
    result = validate([V2])
    assert not result.clean
    assert result.readiness.overall == "BLOCKED"
    assert any(b["code"] == "UPF-061" for b in result.readiness.blockers)


def test_v2_design_aware_still_blocked():
    result = validate([V2], netlist=DESIGN)
    assert not result.clean
    assert result.readiness.overall == "BLOCKED"
    assert any(f.rule == "UPF-061" for f in result.check.findings)


def test_v2_coverage_misses_level_shifter():
    result = validate([V2])
    io = next(d for d in result.coverage.domains if d.domain == "PD_IO")
    assert io.has_level_shifter is False


def test_regression_is_exactly_one_construct():
    """Removing the level-shifter line flips V1 -> V2; re-adding flips back."""
    with open(V1, "r", encoding="utf-8") as fh:
        v1_text = fh.read()
    removed = "\n".join(
        line for line in v1_text.splitlines()
        if "set_level_shifter" not in line
    )
    regressed = validate([V1], netlist=None)
    # Rebuild V1 without the shifter -> must behave like V2.
    from upf_insight.engine.engine import validate_records

    result = validate_records(preprocess(removed, file="<v1-minus-ls>"))
    assert not result.clean
    assert any(f.rule == "UPF-061" for f in result.check.findings)
    assert regressed.clean


# ── Diff ────────────────────────────────────────────────────────────────────

def test_diff_identifies_removed_level_shifter():
    changes = diff_files(V1, V2)
    strategy_changes = [c for c in changes if c.what == "strategy"]
    assert any("level_shifter" in c.name or "level_shifter" in c.detail
               for c in strategy_changes)


def test_diff_v1_vs_v1_is_empty():
    assert diff_files(V1, V1) == []


# ── CI gate ─────────────────────────────────────────────────────────────────

def _baseline_payload(path: str, netlist=None) -> dict:
    return validate([path], netlist=netlist).to_dict()


def test_gate_blocks_regressed_v2():
    baseline = _baseline_payload(V1)
    current = _baseline_payload(V2)
    for policy in ("BLOCKERS_ONLY", "NO_READINESS_REGRESSION", "STRICT"):
        gate = apply_policy(policy, current, baseline)
        assert not gate.passed, policy
        assert gate.exit_code == 1, policy


def test_gate_passes_unchanged_v1():
    baseline = _baseline_payload(V1)
    current = _baseline_payload(V1)
    gate = apply_policy("STRICT", current, baseline)
    assert gate.passed
    assert gate.exit_code == 0


# ── Provenance & determinism ────────────────────────────────────────────────

def test_findings_carry_accurate_lines():
    result = validate([V2])
    errors = [f for f in result.check.findings if f.rule == "UPF-061"]
    assert all(f.line is not None for f in errors)
    # UPF-061 reports the first domain of each differing pair: PD_CPU(38),
    # PD_AO(39), PD_IO(40) in V2. The line must be an accurate source line.
    lines = {f.line for f in errors}
    assert len(lines) == 3
    assert _find_line(V2, "create_power_domain PD_CPU") in lines
    assert _find_line(V2, "create_power_domain PD_AO") in lines
    assert _find_line(V2, "create_power_domain PD_IO") in lines
    # File provenance is populated from the authoritative record stream
    # (see test_provenance.py): single-file runs resolve exactly, ambiguous
    # multi-file colliding lines stay empty rather than invented.
    assert all(os.path.normpath(f.file) == os.path.normpath(V2) for f in errors)


def test_deterministic_output():
    a = validate([V1], netlist=DESIGN).to_dict()
    b = validate([V1], netlist=DESIGN).to_dict()
    assert json.dumps(a, sort_keys=True, default=str) == \
        json.dumps(b, sort_keys=True, default=str)


def test_empty_and_invalid_input_are_honest():
    from upf_insight.engine.engine import validate_records

    empty = validate_records([])
    assert empty.readiness.overall == "INSUFFICIENT_CONTEXT"
    assert empty.support.statuses["NOT_VALIDATED"] == 1
    # A rule handler must never crash the run.
    from upf_insight.model.builder import build_model
    from upf_insight.engine.rules.checker import check_model

    model = build_model([])
    result = check_model(model)
    assert isinstance(result.findings, list)


def test_cli_contract_round_trip():
    """CLI exit codes: 0 for V1, 1 for V2, 2 for missing file."""
    from upf_insight.cli.cli import main

    assert main(["check", V1]) == 0
    assert main(["check", V2]) == 1
    assert main(["check", "no_such_file.upf"]) == 2


def test_cli_gate_without_baseline_gates_current_evidence():
    """--gate alone must evaluate the current evidence (CLI/API agreement)."""
    from upf_insight.cli.cli import main

    assert main(["check", V1, "--gate", "STRICT"]) == 0
    assert main(["check", V2, "--gate", "STRICT"]) == 1


def test_cli_invalid_policy_is_exit_2():
    """An unknown policy is an invalid invocation (2), never silently ignored."""
    from upf_insight.cli.cli import main

    assert main(["check", V2, "--gate", "BOGUS_POLICY"]) == 2


def test_cli_engine_failure_is_exit_3(monkeypatch):
    """An unexpected engine exception is loud and maps to exit 3."""
    from upf_insight.cli import cli as cli_mod

    def boom(*args, **kwargs):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(cli_mod, "validate", boom)
    assert cli_mod.main(["check", V1]) == 3
