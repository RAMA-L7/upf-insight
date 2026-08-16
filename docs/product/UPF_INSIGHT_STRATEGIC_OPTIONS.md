# UPF-Insight — Strategic Options

> **Document kind:** strategy / decision input · **Date:** 2026-08-16.
> **Status:** planning only — no commitment. The decision is made ONLY
> after UPF-Insight is independently validated. This document applies the
> Ṛta Risk Decision Framework conceptually (best / most likely / worst /
> cost of being wrong / survivability / cheapest experiment) without
> modifying it, and without assuming UPF-Insight must become part of Ṛta.

---

## 0. Evidence basis (from the audit)

- Engine: **verified working** — 65 rules, 94 tests green, deterministic,
  honest trust boundary, real CI gate.
- Maturity: **younger than Ṛta** — 94 vs 1,200+ tests; 65 vs 119 rules; one
  realistic fixture family; no git, no CI, no published distribution.
- Adoption: **zero external users** — never distributed, never validated.
- Differentiated strength: model-over-text power-intent analysis with
  voltage-aware level-shifter checks and an honest support boundary — a real
  gap in free tooling (commercial low-power checkers are licensed and
  tool-integrated).

---

## 1. The three options

### OPTION A — Independent UPF product

UPF-Insight stays its own product, hardened and validated on its own.

| Dimension | Assessment |
|---|---|
| User value | High if the validation loop (check → diff → gate → report) lands; power intent is a genuine, underserved block-level problem |
| Technical fit | Excellent — architecture is purpose-built for UPF |
| Differentiation | Good — no free deterministic UPF quality gate exists; Ṛta is SDC, different domain |
| Maintenance cost | Moderate — one more repo/suite/docs to maintain |
| Trust implications | Independent trust story; zero coupling to Ṛta's brand |
| Market potential | Real but unproven — must survive the same external-validation gauntlet Ṛta is in |
| Distribution | Must build its own: git, CI, PyPI, docs, GitHub Action |
| Engineering complexity | Low incremental (close P1/P2 gaps) |
| Risk | The dominant risk is *not technical* — it is adoption (same as Ṛta) |
| Evidence required | External engineers completing the 5-minute UPF workflow |

### OPTION B — UPF + Ṛta interoperability

Both products stay independent but interoperate at the workflow level
(e.g., a shared CI Action pattern, common report/evidence conventions,
cross-linked docs). No shared code.

| Dimension | Assessment |
|---|---|
| User value | Team adopting Ṛta for SDC can adopt UPF-Insight for power intent with one mental model |
| Technical fit | Good — same philosophy, same exit-code contract, same trust vocabulary |
| Differentiation | Strong — "constraint intelligence (SDC + power intent)" is a coherent story |
| Maintenance cost | Low — conventions shared, codebases separate |
| Trust implications | Each keeps its own honesty boundary; cross-claims must be exact |
| Market potential | Wider wedge (both constraint domains) |
| Distribution | Each ships independently; a shared "constraint quality" site could link both |
| Engineering complexity | Low — documentation/CI pattern sharing only |
| Risk | Low — reversible, no code coupling |
| Evidence required | Both products individually validated first; then a shared workflow demo |

### OPTION C — Selected UPF capabilities eventually integrated into Ṛta

Fold chosen UPF analyses into Ṛta (a new "power intent" mode or module).

| Dimension | Assessment |
|---|---|
| User value | One tool for both constraint domains |
| Technical fit | Poor-ish today — Ṛta's engine is SDC-line-scoped; UPF needs model-over-text; merging would require a second analysis core under one CLI |
| Differentiation | Diluted — "SDC validator that also does some UPF" is weaker than two sharp products |
| Maintenance cost | Highest — one frozen engine plus a second analysis architecture |
| Trust implications | Risk of scope blur ("constraint intelligence" overclaiming both domains at once) |
| Market potential | Marginal gain over A or B for a small team |
| Distribution | Single package — but at the cost of the clean SDC story |
| Engineering complexity | High — new analysis core, new rules, new trust model under Ṛta's frozen-engine discipline |
| Risk | Medium-high — conflicts with Ṛta's frozen-engine and block-level boundary discipline |
| Evidence required | Strong demonstrated demand for combined SDC+UPF in one tool, from real users |

