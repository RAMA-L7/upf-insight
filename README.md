<div align="center">

# UPF-Insight

**Power-Intent Intelligence for Digital Design**

*Bring order to power intent before power-aware implementation.*

Deterministic · Evidence-backed · Local-first · Reproducible

</div>

---

## 🆕 What's New

### v0.2.0 (latest)

**Flat + Hierarchical power-intent - now first-class in both Generator and
Validation.**

- **Canonical domain-relation model** - one model powers the generator,
  validator, CLI, API, reports and UI. Domain types are evidence-based:
  SWITCHABLE needs switch evidence, ALWAYS-ON needs an explicit declaration,
  otherwise `UNKNOWN` (never inferred from names).
- **Power Domain Relation Matrix** - cross-domain interactions only
  (ISO / LS / ISO+LS / RET / SW / CTRL), each with provenance; clicking a
  cell opens the evidence. Sharing a supply is a separate **Supply Network**
  view and never a matrix cell.
- **Hierarchical generator + validation** - `top.upf` + child files with
  per-child domain ownership, `load_upf -scope`/`-supply` composition, and a
  full round-trip: generated UPF validates back to the same architecture,
  domains, supplies, hierarchy, relations and provenance.
- **New CLI** - `upf-insight relations FILE...`, `generate --architecture
  hierarchical --domain-type --domain-power --switch --relation`, and
  `upf-insight whats-new` (offline release notes from the terminal).
- **New rules** - UPF-099 (supply-map side undefined) and UPF-100 (loaded
  UPF file missing).

Full details in [CHANGELOG.md](CHANGELOG.md) or run `upf-insight whats-new`.

## Why UPF-Insight

Before power-aware implementation (synthesis, place-and-route, power/IR
analysis, low-power verification), power-intent problems are expensive to
find. Domains, supplies, power states, switches, isolation, level shifters and
retention may each look valid in isolation while the **complete power-intent
system** remains incomplete, contradictory or unsafe.

UPF-Insight analyzes power intent as a *system* - not as isolated commands -
and answers the questions engineers actually ask:

- Is anything seriously wrong with this UPF?
- Are my power domains, supplies and Power State Table coherent?
- Is every domain protected at its boundaries? *(isolation / level shifters)*
- Does retention keep state across power-down? *(retention semantics)*
- Is this power intent **ready** to hand to the low-power flow?
- Did this change regress the previous baseline?

**Move power-intent verification left.** UPF-Insight is the power-intent
quality layer that runs *before* power-aware implementation - deterministic,
offline, and honest about what it does and does not prove.

## What UPF-Insight is - and is not

| ✅ Is | ❌ Is not |
|---|---|
| Deterministic UPF (IEEE 1801) validation | A power/IR analysis engine |
| Power-state-table and strategy intelligence | A low-power implementation tool |
| Model-based crossing and retention checks | "AI-powered" (no LLMs in the analysis path) |
| Readiness verdicts and regression diff | A cloud service (data stays local) |
| CI quality gates | A generic EDA platform |

> **READY ≠ power signoff.** **Coverage ≠ correctness.** **CI pass ≠
> low-power closure.** See
> [docs/upf/TRUST_MODEL.md](docs/upf/TRUST_MODEL.md).

## Product modules

| Module | What it does | Docs |
|---|---|---|
| **Validate** | Deterministic UPF validation with per-finding source provenance (UPF-001…) | [docs/upf/PRODUCT_TAXONOMY.md](docs/upf/PRODUCT_TAXONOMY.md) |
| **Model** | Power-intent object graph (domains, supplies, switches, states, PST, strategies) | `upf-insight model` |
| **PST** | Power State Table expansion and consistency analysis | `upf-insight pst` |
| **Diff** | Semantic power-intent change review (V1/V2 or vs a saved baseline) | `upf-insight diff` + workspace **UPF Diff** |
| **CI Gate** | Policy gate (BLOCKERS_ONLY / NO_READINESS_REGRESSION / STRICT) with exit codes | `upf-insight check --baseline --gate` + workspace **CI Gate** |
| **Reports** | HTML / JSON / text reports from real analysis evidence | `upf-insight report` + workspace **Reports** |
| **Generate** | Power-intent skeleton scaffolder | `upf-insight generate` |
| **Workspace** | Local, offline web UI - feature-first catalog, validate, PST, strategies, design-aware, diff, gate, reports, Test Drive | `upf-insight web` |

## Quick start

```bash
# install (Python 3.10+)
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .

# validate a UPF file
upf-insight check soc.upf

# validate several files in load order
upf-insight check soc.upf io.upf always_on.upf

# machine-readable output for CI
upf-insight check soc.upf --format json

# dump the power-intent model
upf-insight model soc.upf -o model.json

# analyze the Power State Table
upf-insight pst soc.upf

# semantic diff between two versions
upf-insight diff soc.v1.upf soc.v2.upf

# scaffold a power-intent skeleton
upf-insight generate --domains core,io,sram --retention core

# launch the workspace (opens http://localhost:8585)
upf-insight web
```

## 5-minute Test Drive

