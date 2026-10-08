# Changelog

All notable changes to UPF-Insight are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed - three engine defects deferred from PR #1 — 2026-10-09

All three were listed as "found, not fixed here" to keep that diff
reviewable.

- **`add_power_state` dropped its declaration.** The command was recognised
  but never stored, so `model.supply_states` stayed empty and every rule
  consuming it (UPF-025, UPF-030, UPF-032) was unreachable for files using
  the legacy form. It now populates `supply_states` exactly as
  `add_supply_state` does, while UPF-005 still flags it as deprecated. Its
  first argument is deliberately *not* asserted as a supply reference: IEEE
  1801 allows a supply, a power domain or a PST name there, and
  hard-coding `kind="supply"` made UPF-010 claim a *defined* domain was an
  undefined supply — an error-grade `VALIDATED` finding. That false positive
  was caught during this work and is now covered by a test.
- **`add_state_transition` appended to every PST.** Already fixed on `main`
  by `3ffa0b2`, which landed *inside* PR #1 after its description was
  written — so the "out of scope" list was stale, not the code. It now
  targets the table in context; covered here by a regression test so it
  cannot silently regress.
- **`preprocess_file` silently mangled non-UTF-8 input.** `errors="replace"`
  turned an undecodable byte into U+FFFD, so `PD_café` became
  `PD_caf�` in the model and could never match its own references —
  manufacturing false findings against a file that was merely saved in the
  wrong encoding. Decoding is now strict: a `ValueError` names the file and
  the exact byte offset. 0 of 31 UPF/Tcl files in this repo fail strict
  UTF-8, so nothing legitimate breaks. The local API maps it to a 400
  rather than dropping the connection (`UnicodeDecodeError` subclasses
  `ValueError`, which the pre-existing `except OSError` would have missed).

- Golden: `example.syn_ref_bad.upf` gains `UPF-025` (info) and `UPF-032`
  (warning), `warning_count` 9 -> 10. Both adjudicated against ground truth
  (`create_pst` count = 0; no supply-set function references `PON`) — they
  are exactly the two rules PR #1 reported as unreachable.
- Tests: 6 regression tests in `test_engine.py`, verified non-vacuous by
  reverting the fixes and confirming 3 of them fail against unfixed code.

### Added - MCP server now covers every feature (8 -> 19 tools) — 2026-10-08

`upf-insight-mcp` exposed 8 tools while the CLI had 16 commands and the API
11 routes, so an agent could not reach half the engine. Every remaining
feature now has one tool, bound to the same engine code path as the CLI:

- **New tools** - `upf_relations` (domain relation matrix), `upf_analyze`
  (end-to-end with optional netlist), `upf_report` (json/text/html),
  `upf_rule_show` (full detail for one rule code, case-insensitive),
  `upf_rules_audit` (registry/handler sync + `test_ref` resolution),
  `upf_batch` (validate a directory), `upf_lint`, `upf_convert` (json/yaml),
  `upf_quality` (adversarial mutation corpus), `upf_whats_new`, and
  `upf_version`.
- **Read-only by construction** - `upf_lint` calls `lint_file(check_only=True,
  fix=False)` so it can never rewrite a file, and `upf_batch` runs
  `batch_check` only, never the report writer.
- **Same workspace guard** - the new path-taking tools (`batch`, `lint`,
  `convert`, `report`, `analyze`, `relations`) resolve through `_bounded()`;
  `upf_batch` adds `_require_dir()` so a directory is bounded too. Tests
  assert each one rejects `../../etc/passwd`.
- Tests: 8 -> 28 in `test_mcp_server.py`, including one case per new tool and
  a check that every schema carries a description so an agent can choose.

### Fixed - MCP serve loop crashed when the client disconnected

`stdout.write`/`flush` sat outside the try block, so a host shutting down
mid-session raised `OSError` out of the serve loop and killed the server -
contradicting the module's own contract that the loop never crashes. The
write is now guarded and a dead peer ends the loop quietly, matching normal
MCP lifecycle. Found by running the real `upf-insight-mcp` binary over a
pipe, not by the in-process tests.

### Measured - external corpora re-validated (AnyCore 65% -> 1.4%, Tenstorrent 100% -> 0%) — 2026-10-03

Both external corpora named in `docs/validation/REAL_WORLD_REPORT.md` were
located on this host and re-measured against the current engine. The historical
65% / 100% figures were previously labelled unverified; they are now replaced
by measurements.

