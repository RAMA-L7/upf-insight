# Claude Code guidance for UPF-Insight

This file gives an AI assistant the working context it needs to operate in
this repository.

## Project

UPF-Insight is a deterministic, local-first, evidence-backed validator for
IEEE 1801 (UPF) power-intent files. It is the power-intent sibling of the
Ṛta / sdc-tools constraint validator. Its philosophy:

- **No LLMs in the analysis path.** The engine is deterministic.
- **Every finding traces to a line.** Rule codes (UPF-001…) carry provenance.
- **Honest support boundaries.** "No errors" ≠ "power proven correct".

## Repository map

```
upf_insight/
  preprocess/upf_preprocess.py   # Tcl/UPF command-record preprocessing
  model/
    power_model.py               # power-intent object graph
    builder.py                   # command stream -> model
  engine/
    engine.py                    # validate() orchestration
    rules/
      rules_registry.py          # canonical rule codes (UPF-001..084)
      checker.py                 # deterministic rule dispatch
      upf_rules.py               # rule handler implementations
      finding.py                 # shared Finding type (breaks import cycle)
    trust/support_boundary.py    # VALIDATED / PARTIAL / ... statuses
    pst/analyzer.py              # Power State Table analysis
  generate/generator.py          # skeleton scaffolder
  diff/differ.py                 # semantic model-level diff
  report/reporter.py             # text / JSON formatting
  cli/cli.py                     # upf-insight {check|model|pst|diff|generate|web}
  api/api_server.py              # stdlib-only local HTTP API
  workspace/webui/index.html     # vanilla-JS workspace
tests/                           # pytest suite (golden + mutation)
tests/examples/                  # known-good / known-bad UPF fixtures
docs/                            # product, upf, company, features docs
```

## Common tasks

- **Add a rule**: implement in `upf_rules.py`, register in `rules_registry.py`,
  add positive/negative tests in `tests/`.
- **Run tests**: `python -m pytest tests/ -q`
- **Smoke test CLI**: `upf-insight check tests/examples/example.soc.upf`
- **Edit the workspace**: the web UI is vanilla JS served by `api_server.py`;
  there is no build step.

## Conventions

- Python 3.10+, typed, `from __future__ import annotations`.
- Determinism: no hash-order dependence in rule output; sort where needed.
- Rules must never crash the whole run (checker catches handler exceptions).
- Package data (`*.upf`, `*.tcl`) is declared in `pyproject.toml`.

## Reference project

UPF-Insight mirrors the sdc-tools / Ṛta codebase at `D:\freebuff\sdc-tools-main`
(named `rta` inside). When porting a pattern (preprocess, checker, support
boundary, CLI contract), consult the sdc-tools original for the established
convention.
