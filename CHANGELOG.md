# Changelog

All notable changes to UPF-Insight are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Workspace: feature-first Tool Home with grouped capability catalog
  (CORE / ANALYZE / ADVANCED / OUTPUT & KNOWLEDGE); no hidden "More tools".
- Workspace: **UPF Diff** page (semantic V1/V2 comparison with next actions).
- Workspace: **CI Gate** page (policy PASS/FAIL, exit code, reasons, JSON).
- Workspace: **Reports** page (HTML / JSON / text from real evidence).
- API: `/api/diff`, `/api/gate`, `/api/report`, `/api/sample` (bounded to
  `workspace/samples/`).
- Test Drive: full regression scenario (validate → diff → gate) using the
  realistic CPU-subsystem V1/V2 fixtures.

### Fixed
- Finding `file` provenance resolved from the authoritative command-record
  index — single-file runs always populate it; ambiguous multi-file lines
  stay empty (never invented).
- CLI `--gate` without `--baseline` now actually gates the current evidence
  (previously silently ignored); an unknown policy is an invalid invocation
  (exit 2), matching the API's HTTP 400.
- Semantic diff no longer treats provenance (`declared_line`/`declared_file`)
  as semantics — comment/line-shift edits produce zero changes.
- Web design-aware mode: dict design context normalized to `DesignContext`
  (design-aware rules + readiness no longer silently degrade or crash).
- Readiness `mode` honestly flips to `DESIGN_AWARE` when a design snapshot
  is supplied.
- Suppressed the browser's automatic favicon 404.

### Added
- Project scaffold: package layout, `pyproject.toml`, MIT `LICENSE`, CLI entry
  points (`upf-insight` / `upfi`), pytest configuration.
- `preprocess.upf_preprocess`: Tcl/UPF command-record preprocessing (comments,
  line continuations, provenance).
- `model.power_model`: power-intent object graph (domains, supply
  ports/nets/sets, switches, supply states, PST, isolation/level-shifter/
  retention strategies).
- `model.builder`: command-stream → model builder with bounded Tcl-aware
  tokenization and provenance tracking.
- `engine.rules`: rule registry (UPF-001…084), deterministic checker, rule
  handlers (layers 1–5).
- `engine.trust.support_boundary`: VALIDATED / PARTIALLY_VALIDATED /
  NETLIST_REQUIRED / TCL_EXECUTION_REQUIRED / UNSUPPORTED / NOT_VALIDATED.
- `engine.pst.analyzer`: Power State Table expansion and consistency analysis.
- `engine.engine`: top-level validate orchestration.
- `cli`: `check`, `model`, `pst`, `diff`, `generate`, `web` commands with
  exit-code contract (0/1/2/3).
- `generate.generator`: power-intent skeleton scaffolder.
- `diff.differ`: semantic model-level UPF diff (ADD/REMOVE/MODIFY).
- `report.reporter`: text and JSON result formatting.
- `api.api_server`: stdlib-only local HTTP JSON API + vanilla-JS workspace.
- `tests`: 8-test core engine suite with golden known-good/known-bad fixtures.

### Added (post-0.1.0)
- `set_domain_supply_net` / `set_port_attributes` modeled by the builder; the
  generated skeleton now validates without UPF-001 / UPF-020.
- Isolation rule family implemented: UPF-040 (non-always-on isolation supply),
  UPF-041 (self-located isolation in switchable domain), UPF-042 (missing
  isolation on crossing), UPF-043 (redundant isolation), UPF-044 (-applies_to
  missing inouts), UPF-046 (invalid clamp value), UPF-047 (isolation control
  not always-on).
- PST rule family implemented: UPF-030 (declared state never used), UPF-031
  (PST references undeclared state), UPF-033 (empty/unreachable PST state),
  UPF-034 (duplicate/overlapping PST combination), UPF-035 (transition to
  undeclared state), UPF-036 (strategy not PST-conditioned).
