# Experiment 4 — Engineer UX Comparison: Inputs

> **Date:** 2026-08-18 · **Status:** framework ready
> **Input:** 10 representative findings from adversarial corpus
> **Task:** Compare existing UX (Condition A) vs MiMo-assisted explanation (Condition B)
> **Measure:** Time to understand, root cause identification, correctness, actionability, confidence

---

## Evaluation framework

### Metrics

| Metric | Scale | Definition |
|---|---|---|
| Finding understood correctly | binary (0/1) | Engineer correctly identifies the semantic defect |
| Root cause identified | binary (0/1) | Engineer traces the finding to the specific UPF construct |
| Time to understand | seconds | Time from reading the finding to stating the defect |
| Time to root cause | seconds | Time from reading the finding to identifying the UPF construct |
| Actionability | 1–5 Likert | Engineer can immediately state what to fix |
| Confidence | 1–5 Likert | Engineer's confidence in their interpretation |
| Preference | A/B/neither | Which presentation was more helpful |

### Conditions

**Condition A — Existing Ṛta UX:**
```
Rule code + severity + message + source line + inspector panel
```

**Condition B — MiMo-assisted:**
```
Rule code + severity + message + source line +
plain-language explanation + semantic relationship diagram + suggested fix
```

---

## Finding 1 — UPF-010: Undefined Supply Reference

**Rule:** UPF-010 (error, REFERENCE)
**Description:** A supply net/port/set is referenced before it is defined.
**Semantic inputs:** supply references, supply definitions
**Context:** UPF_ONLY

### Condition A — Existing UX

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-010                                │
│ Severity: ERROR                                 │
│ Message: Undefined supply reference             │
│                                                 │
│ Source: line 42                                 │
│ Subject: vdd_ghost                              │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

### Condition B — MiMo-assisted

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-010                                │
│ Severity: ERROR                                 │
│ Message: Undefined supply reference             │
│ Source: line 42                                 │
│                                                 │
│ What happened:                                  │
│ The design references supply "vdd_ghost" but    │
│ no create_supply_net / create_supply_port /      │
│ create_supply_set command defines it.           │
│                                                 │
│ Semantic relationship:                          │
│                                                 │
│   create_power_domain core                      │
│     -primary_power_net vdd_ghost  ← referenced  │
│                                                 │
│   (no create_supply_net vdd_ghost)    ← missing │
│                                                 │
│ Why it matters:                                 │
│ The validator cannot determine the supply       │
│ topology without knowing what vdd_ghost is.     │
│ Without a definition, the switch output,        │
│ domain primary, and PST rows are all            │
│ unverifiable.                                   │
│                                                 │
│ Suggested fix:                                  │
│ Add: create_supply_net vdd_ghost -resolve port  │
│ or change the reference to an existing supply.  │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

---

## Finding 2 — UPF-039: Impossible PST State

**Rule:** UPF-039 (error, PST)
**Description:** A PST row declares a switch output ON while its input supply is OFF.
**Semantic inputs:** switch in/out supplies, PST rows
**Context:** UPF_ONLY

### Condition A — Existing UX

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-039                                │
│ Severity: ERROR                                 │
│ Message: Impossible PST state                   │
│                                                 │
│ Source: line 67                                 │
│ Subject: pst_top / BROKEN                       │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

### Condition B — MiMo-assisted

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-039                                │
│ Severity: ERROR                                 │
│ Message: Impossible PST state                   │
│ Source: line 67                                 │
│                                                 │
│ What happened:                                  │
│ PST state "BROKEN" declares VDD = OFF but       │
│ VDD_SW_OUT = ON. Power cannot appear            │
│ downstream when the switch input is OFF.        │
│                                                 │
│ Semantic relationship:                          │
│                                                 │
│   VDD ──► SW_CORE ──► VDD_SW_OUT               │
│   OFF                 ON  ← impossible           │
│                                                 │
│ Why it matters:                                 │
│ The PST is supposed to describe legal power     │
│ combinations. This state implies power          │
│ materializes from nowhere, which violates the   │
│ supply hierarchy constraint.                    │
│                                                 │
│ Suggested fix:                                  │
│ Either:                                         │
│   1. Set VDD_SW_OUT = OFF when VDD = OFF        │
│   2. Or remove the BROKEN state entirely        │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

---

## Finding 3 — UPF-041: Isolation Self-Located in Switchable Domain

**Rule:** UPF-041 (error, STRATEGY)
**Description:** Isolation -location self in a switchable domain loses power.
**Semantic inputs:** isolation location, domain primary
**Context:** UPF_ONLY