Run the complete power-intent loop on a realistic CPU-subsystem sample
(switchable CPU domain, isolation, level shifting, retention, PST):

```bash
# 1. analyze the known-good version
upf-insight check tests/examples/cpu_subsys/cpu_subsys_v1.upf

# 2. analyze the regressed version (one level shifter removed)
upf-insight check tests/examples/cpu_subsys/cpu_subsys_v2.upf   # UPF-061, BLOCKED

# 3. diff the two versions
upf-insight diff tests/examples/cpu_subsys/cpu_subsys_v1.upf \
               tests/examples/cpu_subsys/cpu_subsys_v2.upf

# 4. gate the change in CI
upf-insight check tests/examples/cpu_subsys/cpu_subsys_v1.upf --save-baseline baseline.json
upf-insight check tests/examples/cpu_subsys/cpu_subsys_v2.upf \
    --baseline baseline.json --gate STRICT; echo $?   # 1 - blocked

# 5. produce a report
upf-insight report tests/examples/cpu_subsys/cpu_subsys_v2.upf -o report.html
```

Walkthrough: [docs/features/README-12-five-minute-upf-workflow.md](docs/features/README-12-five-minute-upf-workflow.md)

`upf-insight` is the CLI. **`upfi` remains as a fully supported alias** -
every command above works with either name.

## CLI reference

```text
upf-insight check design.upf               # validate (errors/warnings/info + support)
upf-insight check design.upf --format json # machine-readable
upf-insight check design.upf --rule UPF-040 --rule UPF-061   # focused rules
upf-insight model design.upf -o model.json # power-intent model dump
upf-insight pst   design.upf               # Power State Table analysis
upf-insight diff  old.upf new.upf          # semantic power-intent diff (ADD/REMOVE/MODIFY)
upf-insight relations design.upf           # power-domain relation graph + matrix
upf-insight generate --domains core,io --always-on clk,rst --retention core
upf-insight generate --architecture hierarchical --hierarchy core_a,core_b \
    --domain-type core_a:switchable --switch sw_a:core_a:vdd_aon:vdd_a:pg_en \
    --relation core_a:sram:isolation,level_shift
upf-insight whats-new                       # release notes (offline); --all = full changelog
upf-insight web                            # local workspace (stdlib-only API server)
```

Exit-code contract for CI: **0** pass · **1** issues found · **2** invalid
invocation · **3** engine failure. An engine failure can never produce a
passing result.

## Power-intent workflow

```
Design / UPF authoring → UPF-Insight → understanding · validation ·
model · PST · readiness · regression protection → power-aware implementation
```

1. **Validate** - run the rule engine; every finding traces to a line.
2. **Build the model** - domains, supplies, switches, states and strategies as
   a queryable object graph.
3. **Analyze the PST** - legal power combinations, declared vs used states,
   transition consistency.
4. **Protect regressions** - diff semantically, then gate changes in CI.

## Trust model

UPF-Insight reports what it validated, what it partially validated, and what
it skipped:

- `VALIDATED` · `PARTIALLY_VALIDATED` · `NETLIST_REQUIRED` ·
  `TCL_EXECUTION_REQUIRED` · `UNSUPPORTED` · `NOT_VALIDATED`

Tcl execution constructs are **detected, never executed**. The analysis runs
locally; nothing leaves your machine. [Full trust model](docs/upf/TRUST_MODEL.md).

## Benchmarks

UPF-Insight ships with rerunnable evidence: a **94-test suite** (engine,
flow/coverage, generator, API security, plus the realistic CPU-subsystem
Test Drive regression suite) over golden known-good/known-bad fixtures.
See [docs/upf/BENCHMARK_EVIDENCE_MAP.md](docs/upf/BENCHMARK_EVIDENCE_MAP.md).

```bash
python -m pytest tests/ -q
```

## Architecture

```
preprocess · model (power_model, builder) · checker · rules_registry ·
upf_rules · support_boundary · pst/analyzer · generate · diff · reporter
        │
        ├── CLI (upf-insight / upfi)   → terminals, CI, scripts
        ├── api + workspace/webui      → local, offline web workspace
        └── reporter                   → text / JSON reports
```

The backend is deterministic and frozen behind a stable CLI contract; the
frontend is a consumer. [Repository architecture](docs/upf/REPOSITORY_ARCHITECTURE.md).

## Open source

UPF-Insight is MIT-licensed. The analysis engine, parser, model, rule
registry, CLI and local reports are open. See [LICENSE](LICENSE).

## Documentation

- [Product taxonomy](docs/upf/PRODUCT_TAXONOMY.md)
- [Trust model](docs/upf/TRUST_MODEL.md)
- [Rules registry](docs/upf/RULES_REGISTRY.md)
- [UPF fundamentals](docs/upf/UPF_FUNDAMENTALS.md)
- [Benchmark evidence map](docs/upf/BENCHMARK_EVIDENCE_MAP.md)
- [Roadmap](docs/upf/PRODUCT_ROADMAP.md)
- Per-module references: `docs/features/`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues: open a private
report - do not post exploit details publicly.

## License

MIT - see [LICENSE](LICENSE).