| Corpus | Historical | Measured now |
|---|---|---|
| AnyCore RISC-V (37 files, `power_spec/*.upf` @ `419cc6c`) | 4012 findings, 65% FP | **2268 findings, 32 FP (1.4%)** |
| Tenstorrent AOU (1 file, 9 commands, Apache-2.0) | 1 finding, 100% FP | **0 findings, 0 FP** |

- `scripts/validate_external.py` — new harness. Read-only (SHA-256 manifest
  compared before/after each run), deterministic (`--verify-determinism` runs
  each corpus twice and compares), and it reports each finding in exactly one of
  five categories: parser failure / normalization failure / genuine semantic /
  ambiguous / validator defect. A corpus that is absent is reported as
  `unavailable` with the reason, never skipped silently.
- `--load-set` mode validates a whole corpus as one load set, which is how
  hierarchical UPF is actually consumed. Per-file is 5.0% FP; load-set is
  **1.4%**, because a top file `load_upf`s children into named scopes and
  single-file validation under-reports the model.
- `tests/test_external_corpus_regressions.py` — 23 hard assertions, one per
  defect found below.
- `tests/fixtures/soc_top.v` + `soc_top.upf` and
  `tests/test_netlist_design_aware.py` — RTL -> Yosys -> synthesized netlist ->
  UPF -> design-aware validation, including a negative control proving a
  genuinely absent signal is still reported.

### Fixed - nine defects found only in real open-source UPF — 2026-10-03

None of these were visible from the shipped corpus; each was found by running
the external corpora and inspecting the original UPF construct.

- **Backslash continuation inside braces** — Tcl treats a backslash before a
  newline as whitespace *everywhere*, including inside `{}`. The lexer
  preserved it, putting a literal `\` into multi-line port lists and producing
  "unknown target `'\'`" once per continuation. Also handles `…  \ ` with a
  trailing space after the backslash, which AnyCore emits.
- **`create_power_domain -include_scope PD_RAM`** — real UPF puts flags before
  the name, so `args[0]` named the domain `-include_scope` and the real name was
  lost. The name is now the first positional argument.
- **Plain Tcl reported as unknown UPF** — a `.upf` file is a Tcl script;
  `set`, `source`, `foreach`, `[set_scope …]` are not UPF commands and no longer
  raise UPF-001. Genuinely unknown commands are still reported.
- **`create_supply_net -domain` / `-reuse` / `-exclude`** — legal IEEE 1801,
  previously rejected (543 findings in AnyCore alone).
- **`create_power_domain -scope`** — legal IEEE 1801, previously rejected.
- **`set_isolation -diff_supply_only`** — legal IEEE 1801, previously rejected.
- **`-control_port {ctrl sig}` pairs** — the pair's first half names the port
  *role*, not the signal. Rules were comparing the braced literal against the
  design. The signal half is now extracted; the role is retained so a condition
  legitimately referencing `{ctrl}` is not flagged.
- **Relative `set_scope` composition** — `set_scope` assigned absolutely,
  dropping the prefix a child was loaded into, so supplies were keyed `btb/VDD`
  while the parent referenced `fs1/btb/VDD`. Relative scopes now compose;
  restating the current scope stays idempotent.
- **`UPF-081` compared `{sig sense}` against the design** — `-save_signal
  {ret_en high}` could never match. Now split into `save_signal_name` /
  `save_signal_sense`, verified against a synthesized netlist.

### Fixed - real-world false positives (shipped corpus now 0%) — 2026-10-02

The parser and grammar defects recorded in the v0.3.0 validation report are
fixed. False-positive rate on `tests/corpus/` goes from **44% (15 of 34) to 0%
(0 of 21)**; all 21 remaining findings are genuine / needs-review advisories.

- **Multi-line brace groups (D4)** — `preprocess()` now tracks brace/bracket
  depth across newlines and splits a command only at depth 0, so a multi-line
  `-elements { ... }` is one command rather than N+1 phantom commands. An
  unbalanced brace no longer swallows the rest of the file: if the next line
  begins with a real UPF command, the lexer emits what it has (UPF-006 reports
  the imbalance) and resumes at depth 0.
- **Grammar coverage (D1)** — accepts and models the legal IEEE 1801 spellings
  the engine previously rejected: `-include_scope` on `create_power_domain`,
  `-isolation_power_net`/`-isolation_ground_net`,
  `-retention_power_net`/`-retention_ground_net`, and `-location` on the
  isolation/level-shifter/repeater control commands.
