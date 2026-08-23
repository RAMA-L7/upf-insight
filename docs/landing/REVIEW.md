# Landing Page Review — Senior EDA Product Designer

> **Date:** 2026-08-18 · **File:** `docs/landing/index.html`
> **Reviewer perspective:** EDA product design, not generic SaaS

---

## Executive summary

The page has strong technical content and real evidence. The core problem is **generic SaaS visual patterns that undermine EDA credibility**. The metrics and adversarial sections are the strongest parts. The capabilities section and hero need the most work.

| Priority | Count | Theme |
|---|---|---|
| P0 | 2 | Technically misleading claims |
| P1 | 7 | Product/UX problems that hurt EDA credibility |
| P2 | 5 | Polish and consistency |

---

## P0 — Technically misleading

### P0-1. Hero claims "trust" contradicts the trust model

**Section:** Hero (line: `Power-intent validation you can trust`)

The README explicitly states:
- "READY ≠ power signoff"
- "Coverage ≠ correctness"
- "CI pass ≠ low-power closure"

The trust model says Ṛta validates what it can prove from the UPF alone, skips what needs netlist context, and never claims completeness. Saying "you can trust" implies completeness that the tool deliberately does not claim.

**Fix:** Replace with "Evidence-backed power-intent validation" or "Power-intent validation you can reason about" — emphasizing that the tool gives you evidence to reason with, not a trust seal.

### P0-2. GitHub link is a placeholder

**Section:** CTA (line: `<a href="https://github.com" class="btn btn-primary">View on GitHub</a>`)

This points to `github.com` root, not the actual repo. An EDA engineer clicking this will land on the GitHub homepage and immediately lose confidence.

**Fix:** Either link to the actual repo URL or remove the link until the repo is public. A broken CTA is worse than no CTA.

---

## P1 — Important product/UX problems

### P1-1. Emoji icons in capabilities are generic SaaS, not EDA

**Section:** Capabilities (⚡ 🔋 ⏻ 🛡 ↔ 💾 📊 🔗)

Every SaaS landing page uses emoji icons. An EDA product should not. These icons signal "marketing page" to an engineer who builds chips. The existing project uses monochrome schematic-style SVGs in the workspace — that visual language is far more credible.

**Fix:** Replace with either:
- Small inline SVG schematic icons (supply rail, domain box, switch diamond, isolation barrier, etc.)
- Or remove icons entirely and let the text carry the section. The content is strong enough.

### P1-2. Hero radial gradient glow is generic SaaS

**Section:** Hero (`hero::before` with `radial-gradient(circle, rgba(110,168,254,0.08)...)`)

The soft blue glow behind the hero text is the single most recognizable SaaS landing page pattern. It signals "we raised a Series A" not "we validate power intent."

**Fix:** Remove the glow. The dark background with clean typography is enough. If you want visual interest, use a subtle grid pattern or a faded version of the supply topology SVG as a background element — something technically grounded.

### P1-3. Section ordering is backwards

**Current order:** Hero → Problem → Visualization → Capabilities → Evidence → Findings → Architecture → Adversarial → CLI → Docs → CTA

The reader sees the supply topology diagram (section 3) before understanding what the tool does (section 4). This is backwards for an EDA audience who needs to understand the capability before appreciating the visualization.

**Fix:** Reorder to:
1. Hero
2. Problem
3. **Capabilities** (what the tool does)
4. **Architecture** (how it works)
5. **Evidence** (proof it works)
6. **Visualization** (show the output)
7. **Findings** (show the UX)
8. **Adversarial** (stress test)
9. CLI
10. Docs
11. CTA
12. Footer

This follows the EDA engineer's mental model: problem → solution → proof → output → how to use.

### P1-4. "100% deterministic" is a trivially true claim

**Section:** Evidence metrics (`100% deterministic · same input → same output · always`)

Every parser, every compiler, every rule engine is deterministic. This claim doesn't differentiate Ṛta from anything. It wastes a metric card slot that could hold a more meaningful number.

**Fix:** Replace with something actually differentiating:
- "0 cloud dependencies" (offline-first)
- "0 LLM calls in analysis path" (deterministic, not probabilistic)
- "0 data leaves your machine" (privacy)
- Or remove the card entirely — the other 5 metrics are stronger.

### P1-5. No Python version requirement

**Section:** CTA (`pip install upf-insight`)

The README says Python 3.10+ is required. An engineer who tries `pip install` on Python 3.8 will get a confusing error. The CTA should set expectations.

**Fix:** Add `# Python 3.10+` above the install command, or change to:
```
$ pip install upf-insight    # Python 3.10+
```

### P1-6. No mention of the `upfi` alias

**Section:** CLI

The README says "`upfi` remains as a fully supported alias — every command above works with either name." This is important for existing users who may know the tool by either name. The landing page only shows `upf-insight`.

**Fix:** Add a note in the CLI section: "Both `upf-insight` and `upfi` work interchangeably."

### P1-7. No Test Drive workflow in CTA

**Section:** CTA

