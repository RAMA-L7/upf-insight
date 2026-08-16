# UPF-Insight — Product Specification

> **Document kind:** product specification (high-fidelity behavior contract).
> **Date:** 2026-08-14 · **Version:** v0.1.0
> **Status:** matches the shipped v0.1.0 scaffold.

---

## 1. Overview

UPF-Insight validates, models, and analyzes IEEE 1801 (UPF) power-intent
files deterministically and locally. It is the power-intent sibling of the
Ṛta SDC validator: same philosophy (deterministic engine, per-finding
evidence, honest support boundary), applied to power intent.

**Scope (v0.1.0):** static layers 1–5 of the rule catalog, model dump, PST
analysis, semantic diff, generator, local web workspace.

## 2. Functional requirements

### FR-1 Validate (implemented)

Input: one or more `.upf` files, in load order.
Process:
1. Preprocess each file into command records (comments stripped,
   continuations joined, provenance kept).
2. Build the power-intent model (domains, supplies, switches, states, PST,
   strategies).
3. Run deterministic rule handlers keyed by registry code.
4. Derive the support boundary.
5. Format as text or JSON.

Output: findings with `rule`, `severity`, `message`, `file`, `line`,
`support`; counts; support boundary; PST summary.
Exit codes: 0 clean (no errors) / 1 issues / 2 bad invocation / 3 engine
failure.

### FR-2 Model dump (implemented)

`upf-insight model FILE... -o model.json` — serialize `PowerIntentModel`
including `unsupported_commands` for boundary transparency.

### FR-3 PST analysis (implemented)

`upf-insight pst FILE...` — PST name, state count, declared vs used supply
states, unused/undeclared lists, transition count, coverage note. `--json`
for machine output.

### FR-4 Generate (implemented)

`upf-insight generate --domains core,io --always-on clk,rst --retention core`
— emits a structurally valid UPF skeleton (version, design top, domains,
supply network, states + PST, retention, always-on attributes).

### FR-5 Diff (implemented)

`upf-insight diff OLD NEW` — model-level comparison emitting ADD/REMOVE/
MODIFY records for domains, supplies, switches, PSTs, and strategy-count
changes. Semantic, not textual.

### FR-6 Workspace (implemented)

`upf-insight web --port N` (default 8585) — stdlib-only local HTTP API:
- `GET /api/version` · `GET /api/rules` · `POST /api/validate` ·
  `POST /api/generate`
- vanilla-JS workspace at `/` (paste UPF → validate → findings table +
  support boundary; "Generate skeleton" button).

### FR-7 Custom rules (planned, v0.2.0)

YAML rulesets validated against the same model; no core-registry changes
required.

### FR-8 Reports (partial)

Text + JSON now. JUnit/HTML planned.

## 3. Non-functional requirements

| NFR | Requirement |
|---|---|
| Determinism | Same input → same findings → same exit code, every machine. |
| Locality | All analysis on-machine; API binds 127.0.0.1; no telemetry. |
| No LLM | The engine contains no LLM call; reasoning is pure code. |
| No EDA tool | Works without Synopsys/Cadence/Siemens. |
| Stdlib-first | Runtime deps: `pyyaml` only. Web has zero build step. |
| Honesty | Support boundary always disclosed; "no errors ≠ proven correct". |
| Robustness | A failing rule never crashes the run. |

## 4. Rule catalog summary

Layers and codes: see [RULES_REGISTRY.md](../upf/RULES_REGISTRY.md).

Implemented handlers in v0.1.0: UPF-001, 011, 020, 022, 023, 032, 034, 045,
050, 052, 060. Registered but dormant rules are listed with a status table;
the registry is the contract, implementation catches up layer by layer.

## 5. Acceptance criteria (v0.1.0)

- [x] `upf-insight check example.soc.upf` exits 0.
- [x] `upf-insight check example.broken.upf` exits 1 with the expected rule
      codes.
- [x] `upf-insight pst`, `model`, `generate`, `diff`, `web` all run.
- [x] `upf-insight --version` prints `upf-insight 0.1.0`.
- [x] `python -m pytest tests/ -q` → 8 passed.
- [x] Support boundary present in text output.

## 6. Known limits (v0.1.0)

- Layer 6 (design-aware) requires netlist context — v2.
- Tcl execution constructs detected, never executed.
- `load_upf` recorded but not yet scope-followed.
- Option-level validation (UPF-002/003) not yet implemented.
- `--rule` filter accepted but not yet applied (reserved).
- Web UI has no Model/PST panels yet (validate only).