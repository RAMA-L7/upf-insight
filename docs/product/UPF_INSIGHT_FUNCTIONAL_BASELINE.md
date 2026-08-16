# UPF-Insight — Functional Baseline (v0.1.0 + audit fixes)

> **Document kind:** functional contract — the *actual* current behavior of
> the product, verified against the live repository on 2026-08-16.
> **Status:** this is the baseline the product must not regress from. Every
> claim below was executed or asserted in this audit.
>
> **Do NOT inflate.** Anything not implemented is explicitly labeled
> `NOT IMPLEMENTED`; anything partial is labeled `PARTIAL`.

---

## 1. Product identity (one paragraph)

UPF-Insight is a deterministic, local-first, evidence-backed validator for
IEEE 1801 (UPF) power-intent files. It preprocesses UPF/Tcl into command
records, builds a power-intent object model (domains, supplies, switches,
states, PST, strategies), runs a layered rule engine (65 implemented rules),
analyzes the Power State Table, derives a categorical readiness verdict and
structural coverage, and can gate changes in CI against a saved baseline.
It is the power-intent sibling of Ṛta, shares its philosophy (deterministic
engine, per-finding evidence, honest support boundary, no LLM, no EDA tool),
but is its own product with its own model-over-text architecture.

## 2. Supported UPF constructs

Verified against `upf_insight/model/builder.py` (`_SUPPORTED` set) and the
rule handlers. A construct is "supported" when it is parsed into the model
and analyzed; commands outside the set are captured as
`unsupported_commands` (reported in the support boundary), never silently
dropped.

| Construct | Modeled as | Rules that analyze it |
|---|---|---|
| `upf_version` | version string | UPF-004 |
| `set_design_top` | design_top | — |
| `set_scope` | scope changes | UPF-016 |
| `create_power_domain` (+ `-elements`, `-primary_supply_set`, `-supply`) | PowerDomain | UPF-011, 012, 020, 021, 080, 083 |
| `set_domain_supply_net` | primary power/ground on domain | UPF-020 |
| `create_supply_net` / `create_supply_port` / `create_supply_set` | SupplyNet/Port/Set with functions | UPF-010, 013, 022, 023, 024, 025, 084, 098 |
| `connect_supply_net` | connectivity edges | UPF-015, 022, 024 |
| `create_power_switch` (+ `-on_state`/`-off_state` triples) | PowerSwitch with conditions | UPF-070, 071, 072, 073, 074 |
| `add_port_state` / `add_supply_state` | SupplyState with nominal voltage | UPF-025, 030, 031, 060/061/062 (voltage) |
| `create_pst` / `add_pst_state` / `add_state_transition` | Pst + PowerState rows + transitions | UPF-030…038 |
| `set_isolation` / `set_isolation_control` | IsolationStrategy + control binding | UPF-040…047, 081, 082 |
| `set_level_shifter` / `set_level_shifter_control` | LevelShifterStrategy | UPF-060…064, 081 |
| `set_retention` / `set_retention_control` | RetentionStrategy | UPF-050…054, 081, 083 |
| `set_repeater` / `set_repeater_control` | RepeaterStrategy | UPF-090…094 |
| `set_port_attributes` | always-on attributes on signals | UPF-047, 051, 064, 071, 072, 091 |
| `set_equivalent` | equivalence pairs | UPF-098 |
| `update_supply_net` / `update_supply_set` | net/set updates | — |
| `map_isolation_cell` / `map_level_shifter_cell` / `map_retention_cell` | library-mapping records | — |
| `load_upf` | composition event | UPF-097 |
| `upf_promote` / `upf_demote` | hierarchy events | UPF-095, 096 |

## 3. Supported analyses

1. **Validate** — 65-rule layered check (SYNTAX → REFERENCE → SUPPLY_DOMAIN
   → PST → STRATEGY → DESIGN), per-finding `rule / severity / message /
   line / support`.
2. **Model** — power-intent object graph dump to JSON.
3. **PST** — state inventory, declared-vs-used, transitions, cross-state
   power-down/tri-state events.
4. **Readiness** — categorical verdict across 5 dimensions
   (POWER_STATES, SUPPLY_NETWORK, STRATEGIES, CONSISTENCY, DESIGN_CONTEXT).
5. **Coverage** — structural domain/supply coverage with per-domain gaps.
6. **Diff** — model-level ADD/REMOVE/MODIFY between two versions.
7. **Generate** — template-driven UPF skeleton that round-trips cleanly.
8. **Gate** — declarative CI policy over current + baseline evidence.
9. **Design-aware** — UPF-080…084 against an optional JSON design context.
10. **Report** — text / JSON / JUnit XML / self-contained HTML.

## 4. Input requirements

| Input | Required? | Notes |
|---|---|---|
| UPF file(s) | **REQUIRED** (≥1 for `check/model/pst/coverage/report`) | Load order matters; multi-file supported |
| Design context (JSON snapshot) | OPTIONAL | Enables UPF-080…084; without it the boundary reports NETLIST_REQUIRED |
| Baseline JSON | OPTIONAL (`--baseline`) | Required for gating |
| Policy | OPTIONAL (`--gate`) | Built-ins BLOCKERS_ONLY / NO_READINESS_REGRESSION / STRICT, or custom JSON |
| Custom rule YAML | **NOT IMPLEMENTED** | Only `--rule` code filtering exists |

