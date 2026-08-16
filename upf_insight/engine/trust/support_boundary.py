"""Trust / support boundary for UPF validation.

Mirrors the sdc-tools support_boundary model: UPF-Insight reports what it
validated, what it partially validated, and what it skipped. A clean result
means "no rule fired", never "power intent proven correct".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ...model.power_model import PowerIntentModel

#: Support status vocabulary (mirrors sdc-tools)
VALIDATED = "VALIDATED"
PARTIALLY_VALIDATED = "PARTIALLY_VALIDATED"
NETLIST_REQUIRED = "NETLIST_REQUIRED"
TCL_EXECUTION_REQUIRED = "TCL_EXECUTION_REQUIRED"
UNSUPPORTED = "UNSUPPORTED"
NOT_VALIDATED = "NOT_VALIDATED"


@dataclass
class SupportReport:
    statuses: Dict[str, int]
    notes: List[str]

    def to_dict(self) -> dict:
        return {"statuses": self.statuses, "notes": self.notes}


def compute_support_boundary(model: PowerIntentModel) -> SupportReport:
    """Derive the support boundary for a validated model.

    - Every unsupported command lowers validation completeness.
    - Power-switch / PST / voltage-dependent rules are PARTIAL without a
      netlist and a complete power-state table.
    - Design-aware rules (UPF-080…) require NETLIST_REQUIRED context.
    """
    counts: Dict[str, int] = {
        VALIDATED: 0,
        PARTIALLY_VALIDATED: 0,
        NETLIST_REQUIRED: 0,
        TCL_EXECUTION_REQUIRED: 0,
        UNSUPPORTED: 0,
        NOT_VALIDATED: 0,
    }
    notes: List[str] = []

    # No UPF commands parsed at all: nothing was validated. This must take
    # precedence over the VALIDATED credit below, or an empty file would be
    # reported as fully validated.
    if model.commands_seen == 0:
        counts[NOT_VALIDATED] = 1
        notes.append("No UPF commands were parsed.")
        return SupportReport(statuses=counts, notes=notes)

    if model.unsupported_commands:
        counts[UNSUPPORTED] = len(model.unsupported_commands)
        notes.append(
            f"{len(model.unsupported_commands)} command(s) were parsed but not "
            f"modeled (support boundary)."
        )
    else:
        counts[VALIDATED] += 1

    if model.psts:
        counts[VALIDATED] += 1
    elif model.supply_states:
        counts[PARTIALLY_VALIDATED] += 1
        notes.append("Power states exist but no complete PST — voltage-dependent "
                     "rules run at reduced (PARTIAL) strength.")

    if model.switches:
        counts[PARTIALLY_VALIDATED] += 1
        notes.append("Power-switch semantics require supply-state analysis; "
                     "switch checks are PARTIAL without it.")

    # Design-aware layer is out of scope for v1 (no netlist reader yet).
    design = getattr(model, "design", None)
    if design is None:
        counts[NETLIST_REQUIRED] += 1
        notes.append("Design-aware rules (UPF-080..084) require a netlist/RTL "
                     "context, which v1 does not provide.")

    # Detect Tcl execution constructs without executing them.
    for cmd in model.unsupported_commands:
        if "exec" in cmd.lower() or "source" in cmd.lower():
            counts[TCL_EXECUTION_REQUIRED] += 1
    if counts[TCL_EXECUTION_REQUIRED]:
        notes.append("Tcl execution constructs detected but never executed.")

    if not any(v for v in counts.values()):
        counts[NOT_VALIDATED] = 1
        notes.append("No UPF commands were parsed.")

    return SupportReport(statuses=counts, notes=notes)


__all__ = [
    "VALIDATED",
    "PARTIALLY_VALIDATED",
    "NETLIST_REQUIRED",
    "TCL_EXECUTION_REQUIRED",
    "UNSUPPORTED",
    "NOT_VALIDATED",
    "SupportReport",
    "compute_support_boundary",
]