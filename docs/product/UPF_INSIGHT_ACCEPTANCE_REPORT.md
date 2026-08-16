# UPF-Insight — Acceptance Report

> **Document kind:** acceptance / readiness review.
> **Date:** 2026-08-16 · **Baseline:** v0.1.0 + audit fixes.
> **Method:** every status below was verified by executing the real product
> (engine, CLI, API, web UI, tests) during the audit — no claim is carried
> from documentation alone.

---

## 1. Final capability matrix

| Capability | Status | Evidence | Tests | Limitation |
|---|---|---|---|---|
| UPF/Tcl preprocessing | **PASS** | lexer executed on fixtures; continuations/comments/braces verified | test_engine 1–2 | Tcl execution never performed (by design) |
| Power-intent model + builder | **PASS** | `model` JSON dump verified (domains/supplies/PST) | test_engine 7 | ~30 commands modeled |
| Rule engine (65 rules) | **PASS** | 65 registered = 65 handlers (test); families fire on bad fixtures | test_flow_coverage 1–2 | Younger catalog than SDC |
| Syntax layer (001–006) | **PASS** | fired on `syn_ref_bad.upf` | test_engine 26 | — |
| Reference integrity (010–016) | **PASS** | fired on `syn_ref_bad.upf` | test_engine 26 | netlist-dependent subset deferred |
| Supply/domain (020–025) | **PASS** | fired on fixtures | test_engine 12, 22 | — |
| PST (030–038) | **PASS** | analyzer + cross-state verified | test_engine 13, 15 | cross-state NETLIST_REQUIRED |
| Isolation (040–047) | **PASS** | fired on `iso_bad.upf`; no false 043 | test_engine 11 | — |
| Retention/LS (050–064) | **PASS** | fired on `ret_ls_bad.upf`; voltage-aware 061/062 | test_engine 24–25 | needs declared voltages |
| Switches (070–074) | **PASS** | fired on `sw_bad.upf` | test_engine 21 | — |
| Repeaters (090–094) | **PASS** | fired on targeted cases | test_flow_coverage B | — |
| Hierarchical (095–098) | **PASS** (subset) | promote/demote/equivalent verified | test_flow_coverage C/E | resolution NETLIST_REQUIRED |
| Design-aware (080–084) | **PASS** | fired with `cpu_subsys_design.json`; silent without | test_engine 28–29, new fixture | JSON snapshot, no Verilog parser |
| Readiness | **PASS** | BLOCKED/REVIEW_REQUIRED/INSUFFICIENT_CONTEXT verified | test_engine 14–15, new fixture | categorical, not signoff |
| Coverage (structural) | **PASS** | 1.0/1.0 on golden; gaps reported | test_engine 16 | structural only |
| CI gate | **PASS** | STRICT blocks V2 (exit 1), passes V1 (exit 0) | test_engine 18, new fixture | — |
| Diff | **PASS** | V1→V2 shows removed level shifter | new fixture | strategy diff count-based |
| Generator | **PASS** | round-trips 0 errors/0 unsupported | test_generator (12) | skeleton, not full intent |
| Reports (text/JSON/JUnit/HTML) | **PASS** | JUnit/HTML render findings | test_engine 20 | — |
| CLI (9 commands) | **PASS** | all exercised; exit 0/1/2/3 verified | new fixture CLI test | — |
| Web API + workspace | **PASS** | endpoints smoke-tested; LFI guard tests green | test_api_security (7) | single-page UI |
| Trust/support boundary | **PASS** | statuses derived + printed; empty input honest | new fixture | — |
| Determinism | **PASS** | byte-identical JSON across runs | new fixture | — |
| Custom rules (YAML) | **NOT IMPLEMENTED** | only `--rule` filter | — | planned v0.2.0 |
| Version control + CI/CD | **FAIL** | not a git repository; no workflows | — | **P1** |
| Packaging | **PARTIAL** | `pip install -e .` works; wheel unverified | test_generator 12–13 | unpublised |
| Docs freshness | **PARTIAL** | stale counts/claims (evidence map, roadmap, spec) | — | **P2** |
| Performance on large UPF | **UNKNOWN** | no benchmark corpus | — | **P2** |

## 2. P0 findings

**None.**

## 3. P1 findings

| ID | Finding | Evidence | Required action |
|---|---|---|---|
| P1-1 | **Not a git repository** — no version control, no history, no tags, no CI | `git rev-parse` fails; no `.git`; no `.github/` | Init git, commit the verified baseline, add a GitHub Action running `pytest tests/` on push/PR; tag v0.1.0 |
| P1-2 | **No CI/CD** | no `.github/workflows` | Ship the Action in the same change as P1-1; it must run the full suite and a CLI smoke |

(These are process/distribution gaps, not engine defects. The engine itself
is verified working.)

## 4. P2 findings

| ID | Finding | Evidence |
|---|---|---|
| P2-1 | Custom YAML rulesets unimplemented though documented | `docs/features/README-07` vs `--rule` only |
| P2-2 | Design context is a JSON snapshot, not a Verilog parser | `design_context.py` contract |
| P2-3 | Strategy-level diff is count-based; attribute changes not diffed | `differ.py` `len()` comparisons |
| P2-4 | Model-derived findings have empty `file` field (line is accurate) | `finding.py` default; fixture test asserts it |
| P2-5 | Docs stale: evidence map says "8 tests", roadmap/spec list done work as future | `evidence/README.md`, `PRODUCT_ROADMAP.md`, `PRODUCT_SPECIFICATION.md` |
| P2-6 | Coverage is structural only; no per-category inventory score | `coverage.py` |
| P2-7 | No performance benchmark on large UPF | — |
| P2-8 | Single-page workspace; no feature-first entry/catalog | `webui/index.html` |

