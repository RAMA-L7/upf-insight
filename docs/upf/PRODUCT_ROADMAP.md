# UPF-Insight — Product Roadmap

> **Document kind:** product roadmap.
> **Date:** 2026-10-01 · **Version:** v0.3.0 (see `pyproject.toml`)

> **This document is a snapshot, regenerated from the code.** Figures below
> are read from the registry, the test suite, and `engine/quality.py` — not
> carried forward by hand. If a number here disagrees with the code, the code
> wins; regenerate rather than edit.

---

## Vision

UPF-Insight is the power-intent quality layer that runs **before** power-aware
implementation — the low-power sibling of the Ṛta SDC validator. Deterministic,
local-first, honest about its support boundary.

## Where we are — v0.3.0 (shipped)

| Metric | Value | Source |
|---|---|---|
| Registered rules | **77** (UPF-001…100) | `rules_registry.registered_rules()` |
| Registry/handler parity | **exact**, audit clean | `rules/audit.py` |
| Test suite | **299 passing** | `python -m pytest tests/ -q` |
| Mutation corpus | **42 / 42 detected** (100%) | `engine/quality.py` |
| Mutation precision | **0.57** overall, **0.74** on errors | `engine/quality.py` |
| CLI subcommands | 16 top-level (+3 under `rules`) | `cli/cli.py` |
| Python | 3.10+, stdlib-only core, `pyyaml` the sole dependency | `pyproject.toml` |

Rule layers: STRATEGY 36 · PST 10 · REFERENCE 10 · DESIGN 8 · SYNTAX 6 ·
SUPPLY_DOMAIN 6 · SUPPLY 1.

### Shipped in v0.3.0

- Preprocess → model → check → support-boundary → PST → readiness pipeline,
  with semantic diff, generator, batch/lint/convert tools, and a local web UI.
- **Cross-file scope semantics** — scope is per-file state; `load_upf -scope`
  establishes the child's scope per IEEE 1801. Results no longer depend on the
  order files are listed on the command line.
- **PST transition context** — `add_state_transition` applies to the table
  currently being defined, not to every table.
- **Generated rules reference** — `docs/upf/RULES_REGISTRY.md` is built from
  the live registry and guarded by a drift test, so it cannot fall behind again.
- Honest support boundary: internal rule errors report `NOT_VALIDATED`, never
  `VALIDATED`; `support_boundary` is populated on every run.

## Next — v0.4.0 (precision and reach)

The mutation corpus detects every seeded defect but fires on **43% of its
findings** (precision 0.57). That is the clearest measure of the gap between
"catches the bug" and "tells you something true". v0.4.0 is about closing it.

- **Precision work** — triage the non-error findings the mutation corpus
  provokes; either sharpen the rules or demote what cannot be decided without
  a netlist. Target: error-precision above 0.9.
- **Retention coverage (UPF-083)** — compare declared retention against actual
  sequential elements. Catches both under-retention (silent corruption) and
  over-retention (2–3× area on don't-care flops), which is invisible today.
- **Endpoint crossing coverage (UPF-082)** — with a netlist, compute real
  domain crossings and diff them against declared strategies. This is the
  change that moves the tool from *"you declared isolation for PD_CORE"* to
  *"these 14 signals reach PD_AON with no strategy"*.
- **CI first-class** — a GitHub Action and pre-commit hook. The engine is
  deterministic with a 0/1/2/3 exit contract and is already CI-shaped; nothing
  uses it yet.

## Later — v0.5.0 (adoption)

- **Baseline workflow** — `--save-baseline` / `--baseline` / `--gate` exist;
  what is missing is the flow: review findings → accept → save → gate future
  PRs against it.
- **`set_port_attributes` depth** — `always_on`, `supply`, and isolation
  attributes are parsed shallowly. Deeper inference converts several
  `PARTIAL`/`NETLIST_REQUIRED` statuses to `VALIDATED`.
- **Open-source conformance corpus** — parse public IEEE 1801 examples. Makes
  the support boundary concrete instead of theoretical.

## v1.0 (production hardening)

- Packaging polish, release automation, signature/provenance on reports.
- Multi-corner and DVFS operating-point modeling.
- Power-state groups and macros (UPF 3.0/4.0 depth).

## Known gaps (verified, not scheduled)

Recorded so they are not rediscovered as "bugs":

- `differ.py` compares strategies **count-only**; a content change inside an
  isolation/retention/level-shifter strategy is not detected.
- `record_files` is keyed by **line number alone**, so two files with commands
  on the same line are ambiguous. Consumers correctly return "no file" rather
  than guessing, but the provenance is weaker than it looks.
- `RepeaterStrategy` carries no `scope` field, so cross-scope duplicate
  detection is weaker for repeaters than for the other three strategy types.
- `analyze_pst` analyzes the **first** PST only; a multi-table design gets one
  table's coverage report.
- `create_supply_net -resolve`, `create_supply_port -domain`, and
  `create_pst -supplies` are accepted and then discarded.
- `add_power_state` is deliberately **not modeled** — it is deprecated in
  IEEE 1801 and correctly reported by UPF-005. This is intentional, not an
  oversight.

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