- `engine.readiness`: categorical power-intent readiness verdict
  (READY / READY_WITH_ADVISORIES / REVIEW_REQUIRED / BLOCKED /
  INSUFFICIENT_CONTEXT) across five dimensions (POWER_STATES,
  SUPPLY_NETWORK, STRATEGIES, CONSISTENCY, DESIGN_CONTEXT).
- Power-switch rule family implemented: UPF-070 (switch references undefined
  supply), UPF-071 (switch control not always-on), UPF-072 (always-on signal
  into switchable domain), UPF-073 (switch output unused), plus UPF-021
  (domain element overlap), UPF-024 (unknown connect target), UPF-025
  (unreferenced supply state).
- Retention + level-shifter families implemented: UPF-051 (retention control
  not always-on), UPF-053 (save/restore tied to one signal), UPF-061 (missing
  level shifter across differing voltages), UPF-062 (wrong level-shifter rule
  for the voltage direction), UPF-063 (self-located LS in switchable domain).
  `add_port_state` now captures the nominal ON voltage for these checks.
- `example.ret_ls_bad.upf` fixture + retention/LS tests; suite now 25 tests.
- Syntax + reference layers implemented: UPF-002 (illegal option), UPF-003
  (missing required argument), UPF-004 (unsupported upf_version), UPF-005
  (deprecated add_power_state), UPF-006 (unbalanced braces/brackets), UPF-010
  (undefined supply reference), UPF-012 (unresolvable instance path), UPF-013
  (duplicate definition, same-kind only), UPF-014 (use-before-definition),
  UPF-015 (self-connect dependency cycle), UPF-016 (unverifiable set_scope).
  Builder records `syntax_issues`, `duplicate_definitions`, `references` and
  `scope_changes`; the netlist-dependent remainder of 012/015/016 is
  NETLIST_REQUIRED (deferred to v2). Suite now 27 tests.
- Design-aware layer implemented: UPF-080 (unknown `-elements` instance),
  UPF-081 (unknown control signal), UPF-082 (uncovered endpoint crossing),
  UPF-083 (retention coverage gap), UPF-084 (library PG mismatch). These
  consume an optional JSON design context (`engine.design.design_context`,
  wired as `check --netlist design.json` and the web API `design` payload)
  and stay silent — with a NETLIST_REQUIRED support note — when none is
  supplied. Suite now 29 tests.
- `engine.coverage`: structural domain/supply coverage (primary supply,
  switchability, isolation/retention/level-shifter strategy coverage).
- `engine.policy`: declarative CI policy engine — BLOCKERS_ONLY /
  NO_READINESS_REGRESSION / STRICT gates plus validated custom JSON/YAML
  policies, baseline save/compare, engine-failure-never-disabled.
- CLI: `rules list`, `coverage`, `report` (HTML/text/JSON), `check
  --rule/--junit/--save-baseline/--baseline/--gate`.
- Reporters: JUnit XML and self-contained HTML report.
- Workspace UI: readiness verdict, coverage table, rules page tabs.
- `example.iso_bad.upf` and `example.pst_bad.upf` fixtures plus family tests;
  suite now 20 tests.

### Fixed
- `add_pst_state -state {vdd ON vss ON}` multi-pair brace groups were parsed
  only to the first pair, silently dropping supplies from the model.
- `add_state_transition` read the source state from a non-existent `-state`
  option instead of the positional argument, dropping every transition.
- `-elements {u1 u2}` kept the braces in element names, breaking element
  ownership/overlap checks.
- Duplicate-definition detection was name-based and would have mis-flagged the
  legal `create_supply_port vdd` + `create_supply_net vdd -resolve port` pair;
  it now keys on (kind, name) and tracks nets/ports/sets separately.

## [0.1.0] - 2026-08-14

Initial pre-release scaffold. See "Unreleased" for the full feature set
captured at this baseline.

[Unreleased]: https://github.com/RAMA-L7/upf-insight/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RAMA-L7/upf-insight/releases/tag/v0.1.0