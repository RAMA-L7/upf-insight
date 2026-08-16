# UPF-Insight — Final Acceptance Matrix

> **Status:** applied against the frozen functional baseline
> (`UPF_INSIGHT_FUNCTIONAL_BASELINE.md`). Every status below is backed by
> measured evidence: the 114-test suite, CLI runs, API regression tests, and
> a real Chrome (CDP) browser walkthrough with zero console errors.
> Nothing is marked PASS on the strength of a page existing.

Measured baseline: **114 tests pass · 65 rules (all with handlers) · 9 CLI
commands · 10 API endpoints · 11 workspace pages · version 0.1.0**.

---

## Capability matrix

Legend: Entry = catalog card / page · Input = what the feature asks for ·
Backend = real engine surface · Standalone = usable without a session.

### CORE

| # | Capability | Entry | Input | Backend | Output | Next action | Standalone | Session | Error | Empty | Tests | Browser | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **UPF Validation** | Home → UPF Validation · New Analysis | UPF (req) + design JSON (opt) | `validate` engine + `/api/validate` | findings table (rule, severity, line), readiness, coverage, support | Findings · Coverage · Health · Diff · Gate | ✅ | optional | typed error block | "ready to analyze" empty state | `test_engine.py` + web API tests | ✅ | **PASS** |
| 2 | **Static UPF Lint** | part of UPF Validation (syntax/reference layer) | same | same rules (UPF-001…UPF-05x) | lint findings in the findings table | — | ✅ | — | ✅ | ✅ | `test_engine.py` | ✅ | **PASS** (merged into Validation — one surface, documented reason) |

### ANALYZE

| # | Capability | Entry | Input | Backend | Output | Next action | Standalone | Session | Error | Empty | Tests | Browser | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | **Power Domain Analysis** | Home → Power State Intelligence · Supply Network | analysis result | model + `/api/validate` | PST matrix, per-state supplies, domains | Supply Network · Coverage | ✅ | — | ✅ | ✅ | `test_flow_coverage.py` | ✅ | **PASS** |
| 4 | **Supply Analysis** | Home → Supply Network | analysis result | model | domain/supply/switch tables | Coverage | ✅ | — | ✅ | ✅ | `test_flow_coverage.py` | ✅ | **PASS** |
| 5 | **Power State / PST Analysis** | Home → Power States | analysis result | PST analyzer | state matrix, transitions, legality | Supply Network | ✅ | — | ✅ | ✅ | `test_engine.py` | ✅ | **PASS** |
| 6 | **Isolation Analysis** | Home → Strategies | analysis result | strategy model | isolation tables (clamp, control, supply) | Design Context | ✅ | — | ✅ | ✅ | `test_engine.py` | ✅ | **PASS** |
| 7 | **Level Shifter Analysis** | Home → Strategies | analysis result | strategy model + voltage-aware UPF-061/062 | level-shifter tables + voltage findings | Design Context | ✅ | — | ✅ | ✅ | `test_engine.py` | ✅ | **PASS** |
| 8 | **Retention Analysis** | Home → Strategies | analysis result | strategy model + UPF-083 | retention tables (save/restore) | Design Context | ✅ | — | ✅ | ✅ | `test_engine.py` | ✅ | **PASS** |
| 9 | **Reference / Hierarchy** | Validation findings (reference layer) + Design page | UPF | reference rules + design snapshot | undefined/duplicate/use-before-def findings | Findings | ✅ | — | ✅ | ✅ | `test_engine.py` | ✅ | **PASS** |
| 10 | **Design-aware Analysis** | Home → Design Context | netlist JSON (opt) + UPF | UPF-080…084 + normalized `DesignContext` | netlist-grounded findings; mode flips to `DESIGN_AWARE` | Findings | ✅ | — | ✅ | ✅ | web API design tests | ✅ | **PASS** |
| 11 | **Coverage** | Home → Coverage | analysis result | coverage analyzer | domain/supply coverage %, gaps, unreferenced supplies | Health | ✅ | — | ✅ | ✅ | `test_flow_coverage.py` | ✅ | **PASS** |
| 12 | **Readiness** | Home → Readiness (Health) | analysis result | 5-dimension readiness | verdict + blockers + review items + why | Support boundary | ✅ | — | ✅ | ✅ | `test_engine.py` | ✅ | **PASS** |

### ADVANCED

| # | Capability | Entry | Input | Backend | Output | Next action | Standalone | Session | Error | Empty | Tests | Browser | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 13 | **UPF Diff** | Home → UPF Diff · nav | Version A + Version B UPF | `differ.diff_models` + `/api/diff` | semantic ADD/REMOVE/MODIFY table (provenance-free) | Validate A/B · Gate on B | ✅ | — | ✅ | ✅ | `test_diff_semantics.py` + web API | ✅ | **PASS** |
| 14 | **CI Gate** | Home → CI Gate · nav | candidate UPF + policy (+ opt baseline) | policy engine + `/api/gate` | PASS/FAIL, exit code, reasons, JSON download | Reports · Validation | ✅ | — | ✅ | ✅ | web API gate tests | ✅ | **PASS** |
| 15 | **Test Drive** | Home → Test Drive · nav | built-in scenario (clean/buggy/design/regression) | real `/api/validate` + `/api/diff` + `/api/gate` | findings summary + diff + gate + next actions | Findings · Diff · Gate · Reports | ✅ | — | ✅ | ✅ | `test_cpu_subsys_fixture.py` | ✅ | **PASS** |

