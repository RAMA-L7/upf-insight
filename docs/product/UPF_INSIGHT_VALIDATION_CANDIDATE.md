# UPF-Insight — Validation Candidate (v0.1.0-validation)

> This document records the exact frozen candidate that will be externally
> validated. Everything below is measured, not claimed. After the first
> engineer starts, **no product changes are permitted** until the cohort
> evidence is classified.

## Version / tag

- Version: **0.1.0**
- Tag: **v0.1.0-validation** (local only — nothing pushed)
- Commit: initial commit of the candidate state
- Repository: `D:\freebuff\upf-insight` (git initialized during hardening)

## Measured baseline

| Metric | Value |
|---|---|
| Rules | **65** (all with handlers, all tested, 6 layers) |
| Tests | **122 passed** |
| Capabilities | **19 evaluated** (18 PASS · Feedback NOT IMPLEMENTED) |
| Workspace pages | 11 WORKSPACE + 9 RESULTS (all rendered in browser) |
| API endpoints | 10 |
| CLI commands | 9 |
| Exit codes | 0 pass · 1 gate failed/issues · 2 invalid · 3 engine failure (verified) |

## Supported UPF scope

~30 IEEE 1801 commands modeled: power domains, supply ports/nets/sets,
supply states, PST, power switches, isolation, level shifters, retention,
repeaters, control bindings, port attributes, equivalence, library cell
mapping, promote/demote, load_upf. See
`docs/upf/RULES_REGISTRY.md` + `UPF_INSIGHT_FUNCTIONAL_BASELINE.md` §2/§10.

## Unsupported scope (honest)

- Full IEEE 1801 grammar: PARTIAL; unsupported commands are reported, never
  silent.
- Tcl execution (`proc`, `source`, expressions): detected, never executed
  (`TCL_EXECUTION_REQUIRED`).
- Custom YAML rules: **NOT IMPLEMENTED** (only `--rule` filtering).
- Timing / IR / power analysis: **out of scope by design** — disclosed.

## Fixtures

- `tests/examples/cpu_subsys/` — **cpu_subsys_v1.upf** (known-good),
  **cpu_subsys_v2.upf** (regressed: level shifter removed), and
  **cpu_subsys_design.json** (design context).
- `tests/examples/example.soc.upf` + `example.*.upf` (negative fixtures).
- `upf_insight/workspace/samples/` — the same CPU V1/V2/design served to the
  workspace Test Drive / Diff / Gate / Reports pages.

## Test Drive workflow (the validation scenario)

```
CPU V1 (known-good)  ── validate ──> 0E / REVIEW_REQUIRED
CPU V2 (regressed)   ── validate ──> 3E / BLOCKED
V1 vs V2             ── diff     ──> 1 semantic change (level shifter removed)
V2                   ── CI gate ──> STRICT FAIL, exit 1, reasons
V2                   ── report   ──> HTML/JSON with real findings
```

The planted regression is **not revealed** in the Test Drive description;
the engineer must investigate via Findings / Diff / Gate. Verified
end-to-end in a real browser.

## CI behavior (verified from clean invocation)

| Case | CLI exit | API |
|---|---|---|
| V1 + STRICT | 0 (PASS) | gate.passed=true, exit_code 0 |
| V2 + STRICT | 1 (FAIL) | gate.passed=false, exit_code 1, reasons |
| Missing file | 2 | — |
| Unknown policy | 2 | 400 |
| Engine failure | 3 | — |
| V2 vs V1 baseline (STRICT) | 1 (regression detected) | new blockers reported |

`--gate` alone gates the current evidence (CLI/API agreement).
Machine-readable output: JSON (+ JUnit for `check`).

## Report formats

HTML (human-readable, findings + readiness + support), JSON (full evidence),
text (terminal). All contain real engine data; never placeholders.

## Determinism result

V1 and V2 analyses run 3× each: **byte-identical**. Full JSON scanned
(727 leaf fields): **no nondeterministic fields** (no timestamps, UUIDs,
hashes, or ordering leakage).

## Packaging result

Wheel `upf_insight-0.1.0-py3-none-any.whl` built and **installed in a clean
virtual environment** (not the source tree). Verified from the installed
console command: version, check (exit 0/1), JSON output, HTML report,
STRICT gate, and design-aware mode (`DESIGN_AWARE`).

## Browser result

Real Chrome (CDP) walkthrough: **41/41 steps PASS, 0 console errors, 0
runtime exceptions**. All 19 pages render; generator produces real output;
rules registry shows 65 rows; no dead buttons; no empty pages caused by
missing session; clear empty/error states.

## Finding provenance

Findings carry `file` + `line` resolved from the authoritative command-record
index. Single-file runs always populate `file`; multi-file runs with
colliding line numbers leave it empty (ambiguous — never invented).

## Known limitations

1. No CI pipeline in this repository yet (git initialized; a GitHub Action
   is recommended after the candidate is pushed).
2. Model findings in multi-file colliding-line runs lack `file` (honest).
3. Design context is a JSON snapshot, not a netlist parser.
4. Custom YAML rules not implemented.
5. No timing/IR/signoff analysis — by design.

## Trust boundary (frozen)

- **READY ≠ signoff** — a power-intent review, not a power/IR signoff.
- **Coverage ≠ correctness** — coverage reports what the intent touches.
- **CI PASS ≠ power-intent signoff** — the gate reports policy pass.
- **Deterministic engine** — no LLM, no model inference, offline.
- **Engine failure never becomes PASS** (exit 3).
- **Unsupported constructs are reported**, never silent.

## Exact validation instructions (for engineers)

1. `pip install upf-insight` (or run from the frozen tag).
2. `upf-insight web` → open the local workspace.
3. Home → **Test Drive** → select *CPU regression (validate → diff → gate)* →
   Analyze.
4. Read the findings; open Findings, Diff, CI Gate, Reports to investigate.
5. Run the CLI flow for comparison:
   ```bash
   upf-insight check cpu_subsys_v1.upf --gate STRICT        # exit 0
   upf-insight check cpu_subsys_v2.upf --gate STRICT        # exit 1
   upf-insight diff cpu_subsys_v1.upf cpu_subsys_v2.upf
   upf-insight report cpu_subsys_v2.upf -o report.html
   ```
6. Answer: did you understand what changed and why the gate failed, without
   a developer explaining it?

## Freeze rule

Once Engineer #1 starts: **no code changes, no UI fixes, no wording tweaks**.
Record issues; classify only after the cohort finishes. The next step is
external validation, not further feature development.
