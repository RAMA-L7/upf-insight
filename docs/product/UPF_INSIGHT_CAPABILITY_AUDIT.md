# UPF-Insight — Capability Audit (vs Ṛta engineering standard)

> **Document kind:** audit · **Date:** 2026-08-16 · **Status:** verified
> against the live repository (engine, CLI, API, web UI, tests, fixtures,
> docs). Every PASS below is backed by an executed check in this audit, not
> by documentation claims.
>
> **Reference standard:** Ṛta (the SDC sibling) is used only as a *quality
> benchmark* — not a template to clone. UPF-Insight has its own domain
> (power intent / IEEE 1801) and its own model-over-text architecture, which
> is the correct call for a hierarchical, stateful format.

---

## 1. Executive verdict

UPF-Insight is a **genuine, working, deterministic power-intent validator** —
not a scaffold or demo. It has a real parser, a real power-intent model, 65
implemented rules (all with handlers, all tested), a PST analyzer, readiness,
coverage, a CI policy gate with a deterministic exit-code contract, a
generator that round-trips cleanly, semantic diff, four report formats, a
local web workspace, and an honest trust/support-boundary model. 94 tests
pass on the unmodified-plus-audit-fixes engine.

It is **younger and narrower than Ṛta** in maturity surface (76 → 94 tests vs
1,200+; 65 rules vs 119; one golden example family vs a corpus), and it has
specific gaps documented below. None of the gaps are architecture-blocking;
all are incremental.

---

## 2. Capability table

Legend: **PASS** = verified working with evidence · **PARTIAL** = works but
with documented limits · **MISSING** = not present · **UNKNOWN** = could not
be verified in this audit.