The 5-minute Test Drive is the strongest onboarding artifact in the project — it walks through validate → regress → diff → gate → report on a realistic CPU subsystem. The CTA only offers "View on GitHub" and "CLI Reference." The Test Drive is a much stronger conversion path for an EDA engineer.

**Fix:** Add a third CTA button: "5-Minute Test Drive →" linking to the Test Drive docs.

---

## P2 — Polish improvements

### P2-1. Architecture section is buried

**Section:** Architecture (section 7 of 12)

The pipeline architecture is an important differentiator — it shows the deterministic flow from UPF through parser, semantic model, rule engine, to findings. But it's buried after the Findings section. It should be earlier, right after Capabilities, to establish the technical credibility before showing output examples.

**Fix:** Move to position 4 (after Capabilities, before Evidence).

### P2-2. Footer links are all placeholder `#` links

**Section:** Footer

All four footer links (Documentation, GitHub, CLI Reference, Trust Model) point to `#`. This is a functional landing page issue — these should link to actual docs or be removed.

**Fix:** Link to actual doc paths or remove until the pages exist.

### P2-3. Adversarial grid may break on small screens

**Section:** Adversarial (`grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))`)

On a 320px screen with 24px padding on each side, the available width is 272px. With `minmax(160px, 1fr)`, this allows only 1 column at 160px, leaving 112px of dead space. The 11 cards will stack into a very long vertical list.

**Fix:** On mobile, consider a 2-column layout with smaller cards, or collapse into a summary row showing just "42/42 detected across 11 categories" with an expandable detail.

### P2-4. Finding diagrams use mixed alignment

**Section:** Findings (UPF-062 diagram)

The UPF-062 diagram has inconsistent whitespace — the "Declared/Required" lines are indented differently from the arrow line. This is a minor visual inconsistency but matters for an EDA audience that notices precision.

**Fix:** Align all lines to the same left margin in the monospace block.

### P2-5. No `prefers-color-scheme: light` consideration

**Section:** Global styles

The page is dark-only (`color-scheme: dark`). While dark-first is correct for EDA, some engineers view documentation in light mode. The page should at minimum not break in light mode — currently the `color-scheme: dark` meta tag forces dark mode in supported browsers, which is fine, but there's no fallback for browsers that don't support it.

**Fix:** This is acceptable as-is for a dark-first EDA product. No change needed unless light mode support is desired.

---

## Evaluation against 10 criteria

| # | Criterion | Score | Notes |
|---|---|---|---|
| 1 | EDA credibility | **B+** | Strong content, but emoji icons and SaaS glow undermine it |
| 2 | UPF technical accuracy | **A-** | All rule codes, descriptions, and examples are accurate. P0-1 trust claim is the only issue |
| 3 | Information hierarchy | **C+** | Backwards ordering (visualization before capabilities). Architecture buried |
| 4 | Visual clarity | **B+** | Clean layout, good typography, finding demos are strong |
| 5 | Trustworthiness of claims | **B** | Metrics are real and verifiable. "100% deterministic" is trivial. "Trust" claim contradicts trust model |
| 6 | Differentiation from AI SaaS | **B** | "No LLMs" and adversarial section are strong. Emoji icons and glow are generic |
| 7 | Developer usability | **B+** | Real CLI commands, JSON output, CI gating shown. Missing Python version and upfi alias |
| 8 | Conversion clarity | **C+** | Placeholder GitHub link. No Test Drive CTA. Install command lacks version note |
| 9 | Mobile layout | **B** | Responsive breakpoints present. Adversarial grid may break. Finding diagrams handled with overflow |
| 10 | Visualization grammar consistency | **A** | SVG uses project's established visual language. Finding format matches workspace |

---

## Prioritized redesign recommendation

### Round 1 — Fix P0 (must fix before any publishing)

1. Replace "trust" claim with evidence-backed language
2. Fix or remove placeholder GitHub link

### Round 2 — Fix P1 (significantly improves EDA credibility)

3. Reorder sections: Capabilities → Architecture → Evidence → Visualization → Findings
4. Replace emoji icons with schematic SVGs or remove entirely
5. Remove hero radial gradient glow
6. Replace "100% deterministic" with a differentiating claim
7. Add Python 3.10+ note to install command
8. Add `upfi` alias mention to CLI section
9. Add Test Drive CTA button

### Round 3 — Fix P2 (polish)

10. Move Architecture section earlier
11. Fix footer links or remove placeholders
12. Improve adversarial grid mobile layout
13. Align finding diagram whitespace

---

## What's already strong (don't change)

- **Finding examples** (UPF-062, UPF-039) — these are the best part of the page. The semantic relationship diagram + suggested fix format is exactly what an EDA engineer wants to see.
- **Adversarial grid** — showing 42/42 across 11 categories with per-category breakdowns is unique and credible.
- **Metrics section** — real numbers from the test suite, not marketing claims.
- **CLI section** — real commands, real flags, real output formats.
- **SVG visualization** — uses the project's established visual language correctly.
- **"No LLMs in the analysis path"** — this is the strongest differentiator.
- **"Not marketing claims — engineering evidence"** — this meta-statement is exactly right for an EDA audience.
