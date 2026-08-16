# UPF-Insight — Rules Registry

> **Document kind:** engineering contract — the canonical list of rule codes.
> **Source of truth:** `upf_insight/engine/rules/rules_registry.py`
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

This document mirrors the registry module. Every rule has a stable code, a
severity, a layer, and a description. The registry is the contract between
the checker, reports, the workspace, and (planned) CI policy.

**Layer legend:** `SYNTAX` · `REFERENCE` · `SUPPLY_DOMAIN` · `PST` ·
`STRATEGY` · `DESIGN`

## Layer 1 — Syntax & version (UPF-001…006)

| Code | Severity | Title | Description |
|---|---|---|---|
| UPF-001 | error | Unknown UPF command | The leading command name is not a known UPF command. |
| UPF-002 | error | Illegal option | An option used with a command is not legal for that command. |
| UPF-003 | error | Missing required argument | A required argument (e.g. `-domain`, `-elements`) is absent. |
| UPF-004 | warning | Unsupported upf_version | Requested UPF version is unsupported or conflicts with used features. |
| UPF-005 | warning | Deprecated/legacy syntax | A deprecated UPF 1.0/2.0 form is used. |
| UPF-006 | error | Malformed Tcl | Unbalanced braces/brackets or unterminated continuation. |

## Layer 2 — Reference integrity (UPF-010…016)

| Code | Severity | Title | Description |
|---|---|---|---|
| UPF-010 | error | Undefined supply reference | A supply net/port/set is referenced before it is defined. |
| UPF-011 | error | Undefined power domain | A power domain is referenced but never created. |
| UPF-012 | warning | Undefined instance / bad path | An instance or hierarchical path does not resolve. |
| UPF-013 | error | Duplicate definition | A domain, supply, switch, strategy or PST name is defined twice. |
| UPF-014 | warning | Use-before-definition | An object is used before its defining command (load-order issue). |
| UPF-015 | warning | Circular dependency | Cyclic load order / domain boundary dependency. |
| UPF-016 | warning | Invalid set_scope target | `set_scope` names a module/instance that does not exist. |

## Layer 3 — Supply & domain integrity (UPF-020…025)

| Code | Severity | Title | Description |
|---|---|---|---|
| UPF-020 | error | Domain missing primary supply | A power domain has no `set_domain_supply_net` / `-primary_supply_set`. |
| UPF-021 | error | Domain element overlap | An instance belongs to two power domains. |
| UPF-022 | warning | Unconnected supply | A supply port/net/set is not connected to any supply set. |
| UPF-023 | error | Supply set missing power/ground | A supply set has no power or ground function. |
| UPF-024 | error | Supply connectivity mismatch | `connect_supply_net` direction/port mismatch in hierarchy. |
| UPF-025 | info | Unused supply state | A supply state/voltage is declared but never referenced. |

## Layer 4 — Power state table (UPF-030…036)

| Code | Severity | Title | Description |
|---|---|---|---|
| UPF-030 | error | Declared state never used in PST | `add_port_state`/`add_power_state` declares a state never used by the PST. |
| UPF-031 | error | PST references undeclared state | A PST row uses a state that was never declared. |
| UPF-032 | warning | Missing PST | Power states exist but no `create_pst` was issued. |
| UPF-033 | warning | Empty/unreachable PST state | A PST state covers no legal power combination. |
| UPF-034 | warning | Duplicate/overlapping PST state | Two PST rows declare the same power combination. |
| UPF-035 | warning | Undeclared transition | `add_state_transition` names an undeclared source/target state. |
| UPF-036 | warning | Isolation/LS not PST-conditioned | Isolation or level-shifter policy is not a mandatory/sufficient condition of the PST. |

## Layer 5 — Strategy lint (UPF-040…073)

### Isolation

| Code | Severity | Title | Description |
|---|---|---|---|
| UPF-040 | error | Isolation on non-always-on supply | Isolation cell uses a switchable (non-always-on) supply. |
| UPF-041 | error | Isolation self-located in switchable domain | Isolation `-location self` in a switchable domain loses power. |
| UPF-042 | warning | Missing isolation on crossing | A crossing into/out of a powered-down domain is not isolated. |
| UPF-043 | info | Redundant isolation | Isolation applied on an always-on crossing. |
| UPF-044 | warning | `-applies_to` missing inouts | `-applies_to outputs` misses inouts (bidirectional ports). |
| UPF-045 | error | Isolation without control (or reverse) | `set_isolation` has no matching `set_isolation_control`, or vice versa. |
| UPF-046 | error | Invalid clamp value | `clamp_value` is invalid for the target state/domain. |
| UPF-047 | warning | Isolation control not always-on | Isolation control signal is not driven by always-on logic. |