### Condition A — Existing UX

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-041                                │
│ Severity: ERROR                                 │
│ Message: Isolation self-located in switchable   │
│          domain                                 │
│                                                 │
│ Source: line 35                                 │
│ Subject: iso_core                               │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

### Condition B — MiMo-assisted

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-041                                │
│ Severity: ERROR                                 │
│ Message: Isolation self-located in switchable   │
│          domain                                 │
│ Source: line 35                                 │
│                                                 │
│ What happened:                                  │
│ Isolation "iso_core" is located at "self"       │
│ inside the switchable CORE domain. When CORE    │
│ powers down, the isolation cell also loses       │
│ power and cannot hold the clamp value.          │
│                                                 │
│ Semantic relationship:                          │
│                                                 │
│   CORE (switchable, 0.8V)                       │
│     └── iso_core  ← location: self  ✗          │
│         loses power when CORE = OFF             │
│                                                 │
│   Correct: isolation at parent (AON side)       │
│     AON (always-on, 1.0V)                       │
│       └── iso_core  ← location: parent  ✓      │
│         stays powered, holds clamp              │
│                                                 │
│ Why it matters:                                 │
│ Isolation must survive the power-down it's      │
│ protecting against. If the isolation cell is    │
│ in the domain being powered down, it can't      │
│ hold the output clamp value (0).                │
│                                                 │
│ Suggested fix:                                  │
│ Change: -location self                          │
│ To:     -location parent                        │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

---

## Finding 4 — UPF-051: Retention Control Not Always-On

**Rule:** UPF-051 (warning, STRATEGY)
**Description:** Save/restore control is not driven by always-on logic.
**Semantic inputs:** save/restore controls, port attributes
**Context:** PARTIAL (needs netlist for definitive)

### Condition A — Existing UX

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-051                                │
│ Severity: WARNING                               │
│ Message: Retention control not always-on        │
│                                                 │
│ Source: line 51                                 │
│ Subject: ret_core                               │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

### Condition B — MiMo-assisted

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-051                                │
│ Severity: WARNING                               │
│ Message: Retention control not always-on        │
│ Source: line 51                                 │
│                                                 │
│ What happened:                                  │
│ Retention "ret_core" uses save/restore signals  │
│ that are not declared as always-on. When CORE   │
│ powers down, these signals become undefined     │
│ and the save/restore sequence cannot execute.   │
│                                                 │
│ Semantic relationship:                          │
│                                                 │
│   ret_core                                      │
│     save ← not always_on  ✗                     │
│     restore ← not always_on  ✗                  │
│                                                 │
│   Expected:                                     │
│     set_port_attributes save, restore           │
│       -attribute {always_on true}               │
│                                                 │
│ Why it matters:                                 │
│ Retention only works if the save/restore        │
│ control signals remain valid during the         │
│ power transition. If they're in the switchable  │
│ domain, they disappear before they can trigger. │
│                                                 │
│ Suggested fix:                                  │
│ Add save/restore to the always-on attribute     │
│ list, or drive them from always-on logic.       │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

---

## Finding 5 — UPF-061: Missing Level Shifter

**Rule:** UPF-061 (error, STRATEGY)
**Description:** A crossing between different-voltage domains lacks a level shifter.
**Semantic inputs:** domain voltages, LS strategies
**Context:** UPF_ONLY

### Condition A — Existing UX

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-061                                │
│ Severity: ERROR                                 │
│ Message: Missing level shifter                  │
│                                                 │
│ Source: line 28                                 │
│ Subject: core → io crossing                     │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

### Condition B — MiMo-assisted

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-061                                │
│ Severity: ERROR                                 │
│ Message: Missing level shifter                  │
│ Source: line 28                                 │
│                                                 │
│ What happened:                                  │
│ Signals cross from CORE (0.8V) to IO (1.0V)     │
│ but no level shifter strategy protects this     │
│ crossing.                                       │
│                                                 │
│ Semantic relationship:                          │
│                                                 │
│   CORE (0.8V) ──────► IO (1.0V)                │
│              ???                                │
│   Missing: set_level_shifter                    │
│     -domain core                                │
│     -rule low_to_high                           │
│     -location parent                            │
│                                                 │
│ Why it matters:                                 │
│ Signals crossing from a lower voltage to a      │
│ higher voltage need level shifting to be        │
│ reliably interpreted. Without it, the IO domain │
│ may see undefined logic levels.                 │
│                                                 │
│ Suggested fix:                                  │
│ Add a level shifter with rule low_to_high       │
│ (0.8V → 1.0V is low-to-high direction).        │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

