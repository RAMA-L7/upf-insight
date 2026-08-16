# UPF-Insight — Repository Map

> **Document kind:** company/repository navigation.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## Layout

```
upf-insight/
├── README.md                    # entry point, quick start, CLI, docs index
├── CHANGELOG.md                 # versioned changes
├── CONTRIBUTING.md              # how to contribute
├── CLAUDE.md                    # AI-assistant working context
├── LICENSE                      # MIT
├── pyproject.toml               # packaging, entry points, pytest config
├── upf_insight/                 # the Python package
│   ├── preprocess/upf_preprocess.py
│   ├── model/{power_model.py, builder.py}
│   ├── engine/
│   │   ├── engine.py
│   │   ├── rules/{rules_registry.py, finding.py, checker.py, upf_rules.py}
│   │   ├── trust/support_boundary.py
│   │   └── pst/analyzer.py
│   ├── generate/generator.py
│   ├── diff/differ.py
│   ├── report/reporter.py
│   ├── cli/cli.py
│   ├── api/api_server.py
│   └── workspace/webui/index.html
├── docs/
│   ├── upf/          # product/taxonomy/trust/rules/fundamentals/roadmap/arch/brand/evidence
│   ├── product/      # specification, charter
│   ├── company/      # glossary, engineering checklist, repository map, operating system
│   └── features/     # per-module feature docs (README-01..10)
├── tests/
│   ├── test_engine.py           # core 8-test suite
│   ├── examples/                # golden fixtures (example.soc.upf, example.broken.upf)
│   └── fixtures/                # mutation/negative variants (planned)
└── evidence/
    ├── README.md                # evidence ledger
    └── manifest/                # manifest JSON (planned)
```

## How to navigate

| I want to… | Go to |
|---|---|
| Understand the product | `docs/product/PRODUCT_CHARTER.md`, `docs/product/PRODUCT_SPECIFICATION.md` |
| See the rule catalog | `docs/upf/RULES_REGISTRY.md` |
| Learn UPF concepts | `docs/upf/UPF_FUNDAMENTALS.md` |
| Understand trust | `docs/upf/TRUST_MODEL.md` |
| Understand the architecture | `docs/upf/REPOSITORY_ARCHITECTURE.md` |
| Add a rule | `docs/company/ENGINEERING_CHECKLIST.md` |
| Run tests | `tests/`, `docs/upf/BENCHMARK_EVIDENCE_MAP.md` |

## Naming conventions

- Rules: `UPF-NNN` (layers: 001–006 syntax, 010–016 reference, 020–025
  supply/domain, 030–036 PST, 040–073 strategy, 080–084 design).
- Package: `upf_insight`.
- CLI: `upf-insight`, alias `upfi`.
- Docs mirror the sdc-tools / Ṛta layout for family consistency.