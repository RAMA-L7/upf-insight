# UPF-Insight — MiMo Multimodal Integration Plan

> **Document kind:** product plan / architecture input.
> **Date:** 2026-08-18 · **Version:** v0.5.0
> **Status:** experiments in progress. E1–3 PASS, E4 framework ready for human evaluation.

---

## Core architecture

```
                    UPF-Insight
                           │
             ┌─────────────┴─────────────┐
             │                           │
      Deterministic Core            MiMo-V2.5
             │                           │
        UPF parser                  Images
        Semantic model              SVGs
        74 rules                    Screenshots
        PST engine                  Documents
        Evidence                    Diagrams
        Findings                    Video/audio
             │                           │
             └─────────────┬─────────────┘
                           │
                      Engineer
```

**Deterministic core = truth.**

**MiMo = multimodal understanding, explanation, exploration, and generation.**

---

## 1. Non-authoritative role

### What MiMo can do

- Understand UPF files, SVG diagrams, screenshots, and documentation
- Explain validator findings in plain language
- Generate visual assets (diagrams, illustrations, documentation figures)
- Compare visual representations against semantic models
- Teach UPF concepts at multiple levels
- Review its own outputs for consistency
- Interpret EDA tool screenshots
- Reason over large project contexts (1M tokens)

### What MiMo must never do

- Validate UPF files (the deterministic engine does this)
- Produce validator findings
- Override, modify, or filter engine outputs
- Decide whether a design is "correct"
- Replace the rule engine, PST analyzer, or evidence boundary
- Serve as a runtime dependency for the workspace UI
- Make architectural decisions about the validator

---

## 2. MiMo-assisted workflows

| # | Workflow | Input | Value |
|---|---|---|---|
| 3.1 | Visual Semantic QA | UPF + SVG | Catch visualization regressions |
| 3.2 | Finding Explanation | Finding + UPF + screenshot | Engineer comprehension |
| 3.3 | Mutation Explanation | Valid + mutated + finding + diagram | Educational/debugging |
| 3.4 | UPF Teaching Assistant | Concept + diagram + rules | Onboarding |
| 3.5 | Release Review | Two releases | Change detection |
| 3.6 | UX QA | Finding + screenshot | UI improvement |
| 3.7 | Diagram Self-Critique | All diagrams | Consistency |
| 3.8 | EDA Screenshot Interpretation | EDA screenshot | Engineering interpretation |
| 3.9 | Video Walkthrough Review | Recorded walkthrough | Documentation |
| 3.10 | Audio Engineering Q&A | Voice + UPF + finding | Multimodal Q&A |

---

## 3. Experiments

### Experiment 1 — 10 SVG Visual Semantic Audit ✅ PASS

| Metric | Value |
|---|---|
| Confirmed issues | 4 |
| False issues | 0 |
| Missed issues | 0 |
| Diagrams requiring changes | 3 of 10 |

**Verdict:** MiMo catches real documentation drift without producing false issues.

---

### Experiment 2 — UPF + SVG Consistency Checking ✅ PASS

| Metric | Value |
|---|---|
| Total semantic facts | 38 |
| Correctly represented | 33 (86.8%) |
| Incorrect | 0 |
| Cross-diagram consistency | 8/8 PASS |

**Verdict:** SVGs faithfully represent UPF semantics. No semantic errors.

---

### Experiment 3 — 42 Mutation Visual Explanations ✅ PASS

| Metric | Value |
|---|---|
| HIGH fidelity | 42/42 (100%) |
| Incorrect | 0 |
| Hallucinated | 0 |

**Per-category breakdown:**

| Category | Score |
|---|---|
| Supply topology | 5/5 |
| Power switch | 8/8 |
| Level shifting | 4/4 |
| Isolation | 5/5 |
| Retention | 5/5 |
| Always-on | 2/2 |
| PST | 4/4 |
| Duplicate definitions | 3/3 |
| Supply connectivity | 2/2 |
| Domain relationships | 2/2 |
| Unsupported syntax | 2/2 |

**Verdict:** MiMo can faithfully explain WHY the deterministic validator produces each finding, without inventing or overriding the finding itself.

---

### Experiment 4 — Engineer UX Comparison ⏳ FRAMEWORK READY

