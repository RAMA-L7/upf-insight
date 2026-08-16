# Contributing

Thanks for your interest in UPF-Insight. This project values deterministic,
evidence-backed, local-first engineering. Please read the project docs
before contributing, especially:

- [Engineering checklist](docs/company/ENGINEERING_CHECKLIST.md)
- [Trust model](docs/upf/TRUST_MODEL.md)
- [Glossary](docs/company/GLOSSARY.md)

## Ground rules

- **No LLMs in the analysis path.** The engine is deterministic; a rule must
  always produce the same result for the same input.
- **Every finding traces to evidence.** No rule fires without a file:line
  provenance (and, where relevant, a second line for dual-line interactions).
- **Clean is "no rule fired", never "power proven correct."** Support
  boundary status must be reported on every run.
- **No EDA tool required.** Analysis must run without Synopsys/Cadence/
  Siemens tools.
- **Local-first.** Analysis runs locally; nothing leaves the machine.
- **Stdlib-first.** Prefer the Python standard library. Third-party runtime
  dependencies are a heavy decision (pyyaml is accepted for rules config).

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Running tests

```bash
python -m pytest tests/ -q
```

Tests live in `tests/`. Golden fixtures (known-good/known-bad UPF) live in
`tests/examples/`. A contribution that adds a rule **must** add:
1. A rule implementation in `upf_insight/engine/rules/upf_rules.py`.
2. A registry entry in `upf_insight/engine/rules/rules_registry.py`.
3. Positive and negative test cases in `tests/`.

## Committing

- Keep commits small and focused; match the existing style.
- Never commit secrets, credentials, or internal design data.
- Update `CHANGELOG.md` for user-visible changes.
- If you add a module, add it to the package listing in `pyproject.toml`
  (`[tool.setuptools.packages.find]` already uses `upf_insight*`, so only
  new top-level packages need attention).

## Code style

- Python 3.10+, typed signatures, `from __future__ import annotations`.
- Docstrings on every module and public function.
- No emojis, no decorative comments. Explanations belong in docstrings.

## Reporting issues

- Bugs: include the UPF snippet (minimized), the command, and expected vs
  actual output.
- Rule requests: include the IEEE 1801 clause you believe is violated, an
  example, and the expected rule code family.

## Security

Security issues: open a private report — do not post exploit details
publicly.