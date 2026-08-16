# UPF-Insight — Glossary

> **Document kind:** company reference.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## A

- **Always-on** — logic or supplies that must stay powered in every mode
  (e.g. clock, reset, scan, isolation control). Always-on signals crossing
  into switchable domains must be isolated.

## C

- **Check** — the act of running the rule engine over a power-intent model and
  producing findings with provenance.
- **Composite domain** — a UPF 3.0 abstraction grouping multiple domains for
  boundary modeling.

## D

- **Design-aware** — validation that needs a netlist/RTL context (layer 6,
  v2). Without it, reference checks stay at the model level.
- **Determinism** — same input → same findings → same exit code, every time.
- **Diff** — semantic model-level comparison of two UPF versions
  (ADD/REMOVE/MODIFY).

## F

- **Finding** — one rule violation with `rule`, `severity`, `message`, `file`,
  `line`, `support`.

## I

- **IEEE 1801** — the UPF standard.
- **Isolation** — a strategy that clamps or holds signals at a domain boundary
  so a powered-down domain does not corrupt always-on receivers.
- **Isolation cell** — the physical cell implementing isolation, fed by an
  always-on supply.

## L

- **Level shifter** — a cell translating signal voltage between domains at
  different supply voltages.
- **Load order** — the sequence in which UPF files (and `load_upf`) are read;
  ordering can cause use-before-definition defects.

## M

- **Model** — the in-memory power-intent object graph (domains, supplies,
  switches, states, PST, strategies) that rules query.

## P

- **Power domain** — a named group of logic treated as one power-management
  unit.
- **Power State Table (PST)** — the table of legal operating modes
  (`create_pst` + `add_pst_state`). The contract for isolation/level-shifter
  policy.
- **Power switch** — a power-gating cell controlled by always-on logic.
- **Primary supply** — the domain's main power/ground assignment.

## R

- **Readiness** — a planned aggregate verdict (READY…BLOCKED) over validation
  + scope + PST + coverage.
- **Retention** — a strategy that saves/restores sequential state across
  power-down.
- **Rule** — one deterministic check in the registry (UPF-NNN).

## S

- **Scope** — the current hierarchical position (`set_scope`).
- **Strategy** — protection policy (isolation, level shifter, retention).
- **Support boundary** — what the engine validated vs partially validated vs
  skipped; always disclosed.
- **Supply net / port / set** — the power rail / boundary connection / grouped
  supply-by-function.
- **Supply state** — a legal state of one supply (e.g. ON 1.0, OFF 0.0).

## U

- **UPF (Unified Power Format)** — IEEE 1801 language for power intent.
- **Use-before-definition** — referencing an object before its defining
  command (load-order defect).
- **Unsupported** — a command parsed but not modeled; recorded in the support
  boundary.

## V

- **Validate** — the product module that runs the rule engine.
- **VCT/VCM** — value-conversion types (UPF 3.0) connecting UPF supplies to
  HDL pins.