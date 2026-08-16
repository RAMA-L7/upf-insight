# UPF-Insight — Product Taxonomy

> **Document kind:** product architecture — the capability family and how each
> product module maps to real backend evidence.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## 1. Product family

The workspace is organized into the following product modules. Each module is
grounded in an existing backend capability — none is created for marketing
symmetry.

| Product module | Purpose (one line) | Backend modules |
|---|---|---|
| **Validate** | Deterministic UPF validation with per-finding source provenance | `checker.py`, `rules_registry.py`, `upf_rules.py`, `upf_preprocess.py`, `support_boundary.py` |
| **Model** | Power-intent object graph: domains, supplies, switches, states, PST, strategies | `power_model.py`, `builder.py` |
| **PST** | Power State Table expansion and consistency analysis | `pst/analyzer.py` |
| **Generate** | Power-intent skeleton scaffolder | `generate/generator.py` |
| **Diff** | Semantic power-intent change review vs a saved baseline | `diff/differ.py` |
| **Workspace** | Local, offline web UI (validate / model / PST) | `api/api_server.py`, `workspace/webui/` |
| **Reports** | Text / JSON result formatting | `report/reporter.py` |

Tooling that does not belong to the core analysis family stays grouped under
**Tools**: Generator, Diff, Workspace, Reports. These are real capabilities;
grouping is navigational, never a deprecation.

## 2. Module definitions

Each module below uses the same template: purpose · primary user · input ·
analysis · output · trust boundary.

---

### 2.1 Validate

- **Purpose:** validate a UPF file (or a set of files in load order) against
  the deterministic rule registry and report every finding with severity,
  rule, message, line, plus an explicit analysis-scope trust statement.
- **Primary user:** PD / low-power / verification engineers authoring
  power-intent.
- **Input:** UPF text or file(s); optional custom-rules YAML.
- **Analysis:** preprocessing → model build → semantic checks (UPF-001…084,
  layers 1–5) → PST cross-checks → support-boundary derivation.
- **Output:** findings (error/warning/info), stats, analysis scope, optional
  JSON.
- **Trust boundary:** scope status is always reported (e.g. `NETLIST_REQUIRED`,
  `PARTIALLY_VALIDATED`, `TCL_EXECUTION_REQUIRED`, `UNSUPPORTED`). A clean
  result means "no rule fired", not "power proven correct".
- **CLI:** `upf-insight check` · **UI:** workspace "Validate" panel.

### 2.2 Model

- **Purpose:** expose the power-intent object graph so engineers and tools can
  query what UPF *means*, not just what it says.
- **Primary user:** engineers inspecting domains/supplies/states/strategies;
  tooling consuming the model.
- **Input:** UPF file(s).
- **Analysis:** builder walks preprocessed commands and mutates the model,
  recording provenance on every entity.
- **Output:** JSON model dump (`upf-insight model -o model.json`).
- **Trust boundary:** the model reflects only modeled commands; unmodeled
  commands are listed under `unsupported_commands`.
- **CLI:** `upf-insight model` · **UI:** workspace "Model" panel (planned).

### 2.3 PST

- **Purpose:** expand and validate the Power State Table — declared vs used
  states, legal-combination coverage, transition consistency.
- **Primary user:** engineers reviewing power-state intent.
- **Input:** UPF file(s).
- **Analysis:** supply-state inventory, PST row extraction, declared/used set
  comparison, transition listing.
- **Output:** PST analysis (text or JSON).
- **Trust boundary:** voltage-dependent conclusions (isolation/LS conditioning,
  retention always-on) are PARTIAL without a complete supply-state model.
- **CLI:** `upf-insight pst` · **UI:** workspace "PST" panel (planned).

### 2.4 Generate

- **Purpose:** scaffold a structurally valid power-intent skeleton from a
  domain list, always-on signals, and retention domains.
- **Primary user:** engineers starting a new low-power block.
- **Input:** CLI flags (`--domains`, `--always-on`, `--retention`).
- **Analysis:** template composition (domains → supply network → states →
  strategies → always-on attributes).
- **Output:** UPF text on stdout.
- **Trust boundary:** generated output is a *starting point*; it is not a
  complete, verified power intent.
- **CLI:** `upf-insight generate`.

### 2.5 Diff

- **Purpose:** compare two power-intent models and answer "what changed
  structurally?" across versions.
- **Primary user:** engineers and CI pipelines protecting power-intent quality.
- **Input:** old and new UPF files.
- **Analysis:** model-level comparison (not raw line diff): domains, supplies,
  switches, PST and strategy count changes → ADD/REMOVE/MODIFY records.
- **Output:** change records.
- **Trust boundary:** model diff reflects modeled structure only; unsupported
  commands are outside the comparison.
- **CLI:** `upf-insight diff OLD NEW`.

### 2.6 Workspace

- **Purpose:** a local, offline web UI for validation, model inspection and
  PST analysis — no cloud, no EDA tool, no build step.
- **Primary user:** engineers who prefer a browser over the terminal.
- **Input:** pasted UPF text or file paths.
- **Analysis:** the same engine behind the CLI, served over a stdlib-only
  local HTTP API.
- **Output:** findings table, summary, support boundary.
- **Trust boundary:** the workspace is a consumer of the backend; it adds no
  analysis of its own.
- **CLI:** `upf-insight web` (port 8585 default).

### 2.7 Reports

- **Purpose:** deterministic text and JSON rendering of validation results.
- **Primary user:** terminals, scripts, CI, the workspace.
- **Input:** a `ValidateResult`.
- **Analysis:** formatting only — no new analysis.
- **Output:** human-readable text or machine-readable JSON.
- **Trust boundary:** reports display the engine's honest scope statement.
- **CLI:** `upf-insight check --format text|json`.

## 3. Grouping rationale

- **ANALYZE** (Validate, Model, PST) — first-order analysis of power intent.
- **CHANGE** (Diff) — regression protection.
- **TOOLS** (Generate, Workspace, Reports) — auxiliary capabilities, fully
  preserved.

No artificial modules were created for symmetry; each group corresponds to a
real analysis layer in the backend.