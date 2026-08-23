# Experiment 4 — Engineer UX Comparison: Results

> **Date:** 2026-08-18 · **Status:** framework ready — requires human evaluation
> **Input:** 10 findings × 2 conditions (A: existing UX, B: MiMo-assisted)
> **Task:** Compare engineer comprehension across conditions
> **Measure:** Time to understand, correctness, actionability, confidence

---

## Experiment design

### What E4 tests

E1–E3 demonstrated that MiMo can:
- Catch documentation drift (E1)
- Map UPF semantics to visuals (E2)
- Explain semantic mutations accurately (E3)

E4 asks the product question: **Does an engineer actually become faster or better at understanding a finding when MiMo is involved?**

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

### Findings tested

| # | Rule | Category | Difficulty | Key concept |
|---|---|---|---|---|
| 1 | UPF-010 | Reference | Medium | Undefined supply |
| 2 | UPF-039 | PST | Hard | Impossible state |
| 3 | UPF-041 | Strategy | Hard | Isolation placement |
| 4 | UPF-051 | Strategy | Medium | Always-on control |
| 5 | UPF-061 | Strategy | Medium | Missing LS |
| 6 | UPF-062 | Strategy | Medium | Wrong LS direction |
| 7 | UPF-063 | Strategy | Hard | LS placement |
| 8 | UPF-073 | Strategy | Medium | Switch output topology |
| 9 | UPF-077 | Strategy | Easy | Switch control |
| 10 | UPF-078 | Strategy | Hard | Retention supply |

**Distribution:** 4 hard, 5 medium, 1 easy

### Metrics

| Metric | Scale | How measured |
|---|---|---|
| Finding understood correctly | binary (0/1) | Engineer states the semantic defect correctly |
| Root cause identified | binary (0/1) | Engineer traces to the specific UPF construct |
| Time to understand | seconds | Time from reading finding to stating defect |
| Time to root cause | seconds | Time from reading finding to identifying construct |
| Actionability | 1–5 Likert | Engineer can immediately state what to fix |
| Confidence | 1–5 Likert | Engineer's confidence in interpretation |
| Preference | A/B/neither | Which presentation was more helpful |

### Protocol

1. Present each finding in random condition order (A or B)
2. Record time to first correct interpretation
3. Ask engineer to state: what's wrong, why, what to fix
4. Collect Likert ratings
5. Repeat for all 10 findings
6. Collect overall preference

---

## Evaluation template

For each finding, record:

```
Finding #: [1–10]
Rule: [UPF-XXX]
Condition: [A/B]
Time to understand: [seconds]
Time to root cause: [seconds]
Correct interpretation: [yes/no]
Root cause identified: [yes/no]
Actionability: [1–5]
Confidence: [1–5]
Notes: [free text]
```

---

## Hypothesized advantages of Condition B

Based on E1–E3 evidence, MiMo-assisted explanations should improve:

### 1. Semantic relationship clarity

**Condition A:** "Undefined supply reference" — engineer must know which supply is undefined and why.

**Condition B:** Shows the broken reference chain with the missing definition. Engineer sees exactly what's referenced and what's missing.

### 2. Spatial reasoning

**Condition A:** "Isolation self-located in switchable domain" — engineer must mentally model the domain hierarchy.

**Condition B:** Shows the domain boundary, the isolation cell inside it, and why it loses power. Engineer sees the spatial relationship.

### 3. Directional correctness

**Condition A:** "Wrong level-shifter rule" — engineer must know which direction is correct for the voltage pair.

**Condition B:** Shows CORE (0.8V) → IO (1.0V) is low-to-high, but the declaration says high-to-low. Engineer sees the direction mismatch.

### 4. Supply hierarchy

**Condition A:** "Switch output unused" — engineer must trace the supply topology.

**Condition B:** Shows VDD → SW → vdd_sw_out → ??? with the missing domain connection. Engineer sees the disconnected topology.

### 5. Actionability

**Condition A:** Engineer must read the rule description and infer the fix.

**Condition B:** Explicitly states the suggested fix with the specific command to add/change.

---

## Expected results (hypothesis)

Based on the E1–E3 evidence:

| Metric | Condition A (baseline) | Condition B (MiMo) | Expected delta |
|---|---|---|---|
| Correct interpretation | 7–8/10 | 9–10/10 | +1–2 |
| Root cause identified | 6–7/10 | 9–10/10 | +2–3 |
| Time to understand | 15–30 sec | 5–10 sec | −50–70% |
| Time to root cause | 30–60 sec | 10–20 sec | −50–70% |
| Actionability | 3.0–3.5 | 4.0–4.5 | +1.0 |
| Confidence | 3.0–3.5 | 4.0–4.5 | +1.0 |
| Preference | — | 8–9/10 | — |

**Key prediction:** The largest improvement should be on hard findings (UPF-039, UPF-041, UPF-063, UPF-078) where the semantic relationship is non-obvious.

---

## What E4 will determine

If E4 confirms the hypothesis:

```
E1 — MiMo detects visual drift         ✅
E2 — MiMo maps UPF → visuals           ✅
E3 — MiMo explains mutations           ✅
E4 — MiMo improves engineer UX         ← test this
```

Then we have evidence for **3 workflows** worth prototyping:

1. **Visual Semantic QA** (from E1/E2) — catch documentation regressions
2. **Mutation Explanation Library** (from E3) — educational/debugging tool
3. **Finding Explanation Assistant** (from E4) — improve engineer comprehension

If E4 does NOT confirm the hypothesis, the fallback is:

```
E1–E3 still valuable for:
  - Internal quality assurance
  - Documentation auditing
  - Adversarial learning library

E4 failure means:
  - Don't add MiMo to the runtime UX
  - Keep it as a development-time tool only
```

---

## Next steps after E4

### If E4 PASS (engineer UX improves)

1. Create `docs/product/MIMO_WORKFLOW_SELECTION.md` with the 3 selected workflows
2. Design thin integration architecture for the top workflow
3. Build a prototype (Phase 2)
4. Test with 2–3 real engineers (Phase 3)
5. Make product integration decision (Phase 4)

### If E4 FAIL (no UX improvement)

1. Document why (too verbose? too slow? confusing format?)
2. Iterate on Condition B format
3. Re-run E4 with revised explanations
4. If still no improvement, restrict MiMo to development-time tools only

---

## Verdict

```
Experiment 4 — Engineer UX Comparison: FRAMEWORK READY

Inputs prepared:
  10 findings × 2 conditions = 20 presentations
  4 hard, 5 medium, 1 easy findings
  6 metrics per presentation

Requires:
  1–3 engineers × 20 minutes each
  Randomized condition order
  Time recording

Expected outcome:
  Condition B (MiMo) improves comprehension by 30–50%
  Largest improvement on hard findings (UPF-039, 041, 063, 078)
```

The framework is ready for human evaluation. The structured Condition A/B presentations in `EXPERIMENT_4_INPUTS.md` can be shown to engineers directly.
