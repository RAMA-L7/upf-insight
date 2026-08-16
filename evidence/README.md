# Evidence

Every test, benchmark, and claim in UPF-Insight is backed by a rerunnable
runner. See [docs/upf/BENCHMARK_EVIDENCE_MAP.md](../docs/upf/BENCHMARK_EVIDENCE_MAP.md)
for the full mapping.

## Current evidence

- **Core engine suite** — `tests/test_engine.py` (31 tests)
- **Flow/coverage/generator/API suites** — `tests/test_flow_coverage.py`
  (26) · `tests/test_generator.py` (12) · `tests/test_api_security.py` (7)
- **CPU-subsystem fixture suite** — `tests/test_cpu_subsys_fixture.py`
  (18) — realistic V1/V2 Test Drive regression tests
- **Golden fixtures** — `tests/examples/example.soc.upf` (known-good),
  `tests/examples/example.broken.upf` (known-bad),
  `tests/examples/cpu_subsys/` (V1 known-good / V2 regressed / design
  context)
- **CLI contract smoke** — documented commands in the evidence map
- **Live count** — `python -m pytest tests/ -q` → 114 passed (2026-08-16; +5 diff-semantics, +13 web-API, +2 design-aware normalization)

## Run it

```bash
python -m pytest tests/ -q
```

## Principles

- No marketing number exists without a runner behind it.
- A new rule without a positive and a negative test is not shipped.
- The evidence map is updated in the same change as the tests it documents.

## Planned

- Mutation evidence per implemented rule (target 100+ tests by v1.0).
- Conformance corpus (parse open-source IEEE 1801 examples).
- `evidence/manifest/` JSON — single source of truth for the public
  test/rule/suite counts, mirroring sdc-tools.