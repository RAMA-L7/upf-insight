# Feature 02 — Power State Table (PST) Analysis

> Backend: `engine/pst/analyzer.py`
> CLI: `upf-insight pst`

## What it does

Expands and validates the Power State Table of a power-intent model:
declared vs used supply states, legal-combination coverage, and transitions.

## Output

- PST name, state count
- Declared supply states (from `add_port_state` / `add_supply_state`)
- Used states (the supply-state *values* referenced across `add_pst_state`
  rows)
- Unused / undeclared lists
- Transitions (from `add_state_transition`)
- A deterministic coverage note

## Examples

```bash
upf-insight pst soc.upf
upf-insight pst soc.upf --json
```

```text
PST:            pst_soc
States:         2
Unused states:  (none)
Undeclared:     (none)
Transitions:    0

All declared states are used by the PST.
```

## Trust boundary

Voltage-dependent conclusions (isolation/LS conditioning, retention
always-on) are PARTIAL without a complete supply-state model. The PST analyzer
provides the state inventory that those rules consume; it does not itself
prove electrical safety.

## Roadmap

- UPF-030/031/033/035/036 rule wiring against the analyzer (v0.2).
- Transition legality (PST-state transitions must reference declared states).