---

## 2. Risk decision framework applied (conceptual)

### Best case (all options)
A team adopts the UPF gate in CI, catches a real power-intent regression
before implementation, and the workflow becomes repeatable — exactly the
Plan-A loop Ṛta is trying to prove, in a second domain.

### Most likely case
- **A:** UPF-Insight passes external validation with a small cohort, gains
  a handful of users, becomes a credible sibling product. (ASSUMPTION —
  no users yet.)
- **B:** Both products validate; interoperability is a modest doc/CI effort
  with clear team value.
- **C:** Integration consumes months on architecture work inside Ṛta's
  frozen-engine discipline, with no evidence any user wants the combined
  tool. (ASSUMPTION — no demand signal.)

### Worst case
- **A:** UPF-Insight suffers the same adoption failure Ṛta fears — time
  spent, no users. Survivable: it is a small, honest, MIT codebase; worst
  case it remains an internal evidence asset.
- **B:** Nothing lost — both products stand alone; the shared conventions
  are cheap and useful regardless.
- **C:** The merge destabilizes Ṛta's clean SDC story and consumes the
  frozen-engine trust; worst case of the three.

### Cost of being wrong
| Option | Engineering time | Complexity | Trust risk |
|---|---|---|---|
| A | Low (close P1/P2 gaps) | Low | Low |
| B | Low | Low | Low |
| C | High | High | Medium-high (scope blur on a frozen, trust-first product) |

### Can we survive the worst case?
Yes for A and B (small, reversible, no coupling). C's worst case is the
hardest to walk back (engine discipline, brand scope).

### Cheapest valid experiment
**Do NOT build anything more yet.** The cheapest experiment is the same one
Ṛta is running: put the 5-minute UPF workflow in front of 3–5 engineers and
measure whether they finish, understand the level-shifter finding, and would
put the gate in CI. That evidence decides A vs B vs C — no architecture work
required first.

---

## 3. Recommendation (evidence-based, provisional)

1. **Close the P1 process gaps first** (git init + CI Action + docs
   reconciliation + wheel check) — these are required for *any* option and
   are cheap.
2. **Run external validation of UPF-Insight independently** (3–5 engineers,
   the 5-minute workflow, raw-result capture) — mirroring Ṛta's cohort, in
   the same discipline: no product changes mid-cohort.
3. **Do NOT integrate into Ṛta now (Option C).** Nothing in the evidence
   justifies it: the two domains are architecturally different, the merge
   is the highest-cost/highest-risk option, and no user has asked for it.
4. **Default to Option A, with Option B as the natural next step** — keep
   UPF-Insight independent; share *conventions* (exit codes, trust
   vocabulary, CI Action pattern, report formats) with Ṛta only as
   documented patterns, never as shared code. If both products validate,
   interoperability becomes a doc/CI-layer effort with real team value.
5. **Revisit only on evidence:** if real users across both domains
   explicitly demand one combined tool, *then* evaluate a C-style merge as
   a separate, gated project — not before.

## 4. What should NOT be built now

- No merging of codebases, no shared engine, no "Ṛta power mode".
- No AI assistance, no SaaS, no enterprise governance (same charter
  discipline as Ṛta).
- No feature-count chasing — the goal is the smallest credible UPF product
  that can be independently validated, not "as capable as Ṛta".

## 5. Decision gates (consistent with the risk framework)

| Gate | Trigger | Action |
|---|---|---|
| Continue A | UPF cohort completes; engineers understand findings; ≥1 would use the gate | Harden + distribute UPF-Insight |
| Adopt B | Both products validated; team asks for one workflow story | Shared CI/doc conventions (no shared code) |
| Consider C | ≥3 teams using both products request a combined tool | Separate gated project, with a written RFC |
| Stop A | Cohort shows the finding/loop is not understood or not wanted | Record evidence; reassess; do not build more |

---

*Strategic input only. No repository was modified by this document beyond
the audit's own deliverables in `upf-insight/docs/product/`. The Ṛta
repository is untouched.*
