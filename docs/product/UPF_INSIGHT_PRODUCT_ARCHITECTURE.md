# UPF-Insight — Product Architecture

> **Status:** applied. This document defines the product information
> architecture and workspace workflow contract for UPF-Insight, using Ṛta's
> engineering/product discipline as the *quality reference* — never as a
> template to copy literally. The UPF domain has its own terminology,
> capability set and workflows; this architecture is UPF-specific.
>
> Every capability listed here maps to **real, verified backend support**
> (see `UPF_INSIGHT_FUNCTIONAL_BASELINE.md`). Nothing is listed that is
> not implemented; unsupported surfaces are explicitly marked
> **NOT IMPLEMENTED** rather than becoming fake UI.

---

## 1. Product model

UPF-Insight is a **deterministic, local, offline analysis of IEEE 1801
power intent**. One validation run produces one evidence object:

```
UPF (IEEE 1801) ──► preprocess ──► model ──► check ──► support boundary
                                                ├──► PST analysis
                                                ├──► readiness (5 dims)
                                                └──► coverage
        (optional netlist snapshot) ──► design-aware rules (UPF-080…084)
```

The analysis object is the single source of truth for every result surface.
Tools never invent numbers; they render engine evidence.

## 2. Feature-first entry (Tool Home)

The first screen of the workspace is a **Tool Home**, not a results
dashboard. It answers in seconds:

- **What is UPF-Insight?** — a deterministic power-intent analysis tool.
- **What can I do with it?** — a grouped capability catalog.
- **Which tool do I need?** — one card per capability.

The catalog groups capabilities the way a power-integrity engineer thinks:

| Group | Capabilities (all real, all visible) |
|---|---|
| **CORE** | UPF Validation · UPF Generator |
| **ANALYZE** | Power State Intelligence · Supply Network · Strategies · Design Context · Coverage · Readiness |
| **ADVANCED** | UPF Diff · CI Gate · Test Drive |
| **OUTPUT & KNOWLEDGE** | Reports · Rules · Trust · Documentation |

**No "More Tools".** No hidden primary capabilities. Every card exposes:
What it is · What input it needs · What Ṛta/UPF-Insight does · What you get ·
What you can do next.

## 3. Navigation architecture

Two groups, kept intentionally small:

- **WORKSPACE** (always visible): Home · New Analysis · Validation ·
  Generator · UPF Diff · CI Gate · Reports · Test Drive · Rules · Trust ·
  Documentation.
- **RESULTS** (appears after an analysis exists): Summary · Supply Network ·
  Power States · Strategies · Design · Coverage · Health · Support · Export.

Each item has a reason to exist. The command bar provides search, session
status, and export; it does not duplicate catalog entry points.

## 4. Each feature owns its input surface

There is no "upload once globally, then figure out what to do." Every tool
asks for its own input, at the feature:

| Tool | Input it asks for |
|---|---|
| Validation / New Analysis | UPF (required) + design JSON (optional) |
| Generator | domain / switch / isolation / LS / retention / PST params |
| UPF Diff | Version A UPF + Version B UPF |
| CI Gate | candidate UPF + policy (+ optional baseline JSON) |
| Reports | UPF (+ optional design JSON) + format |
| Test Drive | a built-in scenario (clean / buggy / design-aware / regression) |

Standalone use is the default. Sessions are in-memory per tab and purely
contextual — they never block a standalone workflow.

## 5. Result architecture

The current tool owns the **primary result**; related results are labeled
**next actions**, not a competing dashboard.

- Validation result → Findings (primary) → Coverage · Health · Support · Diff · Gate
- Test Drive regression → findings summary (primary) → Findings · Diff · Gate · Reports
- CI Gate result → PASS/FAIL + reasons (primary) → Reports · Validation
- Diff result → change table (primary) → Validate A/B · Gate on B

Progressive disclosure: dense tables (PST matrix, supply network, findings)
are fully rendered but scannable; rule detail and source excerpts open in
the inspector on demand.

## 6. Standalone workflows

```
Home → UPF Diff → V1 + V2 → Compare → changes → Validate B / Gate on B
Home → CI Gate → candidate UPF → Run Gate → PASS/FAIL + reasons → Reports
Home → Reports → UPF → Generate → HTML/JSON report → download
Home → Test Drive → regression scenario → summary → Findings / Diff / Gate
```

## 7. Session model (optional, never required)

Sessions are in-memory for the current browser tab. A standalone user never
needs them; a user exploring results sees the RESULTS group appear after the
first analysis. Restoring a session from a previous tab requires re-running
the analysis (honest, documented behavior).

## 8. Trust presentation

Frozen disclosures, always visible on results and in the Trust page:

- **READY ≠ signoff** — a power-intent review, not a power/IR signoff.
- **Coverage ≠ correctness** — coverage reports what the intent touches.
- **CI PASS ≠ power-intent signoff** — the gate reports policy pass, not closure.
- **Deterministic engine** — no LLM, no model inference, offline.
- **Engine failure never becomes PASS** — exit 3, never a passing result.
- **Unsupported constructs are reported** — `TCL_EXECUTION_REQUIRED` /
  `UNSUPPORTED`, never silent.

## 9. Error / empty states

Every tool has: empty state (what to do next), missing-input state (toast +
why), invalid-input state (specific message), backend-failure state
(typed error block), and a real-result state. No fake success, no stale
results from another tool/session.

## 10. Beginner / expert path

One application, progressive disclosure. Beginner: Tool Home → card explains
"What/Input/Does/Get/Next" → press the primary action. Expert: command-bar
search, keyboard `/` focus, direct hash routes, JSON export, CLI equivalents
shown where they exist.

## 11. Removed / rejected concepts

- **"More Tools"** — removed; all primary capabilities are visible.
- **Global upload** — rejected; inputs belong to the feature.
- **Quick Actions menu** — retained only for session/export conveniences,
  never as a second catalog.
- **Feedback** — **NOT IMPLEMENTED**; no fake submission surface.

## 12. Relationship to the functional baseline

This architecture is the *how*; `UPF_INSIGHT_FUNCTIONAL_BASELINE.md` is the
*what*. The engine, rule semantics, exit codes, and output contract are
frozen and unchanged by this document.
