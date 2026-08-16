# UPF-Insight — Engineering Checklist

> **Document kind:** company/engineering process.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## Adding a rule (mandatory path)

- [ ] Implement handler in `upf_insight/engine/rules/upf_rules.py` with
      `@_register("UPF-NNN")`.
- [ ] Add the registry entry in `rules_registry.py` (code, severity, layer,
      title, description).
- [ ] Update `docs/upf/RULES_REGISTRY.md` implementation-status table.
- [ ] Add at least one **positive** test (golden input must NOT fire).
- [ ] Add at least one **negative** test (defect input must fire exactly that
      rule with the right line evidence).
- [ ] Run `python -m pytest tests/ -q` — all pass.
- [ ] Smoke the CLI on `tests/examples/example.broken.upf`.

## Adding a command to the model builder

- [ ] Add parsing in `model/builder.py::_dispatch`.
- [ ] Add a dataclass in `model/power_model.py` if a new entity.
- [ ] Wire `PowerIntentModel.to_dict()` if the entity should appear in JSON.
- [ ] If out of the v1 grammar, leave it in `unsupported_commands` and verify
      the support boundary reports it.

## Rule style (determinism + honesty)

- [ ] Pure function: `handler(model) -> list[Finding]`.
- [ ] No randomness, no network, no LLM.
- [ ] Sort output where iteration order could leak (dicts).
- [ ] Never `raise` to the caller — the checker catches handler exceptions.
- [ ] Always set `support`; if reduced-strength, use `PARTIALLY_VALIDATED`.

## CLI contract

- [ ] New commands keep exit codes: 0 pass / 1 issues / 2 bad invocation /
      3 engine failure.
- [ ] `--format json` and `--format text` both work.
- [ ] Aliases `upf-insight` and `upfi` both installed (`pyproject.toml`).

## Docs

- [ ] Feature doc in `docs/features/` (mirror `README-0N-*.md` numbering).
- [ ] Update `docs/upf/PRODUCT_TAXONOMY.md` if a product module changed.
- [ ] Update `docs/upf/BENCHMARK_EVIDENCE_MAP.md` for new tests.
- [ ] Update `CHANGELOG.md` for user-visible changes.

## Test hygiene

- [ ] Fixtures live in `tests/examples/` (known-good) and `tests/fixtures/`
      (mutation variants).
- [ ] No fixture depends on another fixture's file path by accident.
- [ ] Assertions check rule codes, not just "not clean".

## Release checklist (v0.2+, when releasing)

- [ ] `python -m pytest tests/ -q` green.
- [ ] `upf-insight --version` matches `upf_insight/__init__.py` and
      `pyproject.toml`.
- [ ] `pip install .` from a clean venv works.
- [ ] `CHANGELOG.md` current.