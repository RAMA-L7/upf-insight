# UPF Fundamentals — IEEE 1801 Power Intent

> **Document kind:** reference — the domain knowledge UPF-Insight encodes.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## 1. What UPF is

**UPF (Unified Power Format)** is the IEEE 1801 standard — the industry
language for expressing **power intent**: the power architecture of a chip,
described separately from functional RTL. UPF is a Tcl dialect, so it
complements HDLs (SystemVerilog / VHDL) by declaring *how logic is powered*,
not *what the logic computes*.

Versions:

| Version | Standard | Notes |
|---|---|---|
| UPF 1.0 | Accellera (2007) | First unified power format. |
| UPF 2.0 | IEEE 1801-2009 | Ratified; added supply sets, power states. |
| UPF 2.1 | IEEE 1801-2013 | Most widely deployed in industry. |
| UPF 3.0 | IEEE 1801-2018 | Added macros, power state groups, VCT/VCM. |
| UPF 3.1 | IEEE 1801-2022 | Refinements. |
| UPF 4.0 | IEEE 1801-2024 | Latest; extends macros and simulation semantics. |

UPF-Insight targets **2.1 baseline** (most common), with **3.0 additions**
detected, and **4.0** reported for awareness.

## 2. Core concepts

### Power domain
A named group of logic instances treated as one power-management unit. Created
by `create_power_domain NAME -elements {...}`. Domains partition the design;
an instance belongs to exactly one domain.

### Supply network
- **Supply port** (`create_supply_port`) — a power connection at a block
  boundary, with a direction.
- **Supply net** (`create_supply_net`) — the power rail.
- **Supply set** (`create_supply_set`) — a collection of supply nets by
  function (`power`, `ground`, plus secondary functions).
- **Connectivity** — `connect_supply_net` ties nets to ports/sets.
- **Domain assignment** — `set_domain_supply_net` /
  `-primary_supply_set` bind a domain to its primary power/ground.

### Power states & the Power State Table (PST)
- **Supply state** (`add_port_state` / `add_supply_state`) — a legal state of
  one supply (e.g. `ON 1.0` / `OFF 0.0`).
- **Power state** (`add_power_state`) — a legal combination across supplies.
- **PST** (`create_pst` + `add_pst_state`) — the table of legal operating
  modes (e.g. normal, standby, retention, power-down).
- **Transitions** (`add_state_transition`) — legal mode changes.

The PST is the contract for the rest of the flow: isolation and level-shifter
policy must be consistent with the states the PST declares legal.

### Power switches
`create_power_switch` — power-gating cells that cut a supply rail, controlled
by always-on logic. A switch's input/output supply and on-state define the
gating behavior.

### Strategies (protection cells)
- **Isolation** (`set_isolation`, `set_isolation_control`) — clamp or hold
  signals at domain boundaries so powered-down outputs do not corrupt always-on
  receivers.
- **Level shifters** (`set_level_shifter`) — translate signal voltage between
  domains at different supply voltages.
- **Retention** (`set_retention`, `set_retention_control`) — save/restore
  sequential state so it survives power-down.

### Hierarchy
- `set_scope` navigates the hierarchy.
- `load_upf` composes bottom-up power intent for IP integration.
- `set_design_top` names the top module.

### UPF 3.0/4.0 additions
- **Macros** — parameterized, reusable power-intent fragments.
- **Power state groups** — `create_power_state_group`.
- **VCT/VCM** — value-conversion types for connecting UPF supplies to HDL
  pins (`create_upf2hdl_vct`, `create_hdl2upf_vct`, legacy).
- **Composite domains** — `create_composite_domain` for boundary modeling.

## 3. The command landscape

UPF-Insight's model builder recognizes a growing subset of the UPF command
grammar:

| Category | Commands |
|---|---|
| Scope/design | `upf_version`, `set_design_top`, `set_scope`, `load_upf` |
| Supply | `create_supply_net/port/set`, `connect_supply_net`, `set_domain_supply_net` |
| Domains | `create_power_domain` (+ v3 `create_composite_domain`) |
| States | `add_port_state`, `add_supply_state`, `add_power_state`, `create_pst`, `add_pst_state`, `add_state_transition` |
| Switches | `create_power_switch` |
| Strategies | `set_isolation(+_control)`, `set_level_shifter`, `set_retention(+_control)` |
| Attributes | `set_port_attributes`, `set_design_attributes`, `set_equivalent` |

Unmodeled commands are captured in the model's `unsupported_commands` list so
the support boundary always reports the gap.

## 4. What can go wrong (the validation checklist)

### Syntax & references
- Unknown commands / options; missing required arguments.
- References to undefined domains, supplies, or instances.
- Duplicate definitions; use-before-definition; load-order circularities.

### Supply & domain integrity
- Domain with no primary supply.
- Supply set with no power/ground function.
- Unconnected supply nets; connectivity direction mismatches.

### Power state table
- Declared states never used; PST referencing undeclared states.
- Missing PST entirely; duplicate/overlapping rows; undeclared transitions.
- Isolation / level-shifter policy inconsistent with the PST.

### Strategy lint (the rich layer)
- **Isolation:** non-always-on supply, `-location self` in a switchable
  domain, missing/redundant isolation, `-applies_to` missing inouts, no
  control signal, invalid clamp, control not always-on.
- **Retention:** supply powers down, control not always-on, no elements,
  control tied to constant.
- **Level shifters:** unnecessary (equal voltages), missing (different
  voltages), wrong rule direction, wrong location.
- **Switches/always-on:** switch supply undefined, control not always-on,
  always-on signal entering a switchable domain, unused switch output.

### Design-aware (v2, needs netlist)
- Instance existence, control-signal existence, endpoint-based crossing
  coverage, retention vs actual flops, library PG mapping.

## 5. Industry tools context

Commercial static power checkers (e.g. Synopsys VC LP, SpyGlass LP, MVRC,
Conformal LP, JasperGold Power) run these same layers plus electrical and
formal verification. UPF-Insight intentionally targets the deterministic,
static subset — layers 1–5 — that requires **no EDA tool and no LLM**, and
discloses exactly where its support boundary ends (layer 6 / formal).

## 6. Where to learn more

- IEEE 1801 standard (IEEE GET program, free for individuals).
- IEEE open-source UPF example files at `opensource.ieee.org/upf`.
- Low-power design guides from the major EDA vendors (Synopsys "Low-Power
  Flow" docs, Arm/UPF design guides).

The open-source note: the unrelated physics *pseudopotential* UPF format
(pslibrary `upf-tools`) is **not** IEEE 1801 and is out of scope.