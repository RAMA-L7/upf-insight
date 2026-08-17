# Changelog

All notable changes to UPF-Insight are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-08-17

### Added - Flat + Hierarchical power-intent sprint

- **Canonical power-intent model** (`model.relations`) shared by generator,
  validator, CLI, API, reports and UI - no duplicated engine logic. Domain
  types are evidence-based: SWITCHABLE requires switch evidence, ALWAYS-ON
  requires an explicit always-on declaration, everything else is UNKNOWN.
- **Power Domain Relation Matrix** - cross-domain interactions only
  (ISO / LS / ISO+LS / RET / SW / CTRL) with per-relation provenance and a
  cell → evidence inspector. Sharing a supply is a **Supply Network**
  relationship and never appears in the matrix.
- **Supply network view** - per-net domain/switch ownership, shown separately
  from domain relations (shared VSS is infrastructure, not an interaction).
- **Hierarchy analysis** - domain ownership (UPF file · scope · owner),
  FLAT/HIERARCHICAL architecture detection, and `load_upf -supply` supply
  maps with parent-scope resolution.
- **Flat generator** - arbitrary domains, per-domain power type and supply,
  domain-relation editor that synthesizes the real `set_isolation` /
  `set_level_shifter` / `set_retention` commands.
- **Hierarchical generator** - `top.upf` + child files with per-child domain
  ownership, `set_scope`/`load_upf -scope`/`-supply` composition, switches
  and strategies emitted into the owning child, and deterministic output.
- **Round-trip guarantee** - generated flat and hierarchical projects
  validate back to the same architecture, domain, supply, hierarchy,
  relation, topology and provenance model.
- **Validation rules** - UPF-099 (supply-map side undefined, error) and
  UPF-100 (loaded UPF file missing, warning), both with provenance.
- **CLI** - `upf-insight relations FILE... [--json]`; `generate
  --architecture hierarchical --hierarchy ... --domain-type --domain-power
  --switch --relation`; reports (text/JSON/HTML) expose architecture,
  relations, supply sharing, hierarchy and supply maps.
- **`upf-insight whats-new`** - release notes straight from the terminal
  (notes ship inside the wheel, so it works offline); `--all` prints the
  full changelog and it tells you when your installed version is behind.
  Mirrors the `rta whats-new` flow.

### Added - Workspace / UI

- Feature-first Tool Home with grouped capability catalog
  (CORE / ANALYZE / ADVANCED / OUTPUT & KNOWLEDGE); no hidden "More tools".
- Generator redesign: Flat/Hierarchical selector, per-domain type column,
  domain-relation editor, live generated UPF with Copy/Download/Validate.
- Domain Relations page: domain cards, relation matrix, supply network,
  domain ownership, topology (AON anchors vs unclassified - never implied
  nesting) and supply maps.
- UPF Diff page (semantic V1/V2 with next actions), CI Gate page
  (PASS/FAIL, exit code, reasons, JSON), Reports page (HTML/JSON/text from
  real evidence).
- API: `/api/diff`, `/api/gate`, `/api/report`, `/api/sample` (bounded to
  `workspace/samples/`).
- Test Drive: full regression scenario (validate → diff → gate) using the
  realistic CPU-subsystem V1/V2 fixtures.

### Added - Engine (post-0.1.0, captured in 0.2.0)

- Syntax + reference layers: UPF-002/003/004/005/006/010/012/013/014/015/016.
- Isolation family: UPF-040/041/042/043/044/046/047.
- PST family: UPF-030/031/033/034/035/036.
- Power-switch family: UPF-070/071/072/073 plus UPF-021/024/025.
- Retention + level-shifter families: UPF-051/053/061/062/063.
- Design-aware layer: UPF-080/081/082/083/084 (optional netlist context).
- `engine.readiness` (READY … BLOCKED across five dimensions),
  `engine.coverage` (structural domain/supply), `engine.policy`
  (BLOCKERS_ONLY / NO_READINESS_REGRESSION / STRICT gates + baseline),
  JUnit and self-contained HTML reporters.
- Rule registry: 67+ rules (UPF-001…100).

### Fixed

- **Scope-aware supply resolution** - same-named supplies in sibling scopes
  (e.g. `core_a/vdd_core_sw` vs `core_b/vdd_core_sw`) never cross-resolve;
  switch relations attribute to the correct gated domain.
- **`load_upf` supply maps resolve** - `-supply` references the parent scope,
  so hierarchical projects no longer produce false UPF-010 "undefined
  supply" findings.
- **Strategy scope provenance** - isolation/level-shifter/retention strategies
  carry their declared scope; rules resolve supplies in that scope instead of
  the model's final current scope.
- **Hierarchical generator completeness** - per-domain supplies, switch input
  supplies and cross-scope relations are emitted correctly; relations
  synthesize real strategies instead of comments.
- Finding `file` provenance resolved from the authoritative command-record
  index - single-file runs always populate it; ambiguous multi-file lines
  stay empty (never invented).
- CLI `--gate` without `--baseline` now actually gates the current evidence;
  an unknown policy is an invalid invocation (exit 2).
- Semantic diff no longer treats provenance as semantics - comment/line-shift
  edits produce zero changes.
- `add_pst_state` multi-pair brace groups, `add_state_transition` positional
  source, `-elements` brace stripping, and (kind, name)-keyed duplicate
  detection all corrected.

## [0.1.0] - 2026-08-14

Initial pre-release validation candidate: deterministic UPF power-intent
validation with 67+ rules, readiness scoring, structural coverage, semantic
diff, CI gate (exit 0/1/2/3), HTML/JSON reports, and the feature-first web
workspace with Test Drive. See the [0.2.0] entries for the full feature set
captured at this baseline.

[0.2.0]: https://github.com/RAMA-L7/upf-insight/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/RAMA-L7/upf-insight/releases/tag/v0.1.0