### OUTPUT & KNOWLEDGE

| # | Capability | Entry | Input | Backend | Output | Next action | Standalone | Session | Error | Empty | Tests | Browser | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 16 | **Reports** | Home → Reports · nav | UPF (+ opt design) + format | reporter + `/api/report` | HTML/JSON/text report with real findings + readiness + support | Trust | ✅ | — | ✅ | ✅ | web API report tests | ✅ | **PASS** |
| 17 | **Rules** | Home → Rules · nav | none (reference) | rule registry + `/api/rules` | 65 rules browsed by severity/layer | Documentation | ✅ | — | ✅ | ✅ | registry tests | ✅ | **PASS** |
| 18 | **Documentation** | Home → Documentation · nav | none (reference) | repo docs | journey + CLI/API references | Rules | ✅ | — | ✅ | ✅ | — | ✅ | **PASS** |
| 19 | **Trust** | Home → Trust · nav | none (disclosure) | support boundary (real evidence) | frozen disclosures + boundary | Support boundary | ✅ | — | ✅ | ✅ | support tests | ✅ | **PASS** |
| 20 | **Feedback** | — | — | — | — | — | — | — | — | — | — | — | **NOT IMPLEMENTED** (no fake surface; documented, not built) |

---

## Verified workflow loops (browser + API)

- **Test Drive regression** — `V2 validate (3E/11W/BLOCKED) → diff V1→V2 (1 semantic change: level-shifter removed) → STRICT gate FAIL (exit 1)` — all rendered from real backend evidence. ✅
- **Diff standalone** — Home → Diff → samples → Compare → change table + next actions. ✅
- **Gate standalone** — Home → CI Gate → sample V2 → STRICT → FAIL + reasons + disclosure + JSON download. ✅
- **Reports standalone** — Home → Reports → sample V2 → HTML report frame contains UPF-061. ✅

## Verification summary

| Check | Result |
|---|---|
| Full test suite | **114 passed** (94 baseline + 5 diff semantics + 13 web API + 2 design-aware normalization) |
| CLI end-to-end | check/model/pst/coverage/report/diff/generate/rules verified; exit codes 0/1/2/3 contract intact |
| API | 10 endpoints; error states (400) verified; path traversal blocked (403/404) |
| Determinism | repeated CLI runs byte-identical |
| Browser (CDP, real Chrome) | **23/23 steps PASS · 0 console errors · 0 runtime exceptions** |
| Diff quality | provenance-free: comment/line-shift edits produce 0 changes; real removal produces exactly 1 |
| Design-aware honesty | dict design normalized to `DesignContext`; readiness mode flips to `DESIGN_AWARE`; no silent degradation |
| Packaging | `pyproject.toml` wheel-able entry point (`upf-insight`) — **not yet tested from a clean environment** (P2) |

## Findings

- **P0** — none.
- **P1** — none blocking the validation workflow.
- **P2**
  1. No version control / CI in the project directory (git init + GitHub Action recommended before external validation).
  2. Model-derived findings carry accurate `line` but an empty `file` field (single-file runs unambiguous; documented gap).
  3. Wheel install not yet verified from a clean environment.
  4. Custom YAML rules **NOT IMPLEMENTED** (only `--rule` filtering) — documented, not hidden.

## Known limitations (from functional baseline)

- Full IEEE 1801 grammar: PARTIAL (~30 commands modeled; unsupported commands reported, never silent).
- Tcl execution (`proc`/`source`/expressions): detected, never executed (`TCL_EXECUTION_REQUIRED`).
- Design context is a JSON snapshot, not a netlist parser.
- No timing/IR/signoff analysis — by design, disclosed.

## Validation freeze (Phase 18)

The **validation candidate is v0.1.0** (current version). Freeze discipline for
the external cohort:

- No product changes after the first engineer starts.
- No "quick fixes", wording tweaks, or feature additions during the cohort.
- Record findings; decide only after the cohort evidence is classified.
- The candidate is frozen as a *documented state* — this project directory is
  **not a git repository yet**, so there is no tag. `git init` + a tag is the
  P2 prerequisite to make the freeze mechanically enforceable.

## Final product decision (Phase 19)

**Deferred until external validation.** The three options (independent UPF
product / UPF + Ṛta interoperability / selected UPF capabilities integrated
into Ṛta) are evaluated in `UPF_INSIGHT_STRATEGIC_OPTIONS.md`; the decision
must be made on engineer evidence, not technical enthusiasm.