| Capability | UPF-Insight status | Evidence | Ṛta equivalent | Gap | Risk | Priority | Recommendation |
|---|---|---|---|---|---|---|---|
| UPF/Tcl preprocessing | **PASS** | `upf_preprocess.py` lexer: comments, continuations, brace/bracket/quote state, provenance; tests 1–2 | SDC preprocess | None material; Tcl execution never performed (by design) | L | — | Keep |
| Power-intent model | **PASS** | `power_model.py` + `builder.py` (domains, supplies, switches, states, PST, strategies, controls); `upf-insight model` JSON verified | Checker model | None | L | — | Keep |
| Rule registry (65 rules, 6 layers) | **PASS** | `rules_registry.py`; `rules list` shows 65; every registered rule has a handler (test) | 119 SDC rules | UPF domain is smaller/catalog is younger | M | P2 | Grow with conformance corpus |
| Syntax layer (UPF-001…006) | **PASS** | UPF-002/003/004/005/006 verified on `example.syn_ref_bad.upf` | SDC syntax rules | None | L | — | Keep |
| Reference integrity (UPF-010…016) | **PASS** | Verified on `example.syn_ref_bad.upf`; duplicate-definition keyed on (kind, name) | SDC reference rules | Netlist-dependent parts deferred (NETLIST_REQUIRED) — honest | L | P2 | v2 with netlist |
| Supply & domain integrity (UPF-020…025) | **PASS** | Verified on fixtures; element-overlap, unconnected-supply, missing-functions | SDC structural rules | None | L | — | Keep |
| PST analysis (UPF-030…038) | **PASS** | `pst/analyzer.py`; declared-vs-used, transitions, cross-state power-down events; verified | Clock intelligence | Cross-state analysis is NETLIST_REQUIRED (honest) | M | P2 | v2 with netlist |
| Strategy lint — isolation (UPF-040…047) | **PASS** | Verified on `example.iso_bad.upf`; control pairing, clamp, location, inouts | SDC exceptions lint | None | L | — | Keep |
| Strategy lint — retention/LS/repeater (UPF-050…064, 090…094) | **PASS** | Verified on fixtures; voltage-aware LS rules (061/062), control pairing | SDC exceptions lint | Voltage knowledge needs declared supply states (documented) | M | P2 | Keep |
| Power-switch rules (UPF-070…074) | **PASS** | Verified on `example.sw_bad.upf`; undefined supply, control, unused output, state triples | SDC clock/exception lint | — | L | — | Keep |
| Hierarchical UPF (UPF-095…098) | **PASS** (subset) | promote/demote/load_upf/set_equivalent verified; resolution deferred | SDC hierarchy | Cross-scope resolution NETLIST_REQUIRED | M | P2 | v2 |
| Design-aware layer (UPF-080…084) | **PASS** | Verified with `cpu_subsys_design.json`: instance/control/crossing/retention/PG checks fire and stay silent when appropriate | Design-aware validation | Design context is a JSON snapshot; no Verilog parser | M | P2 | Add Verilog parse or document snapshot contract |
| Readiness verdict (5 dimensions) | **PASS** | `readiness.py`; BLOCKED/REVIEW_REQUIRED/READY verified on fixtures; never a numeric score | Readiness | — | L | — | Keep |
| Structural coverage | **PASS** | `coverage.py`; domain/supply 1.0 on golden; "coverage ≠ correctness" framing | Coverage | Coverage is structural, not per-construct-category | M | P2 | Add category inventory (see baseline doc) |
| CI policy gate | **PASS** | `policy_engine.py`; BLOCKERS_ONLY / NO_READINESS_REGRESSION / STRICT; exit 0/1 verified; engine failure never passes | CI gate | — | L | — | Keep |
| Semantic diff | **PASS** | `differ.py`; ADD/REMOVE/MODIFY verified (V1→V2 shows removed level shifter) | SDC diff | Strategy diff is count-based (does not detect e.g. clamp-value change); `vars()` comparison reports line-number shifts as MODIFY | M | P2 | Refine strategy-level diff |
| Generator | **PASS** | `generator.py` validates params; generated UPF round-trips with 0 errors/0 unsupported (tests) | SDC generator | — | L | — | Keep |
| Reports (text/JSON/JUnit/HTML) | **PASS** | `reporter.py`; JUnit + HTML verified; report contains real findings | Reports | — | L | — | Keep |
| CLI (9 commands, exit 0/1/2/3) | **PASS** | All commands exercised in audit; exit codes verified | CLI | — | L | — | Keep |
| Local web API + workspace | **PASS** | stdlib `http.server`; LFI guard tests pass; validate/generate/rules/version endpoints verified | API + workspace | Vanilla-JS single-page; no per-feature catalog | L | P2 | Feature-first entry (see UX section) |
| Trust / support boundary | **PASS** | `support_boundary.py`; VALIDATED/PARTIAL/NETLIST_REQUIRED/TCL_EXECUTION_REQUIRED/UNSUPPORTED/NOT_VALIDATED | Trust model | — | L | — | Keep |
| Determinism | **PASS** | Byte-identical JSON across repeated runs (verified); no LLM, no network, no randomness | Determinism | — | L | — | Keep |
| Error handling / never-crash | **PASS** | checker wraps handlers; CLI returns 3 on engine failure (verified) | Error handling | — | L | — | Keep |
| Custom rules (YAML) | **MISSING** | Only `--rule` filter; no YAML ruleset engine | Custom rules | Planned v0.2.0 | M | P2 | Defer until after validation |
| Test suite (76 → 94) | **PASS** | `pytest tests/` → 94 passed in audit | 1,200+ | 10× smaller; no mutation evidence yet | M | P2 | Grow per evidence map |
| Realistic end-to-end fixture | **PASS** (new) | `tests/examples/cpu_subsys/` V1+V2+design context; 18 regression tests | Test Drive DMA sample | — | L | — | Keep |
| Version control / CI/CD | **MISSING** | `upf-insight/` is **not a git repository**; no `.github/workflows` | git + CI | **Critical**: no history, no CI, no tag | **H** | **P1** | Init git + GitHub Action immediately |
| Packaging (PyPI) | **PARTIAL** | `pyproject.toml` complete; `pip install -e .` works; wheel not verified from clean env | PyPI-published | Not published | M | P2 | Publish only after validation |
| Documentation freshness | **PARTIAL** | Docs exist and are strong, but stale in places (evidence map says "8 tests", roadmap says v0.2.0 items that are done) | Docs | Stale counts/claims | M | P2 | Reconcile with live repo |
| Performance | **UNKNOWN** | No large-UPF benchmark; engine is linear-ish single-pass but unmeasured | Perf profile | No data | M | P2 | Benchmark a real UPF corpus |
| Security | **PASS** (web) | LFI guards + tests; local-only binding; no telemetry | Security posture | — | L | — | Keep |