## 5. Known limitations (honest)

- **Not full IEEE 1801:** ~30 commands modeled; others reported as
  UNSUPPORTED (never silent). No Tcl execution.
- **Static-layer truth:** always-on claims, crossing and electrical behavior
  are PARTIAL / NETLIST_REQUIRED without a full supply-state model and
  netlist. The support boundary always states this.
- **Hierarchical scope following** for `load_upf` is recorded but not
  resolved (UPF-097 is honest about it).
- **Voltage analysis** requires declared `add_port_state` voltages; absent
  voltages make level-shifter checks defer.

## 6. Unsupported UPF constructs (by design or unimplemented)

`proc`, `source`, `foreach`, `if/switch` (Tcl execution — detected,
never executed), full `-update` semantics, multi-scope `load_upf`
resolution, custom YAML rulesets, Verilog/netlist parsing.

## 7. Test counts

| Suite | Count |
|---|---|
| Pre-existing (engine/flow/generator/api-security) | 76 |
| New fixture regression tests | 18 |
| **Total (verified green)** | **94** |

## 8. Fixture count

| Fixture family | Files |
|---|---|
| Golden/bad examples (pre-existing) | 9 (soc, broken, iso_bad, pst_bad, pst_cross_bad, ret_ls_bad, sw_bad, syn_ref_bad, design_bad + design.json) |
| **CPU-subsystem Test Drive (new)** | **3** (v1, v2, design.json) |
| **Total** | **12 + 1 design context** |

## 9. Workflow verification

| Workflow | Verified result |
|---|---|
| Install → analyze | `pip install -e .`; `upf-insight check` PASS on V1 |
| Understand findings | V2: UPF-061 ×3, readiness BLOCKED, each with source line + why-it-matters |
| Compare V1/V2 | diff shows `MODIFY strategy 'level_shifter' count 1 -> 0` |
| Gate | baseline save → STRICT gate V2 exit 1, V1 exit 0 |
| Report | self-contained HTML with real findings |
| Design-aware | `--netlist` enables UPF-080…084; V1 clean, V2 blocked |

## 10. CLI / API / UI verification

- **CLI:** all 9 subcommands exercised; `--format text/json/junit`,
  `--rule`, `--save-baseline`, `--baseline --gate`, `--netlist`,
  `--version` verified.
- **API:** `GET /`, `/api/version`, `/api/rules` (65), `POST
  /api/validate` (content + file path), `POST /api/generate` verified;
  LFI guard rejects traversal (403/400).
- **UI:** single-page vanilla-JS workspace loads and calls the real API.
  UX evaluation below.

## 11. UX evaluation (Phase 8)

Current state is a **functional single-page workspace** (validate + model +
PST panels, rules/readiness/coverage rendering). It does not yet have Ṛta's
feature-first entry, capability catalog, per-feature standalone workflows,
or progressive-disclosure result → next-action navigation. Because the
backend is a clean consumer contract, these are presentation-layer
improvements, not engine changes.

Recommended (after functional validation, not before):
1. Feature-first entry: Validate / Model / PST / Generate / Diff / Gate /
   Reports as cards with "what is this / what input / what result / next".
2. Per-feature input ownership (validate asks for UPF; diff asks for two
   files; generate asks for params — no global upload).
3. Standalone default + optional session (validate → readiness → gate →
   report), with honest empty/error states.
4. Progressive disclosure on dense result tables (findings → detail →
   evidence).
5. Trust disclosures pinned visibly on every result surface.

## 12. Trust verification (Phase 9)

Verified against the live implementation:

| Claim | Verified? | Where |
|---|---|---|
| Clean ≠ power-intent correct | ✅ | support boundary printed on every run; readiness never claims signoff |
| Coverage ≠ correctness | ✅ | `coverage.py` docstring + UI framing |
| CI PASS ≠ low-power closure | ✅ | `policy_engine.py` + README-12 |
| READY ≠ signoff | ✅ | `readiness.py` categorical model |
| Tcl detected, never executed | ✅ | `support_boundary.py` TCL_EXECUTION_REQUIRED |
| Deterministic / no LLM / no network | ✅ | byte-identical JSON; stdlib-only; localhost-bound |
| Empty input honesty | ✅ (fixed in audit) | NOT_VALIDATED + INSUFFICIENT_CONTEXT |
| Design-aware boundary honesty | ✅ (fixed in audit) | readiness now reports supplied context truthfully |

No overclaim found: the tool never implies PASS = silicon-safe, never
presents coverage as correctness, and never claims STA/IR/simulation
capability.

## 13. Readiness verdict

**Not ready for external validation yet** — the two P1 process gaps (no git,
no CI) must close first, and the docs must be reconciled so a new engineer
reads accurate counts. The **engine is ready**; the **distribution surface
is not**. Expected effort: small (git init + Action + docs pass + optional
wheel check ≈ one focused sprint).

---

*No Ṛta repository file was touched. All changes in this audit are confined
to `D:\freebuff\upf-insight`.*
