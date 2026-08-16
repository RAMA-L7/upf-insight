# UPF-Insight — Repository Architecture

> **Document kind:** engineering architecture.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## 1. One-liner

UPF-Insight preprocesses IEEE 1801 (UPF/Tcl) files, builds an in-memory
**power-intent model**, runs a **deterministic rule engine** over it, and
reports findings with provenance plus an honest **support boundary** — over a
stable CLI, a local stdlib-only API, and a vanilla-JS workspace.

## 2. Data flow

```
UPF files (load order)
      │  upf_preprocess.py       # comments, continuations -> CommandRecord[]
      ▼
CommandRecord[]
      │  model/builder.py        # bounded Tcl tokenization -> model mutation
      ▼
PowerIntentModel  ───────────────►  model dump (`upf-insight model`)
      │
      ├─► engine/rules/checker.py     # dispatch handlers by registry code
      │        │   upf_rules.py       # deterministic rule implementations
      │        ▼
      │   findings[] (rule, severity, message, file, line, support)
      │
      ├─► engine/trust/support_boundary.py   # VALIDATED / PARTIAL / ...
      │
      └─► engine/pst/analyzer.py     # Power State Table consistency
      │
      ▼
ValidateResult  ─────────────────►  reporter (text/json)
                                     CLI exit code (0/1/2/3)
                                     workspace API
```

## 3. Module map

```
upf_insight/
  __init__.py
  preprocess/upf_preprocess.py   # Tcl/UPF command-record preprocessing
  model/
    power_model.py               # PowerDomain, Supply*, PowerSwitch,
                                 # SupplyState, PowerState, Pst, Strategies,
                                 # PowerIntentModel (to_dict for JSON)
    builder.py                   # command stream -> model; scope tracking
  engine/
    engine.py                    # validate(): orchestrate the pipeline
    rules/
      rules_registry.py          # canonical Rule dataclass list (UPF-001..084)
      finding.py                 # shared Finding type (breaks import cycle)
      checker.py                 # dispatch; CheckResult; never-crash guarantee
      upf_rules.py               # _register decorator + handler functions
    trust/support_boundary.py    # status vocabulary + boundary derivation
    pst/analyzer.py              # PstAnalysis; declared vs used states
  generate/generator.py          # power-intent skeleton scaffolder
  diff/differ.py                 # model-level ADD/REMOVE/MODIFY diff
  report/reporter.py             # format_text / format_json
  cli/cli.py                     # argparse surface; exit codes 0/1/2/3
  api/api_server.py              # stdlib http.server JSON API + web server
  workspace/webui/index.html     # vanilla-JS workspace (no build step)
```

## 4. Design decisions

### Determinism
- No LLM, no randomness, no network in the engine.
- Rule output order is sorted where iteration order could leak.
- `PowerIntentModel.to_dict()` gives stable JSON.

### Model-over-text
SDC validation can be largely line-scoped; UPF is hierarchical and stateful.
UPF-Insight therefore validates against a **model**, not raw text. The builder
is the only place that touches command tokens; rules query the model. This is
the central difference from the sdc-tools architecture and the reason the
`model/` package exists.

### Never-crash rule engine
`checker.check_model` wraps every handler in a try/except; a failing rule is
reported as an engine-scope finding rather than aborting the run.

### Import-cycle safety
`finding.py` exists as its own module because the checker (dispatcher) and
`upf_rules` (producers) both need `Finding`.

### Stdlib-only runtime
The API server uses only `http.server` / `json` / `urllib`. `pyyaml` is the
single runtime dependency (custom rules, future). The web UI has zero build
step.

### Package data
`pyproject.toml` ships `*.upf`, `*.tcl`, workspace assets, and manifest JSON
in the wheel.

## 5. CLI contract

```
upf-insight check FILE [FILE...] [--format text|json] [--rule CODE ...]
upf-insight model FILE [FILE...] [-o OUT.json]
upf-insight pst   FILE [FILE...]
upf-insight diff  OLD NEW
upf-insight generate [--domains A,B] [--always-on A,B] [--retention A,B]
upf-insight web   [--port N]
```

Exit codes: **0** pass · **1** issues · **2** invalid invocation · **3** engine
failure. An engine failure can never produce a passing result.

## 6. Trust boundary mechanics

`compute_support_boundary(model)` derives counts per status:
- any `unsupported_commands` → `UNSUPPORTED` count + note.
- PST present → `VALIDATED`; supply states without a full PST → PARTIAL.
- switches present → PARTIAL (needs supply-state analysis).
- design-aware layer → `NETLIST_REQUIRED` (v1 has no netlist reader).
- `exec`/`source` constructs → `TCL_EXECUTION_REQUIRED` (detected, not run).
- no commands at all → `NOT_VALIDATED`.

The boundary is always printed/reported — "no findings" never silently means
"proven correct".

## 7. Extensibility

- **New rule**: add handler in `upf_rules.py` (`@_register("UPF-NNN")`) +
  registry entry + tests. The checker picks it up automatically.
- **New command**: add parsing in `builder._dispatch` and (if a new entity)
  a dataclass in `power_model.py`.
- **New report format**: add a function in `report/reporter.py`.
- **Custom rules**: YAML rulesets (planned) validate against the same model
  without touching the core registry.