---

## 3. What UPF-Insight already does well (verified)

1. **Honest trust model, implemented** — the support boundary is derived,
   printed, and never weakened. "No errors ≠ power proven correct" is
   enforced structurally (empty input → NOT_VALIDATED + INSUFFICIENT_CONTEXT
   after this audit's fixes).
2. **Model-over-text is the right architecture for UPF** — a hierarchical,
   stateful format cannot be validated line-by-line; the builder/model split
   is genuinely correct (and is *more* appropriate here than Ṛta's SDC
   approach).
3. **Deterministic, offline, no-LLM** — verified byte-identical output.
4. **A real CI gate** — declarative policies, exit-code contract, baseline
   comparison, engine-failure-never-disabled.
5. **Generator self-consistency** — generated UPF always round-trips through
   the validator (test-enforced).
6. **Voltage-aware level-shifter analysis** — UPF-061/062 reason about
   declared supply-state voltages; this is real domain value, not keyword
   coverage.
7. **Never-crash rule engine** and a bounded Tcl-aware tokenizer with
   provenance.

## 4. What Ṛta does better

1. **Maturity of evidence** — 1,200+ tests, parity harness, mutation/golden
   suites, release smoke; UPF-Insight has 94 tests and no parity/mutation
   harness yet.
2. **Distribution** — Ṛta is PyPI-published with a GitHub Action and a
   deployed business site; UPF-Insight is local-only, unpublished, and not
   even a git repo.
3. **Workflow discipline** — Ṛta's feature-first catalog, per-feature
   workflows, standalone/session model, and acceptance/regression doctrine
   are more mature than UPF-Insight's single-page workspace.
4. **Corpus/fixtures** — Ṛta has real-design samples + netlists; UPF-Insight
   now has one realistic fixture family (this audit).
5. **Performance engineering** — Ṛta has been profiled on real SDCs;
   UPF-Insight has no large-UPF benchmark.

## 5. Biggest gaps (ranked)

1. **No version control / no CI** (P1) — the repo cannot be audited,
   released, or collaborated on safely.
2. **No custom rules engine** (P2) — the `--rule` filter exists but YAML
   rulesets are unimplemented despite being documented.
3. **Design context is a JSON snapshot, not a parser** (P2) — honest but
   limits the design-aware story to hand-authored snapshots.
4. **Strategy-level diff is shallow** (P2) — count-based; attribute changes
   (e.g. a clamp value) are not diffed.
5. **Docs lag implementation** (P2) — evidence map/roadmap/specification
   claim v0.2.0 work as future that is already done, and stale test counts.
6. **Coverage is structural only** (P2) — no per-construct-category
   inventory like Ṛta's 39-category SDC coverage (see baseline doc for the
   proposed UPF inventory).

## 6. Findings fixed during this audit

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 1 | `-elements {u1 u2}` in strategy commands kept braces → `['{u1', 'u2}']`; false UPF-083 and broken multi-element lists | `_split_opt` now strips the enclosing braces (mirrors the existing `create_power_domain` fix) | 94 tests green; retention coverage verified |
| 2 | Readiness always reported "netlist/RTL context not provided (v1)" even when a design context was supplied | `compute_readiness` checks `model.design` and reports instance/port counts | Design-aware readiness now READY with accurate summary |
| 3 | Empty input → readiness REVIEW_REQUIRED instead of INSUFFICIENT_CONTEXT (unconditional final aggregate clobbered the verdict) | Aggregate only when commands were parsed | Empty-input test asserts INSUFFICIENT_CONTEXT |
| 4 | Empty input → support boundary VALIDATED instead of NOT_VALIDATED | Early return NOT_VALIDATED when zero commands parsed | Empty-input test asserts NOT_VALIDATED=1 |

None of the fixes change rule semantics, rule IDs, severities, or the
deterministic computation for well-formed inputs — they restore the trust
contract for edge cases the engine previously mis-stated.

---

*Audit evidence: full pytest suite (94 passed), CLI exercised for every
command, web API smoke-tested, determinism diffed, fixtures inspected, docs
cross-checked against implementation. Nothing in the Ṛta repository was
touched.*
