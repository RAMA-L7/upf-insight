# UPF-Insight — Product Roadmap

> **Document kind:** product roadmap.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## Vision

UPF-Insight is the power-intent quality layer that runs **before** power-aware
implementation — the low-power sibling of the Ṛta SDC validator. Deterministic,
local-first, honest about its support boundary.

## Now — v0.1.0 (scaffold, shipped)

- Full repo skeleton mirroring the sdc-tools layout: package, CLI, docs,
  tests, examples.
- Preprocess → model build → check → support boundary → PST pipeline.
- Layers 1–5 rule catalog (registry contract), initial handlers for:
  UPF-001, 011, 020, 022, 023, 032, 034, 045, 050, 052, 060.
- Commands: `check`, `model`, `pst`, `diff`, `generate`, `web`.
- 8-test core engine suite; golden known-good/known-bad fixtures.

## Next — v0.2.0 (rule completeness)

- Complete Layer 1–2 handlers: option validation (UPF-002/003), duplicate
  detection (UPF-013), use-before-definition (UPF-014), scope checks.
- Complete Layer 4: UPF-030/031/033/035/036 against the PST analyzer.
- Complete Layer 5 isolation set: UPF-040…047 (isolation supply/location,
  applies_to, clamp).
- Custom rules (YAML) — first-class user-defined rulesets.
- Reports: JUnit/HTML + `--junit` flag for CI.

## Later — v0.3.0 (readiness & diff depth)

- **Readiness** model (seven power-intent dimensions, aggregate verdict:
  READY / READY_WITH_ADVISORIES / REVIEW_REQUIRED / BLOCKED /
  INSUFFICIENT_CONTEXT).
- **Diff** upgrades: saved-baseline snapshots (JSON), finding identity,
  trust/coverage deltas, gate policies (`--gate`) + exit-code enforcement.
- Full level-shifter + retention + switch rule families.

## v1.0 (production hardening)

- 100+ evidence test suite (mutation-tested rule set).
- Conformance corpus: parse open-source IEEE 1801 examples for the support
  boundary.
- Packaging polish, CI actions, pre-commit hooks.
- Retention-coverage helper: sequential-element vs retention strategy
  alignment (needs netlist — see v2).

## v2.0 (design-aware)

- **Netlist/RTL context** reader (mirrors sdc-tools `design_context`):
  - Instance existence (UPF-080)
  - Control-signal existence (UPF-081)
  - Endpoint-based crossing coverage (UPF-082)
  - Retention coverage vs actual flops (UPF-083)
  - Library PG mapping (UPF-084)
- Power-state group and macro support (UPF 3.0/4.0 depth).

## v3.0 (team/enterprise)

- Corporate policy rulesets, CI plugins, golden integrations.
- Formal-adjacent retention helpers and PST formal checking.

## Out of scope (by design)

- Power/IR analysis, STA, formal equivalence.
- "AI-powered" analysis in the engine path.
- Any cloud dependency.

## Principles that never change

- Deterministic engine; same input → same output.
- Every finding traces to evidence.
- Support boundary always disclosed ("no errors ≠ proven correct").
- Local-first; Tcl detected, never executed.
- Open-core: community MIT; enterprise layers are additive, never
  degradations.