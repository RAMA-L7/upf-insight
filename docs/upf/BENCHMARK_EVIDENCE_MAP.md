# UPF-Insight — Benchmark Evidence Map

> **Document kind:** evidence map — every test/benchmark claim is backed by a
> rerunnable runner.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## 1. Principle

No marketing number exists without a runner behind it. This file maps every
claim to its executable evidence.

## 2. Core engine suite (`tests/test_engine.py`)

| # | Test | What it proves | Run |
|---|---|---|---|
| 1 | `test_preprocess_strips_comments_and_joins` | Comments removed; command names extracted; provenance kept | `pytest tests/test_engine.py::test_preprocess_strips_comments_and_joins` |
| 2 | `test_preprocess_line_continuation` | Backslash line continuations joined | same file, that test |
| 3 | `test_golden_example_is_clean` | Known-good 3-domain UPF yields no errors | `pytest ...::test_golden_example_is_clean` |
| 4 | `test_broken_example_fires_expected_rules` | Known-bad UPF fires UPF-001/011/045/052 | `pytest ...::test_broken_example_fires_expected_rules` |
| 5 | `test_support_boundary_counts_unsupported` | Support boundary reports UNSUPPORTED | `pytest ...::test_support_boundary_counts_unsupported` |
| 6 | `test_pst_analysis_golden` | PST expansion: states used/declared consistent | `pytest ...::test_pst_analysis_golden` |
| 7 | `test_model_dump_contains_domains` | Model dump contains domains | `pytest ...::test_model_dump_contains_domains` |
| 8 | `test_checker_never_crashes_on_empty_model` | Empty model → no crash, no findings | `pytest ...::test_checker_never_crashes_on_empty_model` |
| 9 | `test_generated_skeleton_is_supported` | Generator output has no UPF-001/UPF-020 | `pytest ...::test_generated_skeleton_is_supported` |
| 10 | `test_set_domain_supply_net_is_modeled` | `set_domain_supply_net` gives a domain a primary supply | `pytest ...::test_set_domain_supply_net_is_modeled` |
| 11 | `test_isolation_family_fires_on_bad_fixture` | Isolation family (040/041/044/045/046/047) fires on `example.iso_bad.upf`; 043 does not false-fire on switchable domain | `pytest ...::test_isolation_family_fires_on_bad_fixture` |
| 12 | `test_pst_family_fires_on_bad_fixture` | PST family (030/031/033/034/035) fires on `example.pst_bad.upf` | `pytest ...::test_pst_family_fires_on_bad_fixture` |
| 13 | `test_pst_transition_parsing_multipair` | Multi-pair `-state {vdd ON vss ON}` parsed; transitions recorded; no false findings | `pytest ...::test_pst_transition_parsing_multipair` |
| 14 | `test_readiness_golden_is_review_required` | Golden → categorical readiness verdict (no BLOCKED; design-aware caps at REVIEW) | `pytest ...::test_readiness_golden_is_review_required` |
| 15 | `test_readiness_bad_fixture_is_blocked` | Isolation-bad fixture → overall BLOCKED with UPF-040 blocker | `pytest ...::test_readiness_bad_fixture_is_blocked` |
| 16 | `test_coverage_golden_full` | Golden → domain/supply coverage 1.0 | `pytest ...::test_coverage_golden_full` |
| 17 | `test_rule_filter_restricts_findings` | `--rule UPF-031` yields only that rule | `pytest ...::test_rule_filter_restricts_findings` |
| 18 | `test_policy_gate_blocks_regression` | STRICT gate fails on new blockers/review vs baseline; no-regression passes | `pytest ...::test_policy_gate_blocks_regression` |
| 19 | `test_policy_invalid_input_exits_2` | Unknown policy raises ValueError (→ CLI exit 2) | `pytest ...::test_policy_invalid_input_exits_2` |
| 20 | `test_junit_and_html_reporters` | JUnit XML + self-contained HTML report render findings/readiness | `pytest ...::test_junit_and_html_reporters` |
| 21 | `test_switch_family_fires_on_bad_fixture` | Switch family (024/070/071/073) fires on `example.sw_bad.upf` | `pytest ...::test_switch_family_fires_on_bad_fixture` |
| 22 | `test_domain_element_overlap_fires` | UPF-021 fires when an instance is in two domains | `pytest ...::test_domain_element_overlap_fires` |
| 23 | `test_elements_brace_stripping` | `-elements {u1 u2}` parsed to `["u1","u2"]` | `pytest ...::test_elements_brace_stripping` |
| 24 | `test_retention_ls_family_fires_on_bad_fixture` | Retention + LS family (050/051/053/062) fires on `example.ret_ls_bad.upf` | `pytest ...::test_retention_ls_family_fires_on_bad_fixture` |
| 25 | `test_level_shifter_voltage_rules` | UPF-061/063 fire on voltage-differing + switchable domains; 061 fires once per pair | `pytest ...::test_level_shifter_voltage_rules` |
| 26 | `test_syntax_reference_family_fires_on_bad_fixture` | Syntax/reference layer (002/003/004/005/006/010/012/013/014) fires on `example.syn_ref_bad.upf`; golden port+net+resolve pair is NOT a duplicate | `pytest ...::test_syntax_reference_family_fires_on_bad_fixture` |
| 27 | `test_syntax_valid_fixture_has_no_syntax_errors` | Golden `example.soc.upf` produces no syntax/reference findings | `pytest ...::test_syntax_valid_fixture_has_no_syntax_errors` |
| 28 | `test_design_aware_family_fires_with_netlist` | Design-aware family (080/081/082/083/084) fires on `example.design_bad.upf` with `example.design.json`; silent without it | `pytest ...::test_design_aware_family_fires_with_netlist` |
| 29 | `test_design_aware_golden_is_silent` | Golden produces no UPF-08x findings without a design context | `pytest ...::test_design_aware_golden_is_silent` |

