"""Netlist-aware port coverage: UPF port intent vs. the design snapshot.

The analog of :mod:`upf_insight.engine.coverage` at port granularity:
every netlist port is bucketed as

- ``CONSTRAINED``      - named by ``set_port_attributes`` with attributes;
- ``PARTIAL``          - bound to a domain element or mentioned with empty
  attributes, but never given real attributes;
- ``UNCONSTRAINED``    - present in the design, absent from the UPF;
- ``NOT_APPLICABLE``   - constrained in the UPF but not present in the design.

Coverage is structural evidence only - it reports what the power intent
*touches*, never whether the design is correct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ...model.power_model import PowerIntentModel
from .design_context import DesignContext

__all__ = ["PortCoverage", "DesignCoverageResult", "analyze_design_coverage"]

CONSTRAINED = "CONSTRAINED"
UNCONSTRAINED = "UNCONSTRAINED"
PARTIAL = "PARTIAL"
NOT_APPLICABLE = "NOT_APPLICABLE"

_STATUS_ORDER = (CONSTRAINED, PARTIAL, UNCONSTRAINED, NOT_APPLICABLE)


@dataclass
class PortCoverage:
    port: str
    direction: str
    status: str
    evidence: str = ""

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "direction": self.direction,
            "status": self.status,
            "evidence": self.evidence,
        }


@dataclass
class DesignCoverageResult:
    status: str = "OK"
    domain_count: int = 0
    input_ports: Dict[str, int] = field(default_factory=dict)
    output_ports: Dict[str, int] = field(default_factory=dict)
    ports: List[PortCoverage] = field(default_factory=list)
    unconstrained_inputs: List[str] = field(default_factory=list)
    unconstrained_outputs: List[str] = field(default_factory=list)
    ratios: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "domain_count": self.domain_count,
            "input_ports": {k: self.input_ports[k] for k in sorted(self.input_ports)},
            "output_ports": {k: self.output_ports[k] for k in sorted(self.output_ports)},
            "ports": [p.to_dict() for p in sorted(self.ports, key=lambda p: p.port)],
            "unconstrained_inputs": self.unconstrained_inputs,
            "unconstrained_outputs": self.unconstrained_outputs,
            "ratios": {k: self.ratios[k] for k in sorted(self.ratios)},
            "notes": self.notes,
            "coverage_is_not_correctness": True,
        }


def _domain_element_names(model: PowerIntentModel) -> Dict[str, str]:
    """Map each domain element (bare name) to its owning domain."""
    bindings: Dict[str, str] = {}
    for key in sorted(model.domains):
        dom = model.domains[key]
        for element in dom.elements:
            bare = element.rsplit("/", 1)[-1].strip()
            if bare and bare not in bindings:
                bindings[bare] = dom.name
    return bindings


def _classify(port: str, attrs: List[str],
              binding: Optional[str]) -> Tuple[str, str]:
    if any(attr.strip() for attr in attrs):
        return CONSTRAINED, "set_port_attributes"
    evidence_bits: List[str] = []
    if attrs:
        evidence_bits.append("set_port_attributes with no attribute value")
    if binding is not None:
        evidence_bits.append(f"bound to domain {binding}")
    if not evidence_bits:
        return UNCONSTRAINED, ""
    return PARTIAL, "; ".join(evidence_bits)


def analyze_design_coverage(model: PowerIntentModel,
                            context: Optional[DesignContext]) -> DesignCoverageResult:
    """Cross-reference UPF port intent against the netlist snapshot."""
    result = DesignCoverageResult()
    result.notes.append("coverage_is_not_correctness")
    result.domain_count = len(model.domains)

    design_ports: List[str]
    directions: Dict[str, str]
    if context is None or not context.ports:
        result.status = "INSUFFICIENT_CONTEXT"
        result.notes.append("insufficient_context")
        for status in _STATUS_ORDER:
            result.input_ports[status] = 0
            result.output_ports[status] = 0
        result.ratios = {"input_port_coverage": 0.0, "output_port_coverage": 0.0}
        return result

    design_ports = sorted(set(context.ports))
    directions = dict(getattr(context, "port_directions", {}) or {})

    attributes = model.port_attributes
    bindings = _domain_element_names(model)

    input_counts: Dict[str, int] = {status: 0 for status in _STATUS_ORDER}
    output_counts: Dict[str, int] = {status: 0 for status in _STATUS_ORDER}
    unconstrained_inputs: List[str] = []
    unconstrained_outputs: List[str] = []
    covered_inputs = 0
    total_inputs = 0
    covered_outputs = 0
    total_outputs = 0
    off_bucket_note = False

    for port in design_ports:
        direction = directions.get(port, "unknown")
        attrs = list(attributes.get(port, []))
        binding = bindings.get(port)
        status, evidence = _classify(port, attrs, binding)
        result.ports.append(
            PortCoverage(port=port, direction=direction, status=status,
                         evidence=evidence))
        if direction == "input":
            input_counts[status] += 1
            total_inputs += 1
            if status == CONSTRAINED:
                covered_inputs += 1
            elif status == UNCONSTRAINED:
                unconstrained_inputs.append(port)
        elif direction == "output":
            output_counts[status] += 1
            total_outputs += 1
            if status == CONSTRAINED:
                covered_outputs += 1
            elif status == UNCONSTRAINED:
                unconstrained_outputs.append(port)
        else:
            off_bucket_note = True

    result.input_ports = input_counts
    result.output_ports = output_counts
    result.unconstrained_inputs = sorted(unconstrained_inputs)
    result.unconstrained_outputs = sorted(unconstrained_outputs)
    result.ratios = {
        "input_port_coverage":
            round(covered_inputs / total_inputs, 2) if total_inputs else 0.0,
        "output_port_coverage":
            round(covered_outputs / total_outputs, 2) if total_outputs else 0.0,
    }
    if off_bucket_note:
        result.notes.append(
            "inout_or_unknown_direction_ports_excluded_from_directional_buckets")
    return result
