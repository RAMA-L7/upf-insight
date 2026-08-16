# Feature 04 — Semantic Diff

> Backend: `diff/differ.py`
> CLI: `upf-insight diff`

## What it does

Compares two power-intent models (old vs new UPF files) and reports
structural changes — semantic, not textual.

## Change records

```
ADD    domain 'PD_GPU'
REMOVE supply_net 'vdd_io'
MODIFY supply_set 'vdd_ret'
MODIFY strategy 'retention' count 1 -> 2
```

Kinds: `ADD` / `REMOVE` / `MODIFY`. What: domain, supply_net, supply_set,
switch, pst, strategy. `MODIFY` fires when the serialized entity differs.

## Trust boundary

The diff reflects modeled structure only. Unsupported commands are outside
the comparison; re-run `check` for the support boundary.

## Roadmap

- Saved-baseline snapshots (JSON) + finding identity (v0.3).
- Trust/coverage deltas and gate policies (`--gate`), mirroring the
  sdc-tools readiness-diff model.