---

## Finding 6 — UPF-062: Wrong Level-Shifter Direction

**Rule:** UPF-062 (error, STRATEGY)
**Description:** low_to_high vs high_to_low mismatch for the voltage pair.
**Semantic inputs:** LS rule, domain voltages
**Context:** UPF_ONLY

### Condition A — Existing UX

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-062                                │
│ Severity: ERROR                                 │
│ Message: Wrong level-shifter rule               │
│                                                 │
│ Source: line 38                                 │
│ Subject: ls_core                                │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

### Condition B — MiMo-assisted

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-062                                │
│ Severity: ERROR                                 │
│ Message: Wrong level-shifter rule               │
│ Source: line 38                                 │
│                                                 │
│ What happened:                                  │
│ Level shifter "ls_core" is declared as          │
│ high_to_low, but CORE (0.8V) → IO (1.0V) is    │
│ a low-to-high voltage crossing.                 │
│                                                 │
│ Semantic relationship:                          │
│                                                 │
│   CORE 0.8V ──────────► IO 1.0V                │
│          LOW → HIGH                             │
│                                                 │
│   Declared: high_to_low  ✗                      │
│   Required: low_to_high  ✓                      │
│                                                 │
│ Why it matters:                                 │
│ A level shifter in the wrong direction won't    │
│ properly boost the signal voltage. The lower    │
│ voltage domain's output may not reach the       │
│ higher domain's input threshold.                │
│                                                 │
│ Suggested fix:                                  │
│ Change: -rule high_to_low                       │
│ To:     -rule low_to_high                       │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

---

## Finding 7 — UPF-063: Level Shifter Self-Located in Switchable Domain

**Rule:** UPF-063 (error, STRATEGY)
**Description:** -location self for a level shifter in a switchable domain.
**Semantic inputs:** LS location, domain primary
**Context:** UPF_ONLY

### Condition A — Existing UX

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-063                                │
│ Severity: ERROR                                 │
│ Message: Level shifter self-located in          │
│          switchable domain                      │
│                                                 │
│ Source: line 39                                 │
│ Subject: ls_core                                │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

### Condition B — MiMo-assisted

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-063                                │
│ Severity: ERROR                                 │
│ Message: Level shifter self-located in          │
│          switchable domain                      │
│ Source: line 39                                 │
│                                                 │
│ What happened:                                  │
│ Level shifter "ls_core" is located at "self"    │
│ inside the switchable CORE domain. When CORE    │
│ powers down, the level shifter also loses       │
│ power and cannot shift voltages.                │
│                                                 │
│ Semantic relationship:                          │
│                                                 │
│   CORE (switchable, 0.8V)                       │
│     └── ls_core  ← location: self  ✗           │
│         loses power when CORE = OFF             │
│                                                 │
│   Correct: LS at parent (AON side)              │
│     AON (always-on, 1.0V)                       │
│       └── ls_core  ← location: parent  ✓       │
│         stays powered during transitions        │
│                                                 │
│ Why it matters:                                 │
│ Like isolation, the level shifter must survive  │
│ the power transition. If it's in the switchable │
│ domain, it disappears before it can shift.      │
│                                                 │
│ Suggested fix:                                  │
│ Change: -location self                          │
│ To:     -location parent                        │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

---

## Finding 8 — UPF-073: Switch Output Unused

**Rule:** UPF-073 (error, STRATEGY)
**Description:** A power switch output supply is not used by any domain.
**Semantic inputs:** switch output, domain primary supplies
**Context:** UPF_ONLY

### Condition A — Existing UX

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-073                                │
│ Severity: ERROR                                 │
│ Message: Switch output unused                   │
│                                                 │
│ Source: line 22                                 │
│ Subject: sw_core / vdd_sw_out                   │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

### Condition B — MiMo-assisted

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-073                                │
│ Severity: ERROR                                 │
│ Message: Switch output unused                   │
│ Source: line 22                                 │
│                                                 │
│ What happened:                                  │
│ Power switch "sw_core" produces output          │
│ "vdd_sw_out" but no power domain uses it as     │
│ its primary supply. The switched power has      │
│ nowhere to go.                                  │
│                                                 │
│ Semantic relationship:                          │
│                                                 │
│   VDD ──► SW_CORE ──► vdd_sw_out ──► ???       │
│                                  (no domain)    │
│                                                 │
│   Expected:                                     │
│     create_power_domain core                    │
│       -primary_power_net vdd_sw_out             │
│                                                 │
│ Why it matters:                                 │
│ The switch exists to power-gate a domain. If    │
│ no domain uses the switched output, the         │
│ switch serves no purpose and the domain is      │
│ either unpowered or on the wrong supply.        │
│                                                 │
│ Suggested fix:                                  │
│ Either:                                         │
│   1. Set the domain's primary to vdd_sw_out     │
│   2. Or remove the unused switch                │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