### Retention

| Code | Severity | Title | Description |
|---|---|---|---|
| UPF-050 | error | Retention supply powers down | The retention supply is not always-on. |
| UPF-051 | warning | Retention control not always-on | Save/restore control is not driven by always-on logic. |
| UPF-052 | warning | Retention without coverage | `set_retention` references no retention elements. |
| UPF-053 | warning | Retention control tied constant | Retention control is tied to a constant and never toggles. |

### Level shifters

| Code | Severity | Title | Description |
|---|---|---|---|
| UPF-060 | info | Unnecessary level shifter | Level shifter between equal-voltage domains (wasted area/power). |
| UPF-061 | error | Missing level shifter | A crossing between different-voltage domains lacks a level shifter. |
| UPF-062 | error | Wrong level-shifter rule | `low_to_high` vs `high_to_low` mismatch for the voltage pair. |
| UPF-063 | error | Level shifter self-located in switchable domain | `-location self` for a level shifter in a switchable domain. |

### Switches & always-on

| Code | Severity | Title | Description |
|---|---|---|---|
| UPF-070 | error | Switch references undefined supply | A power switch references a supply net defined after it. |
| UPF-071 | warning | Switch control not always-on | Power-switch control signal is not from always-on logic. |
| UPF-072 | error | Always-on signal into switchable domain | An always-on signal (clk/rst/scan) crosses into a switchable domain un-isolated. |
| UPF-073 | info | Switch output unused | A power switch output supply is not used by any domain. |

## Layer 6 — Design-aware (UPF-080…084, v2, requires netlist/RTL context)

| Code | Severity | Title | Description |
|---|---|---|---|
| UPF-080 | warning | Unknown `-elements` instance | An instance in `-elements` does not exist in the netlist. |
| UPF-081 | warning | Unknown control signal | An isolation/retention/switch control signal is not in the design. |
| UPF-082 | warning | Uncovered crossing (endpoint-based) | A cross-domain signal lacks a strategy when considering endpoints. |
| UPF-083 | warning | Retention coverage gap | Retention coverage does not cover the sequential elements present. |
| UPF-084 | warning | Library PG mismatch | UPF supply mapping conflicts with liberty PG pin declarations. |

## Implementation status

| Layer | Rules | Implemented in v0.1.0 |
|---|---|---|
| 1 Syntax | UPF-001…006 | UPF-001, 002, 003, 004, 005, 006 |
| 2 Reference | UPF-010…016 | UPF-010, 011, 012, 013, 014, 015, 016 |
| 3 Supply/domain | UPF-020…025 | UPF-020, 021, 022, 023, 024, 025 |
| 4 PST | UPF-030…036 | UPF-030, 031, 032, 033, 034, 035, 036 |
| 5 Strategy | UPF-040…073 | UPF-040…047, 050, 051, 052, 053, 060, 061, 062, 063, 070…073 |
| 6 Design | UPF-080…084 | UPF-080, 081, 082, 083, 084 (require `--netlist` design context) |

Layer 1/2 rules are builder-side checks recorded into the model
(`syntax_issues`, `duplicate_definitions`, `references`, `scope_changes`) and
converted to findings by their handlers. UPF-012/015/016 cover the
deterministically-checkable subset (wildcard paths, self-connect cycles, scope
names); netlist-dependent parts are NETLIST_REQUIRED and deferred to v2.

Layer 6 rules (UPF-080…084) are silent unless a design context is supplied via
`upf-insight check --netlist design.json` or the web API's `design` payload.
The design context is a JSON netlist snapshot (instances, ports, signals,
liberty PG pins) — see `tests/examples/example.design.json`. Without it the
support boundary reports NETLIST_REQUIRED.

Every registered rule is documented here; not every rule has a handler yet.
Rules without a handler are dormant — the checker skips them and the support
boundary records the gap. This keeps the registry the *contract* while
implementation catches up layer by layer.