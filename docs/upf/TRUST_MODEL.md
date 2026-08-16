# UPF-Insight — Trust Model

> **Document kind:** engineering/trust architecture.
> **Date:** 2026-08-14 · **Version:** v0.1.0

---

## 1. The core honesty principle

UPF-Insight reports **what it validated**, **what it partially validated**,
and **what it skipped**. Three statements are always kept prominent:

> **Clean ≠ power proven correct.** **Coverage ≠ correctness.**
> **CI pass ≠ low-power closure.**

A result of "no findings" means *no deterministic rule fired* against the
model that was built. It does not mean the power intent is safe, legal, or
complete.

## 2. Support statuses

Every validation run derives a support boundary from the model:

| Status | Meaning |
|---|---|
| `VALIDATED` | The check was fully performed against the modeled intent. |
| `PARTIALLY_VALIDATED` | The check ran at reduced strength (e.g. retention always-on needs a complete supply-state/PST model). |
| `NETLIST_REQUIRED` | The check needs a netlist/RTL context not supplied (design-aware rules UPF-080…084 in v1). |
| `TCL_EXECUTION_REQUIRED` | The intent requires executing Tcl constructs to resolve. Tcl is **detected, never executed**. |
| `UNSUPPORTED` | A command was parsed but not modeled; its semantics are outside the support boundary. |
| `NOT_VALIDATED` | No UPF commands were parsed at all. |

The boundary is deterministic: the same input always yields the same
boundary.

## 3. What the v1 engine validates

Layers 1–5 of the rule catalog, fully static:

1. **Syntax & version** — unknown commands, illegal options, missing
   arguments, malformed Tcl.
2. **Reference integrity** — undefined domains/supplies, duplicates,
   use-before-definition, load-order issues.
3. **Supply & domain integrity** — missing primary supply, unconnected
   supplies, supply sets without power/ground functions.
4. **Power State Table** — declared vs used states, missing PST, duplicates.
5. **Strategy lint** — isolation control, retention supply/elements,
   level-shifter advisories, always-on correctness at the static level.

## 4. What v1 does NOT validate

- **Design awareness** (UPF-080…084): instance existence, control-signal
  existence, endpoint-based crossing coverage, retention coverage vs actual
  flip-flops, library PG mapping. These require a netlist/RTL context and are
  planned for v2. The boundary is always disclosed (`NETLIST_REQUIRED`).
- **Tcl execution**: any construct that requires running Tcl to resolve is
  never executed — it is detected and surfaced as
  `TCL_EXECUTION_REQUIRED` / `UNSUPPORTED`.
- **Electrical/timing truth**: UPF-Insight is not a power/IR analyzer and not
  an STA tool.

## 5. Evidence

Every finding carries provenance:

- `rule` — the registry code (UPF-040 etc.)
- `severity` — error / warning / info
- `file` + `line` — where the evidence lives in the source UPF
- `support` — the status under which the finding was produced

Findings without a line (e.g. cross-referenced strategies) state their
support level explicitly. Dual-line findings (rule references two locations)
are planned.

## 6. Determinism guarantee

- No randomness, no LLM, no network. Same input → same model → same findings
  → same exit code, on every machine.
- Rule handlers may never crash the run: the checker catches handler
  exceptions and reports them as engine-scope findings.
- Iteration over model dictionaries is sorted before emission where order
  could affect output.

## 7. Local-first guarantee

Analysis runs entirely on the local machine. The workspace is a stdlib-only
HTTP server bound to `127.0.0.1`. Nothing is uploaded; no analytics are
collected.

## 8. Readiness vocabulary (planned)

Readiness verdicts (v2, mirroring the sdc-tools model):

`READY` · `READY_WITH_ADVISORIES` · `REVIEW_REQUIRED` · `BLOCKED` ·
`INSUFFICIENT_CONTEXT`

A readiness verdict aggregates check + scope + PST + coverage into a
handoff-oriented answer, with the same honesty framing.

## 9. Rule severity semantics

| Severity | Meaning |
|---|---|
| `error` | The modeled intent is inconsistent or unsafe (e.g. isolation without control, undefined domain). |
| `warning` | A real risk that the static layer can only partially confirm (e.g. retention always-on needs PST). |
| `info` | An advisory that is not wrong but worth review (e.g. potentially unnecessary level shifter). |

Severity lives in the registry and can be overridden by custom rulesets
(planned).