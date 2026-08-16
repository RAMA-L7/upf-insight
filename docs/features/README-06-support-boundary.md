# Feature 06 — Support Boundary / Trust Model

> Backend: `engine/trust/support_boundary.py`
> Docs: [docs/upf/TRUST_MODEL.md](../upf/TRUST_MODEL.md)

## What it does

Derives, deterministically, what the engine validated, partially validated,
and skipped for a given model.

## Statuses

| Status | When |
|---|---|
| `VALIDATED` | Check fully performed against modeled intent. |
| `PARTIALLY_VALIDATED` | Reduced strength (e.g. retention always-on without a full supply-state/PST model). |
| `NETLIST_REQUIRED` | Needs a netlist/RTL context (layer 6, v1 does not provide it). |
| `TCL_EXECUTION_REQUIRED` | Needs executing Tcl constructs; detected, never executed. |
| `UNSUPPORTED` | Command parsed but not modeled. |
| `NOT_VALIDATED` | No UPF commands parsed at all. |

## Core honesty

> **Clean ≠ power proven correct. Coverage ≠ correctness. CI pass ≠
> low-power closure.**

The boundary is always printed/reported — "no findings" never silently means
"proven correct".

## Example (broken fixture)

```
Support boundary:
  NETLIST_REQUIRED: 1
  UNSUPPORTED: 1
  note: 1 command(s) were parsed but not modeled (support boundary).
  note: Design-aware rules (UPF-080..084) require a netlist/RTL context,
        which v1 does not provide.
```