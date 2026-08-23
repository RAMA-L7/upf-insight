# UPF-Insight support matrix

Version: 0.3.0 · rules registered: 77 · engine: deterministic, no LLM in the analysis path.

Honest boundary: **"no errors" does not mean "power proven correct"**. Rules with context NETLIST_REQUIRED or PARTIAL are needs netlist/RTL context - advisory without it.

Context distribution: NETLIST_REQUIRED 14 · PARTIAL 13 · UPF_ONLY 50

## Syntax & version (SYNTAX) — 6 rules

| Code | Sev | Context | Title |
|---|---|---|---|
| UPF-001 | error | UPF_ONLY | Unknown UPF command |
| UPF-002 | error | UPF_ONLY | Illegal option |
| UPF-003 | error | UPF_ONLY | Missing required argument |
| UPF-004 | warning | UPF_ONLY | Unsupported upf_version |
| UPF-005 | warning | UPF_ONLY | Deprecated/legacy syntax |
| UPF-006 | error | UPF_ONLY | Malformed Tcl |

## Reference integrity (REFERENCE) — 10 rules

| Code | Sev | Context | Title |
|---|---|---|---|
| UPF-010 | error | UPF_ONLY | Undefined supply reference |
| UPF-011 | error | UPF_ONLY | Undefined power domain |
| UPF-012 | warning | NETLIST_REQUIRED | Undefined instance / bad path |
| UPF-013 | error | UPF_ONLY | Duplicate definition |
| UPF-014 | warning | UPF_ONLY | Use-before-definition |
| UPF-015 | warning | PARTIAL | Circular dependency |
| UPF-016 | warning | NETLIST_REQUIRED | Invalid set_scope target |
| UPF-095 | error | UPF_ONLY | Promoted entity not defined |
| UPF-098 | error | UPF_ONLY | Equivalent supply undefined |
| UPF-099 | error | UPF_ONLY | Supply map reference undefined |

## Supply & domain integrity (SUPPLY_DOMAIN) — 6 rules

| Code | Sev | Context | Title |
|---|---|---|---|
| UPF-020 | error | UPF_ONLY | Domain missing primary supply |
| UPF-021 | error | NETLIST_REQUIRED | Domain element overlap |
| UPF-022 | warning | UPF_ONLY | Unconnected supply |
| UPF-023 | error | UPF_ONLY | Supply set missing power/ground |
| UPF-024 | error | UPF_ONLY | Supply connectivity mismatch |
| UPF-025 | info | UPF_ONLY | Unused supply state |

## Power state table (PST) — 10 rules

| Code | Sev | Context | Title |
|---|---|---|---|
| UPF-030 | error | UPF_ONLY | Declared state never used in PST |
| UPF-031 | error | UPF_ONLY | PST references undeclared state |
| UPF-032 | warning | UPF_ONLY | Missing PST |
| UPF-033 | warning | UPF_ONLY | Empty/unreachable PST state |
| UPF-034 | warning | UPF_ONLY | Duplicate/overlapping PST state |
| UPF-035 | warning | UPF_ONLY | Undeclared transition |
| UPF-036 | warning | PARTIAL | Isolation/LS not PST-conditioned |
| UPF-037 | warning | PARTIAL | Un-isolated power-down crossing |
| UPF-038 | warning | UPF_ONLY | Switchable net not modeled by PST |
| UPF-039 | error | UPF_ONLY | Impossible PST state |

## Strategy lint (STRATEGY) — 36 rules

