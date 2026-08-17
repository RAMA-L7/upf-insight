"""Power State Table (PST) analyzer.

Expands and validates the power-state table of a PowerIntentModel:

- state inventory (declared vs used)
- legal-combination coverage
- transition consistency
- isolation / level-shifter policy conditioning

Produces a deterministic report; the checker's UPF-03x rules consume the same
data. Mirror of the sdc-tools `clock_relations`/`constraint_readiness` style.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ...model.power_model import PowerIntentModel, Pst


@dataclass
class PstAnalysis:
    pst_name: Optional[str] = None
    state_count: int = 0
    declared_supply_states: List[str] = field(default_factory=list)
    used_supply_states: List[str] = field(default_factory=list)
    unused_states: List[str] = field(default_factory=list)
    undeclared_states: List[str] = field(default_factory=list)
    transitions: List[tuple] = field(default_factory=list)
    coverage_note: str = ""
    cross_state_events: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pst_name": self.pst_name,
            "state_count": self.state_count,
            "declared_supply_states": self.declared_supply_states,
            "used_supply_states": self.used_supply_states,
            "unused_states": self.unused_states,
            "undeclared_states": self.undeclared_states,
            "transitions": [list(t) for t in self.transitions],
            "coverage_note": self.coverage_note,
            "cross_state_events": self.cross_state_events,
        }


def analyze_pst(model: PowerIntentModel) -> PstAnalysis:
    """Analyze the (first) PST of the model and its declared supply states."""
    analysis = PstAnalysis()
    declared = {s.name for s in model.supply_states}
    analysis.declared_supply_states = sorted(declared)

    if not model.psts:
        analysis.coverage_note = "No PST found; power-state coverage cannot be verified."
        return analysis

    pst: Pst = next(iter(model.psts.values()))
    analysis.pst_name = pst.name
    analysis.state_count = len(pst.states)

    # Used states = the supply-state *values* referenced across PST rows
    # (e.g. `-state {vdd ON vss ON}` uses ON/ON).
    used = set()
    for state in pst.states:
        used.update(state.supply_states.values())
    analysis.used_supply_states = sorted(used)

    analysis.unused_states = sorted(declared - used)
    analysis.undeclared_states = sorted(used - declared)
    analysis.transitions = list(pst.transitions)
    analysis.cross_state_events = analyze_cross_state(model)

    if not pst.states:
        analysis.coverage_note = "PST exists but has zero states - no legal power combination declared."
    elif analysis.undeclared_states:
        analysis.coverage_note = (
            f"PST references {len(analysis.undeclared_states)} undeclared state(s)."
        )
    elif analysis.unused_states:
        analysis.coverage_note = (
            f"{len(analysis.unused_states)} declared state(s) never appear in the PST."
        )
    else:
        analysis.coverage_note = "All declared states are used by the PST."
    return analysis


def _value_kind(value: str) -> str:
    """Classify a supply-state value as ``ON`` / ``OFF`` / ``HIGHZ``.

    Deterministic heuristic: ``OFF`` if the name says so, ``HIGHZ`` for explicit
    tri-state tokens, otherwise assume powered (declared states are legal).
    """
    v = value.strip().lower()
    if "off" in v:
        return "OFF"
    if v in ("hiz", "highz", "high_z", "hi_z", "z") or "highz" in v or "high_z" in v:
        return "HIGHZ"
    return "ON"


def _resolve_domain_power(model: PowerIntentModel, dom) -> Optional[str]:
    """Resolve a domain's primary power to an underlying net/set name.

    A supply-set reference is resolved through its ``power`` function so
    switchability against power-switch outputs is exact. Mirror of the rule
    layer's resolver, kept local to avoid an import cycle.
    """
    def resolve_power(val: str) -> Optional[str]:
        key = model.scope_key(val, model.current_scope)
        ss = model.supply_sets.get(key) or model.supply_sets.get(val)
        if ss is not None:
            func = ss.functions.get("power") or ss.functions.get("power_switch")
            if func:
                return func
            return val
        return val

    ps = dom.primary_supply_sets
    if "primary_power_net" in ps:
        return resolve_power(ps["primary_power_net"])
    if "primary" in ps:
        return resolve_power(ps["primary"])
    for k, v in ps.items():
        if k.lower() == "power":
            return resolve_power(v)
    return None


def _domain_status(model: PowerIntentModel, dom, state) -> str:
    """A domain's power status (``ON``/``OFF``/``HIGHZ``/``UNKNOWN``) in a PST row."""
    net = _resolve_domain_power(model, dom)
    if net is None:
        return "UNKNOWN"
    val = state.supply_states.get(net)
    if val is None:
        return "UNKNOWN"
    return _value_kind(val)


def analyze_cross_state(model: PowerIntentModel) -> List[dict]:
    """Strict cross-state transition / tri-state analysis.

    Returns a deterministic list of events:
      * ``power_down`` -- a switchable domain is ``ON`` in the source state and
        ``OFF``/``HIGHZ`` in the destination while another domain stays ``ON``
        (an un-isolated crossing may float). ``isolated`` records whether the
        downing domain has an active isolation/clamp.
      * ``unmodeled_switch`` -- a switchable domain's power net (a power-switch
        output) never appears in any PST row, so its tri-state/floating
        behavior cannot be verified.

    A transition in which every switchable domain powers down together is a
    legal standby (no ``ON`` receiver) and is NOT flagged.
    """
    events: List[dict] = []
    switched = {sw.output_supply for sw in model.switches.values() if sw.output_supply}
    if not switched or not model.psts:
        return events
    isolated = {
        iso.domain for iso in model.isolation
        if iso.clamp_value and iso.control_signal
    }

    for pst in model.psts.values():
        states_by_name = {s.name: s for s in pst.states}
        modeled_nets = set()
        for state in pst.states:
            modeled_nets.update(state.supply_states.keys())

        # Tri-state / floating: switchable net never modeled by the PST.
        for dom in model.domains.values():
            net = _resolve_domain_power(model, dom)
            if net and net in switched and net not in modeled_nets:
                events.append({
                    "type": "unmodeled_switch",
                    "pst": pst.name,
                    "domain": dom.name,
                    "net": net,
                })

        # Cross-state: un-isolated power-down into a live receiver.
        for src_name, dst_name in pst.transitions:
            src = states_by_name.get(src_name)
            dst = states_by_name.get(dst_name)
            if src is None or dst is None:
                continue
            for dom in model.domains.values():
                net = _resolve_domain_power(model, dom)
                if not net or net not in switched:
                    continue
                from_kind = _domain_status(model, dom, src)
                to_kind = _domain_status(model, dom, dst)
                if from_kind != "ON" or to_kind not in ("OFF", "HIGHZ"):
                    continue
                receivers = [
                    d.name for d in model.domains.values()
                    if d.name != dom.name
                    and _domain_status(model, d, dst) == "ON"
                ]
                if not receivers:
                    continue
                events.append({
                    "type": "power_down",
                    "pst": pst.name,
                    "src": src_name,
                    "dst": dst_name,
                    "domain": dom.name,
                    "from": from_kind,
                    "to": to_kind,
                    "receivers": receivers,
                    "isolated": dom.name in isolated,
                })
    return events


__all__ = ["PstAnalysis", "analyze_pst", "analyze_cross_state", "_value_kind"]