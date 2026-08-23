# Experiment 2 — Structured Semantic Facts from example.soc.upf

> Source: `tests/examples/example.soc.upf`
> Extraction method: deterministic parsing against rules_registry.py

---

## Semantic fact table

### Supply network

| # | Fact | Value | Source command |
|---|---|---|---|
| S1 | Supply port vdd exists | `vdd` (direction: in) | `create_supply_port vdd` |
| S2 | Supply port vss exists | `vss` (direction: in) | `create_supply_port vss` |
| S3 | Supply net vdd exists | `vdd` (resolve: port) | `create_supply_net vdd` |
| S4 | Supply net vss exists | `vss` (resolve: port) | `create_supply_net vss` |
| S5 | vdd connected to vdd port | `connect_supply_net vdd -ports vdd` | `connect_supply_net` |
| S6 | vss connected to vss port | `connect_supply_net vss -ports vss` | `connect_supply_net` |
| S7 | Supply set primary | power: vdd, ground: vss | `create_supply_set primary` |
| S8 | Supply set vdd_ret | power: net vdd_ret_net, ground: vss | `create_supply_set vdd_ret` |

### Power domains

| # | Fact | Value | Source command |
|---|---|---|---|
| D1 | Domain PD_CORE exists | elements: {u_cpu}, primary: primary | `create_power_domain PD_CORE` |
| D2 | Domain PD_IO exists | elements: {u_io}, primary: primary | `create_power_domain PD_IO` |
| D3 | Domain PD_SRAM exists | elements: {u_sram}, primary: vdd_ret | `create_power_domain PD_SRAM` |
| D4 | PD_CORE is switchable | primary supply = primary (vdd-based) | Inferred from supply set |
| D5 | PD_IO is switchable | primary supply = primary (vdd-based) | Inferred from supply set |
| D6 | PD_SRAM is always-on | primary supply = vdd_ret (separate rail) | Inferred from supply set |

### Power states

| # | Fact | Value | Source command |
|---|---|---|---|
| P1 | Port state vdd ON | voltage: 1.0 | `add_port_state vdd -state {ON 1.0}` |
| P2 | Port state vdd OFF | voltage: 0.0 | `add_port_state vdd -state {OFF 0.0}` |
| P3 | Port state vss ON | voltage: 0.0 | `add_port_state vss -state {ON 0.0}` |
| P4 | PST pst_soc exists | supplies: {vdd vss} | `create_pst pst_soc` |
| P5 | PST state PS_ON | vdd ON, vss ON | `add_pst_state PS_ON` |
| P6 | PST state PS_OFF | vdd OFF, vss ON | `add_pst_state PS_OFF` |
| P7 | Transition PS_ON → PS_OFF | declared | `add_state_transition PS_ON` |
| P8 | Transition PS_OFF → PS_ON | declared | `add_state_transition PS_OFF` |

### Strategies

| # | Fact | Value | Source command |
|---|---|---|---|
| T1 | Isolation iso_core_to_io | domain: PD_CORE | `set_isolation iso_core_to_io` |
| T2 | Isolation supply | primary (always-on in this context) | `-isolation_supply primary` |
| T3 | Isolation clamp | 0 | `-clamp_value 0` |
| T4 | Isolation applies_to | outputs | `-applies_to outputs` |
| T5 | Isolation signal | iso_en | `-isolation_signal iso_en` |
| T6 | Retention ret_sram | domain: PD_SRAM | `set_retention ret_sram` |
| T7 | Retention supply | vdd_ret | `-retention_supply vdd_ret` |
| T8 | Retention save signal | save | `-save_signal save` |
| T9 | Retention restore signal | restore | `-restore_signal restore` |

### Relationships

| # | Fact | From → To | Notes |
|---|---|---|---|
| R1 | PD_CORE primary → primary supply set | PD_CORE → primary | primary connects to vdd |
| R2 | PD_IO primary → primary supply set | PD_IO → primary | primary connects to vdd |
| R3 | PD_SRAM primary → vdd_ret supply set | PD_SRAM → vdd_ret | vdd_ret connects to vdd_ret_net |
| R4 | iso_core_to_io on PD_CORE | PD_CORE → PD_IO | isolation from core to io |
| R5 | ret_sram on PD_SRAM | PD_SRAM | retention for SRAM domain |

### Design top

| # | Fact | Value |
|---|---|---|
| DT1 | Design top module | soc_top |
| DT2 | UPF version | 3.0 |

---

## Total semantic fact count

| Category | Count |
|---|---|
| Supply network | 8 |
| Power domains | 6 |
| Power states | 8 |
| Strategies | 9 |
| Relationships | 5 |
| Design top | 2 |
| **Total** | **38** |

---

## Applicable SVG diagrams

| Diagram | Relevance | Semantic facts to check |
|---|---|---|
| 01 — Validation Architecture | Process-level, not UPF-specific | N/A (illustrative) |
| 02 — Supply Topology | **Direct** — supply/domain topology | S1–S8, D1–D6, R1–R3 |
| 03 — Power Switch States | Not applicable — no power switch in example | N/A |
| 04 — Isolation Placement | **Direct** — isolation strategy | T1–T5 |
| 05 — Level Shifter Direction | Not applicable — no level shifter in example | N/A |
| 06 — Retention Architecture | **Direct** — retention strategy | T6–T9 |
| 07 — PST Power States | **Direct** — power states | P1–P8 |
| 08 — Evidence Boundary | Conceptual, not UPF-specific | N/A (illustrative) |
| 09 — Finding Cascade | Finding dependency, not UPF-specific | N/A (illustrative) |
| 10 — Adversarial Showcase | Summary, not UPF-specific | N/A (illustrative) |

**Applicable diagrams for consistency check: 4**

| Diagram | Applicable facts |
|---|---|
| 02 — Supply Topology | 19 facts (S1–S8, D1–D6, R1–R3 + inference) |
| 04 — Isolation | 5 facts (T1–T5) |
| 06 — Retention | 4 facts (T6–T9) |
| 07 — PST States | 8 facts (P1–P8) |
| **Total** | **36 facts across 4 diagrams** |