| Code | Sev | Context | Title |
|---|---|---|---|
| UPF-040 | error | PARTIAL | Isolation on non-always-on supply |
| UPF-041 | error | UPF_ONLY | Isolation self-located in switchable domain |
| UPF-042 | warning | NETLIST_REQUIRED | Missing isolation on crossing |
| UPF-043 | info | UPF_ONLY | Redundant isolation |
| UPF-044 | warning | NETLIST_REQUIRED | -applies_to missing inouts |
| UPF-045 | error | UPF_ONLY | Isolation without control (or reverse) |
| UPF-046 | error | UPF_ONLY | Invalid clamp value |
| UPF-047 | warning | PARTIAL | Isolation control not always-on |
| UPF-050 | error | PARTIAL | Retention supply powers down |
| UPF-051 | warning | PARTIAL | Retention control not always-on |
| UPF-052 | warning | UPF_ONLY | Retention without coverage |
| UPF-053 | warning | UPF_ONLY | Retention control tied constant |
| UPF-054 | error | UPF_ONLY | Retention without control |
| UPF-060 | info | PARTIAL | Unnecessary level shifter |
| UPF-061 | error | UPF_ONLY | Missing level shifter |
| UPF-062 | error | UPF_ONLY | Wrong level-shifter rule |
| UPF-063 | error | UPF_ONLY | Level shifter self-located in switchable domain |
| UPF-064 | warning | PARTIAL | Level-shifter control not always-on |
| UPF-070 | error | UPF_ONLY | Switch references undefined supply |
| UPF-071 | warning | PARTIAL | Switch control not always-on |
| UPF-072 | error | NETLIST_REQUIRED | Always-on signal into switchable domain |
| UPF-073 | error | UPF_ONLY | Switch output unused |
| UPF-074 | warning | UPF_ONLY | Switch state condition without control |
| UPF-075 | error | UPF_ONLY | Switch cannot toggle |
| UPF-076 | error | UPF_ONLY | Switch without off-state |
| UPF-077 | error | UPF_ONLY | Switch without control port |
| UPF-078 | error | UPF_ONLY | Retention without supply on switchable domain |
| UPF-079 | warning | PARTIAL | Level-shifter threshold out of range |
| UPF-085 | error | UPF_ONLY | Duplicate strategy |
| UPF-086 | warning | UPF_ONLY | Overriding or conflicting strategy |
| UPF-087 | warning | PARTIAL | Low-specificity wildcard |
| UPF-090 | error | UPF_ONLY | Repeater supply not always-on |
| UPF-091 | warning | PARTIAL | Repeater control not always-on |
| UPF-092 | error | UPF_ONLY | Repeater self-located in switchable domain |
| UPF-093 | warning | UPF_ONLY | Repeater without elements |
| UPF-094 | error | UPF_ONLY | Repeater without control |

## Supply connectivity (SUPPLY) — 1 rules

| Code | Sev | Context | Title |
|---|---|---|---|
| UPF-065 | error | UPF_ONLY | Ground on switched supply |

## Design-aware (DESIGN) — 8 rules

| Code | Sev | Context | Title |
|---|---|---|---|
| UPF-080 | warning | NETLIST_REQUIRED | Unknown -elements instance |
| UPF-081 | warning | NETLIST_REQUIRED | Unknown control signal |
| UPF-082 | warning | NETLIST_REQUIRED | Uncovered crossing (endpoint-based) |
| UPF-083 | warning | NETLIST_REQUIRED | Retention coverage gap |
| UPF-084 | warning | NETLIST_REQUIRED | Library PG mismatch |
| UPF-096 | warning | NETLIST_REQUIRED | Demotion not verifiable |
| UPF-097 | warning | NETLIST_REQUIRED | Hierarchical composition unverified |
| UPF-100 | warning | NETLIST_REQUIRED | Loaded UPF file missing |

## Supported UPF commands

- `add_port_state` (2 known options)
- `add_power_state` (2 known options)
- `add_pst_state` (5 known options)
- `add_state_transition` (2 known options)
- `add_supply_state` (2 known options)
- `connect_supply_net` (3 known options)
- `create_power_domain` (4 known options)
- `create_power_switch` (6 known options)
- `create_pst` (2 known options)
- `create_supply_net` (2 known options)
- `create_supply_port` (3 known options)
- `create_supply_set` (4 known options)
- `load_upf` (3 known options)
- `map_isolation_cell` (4 known options)
- `map_level_shifter_cell` (4 known options)
- `map_retention_cell` (4 known options)
- `set_design_top`
- `set_domain_supply_net` (3 known options)
- `set_equivalent` (4 known options)
- `set_isolation` (11 known options)
- `set_isolation_control` (5 known options)
- `set_level_shifter` (7 known options)
- `set_level_shifter_control` (3 known options)
- `set_port_attributes` (2 known options)
- `set_repeater` (10 known options)
- `set_repeater_control` (3 known options)
- `set_retention` (6 known options)
- `set_retention_control` (5 known options)
- `set_scope`
- `update_supply_net` (2 known options)
- `update_supply_set` (4 known options)
- `upf_demote` (5 known options)
- `upf_promote` (5 known options)
- `upf_version`

Commands outside this list are recorded as `unsupported_commands` in the model and surfaced honestly in the support boundary.
