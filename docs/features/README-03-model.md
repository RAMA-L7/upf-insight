# Feature 03 — Power-Intent Model

> Backend: `model/power_model.py` · `model/builder.py`
> CLI: `upf-insight model`

## What it does

Builds an in-memory object graph of the power intent — domains, supply
ports/nets/sets, power switches, supply states, PST rows, and isolation /
level-shifter / retention strategies — from preprocessed UPF commands. Rules
query this model rather than raw text.

## Entities

- `PowerDomain` — name, scope, elements, primary supply sets
- `SupplyPort` / `SupplyNet` / `SupplySet` — direction, connectivity, functions
- `PowerSwitch` — input/output supply, control, on-state
- `SupplyState` / `PowerState` / `Pst` — state inventory + PST rows
- `IsolationStrategy` / `LevelShifterStrategy` / `RetentionStrategy` — policy
  fields incl. location, clamp, control

Every entity records its `declared_line` for evidence.

## Builder

`builder.py` walks `CommandRecord`s, tokenizes with a bounded Tcl-aware
splitter (keeps `{...}` / `[...]` groups together), and mutates the model.
Unmodeled commands land in `PowerIntentModel.unsupported_commands` so the
support boundary stays honest.

## JSON dump

```bash
upf-insight model soc.upf -o model.json
```

The dump includes `commands_seen` and `unsupported_commands` alongside the
entity maps.

## Why model-over-text

UPF is hierarchical and stateful. SDC validation can be largely line-scoped;
UPF cannot. The builder is the single place that touches command tokens;
every rule consumes the model. This is the central architectural difference
from the sdc-tools line-oriented approach.