## 4a. API endpoints and workspace surfaces

Local HTTP API (`upf-insight web`, stdlib only, no egress):

| Endpoint | Purpose | Input |
|---|---|---|
| `GET /api/version` | product/version metadata | — |
| `GET /api/design` | theme/status metadata | — |
| `GET /api/rules` | rule registry | — |
| `GET /api/sample?name=` | built-in fixture content (bounded to `workspace/samples/`) | `cpu_v1` · `cpu_v2` · `cpu_design` |
| `POST /api/validate` | full analysis | `content` (UPF text) or `files` + optional `design` |
| `POST /api/generate` | UPF generation | `params` (domains/switches/isolation/LS/retention/PST) |
| `POST /api/diff` | semantic diff | `old` + `new` UPF text (+ file names) |
| `POST /api/gate` | CI policy evaluation | `content` + `policy` + optional `baseline` |
| `POST /api/report` | report generation | `content` + `format` (`html`\|`json`\|`text`) |

Workspace pages (all standalone, own input surface): Home · New Analysis ·
Validation · Generator · UPF Diff · CI Gate · Reports · Test Drive · Rules ·
Trust · Documentation, plus the RESULTS group (Summary, Supply Network,
Power States, Strategies, Design, Coverage, Health, Support, Export) that
appears once an analysis exists. No "More Tools"; every capability is
visible from the catalog.

## 5. Output contract

- **Findings:** `{rule, severity, message, file, line, support}`.
  Line is accurate for model-derived findings; the file field is currently
  empty on model-derived findings (documented gap — single-file runs are
  unambiguous, multi-file runs attribute by line).
- **Exit codes:** `0` pass · `1` gate failed / issues · `2` invalid
  invocation · `3` engine failure. Engine failure can never produce a pass.
- **Support boundary:** counts per status + human notes, always emitted.
- **Readiness:** one of READY / READY_WITH_ADVISORIES / REVIEW_REQUIRED /
  BLOCKED / INSUFFICIENT_CONTEXT, with per-dimension status + summary +
  findings, plus explicit blockers/review/advisories lists.
- **Coverage:** per-domain booleans + gap list, domain_coverage and
  supply_coverage floats (structural evidence only).
- **Gate:** `{policy, passed, exit_code, reasons}`.

## 6. Severity semantics

| Severity | Meaning | Readiness tier |
|---|---|---|
| `error` | Modeled intent is inconsistent or unsafe (e.g. UPF-061 missing level shifter, UPF-045 isolation without control) | BLOCKED (for blocker rules at error) |
| `warning` | Real risk the static layer can only partially confirm (always-on status, netlist-dependent) | REVIEW_REQUIRED |
| `info` | Advisory worth review (redundant isolation, unnecessary level shifter) | READY_WITH_ADVISORIES |

## 7. Deterministic behavior

Verified: repeated runs produce byte-identical JSON. No randomness, no LLM,
no network, no telemetry. Iteration order is sorted where output order could
leak. Rule handlers may never crash the run (checker catches and reports).

## 8. Trust disclosures (frozen wording)

- **Clean ≠ power-intent correct.** A clean result means no deterministic
  rule fired against the modeled intent.
- **Coverage ≠ correctness.** Coverage reports what the intent *touches*,
  not that it is safe.
- **CI PASS ≠ low-power closure.** The gate protects against regression; it
  does not verify timing, IR, or signoff.
- **READY ≠ signoff.** Readiness is categorical evidence, not a proof of
  electrical correctness.
- **Tcl is detected, never executed.** `TCL_EXECUTION_REQUIRED` /
  `UNSUPPORTED` statuses report execution-bound constructs without running
  them.
- **No EDA tool, no LLM, no upload.** Analysis runs entirely on-machine.

## 9. Limitations / unsupported

| Area | Status | Detail |
|---|---|---|
| Full IEEE 1801 grammar | **PARTIAL** | ~30 commands modeled; others captured as unsupported (reported, never silent) |
| Tcl execution (`proc`, `source`, `foreach`, expressions) | **NOT IMPLEMENTED** (detected only) | TCL_EXECUTION_REQUIRED status |
| Verilog/netlist parser | **NOT IMPLEMENTED** | Design context is a JSON snapshot contract |
| Custom YAML rulesets | **NOT IMPLEMENTED** | Documented as planned |
| Strategy-level diff detail | **PARTIAL** | Count-based for strategies; attribute-level diffs not yet emitted |
| File attribution on model findings | **PARTIAL** | Accurate lines; empty file field on model-derived findings |
| Performance on large UPF | **UNKNOWN** | No corpus benchmark yet |
| IEEE 1801 conformance corpus | **NOT IMPLEMENTED** | Parse-only corpus planned |

## 10. UPF coverage inventory (Phase 4)

