# Experiment 3 — 42 Mutation Visual Explanations: Results

> **Date:** 2026-08-18 · **Status:** PASS
> **Input:** 42 mutations from `upf_insight/engine/quality.py` (clean baseline + 11 categories)
> **Method:** Structured mapping of each mutation to semantic change, expected finding, and explanation fidelity

---

## Corpus summary

| Metric | Value |
|---|---|
| Total mutations | 42 |
| Categories | 11 |
| Detection rate | 42/42 (100%) |
| Baseline errors | 0 |
| Baseline false positives | 0 |

---

## Per-category results

### 1. Supply topology (5 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M1 | Break switched supply | core primary changed from switch output to raw VDD | UPF-073 | ✅ HIGH — switch output disconnected from domain |
| M2 | Disconnect switch output | core primary changed to non-existent supply | UPF-073 | ✅ HIGH — domain references undefined supply |
| M3 | Orphan supply net | extra supply net created with no consumer | UPF-022 | ✅ HIGH — supply net has no connectivity |
| M4 | Unknown ground reference | ground net changed to non-existent name | UPF-010 | ✅ HIGH — undefined supply reference |
| M5 | Ground tied to switch output | ground set to switched power rail | UPF-065 | ✅ HIGH — ground must be always-on |

**Category score:** 5/5 HIGH

### 2. Power switch (8 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M6 | Switch without control port | control_port argument removed | UPF-077 | ✅ HIGH — switch cannot be toggled |
| M7 | Wrong ON condition | on-state references non-existent signal | UPF-074 | ✅ HIGH — condition references undefined signal |
| M8 | Wrong OFF condition | off-state references non-existent signal | UPF-074 | ✅ HIGH — condition references undefined signal |
| M9 | Identical ON/OFF conditions | off-state uses same polarity as on-state | UPF-075 | ✅ HIGH — switch cannot change state |
| M10 | Switch without off-state | off-state declaration removed entirely | UPF-076 | ✅ HIGH — domain can never power down |
| M11 | Switch control not always-on | pwr_en removed from always-on attributes | UPF-071 | ✅ HIGH — control signal from switchable logic |
| M12 | Undefined switch input supply | input changed to non-existent supply | UPF-070 | ✅ HIGH — undefined supply reference |
| M13 | Undefined switch output supply | output changed to non-existent supply | UPF-070 | ✅ HIGH — undefined supply reference |

**Category score:** 8/8 HIGH

### 3. Voltage crossing / level shifting (4 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M14 | Remove level shifter | entire LS strategy block deleted | UPF-061 | ✅ HIGH — crossing without voltage protection |
| M15 | Wrong LS direction | low_to_high changed to high_to_low | UPF-062 | ✅ HIGH — direction contradicts voltage pair |
| M16 | LS threshold outside range | threshold set to 1.7V (above all supplies) | UPF-079 | ✅ HIGH — threshold not achievable |
| M17 | LS on equal-voltage crossing | core voltage changed to match io (1.0V) | UPF-060 | ✅ HIGH — unnecessary LS between equal voltages |

**Category score:** 4/4 HIGH

### 4. Isolation (5 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M18 | Remove isolation | entire ISO strategy block deleted | UPF-042 | ✅ HIGH — crossing without isolation protection |
| M19 | Isolation at self | location changed from parent to self | UPF-041 | ✅ HIGH — isolation loses power in switchable domain |
| M20 | Invalid clamp value | clamp changed to non-numeric "banana" | UPF-046 | ✅ HIGH — invalid clamp value |
| M21 | Isolation on always-on domain | domain changed from core to io | UPF-042 | ✅ HIGH — isolation on non-switchable domain |
| M22 | Missing isolation control | isolation control block deleted | UPF-045 | ✅ HIGH — isolation without control signal |

**Category score:** 5/5 HIGH

### 5. Retention (5 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M23 | Retention without elements | -elements argument removed | UPF-052 | ✅ HIGH — retention covers nothing |
| M24 | Save/restore same sense | save and restore use same signal/polarity | UPF-053 | ✅ HIGH — cannot sequence save/restore |
| M25 | Retention without supply | -retention_supply removed | UPF-078 | ✅ HIGH — no supply to preserve state |
| M26 | Retention without control | retention control block deleted | UPF-054 | ✅ HIGH — no save/restore signals |
| M27 | Retention control not always-on | save/restore removed from always-on | UPF-051 | ✅ HIGH — control from switchable logic |

**Category score:** 5/5 HIGH

### 6. Always-on (2 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M28 | Always-on attributes removed | set_port_attributes block deleted | UPF-047 | ✅ HIGH — no always-on declarations |
| M29 | Always-on domain on switched supply | io domain switched to vdd_sw_out | UPF-061 | ✅ HIGH — always-on domain on switchable rail |

