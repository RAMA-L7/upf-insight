# Feature 09 — Reports

> Backend: `report/reporter.py`
> CLI: `upf-insight check --format text|json|junit` · `upf-insight report`

## What it does

Deterministic rendering of a `ValidateResult` as text, JSON, JUnit XML, or a
self-contained HTML report. Formatting only — no new analysis.

## Text output

```text
UPF-Insight — deterministic power-intent validation
==================================================
Files:  1   Commands: 22

[WARNING] UPF-050  :33   Retention supply 'vdd_ret' always-on status must be
                         confirmed against the PST / supply states. (support=PARTIAL)
[WARNING] UPF-052  :33   set_retention for domain 'PD_SRAM' references no
                         retention elements (-elements empty).  (support=VALIDATED)

Support boundary:
  VALIDATED: 2
  NETLIST_REQUIRED: 1
  note: Design-aware rules (UPF-080..084) require a netlist/RTL context, ...

PST: All declared states are used by the PST.

Readiness: REVIEW_REQUIRED
  POWER_STATES: READY — 2 PST state(s), 2 transition(s), 3 declared supply state(s).
  SUPPLY_NETWORK: READY — 3 domain(s), 2 net(s), 2 set(s), 2 port(s), 0 switch(es).
  STRATEGIES: REVIEW_REQUIRED — 1 isolation, 0 level-shifter, 1 retention strategy(ies).
  CONSISTENCY: READY — No unsupported commands parsed.
  DESIGN_CONTEXT: REVIEW_REQUIRED — netlist/RTL context not provided (v1)

Coverage: domain 1.0 supply 1.0
  PD_CORE: covered

Summary: 0 error(s), 2 warning(s), 0 info(s) — PASS
```

## JSON output

The full `ValidateResult.to_dict()`: findings, counts, support boundary, PST,
readiness verdict, and coverage.

## JUnit XML (CI)

```bash
upf-insight check design.upf --format junit > junit.xml
```

One `<testcase>` per finding; error/warning findings emit `<failure>`.

## HTML report

```bash
upf-insight report design.upf -o report.html
```

Self-contained HTML with the readiness verdict banner, support chips, and a
color-coded findings table.