Run all: `python -m pytest tests/ -q`

## 3. Fixtures

| Fixture | Purpose |
|---|---|
| `tests/examples/example.soc.upf` | Golden known-good: 3 domains, supplies, states, PST, isolation, retention |
| `tests/examples/example.broken.upf` | Known-bad: 7+ injected defects exercising the rule set |
| `tests/examples/example.iso_bad.upf` | Isolation-family fixture: power switch + `-location self`, switchable isolation supply, invalid clamp, missing inouts/control |
| `tests/examples/example.pst_bad.upf` | PST-family fixture: unused declared state, undeclared state in row, duplicate combination, unreachable state, transition to ghost state |
| `tests/examples/example.sw_bad.upf` | Switch-family fixture: undefined switch output supply, unknown connect target, control not always-on, unused switch output |
| `tests/examples/example.ret_ls_bad.upf` | Retention/LS-family fixture: save=restore signal, wrong voltage rule, no retention elements |
| `tests/examples/example.syn_ref_bad.upf` | Syntax/reference fixture: illegal option, unsupported version, malformed Tcl, undefined supply, duplicate domain, use-before-definition, wildcard path |
| `tests/examples/example.design.json` | Design-context fixture: instances, ports, signals, liberty PG pins (for UPF-080…084) |
| `tests/examples/example.design_bad.upf` | Design-aware fixture: unknown instance, unknown switch control, uncovered crossing, retention gap, PG mismatch |
| `tests/examples/cpu_subsys/cpu_subsys_v1.upf` | **Realistic Test Drive fixture (V1, known-good):** CPU-subsystem power intent — switchable CPU domain, always-on control domain, 1.8 V I/O domain, SRAM retention domain, power switch, isolation, level shifter, retention, complete PST |
| `tests/examples/cpu_subsys/cpu_subsys_v2.upf` | **V2 (regressed):** same design with the I/O level shifter removed — UPF-061 fires on every voltage-differing pair; readiness BLOCKED |
| `tests/examples/cpu_subsys/cpu_subsys_design.json` | Matching design context for the CPU subsystem (instances, ports, signals, PG pins) |

### CPU-subsystem Test Drive suite (`tests/test_cpu_subsys_fixture.py`, 18 tests)

| Test group | What it proves |
|---|---|
| V1 known-good | 0 errors, coverage 1.0/1.0, not BLOCKED, clean in design-aware mode, no false UPF-083 |
| V2 regressed | UPF-061 ×3 (one per voltage pair), BLOCKED, coverage gap, blocked in design-aware mode |
| Regression is one construct | Removing exactly the level-shifter line flips V1 → V2 behavior; re-adding flips back |
| Diff | Removed level shifter visible as strategy MODIFY; V1 vs V1 → no changes |
| CI gate | STRICT / NO_READINESS_REGRESSION / BLOCKERS_ONLY all block V2 (exit 1); unchanged V1 passes (exit 0) |
| Provenance & determinism | Accurate source lines; byte-identical JSON across runs; empty/invalid input honest (INSUFFICIENT_CONTEXT, NOT_VALIDATED); CLI exit 0/1/2 |

## 4. CLI contract smoke

| Command | Expected |
|---|---|
| `upf-insight check example.soc.upf` | exit 0, "PASS", no errors |
| `upf-insight check example.broken.upf` | exit 1, "FAIL", rule codes present |
| `upf-insight pst example.soc.upf` | PST name + state counts |
| `upf-insight model example.soc.upf -o model.json` | JSON dump |
| `upf-insight generate --domains core,io` | valid UPF skeleton on stdout |
| `upf-insight diff old new` | ADD/REMOVE/MODIFY records |
| `upf-insight --version` | `upf-insight 0.1.0` |

## 5. Next: mutation evidence (planned)

For every implemented rule, add:
1. A positive fixture (must NOT fire).
2. A negative fixture (must fire exactly that rule).
3. A mutation test: introduce one defect into the golden file → assert the
   exact rule code + line fires.

Target: **100+ tests** by v1.0. New rules without both a positive and a
negative test are not considered shipped.

## 6. Conformance corpus (planned)

Parse open-source IEEE 1801 examples (`opensource.ieee.org/upf`) purely to
exercise the preprocessor and support-boundary accounting — no licensing
issues for parsing. These are **parse tests**, not correctness tests: we
assert the parser never crashes and the boundary is reported.