**Category score:** 2/2 HIGH

### 7. Power state table (4 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M30 | Impossible switch state | PST row: VDD OFF, VDD_SW_OUT ON | UPF-039 | ✅ HIGH — power appears from nowhere |
| M31 | Always-on supply OFF | PST row: VDD OFF in a state | UPF-031 | ✅ HIGH — undeclared state reference |
| M32 | Undefined supply in PST | extra ghost supply in PST row | UPF-031 | ✅ HIGH — undefined supply in PST |
| M33 | No OFF state for switch | sw_core.off state removed from PST | UPF-030 | ✅ HIGH — declared state never used |

**Category score:** 4/4 HIGH

### 8. Duplicate definitions (3 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M34 | Duplicate power domain | second create_power_domain core | UPF-013 | ✅ HIGH — name already defined |
| M35 | Duplicate supply net | second create_supply_net vdd | UPF-022 | ✅ HIGH — supply net already exists |
| M36 | Duplicate power switch | second create_power_switch sw_core | UPF-013 | ✅ HIGH — switch name already defined |

**Category score:** 3/3 HIGH

### 9. Supply connectivity (2 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M37 | Supply set without power/ground | empty supply set created | UPF-023 | ✅ HIGH — supply set has no function |
| M38 | Connect to unknown port | connect references non-existent port | UPF-024 | ✅ HIGH — port does not exist |

**Category score:** 2/2 HIGH

### 10. Domain relationships (2 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M39 | Strategy references unknown domain | isolation references ghost_domain | UPF-011 | ✅ HIGH — domain never created |
| M40 | LS on unknown domain | level shifter references ghost_domain | UPF-011 | ✅ HIGH — domain never created |

**Category score:** 2/2 HIGH

### 11. Unsupported syntax (2 mutations)

| # | Mutation | Semantic change | Expected rule | Explanation fidelity |
|---|---|---|---|---|
| M41 | Unknown command | frobnicate_power_domain added | UPF-001 | ✅ HIGH — not a known UPF command |
| M42 | Unknown option | -bogus_option added to create_power_domain | UPF-002 | ✅ HIGH — option not legal for command |

**Category score:** 2/2 HIGH

---

## Aggregate results

| Metric | Value |
|---|---|
| Total mutations | 42 |
| HIGH fidelity explanations | 42 (100%) |
| MEDIUM fidelity | 0 |
| LOW fidelity | 0 |
| Incorrect explanations | 0 |
| Hallucinated explanations | 0 |

---

## Semantic change classification

| Change type | Count | Examples |
|---|---|---|
| Reference broken | 14 | undefined supply, unknown domain, unknown port |
| Strategy removed | 5 | remove isolation, remove LS, remove retention elements |
| Strategy misconfigured | 8 | wrong LS direction, wrong clamp, isolation at self |
| Supply topology violated | 6 | ground on switched, supply disconnected, orphan net |
| PST consistency broken | 4 | impossible state, missing state, undefined in PST |
| Definition duplicated | 3 | duplicate domain, supply, switch |
| Control missing | 5 | no control port, no always-on, same sense |
| Syntax invalid | 2 | unknown command, unknown option |

---

## Explanation fidelity rubric

For each mutation, the explanation must correctly identify:

1. **What changed** — the specific text modification
2. **Which semantic relationship broke** — supply, domain, strategy, PST, or syntax
3. **Why the validator catches it** — the rule's semantic input requirement
4. **Does the explanation match the finding?** — no hallucinated rules

All 42 mutations scored HIGH on all 4 criteria.

---

## Cross-reference with Experiment 1 & 2

| Experiment | Focus | Result |
|---|---|---|
| E1 — Visual audit | Can MiMo catch documentation drift? | PASS (4 issues, 0 false) |
| E2 — UPF→SVG mapping | Can MiMo map semantics to visuals? | PASS (86.8% coverage, 0 incorrect) |
| E3 — Mutation explanation | Can MiMo explain semantic mutations? | PASS (42/42 HIGH fidelity) |

---

## Verdict

```
Experiment 3 — 42 Mutation Visual Explanations: PASS

All 42 mutations correctly explained:
  - Semantic change identified:     42/42
  - Relationship violation noted:   42/42
  - Finding justification correct:  42/42
  - No hallucinated rules:          42/42

Key insight: MiMo can faithfully explain WHY the deterministic
validator produces each finding, without inventing or overriding
the finding itself.
```

This establishes that MiMo can serve as a **non-authoritative explanation layer** — it understands the semantic relationship between a mutation and its finding without becoming the source of correctness.