- **Interchangeable required options** — `_REQUIRED_OPTIONS` now takes spelling
  groups, so `create_power_switch` accepts the 2.1/3.0 `-input_supply` or the
  3.1+ `-input_supply_port` rather than demanding one exact token (UPF-003).
- **Brace-group expansion** — `connect_supply_net` records one entry per
  resolved target instead of appending the raw `{ ... }` value, which is what
  made UPF-024 report one unknown target named `'{ VDD_TOP }'`.
- **Supply-port pairs (D5)** — `_supply_value()` unwraps a `{-port supply}` pair
  and prefers the supply half, accepting both the `_supply` and `_power_net`
  spellings across switch, isolation, retention, and repeater strategies.
- **`map_power_switch`** — added to `_SUPPORTED` and `_LEGAL_OPTIONS`, matching
  the existing `map_*_cell` handlers.

All five former `xfail(strict=True)` markers in `tests/test_real_world_corpus.py`
are inverted to hard assertions — the acceptance criterion set by the validation
report. `test_semantic_checks_still_fire_on_real_upf` pins that the real checks
still fire, so none of this was bought by disabling checks.

The external open-source projects measured at v0.3.0 (65% FP on AnyCore, 100%
on Tenstorrent) have **not** been re-measured — that UPF is not redistributed
in this repository. Their defects were grammar-level and are fixed, so those
figures are a historical upper bound, not a current claim. See
`docs/validation/REAL_WORLD_REPORT.md`.

### Added - real-world validation (tag v0.3.0-validation.1) — 2026-10-01

- `scripts/validate_corpus.py` — runs the CLI over an external UPF corpus,
  buckets every finding by root cause, and reports a false-positive rate.
  Prints an `unclassified` bucket so new failure modes surface rather than
  counting as genuine.