**Input:** 10 findings × 2 conditions (A: existing UX, B: MiMo-assisted)
**Task:** Compare engineer comprehension across conditions
**Measure:** Time to understand, correctness, actionability, confidence

**Conditions:**

```
Condition A — Existing Ṛta UX:
  Rule code + severity + message + source line + inspector panel

Condition B — MiMo-assisted:
  Rule code + severity + message + source line +
  plain-language explanation + semantic relationship diagram + suggested fix
```

**Findings tested (deliberately weighted toward hard cases):**

| # | Rule | Category | Difficulty |
|---|---|---|---|
| 1 | UPF-010 | Reference | Medium |
| 2 | UPF-039 | PST | Hard |
| 3 | UPF-041 | Strategy | Hard |
| 4 | UPF-051 | Strategy | Medium |
| 5 | UPF-061 | Strategy | Medium |
| 6 | UPF-062 | Strategy | Medium |
| 7 | UPF-063 | Strategy | Hard |
| 8 | UPF-073 | Strategy | Medium |
| 9 | UPF-077 | Strategy | Easy |
| 10 | UPF-078 | Strategy | Hard |

**Metrics:**

| Metric | Scale |
|---|---|
| Finding understood correctly | binary (0/1) |
| Root cause identified | binary (0/1) |
| Time to understand | seconds |
| Time to root cause | seconds |
| Actionability | 1–5 Likert |
| Confidence | 1–5 Likert |
| Preference | A/B/neither |

**Expected outcome:** Condition B improves comprehension by 30–50%, largest improvement on hard findings (UPF-039, 041, 063, 078).

**Status:** Framework ready for human evaluation. Needs 1–3 engineers × 20 minutes each.

---

### Experiment 5 — Full-Project Multimodal Architecture Review

**Input:** Complete project corpus (code, docs, diagrams, tests, changelog)
**Task:** Identify where multimodal reasoning adds value
**Measure:** Quality of recommended workflows

---

## 4. Cumulative evidence

| Experiment | Question | Result |
|---|---|---|
| E1 | Can MiMo detect visual documentation drift? | ✅ PASS |
| E2 | Can MiMo map UPF semantics → visual representation? | ✅ PASS |
| E3 | Can MiMo explain deterministic semantic mutations? | ✅ PASS |
| E4 | Can MiMo improve engineer UX? | ⏳ framework ready |
| E5 | Where does multimodal reasoning provide measurable value? | ⏳ pending |

**Key insight across E1–E3:** MiMo produces **zero false issues** and **zero hallucinated rules** when grounded against the deterministic rule registry and UPF source.

---

## 5. Workflow selection (pending E4)

If E4 confirms UX improvement, the top 3 workflows to prototype:

| Priority | Workflow | Evidence base |
|---|---|---|
| 1 | Finding Explanation Assistant | E4 (UX improvement) |
| 2 | Mutation Explanation Library | E3 (42/42 HIGH fidelity) |
| 3 | Visual Semantic QA | E1+E2 (documentation drift + semantic mapping) |

If E4 does NOT confirm improvement, restrict MiMo to development-time tools only (E1–E3 are still valuable for internal QA).

---

## 6. Implementation sequencing

| Phase | Items | Duration |
|---|---|---|
| **Phase 0** — Experiment | Run 5 experiments, measure usefulness | 1 week |
| **Phase 1** — Select | Choose top 3 workflows based on experiment results | 1 day |
| **Phase 2** — Prototype | Build thin integration layer for selected workflows | 1 week |
| **Phase 3** — Validate | Test with real engineers, measure comprehension | 1 week |
| **Phase 4** — Decide | Product integration vs standalone tool vs abandon | 1 day |

**Decision rule:** Only proceed to Phase 2 if experiments show measurable value.

---

## 7. Design principles

1. **Deterministic engine is always authoritative.** MiMo explains, it never validates.
2. **MiMo is not a runtime dependency.** The workspace ships without any LLM API calls.
3. **Experiment before integrating.** Measure usefulness before building product features.
4. **Scientific separation.** MiMo Visual QA Score ≠ UPF Validation Score.
5. **Input, not just output.** MiMo understands images, it doesn't just generate them.
6. **Multimodal context, text reasoning.** MiMo receives images and produces structured text explanations.
7. **Honest boundaries.** MiMo cannot prove UPF correctness — it can only reason about visual and textual representations.
