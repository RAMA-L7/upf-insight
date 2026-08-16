# Feature 01 — Validate (Checker)

> Backend: `engine/rules/checker.py` · `engine/rules/upf_rules.py`
> CLI: `upf-insight check`

## What it does

Runs the deterministic rule engine over a power-intent model and reports every
finding with severity, rule code, message, and file:line provenance.

## Pipeline

```
preprocess -> build_model -> check_model -> support boundary -> PST -> report
```

`check_model` dispatches each registered rule to its handler in
`upf_rules.py` (looked up via `RULE_HANDLERS` by registry code). A handler
that raises is caught and reported as an engine-scope finding — a rule can
never crash the run.

## Finding shape

```json
{"rule": "UPF-045", "severity": "error",
 "message": "Isolation for domain 'PD_CORE' has no set_isolation_control...",
 "file": "soc.upf", "line": 21, "support": "VALIDATED"}
```

## Exit codes

0 clean · 1 issues · 2 invalid invocation · 3 engine failure.

## Implemented handlers (v0.1.0)

UPF-001, 011, 020, 022, 023, 032, 034, 045, 050, 052, 060. See
[docs/upf/RULES_REGISTRY.md](../upf/RULES_REGISTRY.md) for the full catalog
and the implementation-status table.

## Adding a rule

Follow [docs/company/ENGINEERING_CHECKLIST.md](../company/ENGINEERING_CHECKLIST.md):
handler + registry entry + positive/negative tests.

## Example

```bash
upf-insight check soc.upf io.upf --format json
```