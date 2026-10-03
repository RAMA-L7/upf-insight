"""Pipeline stage taxonomy for findings.

A flat list of rule codes hides *where* something went wrong. A parser bug, a
normalization bug and a genuine design violation look identical in a report
unless you already know which layer produced them.

The pipeline is:

    UPF source
       -> Tcl/UPF parse        (PARSE)
       -> normalized IR         (NORMALIZATION)
       -> model construction    (MODEL)
       -> semantic rules        (SEMANTIC)
       -> design/netlist checks (DESIGN)

Each finding is tagged with the stage that produced it, so a reader can tell
"the tool could not read this" from "the tool read it and the design is wrong".

This is metadata only. It never changes a severity, never suppresses a
finding, and never reclassifies one as acceptable — it records *where* a
finding came from so failures can be attributed instead of guessed at.
"""

from __future__ import annotations

from typing import Dict, List

#: Stage identifiers, in pipeline order.
PARSE = "PARSE"
NORMALIZATION = "NORMALIZATION"
MODEL = "MODEL"
SEMANTIC = "SEMANTIC"
DESIGN = "DESIGN"

STAGES = (PARSE, NORMALIZATION, MODEL, SEMANTIC, DESIGN)

#: Human-readable meaning of each stage, for reports and docs.
STAGE_DESCRIPTIONS = {
    PARSE: "The Tcl/UPF lexer could not read the input as commands.",
    NORMALIZATION: "The input parsed, but a construct was not mapped onto "
                  "the IR faithfully (brace groups, pairs, wildcards, "
                  "positional lists).",
    MODEL: "Commands were read, but the resulting object graph is "
           "incomplete or self-contradictory (undeclared references, "
           "duplicate definitions, unresolvable scopes).",
    SEMANTIC: "The model is well-formed; the declared power intent violates "
              "a semantic requirement of IEEE 1801.",
    DESIGN: "The check requires the design (netlist/RTL) to decide, and was "
            "answered against it — a mismatch between UPF and the design.",
}

#: Rules that report on text the lexer could not interpret.
_PARSE_RULES = frozenset({"UPF-001", "UPF-002", "UPF-003", "UPF-004",
                          "UPF-005", "UPF-006"})

#: Rules whose subject is the shape of a construct rather than the intent.
#: A hit here means the IR did not represent the input faithfully.
_NORMALIZATION_RULES = frozenset({"UPF-024", "UPF-087", "UPF-031"})

#: Rules about the object graph itself: references and definitions.
_MODEL_RULES = frozenset({
    "UPF-010", "UPF-011", "UPF-012", "UPF-013", "UPF-014",
    "UPF-015", "UPF-016", "UPF-020", "UPF-021", "UPF-022", "UPF-023",
    "UPF-024", "UPF-025", "UPF-097",
})


def stage_for(rule: str, support: str = "") -> str:
    """Return the pipeline stage that produced ``rule``.

    ``support`` refines the answer where the registry already encodes it:
    a NETLIST_REQUIRED finding is a DESIGN-stage check by definition, since
    it exists precisely because the design context was absent.
    """
    if support == "NETLIST_REQUIRED":
        return DESIGN
    if rule in _PARSE_RULES:
        return PARSE
    if rule in _NORMALIZATION_RULES:
        return NORMALIZATION
    if rule in _MODEL_RULES:
        return MODEL
    return SEMANTIC


def findings_by_stage(findings) -> Dict[str, int]:
    """Count findings per stage, in pipeline order, zeros included."""
    counts = {s: 0 for s in STAGES}
    for f in findings:
        counts[stage_for(f.rule, getattr(f, "support", ""))] += 1
    return counts


def stage_report(findings) -> dict:
    """A stage breakdown suitable for embedding in a report or a CLI surface."""
    counts = findings_by_stage(findings)
    total = sum(counts.values())
    return {
        "stages": counts,
        "total": total,
        "descriptions": dict(STAGE_DESCRIPTIONS),
        # A tool that cannot read its input should not be judged on the
        # semantic findings it produced anyway; this makes the split visible.
        "readable_ratio": (
            round((total - counts[PARSE] - counts[NORMALIZATION]) / total, 4)
            if total else 1.0
        ),
    }


__all__ = [
    "PARSE", "NORMALIZATION", "MODEL", "SEMANTIC", "DESIGN", "STAGES",
    "STAGE_DESCRIPTIONS", "stage_for", "findings_by_stage", "stage_report",
]