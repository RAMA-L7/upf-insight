# UPF-Insight — Product Charter

> **Document kind:** product charter — why the product exists and what it will
> and will not do.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## 1. Mission

Move power-intent verification **left**. UPF-Insight is the deterministic
quality layer that runs on UPF (IEEE 1801) files *before* power-aware
implementation — catching unsafe domain crossings, incoherent power states,
missing isolation, and broken retention before they become expensive floorplan
or signoff problems.

## 2. Problem

Power intent is a *system*, but it is authored as a list of commands. Each
domain, supply, state and strategy can look valid in isolation while the
system as a whole is incomplete, contradictory, or unsafe. Finding these
defects late — at power-aware implementation, IR/signoff, or silicon — is
orders of magnitude more expensive than finding them early.

Commercial low-power checkers solve this but are licensed, tool-integrated,
and not scriptable as a free CI gate. Ad-hoc grep checks miss cross-object
semantics.

## 3. Solution

A deterministic, local-first, open-source validator that:

- Builds a **power-intent model** from UPF commands.
- Runs **layered rules** (syntax → references → supply/domain → PST →
  strategies) with per-finding evidence.
- Analyzes the **Power State Table** for consistency.
- Diffs **semantically** across versions.
- Generates **skeleton** power intent.
- Discloses an honest **support boundary** on every run.

## 4. Who it's for

- **PD / low-power engineers** authoring and reviewing UPF.
- **Verification engineers** building power-aware verification flows.
- **Methodology / CI teams** gating power-intent quality.
- **IP providers** validating reusable power intent.

## 5. What we will do

- Deterministic static validation (layers 1–5) and PST analysis — v1.
- Netlist-aware design checking (layer 6) — v2.
- Readiness verdicts, baseline diff + gate policies — v0.3+.
- Custom YAML rulesets, JUnit/HTML reports — v0.2.
- Conformance corpus + 100+ evidence tests — v1.

## 6. What we will NOT do

- Power/IR analysis or STA (out of scope by design).
- Formal equivalence (out of scope).
- "AI-powered" analysis in the engine (no LLM in the analysis path).
- Cloud-only anything (local-first always).
- Any degradation of the open core (open-core: enterprise additive only).

## 7. Success measures

- Rule fires map to real power-intent defects, with provenance.
- Clean run on golden fixtures; broken fixtures fire exactly the intended
  rules.
- Deterministic output across machines (same input → same result).
- Zero EDA-tool dependency; runs on Python 3.10+ with stdlib + pyyaml.

## 8. Values

Deterministic · Evidence-backed · Local-first · Reproducible · Honest.