- `tests/corpus/` — two shipped files: a hand-written file exercising legal
  IEEE 1801 option spellings, and a UPF-Insight-generated file as a control.
  (A third file — a real third-party SoC UPF, UPF 2.1, 4 domains, 3 power
  switches — was measured but is **not** redistributed here; it belongs to
  another project. See the report's note on the external file.)
- `tests/test_real_world_corpus.py` — regression guard. As shipped, four tests
  were marked `xfail(strict=True)` for the documented parser defects; they
  flipped to passing when fixed, and are now inverted to hard assertions (see
  the Fixed section above). Three assert the semantic checks still fire, so the
  defects cannot be "fixed" by disabling real checks.
- `docs/CAPABILITIES.md` — what the tool does and does not do, bounded by
  measurement rather than aspiration.
- `docs/validation/REAL_WORLD_REPORT.md` — methodology, corpus, per-defect
  analysis, and prioritized improvements.

### Measured result at v0.3.0 (superseded for the shipped corpus — see Fixed above) — 2026-10-02

**56% false-positive rate on UPF the tool did not write** (53 of 95 findings),
against a 100% mutation-detection rate on defects the same author injected.
The control file — generated by UPF-Insight itself — scores 0 errors. The
engine currently validates its own dialect rather than the standard.

Root causes: the accepted-option grammar rejects 9 legal IEEE 1801 options
(52% of all false positives), brace groups are not expanded in
`connect_supply_net`, and `map_power_switch` is unsupported. The switch-grammar
gap additionally disconnects every switch from its supplies, which cascades
into a false UPF-076.

P0 fixes are tracked in the validation report. Until they land, the tool
should not be used as a CI gate.

### Fixed - cross-file scope semantics (behavior change) — 2026-10-01

Scope is now per-file state. Previously `model.current_scope` was never
reset between files, so a UPF file that omitted `set_scope` silently
inherited the previous file's scope and **results depended on the order
files were listed on the command line**.

- `builder`: `current_scope` resets at each file boundary. A file that
  issues no `set_scope` starts at the top scope.
- `builder`: `load_upf <file> -scope <scope>` now establishes the scope the
  child is loaded into. The event recorded `child_scope` but nothing applied
  it; per IEEE 1801 a child inherits that scope and need not repeat
  `set_scope`. Every hierarchical fixture had been repeating `set_scope`
  redundantly, which is why the gap was invisible.
- `rules`: `_domain_by_name` resolved against the model's *final* scope
  rather than each strategy's own scope, so findings could differ by file
  order even after the reset above.

**Impact:** for multi-file runs where a child UPF omits `set_scope`, domain
keys and finding codes change. Single-file runs are unaffected. A genuine
duplicate top-level supply definition across files now surfaces as
`UPF-013` instead of being masked by the bleed.

No new rule code was added: this corrects the model rather than flagging the
designer's (well-formed) UPF.

### Fixed - support-boundary honesty — 2026-10-01

- `checker`: a rule that raised is now reported with `support=NOT_VALIDATED`
  instead of `VALIDATED`. An internal crash proved nothing about the design.
- `checker`: `CheckResult.support_boundary` is populated from
  `compute_support_boundary()`; it was serialized but always `{}`.

### Fixed - local API input bounds — 2026-10-01

- `api_server`: request bodies are capped at 8 MiB (413 on overflow).
- `api_server`: a malformed or non-object JSON body now returns a readable
  4xx instead of dropping the connection. Applies to `/api/validate`,
  `/api/generate`, `/api/diff`, `/api/gate`, and `/api/report`.

### Tests — 2026-10-01

- Added regression tests for cross-file scope: bleed, file-order
  independence, and `load_upf -scope` inheritance.
- Added positive and negative cases for UPF-015, UPF-016, UPF-025, UPF-032
  and UPF-036, which previously had no assertion anywhere in the suite.
- Added API request-body bound tests.
- `test_rule_audit.py` now resolves every `test_ref` against the test tree.
  Five refs pointed at test functions that did not exist; all are repointed.
- `docs/upf/RULES_REGISTRY.md` is now generated by
  `scripts/generate_rules_registry.py`, with a test that fails on drift. It
  previously documented 65 rules and omitted UPF-085..100 entirely.

### Fixed - CI: golden drift, a Windows-only test, and a gate that asserted the wrong verdict — 2026-10-08

Three jobs were red on `main` and on this branch. Two were pre-existing; one
was introduced by the engine work above.

- **Golden contract (`engine-contract`)** - the parser change above moves rule
  output, and the recorded signatures were never refreshed, so the job broke on
  this branch (it was green on `main`). Re-recorded with
  `python scripts/run_golden.py --update`; 18 fixtures, three of them changed:
  `UPF-031` 1->2 (`example.pst_bad`), `UPF-038` subject gains its driving
  supply (`DRV2`) (`example.pst_cross_bad`), and on
  `user_coverage_example.upf` the 30 false `UPF-002` option-illegality errors
  are gone while `UPF-031` 6->16, `UPF-040` 0->3 and `UPF-050` 0->1 now fire
  because the model actually builds (errors 52->32). Every one of these is the
  documented consequence of splitting multi-line commands at brace depth 0.
- **Local API (`api_server`)** - a path that passed the workspace-root bound
  but did not exist reached the engine, raised `FileNotFoundError`, and killed
  the connection. Nonexistent files and netlists now return a readable 400,
  and an unreadable input is caught as a 400 rather than a dropped connection.
- **Tests** - `test_validate_out_of_root_file_returns_400` hardcoded
  `C:\Windows\win.ini`, which only exercises the root bound on Windows. On
  POSIX that string is a *relative* name that resolves inside the root, so the
  test failed on ubuntu and macos with a dropped connection. It now uses an
  existing temp file outside the root, and a new test asserts that a missing
  in-root path returns 400 rather than dropping the connection. `_post` also
  returns the real error body instead of discarding it.
- **CI gate** - `cpu_subsys_v2.upf` is the *deliberately* regressed fixture
  (the 1.8 V level shifter declared in v1 was removed), so
  `GATE [NO_READINESS_REGRESSION] 3 new blocker(s)` -> FAIL is the detector
  working. The job exited non-zero because it expected a PASS. It now runs the
  gate with `continue-on-error` and asserts the verdict is `FAIL`, so the job
  is green precisely while the planted UPF-061 regression is still blocked.

## [0.3.0] - 2026-08-23

### Added - sdc-tools parity sprint

Bringing UPF-Insight to feature parity with the Ṛta / sdc-tools validator:

- **Verilog netlist parser** - `load_design()` accepts `.v/.sv` in addition
  to the JSON design snapshot (ports, instances, buses, sequential
  heuristics; malformed input never crashes).
- **Netlist-aware design coverage** - `analyze_design_coverage()` buckets
  inputs/outputs as CONSTRAINED/UNCONSTRAINED/PARTIAL against UPF port
  attributes ("coverage is NOT correctness").
- **Strategy interaction analysis** - new rules **UPF-085** (duplicate
  strategy) and **UPF-086** (overriding/conflicting strategy: overlapping
  switch outputs, contradictory locations, redefined retention).
- **Wildcard risk analysis** - new rule **UPF-087**: specificity + 0-10 risk
  score for wildcard element/target patterns.
- **New CLI commands** - `analyze` (one-shot E2E with combined HTML report),
  `batch check|report` (directory-wide), `lint` (`--check`/`--fix`),
  `convert` (UPF -> JSON/YAML), `rules show CODE` plus severity/search
  filters.
- **Custom rule sets** - declarative YAML rules via `--custom-rules`
  (`examples/policies/custom_rules_example.yaml`).
- **MCP server** - `upf-insight-mcp` entry point exposing 8 deterministic
  tools over JSON-RPC stdio.
- **CI hardening** - GitHub Actions workflow (3 OS x Python 3.10-3.12,
  registry audit, quality corpus, golden runner, real gate job), reusable
  `upf-gate` composite action, pre-commit hook for staged `.upf/.tcl`.
- **Evidence-as-product** - `scripts/build_evidence.py` (machine-checked
  RELEASE_EVIDENCE.json manifest), `scripts/run_golden.py` (18-fixture
  golden regression with drift reporting),
  `scripts/generate_support_matrix.py` (docs/support_matrix.md).

## [0.2.4] - 2026-08-17

### Added - Semantic hardening: cascade, metadata audit, evidence boundary, quality metrics

Four hardening workstreams that turn the adversarial suite into a maintained
quality contract:

- **Cascade / dependency quality** - dependent rules (UPF-070, UPF-073,
  strategy rules) declare `depends_on` error prerequisites in the registry;
  when a prerequisite errors on the same subject (e.g. UPF-010 undefined
  supply), the dependent finding is downgraded to info and tagged
  `blocked_by` instead of emitting a misleading secondary error. Every
  strategy finding now carries a `subject` for cascade matching.
- **Rule metadata audit** - every registered rule carries `semantic_inputs`,
  a design `context` (UPF_ONLY / NETLIST_REQUIRED / PARTIAL), and a
  `test_ref`. New `upf-insight rules audit` command verifies registry <->
  handler sync, metadata completeness, dependency integrity (no cycles,
  error-only prerequisites), and deterministic sorted ordering. 74 rules, all
  audited clean; `tests/test_rule_audit.py` locks the contract.
- **Evidence boundary (UNKNOWN != FALSE)** - the checker now enforces that a
  fact requiring a netlist is never reported as a definitive error: any
  error finding with NETLIST_REQUIRED support is downgraded to a warning.
  `tests/test_evidence_boundary.py` (10 tests) proves unknown crossings stay
  "may cross ... confirm", missing isolation stays a NETLIST_REQUIRED
  warning, declared voltage facts remain errors, and an empty file is
  NOT_VALIDATED, never VALIDATED.
- **Quality metrics + `upf-insight quality`** - the canonical mutation corpus
  moved into `engine/quality.py` so the CLI, API, and regression suite share
  one source of truth (no test-only copy). The command reports detection
  rate (42/42 = 100%), precision over error findings (28/38), precision over
  all findings, baseline errors/false positives (0/0), and a per-category
  breakdown, in text or `--json`. Exit code is deterministic.

## [0.2.3] - 2026-08-17

### Added - Adversarial coverage expansion (12 categories, 42 mutations)

Expanded mutation testing from 9 cases to a structured semantic matrix
covering every power-intent category the engine models:

- **Structured mutation matrix** - `tests/test_adversarial_coverage.py` (9
  tests): 42 deliberate defects across 11 categories - supply topology (5),
  power switch (8), level shifting (4), isolation (5), retention (5),
  always-on (2), PST (4), duplicates (3), supply connectivity (2), domain
  relations (2), unsupported syntax (2). Detection rate: **42/42**, with
  zero false positives on the clean baseline.
- **Parser fix - `set_port_attributes` multi-target** - the builder only
  recorded the first name in `set_port_attributes clk, rst, save, ...`;
  every target is now parsed, so switch/retention/isolation controls are
  actually recognized as always-on (surfaced real UPF-071/047/051 findings
  that were previously masked).
- **UPF-051 false positive fixed** - retention save/restore controls stored
  as `{name sense}` pairs are now compared by signal name, so a clean
  baseline no longer warns on controls that ARE declared always-on.
- **New rule UPF-065** - domain primary ground wired to a power-switch
  output (ground reference must be an always-on low rail).
- **New rule UPF-077** - power switch with no control port can never be
  toggled.
- **New rule UPF-078** - retention on a switchable domain with no retention
  supply cannot preserve state through power-down.
- **New rule UPF-079** - level-shifter threshold outside every known supply
  voltage is an implausible trip point (review).
- **UPF-060 is now voltage-aware** - when both sides of a crossing have
  known equal voltages the shifter is flagged unnecessary (warning); with
  unknown voltages it stays an info advisory. Removed the unconditional
  baseline info finding.

## [0.2.2] - 2026-08-17

### Added - Adversarial semantic validation (mutation testing)

Proves UPF-Insight catches intentionally broken power intent, not merely that
it accepts generated designs:

- **New rule UPF-039** - impossible PST state: a row declaring a switch
  output ON while its input supply is OFF is physically impossible (power
  appearing out of nowhere). Registered in the rule registry (now 68 rules).
- **UPF-073 upgraded info -> error** - a switch output consumed by no power
  domain is a real defect (the switchable domain is not powered by the
  switch), not an advisory.
- **UPF-053 is now sense-aware** - parses `{name sense}` retention control
  pairs and flags save/restore driven by the same signal with the same sense
  (error, cannot sequence) vs. opposite senses (the canonical IEEE 1801
  pattern).
- **`tests/test_adversarial_mutations.py`** - 12 tests: clean baseline must
  have 0 errors, 9 deliberate mutations each caught by the expected rule
  (break switched supply, disconnect switch output, wrong LS rule, remove
  LS, isolation at self, no retention elements, save/restore same sense,
  impossible PST, remove always-on), plus a SHA-256 determinism regression.
  Mutation detection rate: 9/9.
- Generator tests corrected to model the real topology (switchable domain
  consumes the switch output) so the upgraded UPF-073 stays clean on
  generated intent.

## [0.2.1] - 2026-08-17

### Fixed - Generator semantic hardening (external UPF audit)

Addresses the semantic-topology findings from an independent IEEE 1801 audit:

- **Switched-domain supply topology** - a switchable domain's primary supply
  is now the switch output (`set_domain_supply_net core
  -primary_power_net vdd_sw_out`), and the switch input is the upstream
  supply - `vdd -> switch -> vdd_sw_out -> core` is now the generated model.
- **Per-domain voltage** - new `DomainParam.voltage` (CLI `--domain-voltage`,
  API/UI column). The ON value of each supply in the PST is grounded in the
  owning domain's voltage (ground stays 0V), so level-shifter thresholds and
  `low_to_high` / `high_to_low` rules are meaningful. The validator's
  UPF-061 now fires on a real different-voltage crossing without a shifter.
- **Isolation direction** - `set_isolation` now emits explicit
  `-applies_to outputs` (strategy + relation-synthesized), so the boundary
  direction is never a silent UPF default.
- **Location correctness** - isolation and level shifters on a switchable
  domain are placed at `parent` (the always-on side), not `self`, so they
  keep their supply when the domain powers down (resolves UPF-063).
- **Retention elements + polarity** - `set_retention` carries explicit
  `-elements {regA regB}`, and `set_retention_control` emits save/restore
  with active sense (`-save_signal {save high}` / `-restore_signal
  {restore low}`) instead of bare names.
- **Meaningful PST** - default rows are ALL_ON plus one `sw.<name>.off` per
  switch (VDD ON, switch output OFF); the physically impossible PS_OFF
  (VDD OFF while the switch output is ON) is gone. Only port states actually
  referenced by the PST are declared, so UPF-030 never fires on generated
  output.
- **Level-shifter `-applies_to`** - `set_level_shifter` emits
  `-applies_to both` (and `inputs`/`outputs` when authored) so the covered
  boundary is explicit.

### Added - CLI / API / UI

- CLI `generate --domain-voltage NAME:VOLTS` and `--retention-spec
  DOMAIN[:SUPPLY[:SAVE[:RESTORE[:ELEMENTS]]]]`.
- Generator UI: Voltage column on domains, Applies-to on isolation and
  level shifters, Save/restore sense + Elements on retention, PST default
  ALL_ON.

### Tests

- 6 new regression tests covering applies-to, parent location, retention
  elements/polarity, voltage-grounded PST with UPF-061 detection, meaningful
  default PST (no UPF-030), and CLI voltage/retention-spec.

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