The inventory below is the *measurable* UPF construct/check surface the
product can currently cover — derived from the registry + handlers, not an
aspirational list. It is the basis for a future per-category coverage score
(mirroring Ṛta's 39-category SDC coverage). Current status: the engine
computes structural domain/supply coverage; a per-category inventory score
is **NOT IMPLEMENTED** but every category below is *verifiable* by existing
rules.

| # | UPF power-intent category | Covered by | Status |
|---|---|---|---|
| 1 | Supply nets / ports / sets declaration | model + UPF-010/013/022/023 | ✅ works |
| 2 | Supply functions (power/ground) | UPF-023 | ✅ works |
| 3 | Supply connectivity | UPF-015/024 | ✅ works |
| 4 | Supply states / port states (nominal voltage) | model + UPF-025/030/031 | ✅ works |
| 5 | Power domains | model + UPF-011/020 | ✅ works |
| 6 | Domain elements / ownership | UPF-012/021/080 | ✅ works |
| 7 | Domain primary supply | UPF-020 | ✅ works |
| 8 | Power switches (control + supply mapping) | UPF-070/071/073/074 | ✅ works |
| 9 | Switch state triples (on/off conditions) | UPF-074 | ✅ works |
| 10 | Power State Table (create/add rows) | UPF-032/033/034 | ✅ works |
| 11 | PST state transitions | UPF-033/035 | ✅ works |
| 12 | Declared-vs-used supply states | UPF-030/031 | ✅ works |
| 13 | Cross-state power-down behavior | UPF-037/038 | ✅ works (NETLIST_REQUIRED caveat) |
| 14 | Isolation strategies | UPF-040…047 | ✅ works |
| 15 | Isolation control pairing | UPF-045 (+binding) | ✅ works |
| 16 | Isolation clamp values | UPF-046 | ✅ works |
| 17 | Isolation location | UPF-041 | ✅ works |
| 18 | Isolation applies_to (inouts) | UPF-044 | ✅ works |
| 19 | Level shifters | UPF-060…064 | ✅ works |
| 20 | Voltage-different crossings | UPF-061/062 | ✅ works |
| 21 | Retention strategies | UPF-050…054 | ✅ works |
| 22 | Retention control pairing | UPF-054 (+binding) | ✅ works |
| 23 | Repeater strategies | UPF-090…094 | ✅ works |
| 24 | Always-on signals/attributes | UPF-047/051/064/071/072/091 | ✅ works |
| 25 | Hierarchical UPF (promote/demote) | UPF-095/096 | ✅ works (resolution NETLIST_REQUIRED) |
| 26 | UPF composition (load_upf) | UPF-097 | ✅ works (NETLIST_REQUIRED) |
| 27 | Supply equivalence | UPF-098 | ✅ works |
| 28 | Library cell mapping | model records | ✅ parsed, no rule |
| 29 | Unknown-command detection | UPF-001 | ✅ works |
| 30 | Illegal-option / missing-arg | UPF-002/003 | ✅ works |
| 31 | Malformed Tcl | UPF-006 | ✅ works |
| 32 | UPF version handling | UPF-004 | ✅ works |
| 33 | Deprecated legacy syntax | UPF-005 | ✅ works |
| 34 | Instance existence (design-aware) | UPF-080 | ✅ works (with design context) |
| 35 | Control-signal existence (design-aware) | UPF-081 | ✅ works (with design context) |
| 36 | Endpoint crossing coverage (design-aware) | UPF-082 | ✅ works (with design context) |
| 37 | Retention coverage vs sequential elements (design-aware) | UPF-083 | ✅ works (with design context) |
| 38 | Library PG mapping (design-aware) | UPF-084 | ✅ works (with design context) |
| 39 | Custom YAML rulesets | — | ❌ NOT IMPLEMENTED |
| 40 | Tcl execution semantics | — | ❌ NOT IMPLEMENTED (detected only) |
| 41 | Verilog/netlist parsing | — | ❌ NOT IMPLEMENTED (JSON snapshot only) |

**Counting rule:** "X of Y" is defined as *categories with at least one
implemented, tested rule* out of the 41 listed. Current: **38 of 41**
(categories 39–41 are explicitly NOT IMPLEMENTED). This is a *capability*
inventory, distinct from the structural coverage score the engine computes
per run.

## 11. Test baseline (verified)

- Full suite: **94 passed** (76 pre-existing + 18 new fixture regression
  tests) in ~5 s.
- CLI contract: exit 0/1/2/3 verified; gate 0/1 verified on V1/V2.
- Determinism: byte-identical JSON across runs.
- New fixture: `tests/examples/cpu_subsys/` (V1 known-good, V2 regressed,
  design context) with semantic tests — clean V1, blocked V2, diff, gate,
  line accuracy, determinism, empty/invalid input.

## 12. Not in this baseline (do not claim)

- No timing, IR, or electrical analysis.
- No multi-file *hierarchical scope following* (load_upf recorded, not
  scope-followed).
- No enterprise governance, auth, or multi-user.
- No AI in the analysis path (deterministic by charter).
- No cloud/SaaS processing of UPF (local-first by charter).
