# UPF-Insight — Operating System

> **Document kind:** company/operating principles for contributors.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## 1. Decision principles

1. **Determinism first.** If two runs differ, it is a bug.
2. **Evidence over assertion.** Every finding cites file:line; every claim has
   a rerunnable test.
3. **Honesty over optimism.** "No errors ≠ power proven correct" is said
   loudly, in-product and in docs.
4. **Local-first.** Nothing leaves the machine. No telemetry.
5. **No LLM in the engine.** AI assistance is fine for authorship; the shipped
   engine is pure code.
6. **Open core.** Community MIT forever; enterprise layers additive.
7. **Stdlib-first.** Minimize third-party runtime dependencies.

## 2. Working agreements

- Small, focused commits; one logical change each.
- New rule ⇒ registry + handler + positive test + negative test, or it isn't
  done.
- Update docs in the same change as the code they describe.
- `CHANGELOG.md` updated for user-visible changes.
- Ask before adding a runtime dependency.
- Never commit secrets or internal design data.

## 3. Quality gates (as they exist today)

- `python -m pytest tests/ -q` must be green.
- CLI smoke commands must behave as documented
  (`docs/upf/BENCHMARK_EVIDENCE_MAP.md`).

## 4. Reference project

UPF-Insight is the sibling of **Ṛta / sdc-tools**
(`D:\freebuff\sdc-tools-main`, package `rta`). When in doubt about a
convention (preprocess, checker, support boundary, CLI contract, docs
taxonomy), consult the sdc-tools original.

## 5. Escalation / blocked work

- If a rule cannot be validated statically, lower its support to
  `PARTIALLY_VALIDATED` and document why — never silently over-claim.
- If a UPF command is outside the model grammar, keep it in
  `unsupported_commands` and let the boundary disclose it.

## 6. Releasing (later versions)

- Bump version in `upf_insight/__init__.py` and `pyproject.toml`.
- Update `CHANGELOG.md`.
- Tag `vX.Y.Z`; update the README evidence map.