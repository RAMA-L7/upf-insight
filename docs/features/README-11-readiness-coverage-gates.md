# Feature 11 — Readiness, Coverage & CI Gates

> Backend: `engine/readiness` · `engine/coverage` · `engine/policy`
> CLI: `upf-insight check --save-baseline/--baseline/--gate` ·
> `upf-insight coverage` · `upf-insight rules list`

## 1. Readiness verdict

Mirrors the sdc-tools categorical readiness model — never a numeric score.

```text
READY · READY_WITH_ADVISORIES · REVIEW_REQUIRED · BLOCKED · INSUFFICIENT_CONTEXT
```

Five dimensions aggregate the findings:

| Dimension | Focus |
|---|---|
| `POWER_STATES` | PST rows, declared-vs-used states, transitions |
| `SUPPLY_NETWORK` | domains, supply nets/sets/ports, switches, connectivity |
| `STRATEGIES` | isolation / level-shifter / retention policies |
| `CONSISTENCY` | unknown commands, duplicates, contradictions |
| `DESIGN_CONTEXT` | netlist-aware checks (v1: out of scope, caps at REVIEW) |

A blocker rule (e.g. UPF-040) only blocks at **error** severity; PARTIAL /
NETLIST_REQUIRED warnings on the same code remain advisory/review.

## 2. Coverage

Structural domain/supply coverage:

```bash
upf-insight coverage design.upf
```

- Every domain: has a primary supply? switchable? isolation/retention/
  level-shifter strategy present?
- Supply coverage: every declared supply referenced by a domain, PST, or
  strategy?

Coverage is evidence of what the intent *touches*, never correctness.

## 3. CI gates

```bash
upf-insight check design.upf --save-baseline base.json      # snapshot
upf-insight check design.upf --baseline base.json --gate STRICT
```

Built-in policies (same declarative schema):

| Policy | Fails on |
|---|---|
| `BLOCKERS_ONLY` | current BLOCKED |
| `NO_READINESS_REGRESSION` | NEW blockers + trust regression vs baseline |
| `STRICT` | blockers, new review items, trust/coverage regressions |

Custom policies are inert JSON/YAML validated against a fixed schema; unknown
keys/types are rejected with exit code 2. **Engine failure always exits 3 and
can never be disabled by policy.**

## Exit codes

`0` pass · `1` gate failed · `2` invalid invocation/input · `3` engine failure