---

## Finding 9 — UPF-077: Switch Without Control Port

**Rule:** UPF-077 (error, STRATEGY)
**Description:** A power switch declares no control port.
**Semantic inputs:** control port
**Context:** UPF_ONLY

### Condition A — Existing UX

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-077                                │
│ Severity: ERROR                                 │
│ Message: Switch without control port            │
│                                                 │
│ Source: line 18                                 │
│ Subject: sw_core                                │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

### Condition B — MiMo-assisted

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-077                                │
│ Severity: ERROR                                 │
│ Message: Switch without control port            │
│ Source: line 18                                 │
│                                                 │
│ What happened:                                  │
│ Power switch "sw_core" has no -control_port     │
│ argument. Without a control signal, the switch  │
│ can never be toggled between on and off states. │
│                                                 │
│ Semantic relationship:                          │
│                                                 │
│   sw_core                                       │
│     input:  vdd                                 │
│     output: vdd_sw_out                          │
│     control: ???  ← missing                     │
│                                                 │
│ Why it matters:                                 │
│ A power switch that cannot be controlled is     │
│ effectively stuck. The domain is either always  │
│ on or always off — the power-gating capability  │
│ is lost.                                        │
│                                                 │
│ Suggested fix:                                  │
│ Add: -control_port pwr_en                       │
│ (or whatever signal controls the switch)        │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

---

## Finding 10 — UPF-078: Retention Without Supply on Switchable Domain

**Rule:** UPF-078 (error, STRATEGY)
**Description:** Retention on a switchable domain names no retention supply.
**Semantic inputs:** retention supply, domain primary
**Context:** UPF_ONLY

### Condition A — Existing UX

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-078                                │
│ Severity: ERROR                                 │
│ Message: Retention without supply on            │
│          switchable domain                      │
│                                                 │
│ Source: line 44                                 │
│ Subject: ret_core                               │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

### Condition B — MiMo-assisted

```
┌─────────────────────────────────────────────────┐
│ Finding: UPF-078                                │
│ Severity: ERROR                                 │
│ Message: Retention without supply on            │
│          switchable domain                      │
│ Source: line 44                                 │
│                                                 │
│ What happened:                                  │
│ Retention "ret_core" is applied to the          │
│ switchable CORE domain but has no               │
│ -retention_supply argument. Without a           │
│ dedicated supply that stays on during           │
│ power-down, the retention registers cannot      │
│ preserve state.                                 │
│                                                 │
│ Semantic relationship:                          │
│                                                 │
│   CORE (switchable, 0.8V)                       │
│     └── ret_core                                │
│           retention_supply: ???  ← missing      │
│                                                 │
│   Expected:                                     │
│     set_retention ret_core                      │
│       -domain core                              │
│       -retention_supply ret_vdd                 │
│                                                 │
│ Why it matters:                                 │
│ When CORE powers down, its primary supply       │
│ (vdd_sw_out) goes to 0. Without a separate      │
│ retention supply that stays ON, the flip-flop   │
│ state is lost.                                  │
│                                                 │
│ Suggested fix:                                  │
│ Add: -retention_supply ret_vdd                  │
│ (an always-on supply for the retention regs)    │
│                                                 │
│ [Inspector] [Source] [Rule Info]                │
└─────────────────────────────────────────────────┘
```

---

## Summary

| # | Rule | Category | Key concept | Difficulty |
|---|---|---|---|---|
| 1 | UPF-010 | Reference | Undefined supply | Medium |
| 2 | UPF-039 | PST | Impossible state | Hard |
| 3 | UPF-041 | Strategy | Isolation placement | Hard |
| 4 | UPF-051 | Strategy | Always-on control | Medium |
| 5 | UPF-061 | Strategy | Missing LS | Medium |
| 6 | UPF-062 | Strategy | Wrong LS direction | Medium |
| 7 | UPF-063 | Strategy | LS placement | Hard |
| 8 | UPF-073 | Strategy | Switch output topology | Medium |
| 9 | UPF-077 | Strategy | Switch control | Easy |
| 10 | UPF-078 | Strategy | Retention supply | Hard |

**Distribution:** 4 hard, 5 medium, 1 easy — deliberately weighted toward harder cases.
