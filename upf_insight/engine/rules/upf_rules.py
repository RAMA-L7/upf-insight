"""UPF rule implementations - deterministic handlers keyed by rule code.

Each handler takes a PowerIntentModel and returns a list of Finding. Handlers
are registered in RULE_HANDLERS; the checker dispatches registered rules to
them. Mirror of sdc-tools rule style: pure, evidence-first, no side effects.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from ...model.power_model import PowerIntentModel
from .finding import Finding
from ..pst.analyzer import analyze_cross_state

#: handler signature: (model) -> list[Finding]
RuleHandler = Callable[[PowerIntentModel], List[Finding]]

RULE_HANDLERS: Dict[str, RuleHandler] = {}


def _register(code: str):
    def deco(fn: RuleHandler) -> RuleHandler:
        RULE_HANDLERS[code] = fn
        return fn

    return deco


def _supply_lookup(model: PowerIntentModel, name: str,
                   scope: Optional[str] = None):
    """Resolve a supply name to (net|set|port, scope) if it exists.

    ``scope`` is the scope the reference appears in (a strategy's declared
    scope); the name is resolved as ``<scope>/<name>`` first so child-scoped
    supplies like ``core_a/vdd_core_sw`` resolve to their own scope even
    when the model's current scope points elsewhere at rule time. Falls back
    to the model's current scope, then to a bare-name match."""
    for sc in (scope, model.current_scope):
        if not sc or sc in (".", ""):
            continue
        key = model.scope_key(name, sc)
        if key in model.supply_nets:
            return "net", key
        if key in model.supply_sets:
            return "set", key
        if key in model.supply_ports:
            return "port", key
    key = model.scope_key(name, model.current_scope)
    if key in model.supply_nets:
        return "net", key
    if key in model.supply_sets:
        return "set", key
    if key in model.supply_ports:
        return "port", key
    # fall back to bare-name match
    for kind, table in (("net", model.supply_nets), ("set", model.supply_sets),
                        ("port", model.supply_ports)):
        if name in table:
            return kind, name
    return None, None


# ---------------------------------------------------------------------------
# Layer 1 - Syntax
# ---------------------------------------------------------------------------

@_register("UPF-001")
def _unknown_command(model: PowerIntentModel):
    return [
        Finding(rule="UPF-001", severity="error",
                message=f"Unknown UPF command: '{cmd}'",
                support="UNSUPPORTED")
        for cmd in model.unsupported_commands
    ]


@_register("UPF-002")
def _illegal_option(model: PowerIntentModel):
    return [
        Finding(rule="UPF-002", severity="error",
                message=s["message"], line=s["line"], support=s.get("support"))
        for s in model.syntax_issues if s["rule"] == "UPF-002"
    ]


@_register("UPF-003")
def _missing_required_argument(model: PowerIntentModel):
    return [
        Finding(rule="UPF-003", severity="error",
                message=s["message"], line=s["line"], support=s.get("support"))
        for s in model.syntax_issues if s["rule"] == "UPF-003"
    ]


@_register("UPF-004")
def _unsupported_version(model: PowerIntentModel):
    return [
        Finding(rule="UPF-004", severity="warning",
                message=s["message"], line=s["line"], support=s.get("support"))
        for s in model.syntax_issues if s["rule"] == "UPF-004"
    ]


@_register("UPF-005")
def _deprecated_syntax(model: PowerIntentModel):
    return [
        Finding(rule="UPF-005", severity="warning",
                message=s["message"], line=s["line"], support=s.get("support"))
        for s in model.syntax_issues if s["rule"] == "UPF-005"
    ]


@_register("UPF-006")
def _malformed_tcl(model: PowerIntentModel):
    return [
        Finding(rule="UPF-006", severity="error",
                message=s["message"], line=s["line"], support=s.get("support"))
        for s in model.syntax_issues if s["rule"] == "UPF-006"
    ]


# ---------------------------------------------------------------------------
# Layer 3 - Supply & domain integrity
# ---------------------------------------------------------------------------

@_register("UPF-020")
def _domain_missing_primary(model: PowerIntentModel):
    findings = []
    for key, dom in model.domains.items():
        if not dom.primary_supply_sets:
            findings.append(Finding(
                rule="UPF-020", severity="error",
                message=f"Power domain '{dom.name}' has no primary supply "
                        f"(-primary_supply_set / set_domain_supply_net).",
                line=dom.declared_line))
    return findings


@_register("UPF-022")
def _unconnected_supplies(model: PowerIntentModel):
    findings = []
    for key, net in model.supply_nets.items():
        if not net.connected_to:
            findings.append(Finding(
                rule="UPF-022", severity="warning",
                message=f"Supply net '{net.name}' is not connected to any "
                        f"supply port/net/set.",
                line=net.declared_line))
    return findings


@_register("UPF-023")
def _supply_set_missing_functions(model: PowerIntentModel):
    findings = []
    for key, ss in model.supply_sets.items():
        if "power" not in ss.functions and "ground" not in ss.functions:
            findings.append(Finding(
                rule="UPF-023", severity="error",
                message=f"Supply set '{ss.name}' has no power or ground function.",
                line=ss.declared_line))
    return findings


@_register("UPF-021")
def _domain_element_overlap(model: PowerIntentModel):
    """An instance may belong to only one power domain."""
    findings = []
    owner: dict = {}
    for key, dom in model.domains.items():
        for elem in dom.elements:
            prev = owner.get(elem)
            if prev is not None and prev != dom.name:
                findings.append(Finding(
                    rule="UPF-021", severity="error",
                    message=f"Instance '{elem}' belongs to both power domains "
                            f"'{prev}' and '{dom.name}'.",
                    line=dom.declared_line))
            owner.setdefault(elem, dom.name)
    return findings


@_register("UPF-024")
def _supply_connectivity_mismatch(model: PowerIntentModel):
    """A supply net connected to an unknown/undeclared target."""
    findings = []
    known_ports = {p.name for p in model.supply_ports.values()}
    known_nets = {n.name for n in model.supply_nets.values()}
    for key, net in model.supply_nets.items():
        for target in net.connected_to:
            # target may be a bare name, a set name, or a {net ...} group.
            t = target.strip("{}")
            if t.startswith("net "):
                t = t.split()[1]
            if t not in known_ports and t not in known_nets and \
                    t not in model.supply_sets:
                findings.append(Finding(
                    rule="UPF-024", severity="warning",
                    message=f"Supply net '{net.name}' is connected to unknown "
                            f"target '{target}' (not a declared port/net/set).",
                    line=net.declared_line))
    return findings


@_register("UPF-025")
def _unused_supply_state(model: PowerIntentModel):
    """A supply state/voltage is declared but never referenced."""
    findings = []
    used_parents: set = set()
    for pst in model.psts.values():
        for state in pst.states:
            used_parents.update(state.supply_states.keys())
    for ss in model.supply_sets.values():
        for func in ss.functions.values():
            used_parents.add(func.strip("{}"))
    for st in model.supply_states:
        if st.parent not in used_parents:
            findings.append(Finding(
                rule="UPF-025", severity="info",
                message=f"Supply state '{st.name}' on '{st.parent}' is never "
                        f"referenced by a PST or supply-set function.",
                line=st.declared_line))
    return findings


# ---------------------------------------------------------------------------
# Layer 4 - PST
# ---------------------------------------------------------------------------

def _declared_supply_states(model: PowerIntentModel) -> Dict[str, set]:
    """Map supply name -> set of declared state names (from add_port_state /
    add_supply_state)."""
    per_supply: Dict[str, set] = {}
    for st in model.supply_states:
        per_supply.setdefault(st.parent, set()).add(st.name)
    return per_supply


def _pst_state_combinations(pst) -> List[set]:
    """Each PST row's (supply, state) pairs as a set for overlap checks."""
    return [
        frozenset((s, v) for s, v in state.supply_states.items())
        for state in pst.states
    ]


@_register("UPF-030")
def _declared_state_never_used(model: PowerIntentModel):
    """A declared supply state never used by the PST is a coverage gap."""
    findings = []
    if not model.psts:
        return findings
    used: set = set()
    for pst in model.psts.values():
        for state in pst.states:
            used.update((s, v) for s, v in state.supply_states.items())
    for st in model.supply_states:
        if (st.parent, st.name) not in used:
            findings.append(Finding(
                rule="UPF-030", severity="error",
                message=f"Supply state '{st.name}' on supply '{st.parent}' is "
                        f"declared but never used by the PST.",
                line=st.declared_line))
    return findings


@_register("UPF-031")
def _pst_uses_undeclared_state(model: PowerIntentModel):
    """A PST row uses a supply state that was never declared."""
    findings = []
    declared = _declared_supply_states(model)
    for pst in model.psts.values():
        for state in pst.states:
            for supply, value in state.supply_states.items():
                if value not in declared.get(supply, set()):
                    findings.append(Finding(
                        rule="UPF-031", severity="error",
                        message=f"PST '{pst.name}' state '{state.name}' uses "
                                f"undeclared state '{value}' on supply "
                                f"'{supply}'.",
                        line=state.declared_line))
    return findings


@_register("UPF-032")
def _missing_pst(model: PowerIntentModel):
    if model.supply_states and not model.psts:
        return [Finding(
            rule="UPF-032", severity="warning",
            message="Power states are declared but no create_pst was issued.",
            support="PARTIAL")]
    return []


@_register("UPF-033")
def _empty_or_unreachable_pst_state(model: PowerIntentModel):
    """A PST state covering no legal combination, or unreachable from the
    initial state given the declared transitions."""
    findings = []
    for pst in model.psts.values():
        if not pst.states:
            continue
        for state in pst.states:
            if not state.supply_states:
                findings.append(Finding(
                    rule="UPF-033", severity="warning",
                    message=f"PST '{pst.name}' state '{state.name}' has no "
                            f"supply bindings - covers no legal power "
                            f"combination.",
                    line=state.declared_line))
        # Reachability: a state with no incoming transition and no self-loop
        # is unreachable unless it is the initial state.
        if pst.transitions and len(pst.states) > 1:
            initial = pst.states[0].name
            incoming: set = set()
            for src, dst in pst.transitions:
                incoming.add(dst)
            for state in pst.states:
                if state.name == initial:
                    continue
                if state.name not in incoming and \
                        (state.name, state.name) not in pst.transitions:
                    findings.append(Finding(
                        rule="UPF-033", severity="warning",
                        message=f"PST '{pst.name}' state '{state.name}' is "
                                f"unreachable - no transition targets it.",
                        line=state.declared_line))
    return findings


@_register("UPF-034")
def _duplicate_pst_states(model: PowerIntentModel):
    """Duplicate state names or identical supply-state combinations."""
    findings = []
    for pst in model.psts.values():
        names = [s.name for s in pst.states]
        seen: set = set()
        for name in names:
            if name in seen:
                findings.append(Finding(
                    rule="UPF-034", severity="warning",
                    message=f"PST '{pst.name}' declares duplicate state '{name}'.",
                    line=pst.declared_line))
            seen.add(name)
        combos: set = set()
        for state in pst.states:
            combo = frozenset((s, v) for s, v in state.supply_states.items())
            if combo in combos and combo:
                findings.append(Finding(
                    rule="UPF-034", severity="warning",
                    message=f"PST '{pst.name}' states '{state.name}' duplicate "
                            f"an existing supply-state combination.",
                    line=state.declared_line))
            combos.add(combo)
    return findings


@_register("UPF-035")
def _undeclared_transition(model: PowerIntentModel):
    """add_state_transition names a state that is not a PST row."""
    findings = []
    for pst in model.psts.values():
        names = {s.name for s in pst.states}
        for src, dst in pst.transitions:
            if src not in names or dst not in names:
                bad = [n for n in (src, dst) if n not in names]
                findings.append(Finding(
                    rule="UPF-035", severity="warning",
                    message=f"PST '{pst.name}' transition '{src}' -> '{dst}' "
                            f"references undeclared state(s): "
                            f"{', '.join(bad)}.",
                    line=pst.declared_line))
    return findings


@_register("UPF-036")
def _strategy_not_pst_conditioned(model: PowerIntentModel):
    """Isolation/level-shifter strategies must be conditioned on the PST.

    Statically we can only confirm the *opportunity* exists: when a strategy is
    present, the design should own a PST to condition it. Without the full
    supply-state/strategy conditioning graph this is PARTIAL.
    """
    findings = []
    strategies = list(model.isolation) + list(model.level_shifters)
    if not strategies:
        return findings
    if not model.psts:
        findings.append(Finding(
            rule="UPF-036", severity="warning",
            message=f"{len(strategies)} isolation/level-shifter strategy(ies) "
                    f"present but no PST exists to condition them on.",
            support="PARTIAL"))
    return findings


@_register("UPF-037")
def _unsolated_power_down_crossing(model: PowerIntentModel):
    """Cross-state: a switchable domain powers down while a receiver stays on.

    Emitted only for declared PST transitions where the downing domain is
    ``ON`` in the source state and ``OFF``/``HIGHZ`` in the destination while
    another domain remains ``ON``, and the downing domain has no active
    isolation/clamp. Connectivity is netlist-dependent, hence NETLIST_REQUIRED.
    """
    findings = []
    for ev in analyze_cross_state(model):
        if ev["type"] != "power_down" or ev["isolated"]:
            continue
        recv = ", ".join(ev["receivers"])
        findings.append(Finding(
            rule="UPF-037", severity="warning",
            message=(
                f"Cross-state transition '{ev['pst']}' {ev['src']}->{ev['dst']} "
                f"powers domain '{ev['domain']}' {ev['to']} while '{recv}' "
                f"remains powered; domain '{ev['domain']}' has no active "
                f"isolation/clamp and its outputs may float into '{recv}'."
            ),
            support="NETLIST_REQUIRED"))
    return findings


@_register("UPF-038")
def _switchable_net_not_modeled(model: PowerIntentModel):
    """Tri-state/floating: a switchable domain's power net is absent from the PST."""
    findings = []
    for ev in analyze_cross_state(model):
        if ev["type"] != "unmodeled_switch":
            continue
        findings.append(Finding(
            rule="UPF-038", severity="warning",
            message=(
                f"Switchable domain '{ev['domain']}' primary supply "
                f"'{ev['net']}' (a power-switch output) is never modeled by any "
                f"PST state; its tri-state/floating power behavior cannot be "
                f"verified."
            ),
            support="NETLIST_REQUIRED"))
    return findings


# ---------------------------------------------------------------------------
# Layer 5 - Strategies
# ---------------------------------------------------------------------------

def _switchable_outputs(model: PowerIntentModel) -> set:
    """Nets produced by a power switch (i.e. switchable / not always-on)."""
    return {sw.output_supply for sw in model.switches.values() if sw.output_supply}


def _domain_primary_power(model: PowerIntentModel, dom) -> Optional[str]:
    """Return the power net/set a domain relies on, or None if unknnown.

    A supply-set reference is resolved through its `power` function to the
    underlying net, so switchability against power-switch outputs is exact.
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

    if "primary_power_net" in dom.primary_supply_sets:
        return resolve_power(dom.primary_supply_sets["primary_power_net"])
    if "primary" in dom.primary_supply_sets:
        return resolve_power(dom.primary_supply_sets["primary"])
    for key, val in dom.primary_supply_sets.items():
        if key.lower() == "power":
            return resolve_power(val)
    return None


def _domain_by_name(model: PowerIntentModel, name: str):
    if not name:
        return None
    key = model.scope_key(name, model.current_scope)
    return model.domains.get(key) or model.domains.get(name)


@_register("UPF-040")
def _isolation_non_always_on(model: PowerIntentModel):
    """Isolation supply must be always-on.

    Static: a supply that is a power-switch output can power down, so it cannot
    back an isolation strategy. Anything else requires supply-state analysis.
    """
    findings = []
    switched = _switchable_outputs(model)
    for iso in model.isolation:
        if not iso.isolation_supply:
            continue
        kind, key = _supply_lookup(model, iso.isolation_supply,
                                   getattr(iso, "scope", None))
        if kind is None:
            findings.append(Finding(
                rule="UPF-040", severity="error",
                message=f"Isolation for domain '{iso.domain}' uses unknown "
                        f"isolation supply '{iso.isolation_supply}' - cannot be "
                        f"guaranteed always-on.",
                line=iso.declared_line))
        else:
            # Resolve a supply set through its power function to the net, so
            # switchability (vs power-switch outputs) is exact.
            target = iso.isolation_supply
            if kind == "set":
                ss = model.supply_sets.get(key)
                if ss is not None:
                    target = ss.functions.get("power") or target
            if target in switched:
                findings.append(Finding(
                    rule="UPF-040", severity="error",
                    message=f"Isolation supply '{iso.isolation_supply}' is a "
                            f"power-switch output (can power down); it must be "
                            f"always-on.",
                    line=iso.declared_line))
            else:
                findings.append(Finding(
                    rule="UPF-040", severity="warning",
                    message=f"Isolation supply '{iso.isolation_supply}' always-on "
                            f"status must be confirmed against the PST / supply "
                            f"states.",
                    line=iso.declared_line, support="PARTIAL"))
    return findings


@_register("UPF-041")
def _isolation_self_in_switchable(model: PowerIntentModel):
    """Isolation located `self` inside a switchable domain loses its supply."""
    findings = []
    switched = _switchable_outputs(model)
    for iso in model.isolation:
        if iso.location != "self":
            continue
        dom = _domain_by_name(model, iso.domain)
        if dom is None:
            continue
        primary = _domain_primary_power(model, dom)
        if primary and primary in switched:
            findings.append(Finding(
                rule="UPF-041", severity="error",
                message=f"Isolation for domain '{iso.domain}' is located 'self' "
                        f"but the domain's primary supply '{primary}' is "
                        f"switchable - isolation cells would lose power.",
                line=iso.declared_line))
    return findings


@_register("UPF-042")
def _missing_isolation_crossing(model: PowerIntentModel):
    """Crossings out of a switchable domain need isolation.

    Without a netlist the crossing set is unknown; flag the risk only when a
    switchable domain has no isolation strategy at all.
    """
    findings = []
    switched = _switchable_outputs(model)
    isolated = {iso.domain for iso in model.isolation}
    for key, dom in model.domains.items():
        primary = _domain_primary_power(model, dom)
        if not primary or primary not in switched:
            continue
        if dom.name not in isolated:
            findings.append(Finding(
                rule="UPF-042", severity="warning",
                message=f"Switchable domain '{dom.name}' has no isolation "
                        f"strategy - crossings may leak; confirm against the "
                        f"netlist.",
                line=dom.declared_line, support="NETLIST_REQUIRED"))
    return findings


@_register("UPF-043")
def _redundant_isolation(model: PowerIntentModel):
    """Isolation on an always-on (non-switchable) domain is redundant."""
    findings = []
    switched = _switchable_outputs(model)
    for iso in model.isolation:
        dom = _domain_by_name(model, iso.domain)
        if dom is None:
            continue
        primary = _domain_primary_power(model, dom)
        if primary and primary not in switched:
            findings.append(Finding(
                rule="UPF-043", severity="info",
                message=f"Isolation on domain '{iso.domain}' is redundant - "
                        f"primary supply '{primary}' is not switchable.",
                line=iso.declared_line))
    return findings


@_register("UPF-044")
def _isolation_missing_inout(model: PowerIntentModel):
    """applies_to without inouts may leak bidirectional crossings."""
    findings = []
    for iso in model.isolation:
        tokens = {t for t in iso.applies_to.replace(",", " ").split()}
        if "inout" not in tokens and "inouts" not in tokens:
            findings.append(Finding(
                rule="UPF-044", severity="warning",
                message=f"Isolation for domain '{iso.domain}' does not cover "
                        f"inouts (-applies_to '{iso.applies_to}'); bidirectional "
                        f"crossings may leak.",
                line=iso.declared_line, support="NETLIST_REQUIRED"))
    return findings


@_register("UPF-045")
def _isolation_without_control(model: PowerIntentModel):
    findings = []
    for iso in model.isolation:
        if not iso.control_signal:
            findings.append(Finding(
                rule="UPF-045", severity="error",
                message=f"Isolation for domain '{iso.domain}' has no "
                        f"set_isolation_control (missing -isolation_signal).",
                line=iso.declared_line))
    return findings


@_register("UPF-046")
def _invalid_clamp_value(model: PowerIntentModel):
    """Clamp must be 0/1 or a declared supply state; and must not be absent.

    A clamp value is what holds the isolated output at a defined level. Without
    one the output floats while isolation is active, so the absence is flagged
    as a warning (distinct from an outright invalid value, which is an error).
    """
    findings = []
    known = {s.name for s in model.supply_states}
    for iso in model.isolation:
        if not iso.clamp_value:
            findings.append(Finding(
                rule="UPF-046", severity="warning",
                message=f"Isolation for domain '{iso.domain}' has no "
                        f"-clamp_value; its outputs are undefined (floating) "
                        f"while isolation is active.",
                line=iso.declared_line))
            continue
        val = iso.clamp_value.strip()
        if val in ("0", "1"):
            continue
        if val in known:
            continue
        findings.append(Finding(
            rule="UPF-046", severity="error",
            message=f"Isolation for domain '{iso.domain}' uses clamp value "
                    f"'{iso.clamp_value}' - must be 0, 1, or a declared supply "
                    f"state.",
            line=iso.declared_line))
    return findings


@_register("UPF-047")
def _isolation_control_not_always_on(model: PowerIntentModel):
    """The isolation enable must itself be always-on.

    If the control signal carries an explicit `always_on true` attribute it is
    VALIDATED; otherwise confirm against the netlist/supply analysis.
    """
    findings = []
    always_on = {
        name for name, attrs in model.port_attributes.items()
        if any("always_on" in a.lower() and "true" in a.lower() for a in attrs)
    }
    for iso in model.isolation:
        if not iso.control_signal:
            continue
        if iso.control_signal in always_on:
            continue
        findings.append(Finding(
            rule="UPF-047", severity="warning",
            message=f"Isolation control '{iso.control_signal}' for domain "
                    f"'{iso.domain}' must be always-on; confirm it is not "
                    f"powered down.",
            line=iso.declared_line, support="PARTIAL"))
    return findings


@_register("UPF-050")
def _retention_supply_powers_down(model: PowerIntentModel):
    """Retention supply must be always-on.

    Without a netlist or an explicit supply-state table this is a PARTIAL
    check: we can only flag retention whose supply is not among the nets/sets
    declared at all (clearly wrong) and otherwise defer to the PST layer.
    """
    findings = []
    for ret in model.retentions:
        if ret.retention_supply:
            kind, _ = _supply_lookup(model, ret.retention_supply,
                                     getattr(ret, "scope", None))
            if kind is None:
                findings.append(Finding(
                    rule="UPF-050", severity="error",
                    message=f"Retention supply '{ret.retention_supply}' is not "
                            f"declared anywhere; cannot be always-on.",
                    line=ret.declared_line))
            else:
                findings.append(Finding(
                    rule="UPF-050", severity="warning",
                    message=f"Retention supply '{ret.retention_supply}' always-on "
                            f"status must be confirmed against the PST / supply "
                            f"states (requires power-state analysis).",
                    line=ret.declared_line, support="PARTIAL"))
    return findings


@_register("UPF-052")
def _retention_without_elements(model: PowerIntentModel):
    return [
        Finding(rule="UPF-052", severity="warning",
                message=f"set_retention for domain '{ret.domain}' references no "
                        f"retention elements (-elements empty).",
                line=ret.declared_line)
        for ret in model.retentions
        if not ret.elements
    ]


def _retention_control_always_on(model: PowerIntentModel) -> set:
    return {
        name for name, attrs in model.port_attributes.items()
        if any("always_on" in a.lower() and "true" in a.lower() for a in attrs)
    }


@_register("UPF-051")
def _retention_control_not_always_on(model: PowerIntentModel):
    """Save/restore control must be driven by always-on logic."""
    findings = []
    always_on = _retention_control_always_on(model)
    for ret in model.retentions:
        for sig, label in ((ret.save_signal, "save"),
                           (ret.restore_signal, "restore")):
            if sig and sig not in always_on:
                findings.append(Finding(
                    rule="UPF-051", severity="warning",
                    message=f"Retention {label} control '{sig}' for domain "
                            f"'{ret.domain}' must be always-on; confirm it is "
                            f"not powered down.",
                    line=ret.declared_line, support="PARTIAL"))
    return findings


@_register("UPF-053")
def _retention_control_tied_constant(model: PowerIntentModel):
    """Save and restore driven by the same signal can never toggle both roles."""
    findings = []
    for ret in model.retentions:
        if ret.save_signal and ret.restore_signal and \
                ret.save_signal == ret.restore_signal:
            findings.append(Finding(
                rule="UPF-053", severity="warning",
                message=f"Retention for domain '{ret.domain}' ties save and "
                        f"restore to the same signal '{ret.save_signal}' - "
                        f"the control can never sequence correctly.",
                line=ret.declared_line, support="PARTIAL"))
    return findings


@_register("UPF-054")
def _retention_without_control(model: PowerIntentModel):
    """A retention with no save/restore/control can never be activated."""
    return [
        Finding(rule="UPF-054", severity="error",
                message=f"Retention for domain '{ret.domain}' has no "
                        f"set_retention_control (missing -save_signal / "
                        f"-restore_signal).",
                line=ret.declared_line)
        for ret in model.retentions
        if not ret.save_signal and not ret.restore_signal
        and not ret.control_signal
    ]


@_register("UPF-060")
def _unnecessary_level_shifter(model: PowerIntentModel):
    """Equal-voltage crossings need no level shifter.

    Voltage information comes from supply states; without a full PST this is
    flagged at info level as an advisory.
    """
    return [
        Finding(rule="UPF-060", severity="info",
                message=f"Level shifter on domain '{ls.domain}' - verify the "
                        f"source/target voltages differ; equal voltages need no "
                        f"shifter.",
                line=ls.declared_line, support="PARTIAL")
        for ls in model.level_shifters
    ]


def _supply_voltage(model: PowerIntentModel, supply: str) -> Optional[float]:
    """Nominal ON voltage of a supply, if declared via add_port_state.

    Prefers the explicit ``ON`` state; otherwise falls back to the declared
    state carrying the highest positive voltage (so a non-``ON``-named on-state
    such as ``{VDD_1_8 1.8}`` or ``{NOM 1.8}`` is still detected). ``OFF``-like
    zero-volt states are excluded.
    """
    cands = [
        st for st in model.supply_states
        if st.parent == supply and st.voltage is not None
    ]
    if not cands:
        return None
    cands.sort(key=lambda s: (s.name.lower() != "on", -s.voltage))
    for st in cands:
        if st.voltage > 0:
            return st.voltage
    return None


def _domain_voltage(model: PowerIntentModel, dom) -> Optional[float]:
    """Voltage of a domain's primary power, if resolvable."""
    primary = _domain_primary_power(model, dom)
    if not primary:
        return None
    return _supply_voltage(model, primary)


@_register("UPF-061")
def _missing_level_shifter(model: PowerIntentModel):
    """Different-voltage crossings need a level shifter.

    When voltages are known and a switchable/voltage-different domain has no
    level shifter, flag it; otherwise defer to the PST/netlist layer.
    """
    findings = []
    ls_domains = {ls.domain for ls in model.level_shifters}
    voltages: Dict[str, Optional[float]] = {
        dom.name: _domain_voltage(model, dom) for dom in model.domains.values()}
    known = {n for n, v in voltages.items() if v is not None}
    if len(known) < 2:
        return findings
    checked: set = set()
    for dom in model.domains.values():
        v = voltages[dom.name]
        if v is None:
            continue
        for other in model.domains.values():
            if other.name == dom.name:
                continue
            pair = frozenset((dom.name, other.name))
            if pair in checked:
                continue
            checked.add(pair)
            ov = voltages[other.name]
            if ov is None or abs(v - ov) < 1e-9:
                continue
            # A real voltage difference exists between these domains.
            if dom.name not in ls_domains and other.name not in ls_domains:
                findings.append(Finding(
                    rule="UPF-061", severity="error",
                    message=f"Domains '{dom.name}' ({v}V) and '{other.name}' "
                            f"({ov}V) differ in voltage but neither declares a "
                            f"level shifter.",
                    line=dom.declared_line, support="PARTIAL"))
    return findings


@_register("UPF-062")
def _wrong_level_shifter_rule(model: PowerIntentModel):
    """low_to_high vs high_to_low must match the actual voltage direction.

    When the source/target voltages are known, validate the declared rule.
    """
    findings = []
    voltages: Dict[str, Optional[float]] = {
        dom.name: _domain_voltage(model, dom) for dom in model.domains.values()}
    for ls in model.level_shifters:
        dom = _domain_by_name(model, ls.domain)
        if dom is None:
            continue
        v = voltages.get(dom.name)
        if v is None:
            continue
        for other in model.domains.values():
            if other.name == dom.name:
                continue
            ov = voltages.get(other.name)
            if ov is None or abs(v - ov) < 1e-9:
                continue
            correct = "low_to_high" if v < ov else "high_to_low"
            if ls.rule != "both" and ls.rule != correct:
                findings.append(Finding(
                    rule="UPF-062", severity="error",
                    message=f"Level shifter on domain '{dom.name}' ({v}V) to "
                            f"'{other.name}' ({ov}V) declares rule "
                            f"'{ls.rule}' but needs '{correct}'.",
                    line=ls.declared_line, support="PARTIAL"))
                break
    return findings


@_register("UPF-063")
def _ls_self_in_switchable(model: PowerIntentModel):
    """A level shifter at `self` in a switchable domain loses its supply."""
    findings = []
    switched = _switchable_outputs(model)
    for ls in model.level_shifters:
        if ls.location != "self":
            continue
        dom = _domain_by_name(model, ls.domain)
        if dom is None:
            continue
        primary = _domain_primary_power(model, dom)
        if primary and primary in switched:
            findings.append(Finding(
                rule="UPF-063", severity="error",
                message=f"Level shifter on domain '{ls.domain}' is located "
                        f"'self' but the domain's primary supply '{primary}' "
                        f"is switchable - the shifter would lose power.",
                line=ls.declared_line))
    return findings


@_register("UPF-064")
def _ls_control_not_always_on(model: PowerIntentModel):
    """A level-shifter enable from set_level_shifter_control must be always-on."""
    findings = []
    always_on = {
        name for name, attrs in model.port_attributes.items()
        if any("always_on" in a.lower() and "true" in a.lower() for a in attrs)
    }
    for ls in model.level_shifters:
        if not ls.control_signal:
            continue
        if ls.control_signal in always_on:
            continue
        findings.append(Finding(
            rule="UPF-064", severity="warning",
            message=f"Level-shifter control '{ls.control_signal}' for domain "
                    f"'{ls.domain}' must be always-on; confirm it is not "
                    f"powered down.",
            line=ls.declared_line, support="PARTIAL"))
    return findings


# ---------------------------------------------------------------------------
# Layer 5 - Power switches
# ---------------------------------------------------------------------------

def _switch_control_always_on(model: PowerIntentModel) -> set:
    return {
        name for name, attrs in model.port_attributes.items()
        if any("always_on" in a.lower() and "true" in a.lower() for a in attrs)
    }


@_register("UPF-070")
def _switch_undefined_supply(model: PowerIntentModel):
    """A switch references a supply that is not declared anywhere."""
    findings = []
    known = set()
    for table in (model.supply_nets, model.supply_sets, model.supply_ports):
        known.update(obj.name for obj in table.values())
    for key, sw in model.switches.items():
        for ref, label in ((sw.input_supply, "input"),
                           (sw.output_supply, "output")):
            if ref and ref not in known:
                findings.append(Finding(
                    rule="UPF-070", severity="error",
                    message=f"Power switch '{sw.name}' references undefined "
                            f"{label} supply '{ref}'.",
                    line=sw.declared_line))
    return findings


@_register("UPF-071")
def _switch_control_not_always_on(model: PowerIntentModel):
    """Power-switch control must be always-on (never itself switched)."""
    findings = []
    always_on = _switch_control_always_on(model)
    for key, sw in model.switches.items():
        if not sw.control_port:
            continue
        if sw.control_port in always_on:
            continue
        findings.append(Finding(
            rule="UPF-071", severity="warning",
            message=f"Power switch '{sw.name}' control '{sw.control_port}' "
                    f"must be always-on; confirm it is not powered down.",
            line=sw.declared_line, support="PARTIAL"))
    return findings


@_register("UPF-072")
def _always_on_into_switchable(model: PowerIntentModel):
    """Always-on signals crossing into a switchable domain must be isolated.

    Without a netlist the crossing set is unknown; this is an advisory that
    the design owns always-on signals and switchable domains.
    """
    findings = []
    always_on = _switch_control_always_on(model)
    switched = _switchable_outputs(model)
    if not always_on or not switched:
        return findings
    for sig in sorted(always_on):
        findings.append(Finding(
            rule="UPF-072", severity="warning",
            message=f"Always-on signal '{sig}' may cross into a switchable "
                    f"domain; confirm isolation on the boundary.",
            line=None, support="NETLIST_REQUIRED"))
    return findings


@_register("UPF-073")
def _switch_output_unused(model: PowerIntentModel):
    """A switch output supply not consumed by any domain is dead."""
    findings = []
    used = set()
    for dom in model.domains.values():
        p = _domain_primary_power(model, dom)
        if p:
            used.add(p)
    for key, sw in model.switches.items():
        if sw.output_supply and sw.output_supply not in used:
            findings.append(Finding(
                rule="UPF-073", severity="info",
                message=f"Power switch '{sw.name}' output supply "
                        f"'{sw.output_supply}' is not used by any power domain.",
                line=sw.declared_line))
    return findings


@_register("UPF-074")
def _switch_state_condition_without_control(model: PowerIntentModel):
    """A switch on/off state condition must reference its control port.

    A condition like ``{on vin {en}}`` keys the state to the enable; a
    condition that never mentions the control port cannot be driven by it.
    """
    findings = []
    for key, sw in model.switches.items():
        if not sw.control_port:
            continue
        for cond, label in ((sw.on_state_condition, "on"),
                            (sw.off_state_condition, "off")):
            if not cond:
                continue
            if any(sw.control_port in tok for tok in cond):
                continue
            findings.append(Finding(
                rule="UPF-074", severity="warning",
                message=f"Power switch '{sw.name}' {label} state condition "
                        f"'{' '.join(cond)}' does not reference control port "
                        f"'{sw.control_port}'.",
                line=sw.declared_line))
    return findings


# ---------------------------------------------------------------------------
# Layer 2 - Reference integrity (model-level)
# ---------------------------------------------------------------------------

@_register("UPF-010")
def _undefined_supply_reference(model: PowerIntentModel):
    supply_kinds = ("net", "port", "set")
    defined = {k for k, v in model.definitions.items() if v["kind"] in supply_kinds}
    return [
        Finding(rule="UPF-010", severity="error",
                message=f"Supply '{r['name']}' is referenced but never defined "
                        f"as a net, port or set.",
                line=r["line"], support="VALIDATED")
        for r in model.references
        if r["kind"] == "supply" and r["key"] not in defined
    ]


@_register("UPF-013")
def _duplicate_definition(model: PowerIntentModel):
    return [
        Finding(rule="UPF-013", severity="error",
                message=f"Duplicate definition of '{d['name']}' ({d['kind']}): "
                        f"previously defined at line {d['old_line']}.",
                line=d["new_line"], support="VALIDATED")
        for d in model.duplicate_definitions
    ]


@_register("UPF-014")
def _use_before_definition(model: PowerIntentModel):
    defined = {k: v["line"] for k, v in model.definitions.items()}
    return [
        Finding(rule="UPF-014", severity="warning",
                message=f"'{r['name']}' is used at line {r['line']} before its "
                        f"defining command (line {defined[r['key']]}).",
                line=r["line"], support="VALIDATED")
        for r in model.references
        if r["key"] in defined and defined[r["key"]] > r["line"]
    ]


@_register("UPF-016")
def _invalid_scope_target(model: PowerIntentModel):
    return [
        Finding(rule="UPF-016", severity="warning",
                message=f"set_scope target '{s['scope']}' cannot be verified "
                        f"without a netlist (scope resolution needs "
                        f"design hierarchy).",
                line=s["line"], support="NETLIST_REQUIRED")
        for s in model.scope_changes
        if s["scope"] not in (".", "") and s["scope"] != model.design_top
    ]


@_register("UPF-012")
def _undefined_instance(model: PowerIntentModel):
    """Bad instance paths - deterministic subset only.

    Without a netlist the engine cannot resolve instance names, so most of this
    rule is deferred to a netlist-aware layer. A leading wildcard or an empty
    element token is unambiguously unresolvable and is flagged here.
    """
    findings = []
    for dom in model.domains.values():
        for el in dom.elements:
            if el.startswith("*") or not el.strip():
                findings.append(Finding(
                    rule="UPF-012", severity="warning",
                    message=f"Instance path '{el}' in domain '{dom.name}' does "
                            f"not resolve.",
                    line=dom.declared_line))
    return findings


@_register("UPF-015")
def _circular_dependency(model: PowerIntentModel):
    """Detectable supply/connect cycles (deterministic subset).

    A supply set whose power/ground function references itself, or a net that
    connects to itself, is a hard dependency cycle.
    """
    findings = []
    for key, s in model.supply_sets.items():
        for role, ref in s.functions.items():
            if ref == s.name:
                findings.append(Finding(
                    rule="UPF-015", severity="warning",
                    message=f"Supply set '{s.name}' has a circular "
                            f"{role} function referencing itself.",
                    line=s.declared_line))
    for net in model.supply_nets.values():
        port_names = {p.name for p in model.supply_ports.values()}
        for target in net.connected_to:
            if target == net.name and net.name not in port_names:
                findings.append(Finding(
                    rule="UPF-015", severity="warning",
                    message=f"Supply net '{net.name}' connects to itself "
                            f"(dependency cycle).",
                    line=net.declared_line))
                break
    return findings


@_register("UPF-011")
def _undefined_domain_references(model: PowerIntentModel):
    referenced = set()
    for iso in model.isolation:
        if iso.domain:
            referenced.add(iso.domain)
    for ls in model.level_shifters:
        if ls.domain:
            referenced.add(ls.domain)
    for ret in model.retentions:
        if ret.domain:
            referenced.add(ret.domain)
    defined = {d.name for d in model.domains.values()}
    return [
        Finding(rule="UPF-011", severity="error",
                message=f"Power domain '{name}' is referenced by a strategy but "
                        f"never created.",
                support="VALIDATED")
        for name in sorted(referenced - defined)
    ]


# ---------------------------------------------------------------------------
# Layer 6 - Design-aware (UPF-080…084, requires a design context)
# ---------------------------------------------------------------------------
# These rules are silent unless the model carries a DesignContext (netlist
# snapshot). Without it, the honest support boundary reports NETLIST_REQUIRED.

def _design(model: PowerIntentModel):
    d = getattr(model, "design", None)
    if d is None:
        return None
    # tolerate a plain dict context for the web/tests path
    if isinstance(d, dict):
        from ..design.design_context import DesignContext

        return DesignContext.from_dict(d)
    return d


@_register("UPF-080")
def _unknown_element_instance(model: PowerIntentModel):
    design = _design(model)
    if design is None:
        return []
    findings = []
    for dom in model.domains.values():
        for el in dom.elements:
            if not design.has_instance(el):
                findings.append(Finding(
                    rule="UPF-080", severity="warning",
                    message=f"Instance '{el}' in domain '{dom.name}' does not "
                            f"exist in the netlist.",
                    line=dom.declared_line))
    return findings


@_register("UPF-081")
def _unknown_control_signal(model: PowerIntentModel):
    design = _design(model)
    if design is None:
        return []
    findings = []
    for iso in model.isolation:
        if iso.control_signal and not design.has_signal(iso.control_signal):
            findings.append(Finding(
                rule="UPF-081", severity="warning",
                message=f"Isolation control signal '{iso.control_signal}' for "
                        f"domain '{iso.domain}' is not in the design.",
                line=iso.declared_line))
    for ret in model.retentions:
        for sig in (ret.save_signal, ret.restore_signal):
            if sig and not design.has_signal(sig):
                findings.append(Finding(
                    rule="UPF-081", severity="warning",
                    message=f"Retention signal '{sig}' for domain '{ret.domain}' "
                            f"is not in the design.",
                    line=ret.declared_line))
    for sw in model.switches.values():
        if sw.control_port and not design.has_signal(sw.control_port):
            findings.append(Finding(
                rule="UPF-081", severity="warning",
                message=f"Switch control '{sw.control_port}' is not in the "
                        f"design.",
                line=sw.declared_line))
    return findings


@_register("UPF-082")
def _uncovered_crossing(model: PowerIntentModel):
    """Endpoint-based crossing check.

    Uses the design context's signal map (driver -> receivers). A signal that
    leaves a switchable domain and lands outside it needs an isolation
    strategy on the source domain; otherwise flag the uncovered crossing.
    """
    design = _design(model)
    if design is None:
        return []
    switched = _switchable_outputs(model)
    isolated_domains = {iso.domain for iso in model.isolation}
    findings = []
    dom_by_instance = {}
    for dom in model.domains.values():
        for el in dom.elements:
            dom_by_instance[el] = dom
    for sig, conn in design.signals.items():
        driver = conn.get("driver")
        src = dom_by_instance.get(driver)
        if src is None:
            continue
        primary = _domain_primary_power(model, src)
        if not (primary in switched or src.name in isolated_domains):
            continue  # source not switchable: nothing to isolate
        for recv in conn.get("receivers", []):
            dst = dom_by_instance.get(recv)
            if dst is None or dst.name == src.name:
                continue
            if src.name not in isolated_domains:
                findings.append(Finding(
                    rule="UPF-082", severity="warning",
                    message=f"Signal '{sig}' crosses from switchable domain "
                            f"'{src.name}' to '{dst.name}' without isolation.",
                    line=src.declared_line))
                break
    return findings


@_register("UPF-083")
def _retention_coverage_gap(model: PowerIntentModel):
    """Sequential elements without retention.

    Uses the design context to know which instances are sequential. A
    sequential instance is a retention gap when its domain is retention-worthy
    - either it already has a retention strategy (then every sequential element
    must be covered) or its primary supply is switchable (can power down).
    """
    design = _design(model)
    if design is None:
        return []
    findings = []
    switched = _switchable_outputs(model)
    retained_domains = {r.domain for r in model.retentions}
    covered = set()
    for ret in model.retentions:
        for el in ret.elements:
            covered.add((ret.domain, el))
    for dom in model.domains.values():
        if not dom.elements:
            continue
        insts = design.domain_instances(dom.elements)
        seq = [i for i in insts if i.sequential]
        if not seq:
            continue
        primary = _domain_primary_power(model, dom)
        retention_worthy = (dom.name in retained_domains
                            or (primary is not None and primary in switched))
        if not retention_worthy:
            continue
        for i in seq:
            if (dom.name, i.name) not in covered:
                findings.append(Finding(
                    rule="UPF-083", severity="warning",
                    message=f"Sequential instance '{i.name}' in domain "
                            f"'{dom.name}' is not covered by retention "
                            f"(-elements or a retention strategy).",
                    line=dom.declared_line))
    return findings


@_register("UPF-084")
def _library_pg_mismatch(model: PowerIntentModel):
    """UPF primary supply vs liberty PG pins.

    For each domain element whose module declares PG pins in the design
    context, the domain's primary power/ground must appear among them
    (case-insensitive - PG pin names are conventionally uppercase).
    """
    design = _design(model)
    if design is None:
        return []
    findings = []
    for dom in model.domains.values():
        primary = _domain_primary_power(model, dom)
        if primary is None:
            continue
        insts = design.domain_instances(dom.elements)
        for inst in insts:
            pins = design.pg_pins.get(inst.module)
            if pins is None or not pins:
                continue
            if primary.lower() not in {p.lower() for p in pins}:
                findings.append(Finding(
                    rule="UPF-084", severity="warning",
                    message=f"Primary supply '{primary}' of domain '{dom.name}' "
                            f"is not among the PG pins of '{inst.module}' "
                            f"({', '.join(pins)}).",
                    line=dom.declared_line))
    return findings


# ---------------------------------------------------------------------------
# Layer 5 - Repeater strategies (UPF-090…094)
# ---------------------------------------------------------------------------

def _repeater_always_on(model: PowerIntentModel) -> set:
    return {
        name for name, attrs in model.port_attributes.items()
        if any("always_on" in a.lower() and "true" in a.lower() for a in attrs)
    }


@_register("UPF-090")
def _repeater_supply_not_always_on(model: PowerIntentModel):
    """The repeater supply must be always-on so re-driven signals stay defined."""
    findings = []
    for rep in model.repeaters:
        if not rep.repeater_supply:
            continue
        kind, _ = _supply_lookup(model, rep.repeater_supply,
                                 getattr(rep, "scope", None))
        if kind is None:
            findings.append(Finding(
                rule="UPF-090", severity="error",
                message=f"Repeater supply '{rep.repeater_supply}' for domain "
                        f"'{rep.domain}' is not declared anywhere; cannot be "
                        f"always-on.",
                line=rep.declared_line))
        else:
            findings.append(Finding(
                rule="UPF-090", severity="warning",
                message=f"Repeater supply '{rep.repeater_supply}' for domain "
                        f"'{rep.domain}' always-on status must be confirmed "
                        f"against the PST / supply states.",
                line=rep.declared_line, support="PARTIAL"))
    return findings


@_register("UPF-091")
def _repeater_control_not_always_on(model: PowerIntentModel):
    """Repeater enable must be driven by always-on logic."""
    findings = []
    always_on = _repeater_always_on(model)
    for rep in model.repeaters:
        sig = rep.control_signal or rep.signal
        if not sig:
            continue
        if sig in always_on:
            continue
        findings.append(Finding(
            rule="UPF-091", severity="warning",
            message=f"Repeater control '{sig}' for domain '{rep.domain}' must "
                    f"be always-on; confirm it is not powered down.",
            line=rep.declared_line, support="PARTIAL"))
    return findings


@_register("UPF-092")
def _repeater_self_in_switchable(model: PowerIntentModel):
    """A repeater located `self` in a switchable domain loses its supply."""
    findings = []
    switched = _switchable_outputs(model)
    for rep in model.repeaters:
        if rep.location != "self":
            continue
        dom = _domain_by_name(model, rep.domain)
        if dom is None:
            continue
        primary = _domain_primary_power(model, dom)
        if primary and primary in switched:
            findings.append(Finding(
                rule="UPF-092", severity="error",
                message=f"Repeater on domain '{rep.domain}' is located 'self' "
                        f"but the domain's primary supply '{primary}' is "
                        f"switchable - the repeater would lose power.",
                line=rep.declared_line))
    return findings


@_register("UPF-093")
def _repeater_without_elements(model: PowerIntentModel):
    return [
        Finding(rule="UPF-093", severity="warning",
                message=f"set_repeater for domain '{rep.domain}' references no "
                        f"repeater elements (-elements empty).",
                line=rep.declared_line)
        for rep in model.repeaters
        if not rep.elements
    ]


@_register("UPF-094")
def _repeater_without_control(model: PowerIntentModel):
    """A repeater with no enable signal can never be driven."""
    return [
        Finding(rule="UPF-094", severity="error",
                message=f"Repeater for domain '{rep.domain}' has no "
                        f"set_repeater_control (missing -repeater_signal).",
                line=rep.declared_line)
        for rep in model.repeaters
        if not rep.signal and not rep.control_signal
    ]


# ---------------------------------------------------------------------------
# Hierarchical UPF (UPF-095…097) - promotion/demotion + composition
# ---------------------------------------------------------------------------

@_register("UPF-095")
def _promoted_entity_not_defined(model: PowerIntentModel):
    """A promoted supply/domain must be defined in the child scope."""
    findings = []
    for ev in model.hierarchy_events:
        if ev["op"] != "promote" or not ev["name"]:
            continue
        key = model.scope_key(ev["name"], ev["scope"])
        if key in model.definitions:
            continue
        # tolerate a bare-name definition match (top-scope promotion)
        if any(d["kind"] in ("net", "port", "set", "domain")
               for dk, d in model.definitions.items() if dk == ev["name"]):
            continue
        findings.append(Finding(
            rule="UPF-095", severity="error",
            message=f"upf_promote references '{ev['name']}' which is not "
                    f"defined in scope '{ev['scope']}'.",
            line=ev["line"]))
    return findings


@_register("UPF-096")
def _demotion_not_verifiable(model: PowerIntentModel):
    return [
        Finding(rule="UPF-096", severity="warning",
                message=f"upf_demote of '{ev['name']}' at scope '{ev['scope']}' "
                        f"cannot be verified without a netlist (scope "
                        f"resolution needs design hierarchy).",
                line=ev["line"], support="NETLIST_REQUIRED")
        for ev in model.hierarchy_events
        if ev["op"] == "demote" and ev["name"]
    ]


@_register("UPF-097")
def _hierarchical_composition_unverified(model: PowerIntentModel):
    return [
        Finding(rule="UPF-097", severity="warning",
                message=f"load_upf at scope '{ev['scope']}' composes "
                        f"hierarchical UPF; cross-scope resolution cannot be "
                        f"verified without a netlist.",
                line=ev["line"], support="NETLIST_REQUIRED")
        for ev in model.load_upf_events
    ]


# ---------------------------------------------------------------------------
# Supply equivalence / library mapping (UPF-098)
# ---------------------------------------------------------------------------

@_register("UPF-098")
def _equivalent_supply_undefined(model: PowerIntentModel):
    """Both sides of a set_equivalent must resolve to declared supplies."""
    findings = []
    known = set()
    for table in (model.supply_nets, model.supply_sets, model.supply_ports):
        known.update(obj.name for obj in table.values())
    for eq in model.equivalences:
        for name in eq["names"]:
            if name and name not in known:
                findings.append(Finding(
                    rule="UPF-098", severity="error",
                    message=f"set_equivalent references undefined supply "
                            f"'{name}'.",
                    line=eq["line"]))
    return findings


# ---------------------------------------------------------------------------
# Hierarchical supply mapping (UPF-099) and load_upf provenance (UPF-100)
# ---------------------------------------------------------------------------

@_register("UPF-099")
def _supply_map_reference_undefined(model: PowerIntentModel):
    """Both sides of a load_upf -supply map must resolve to declared supplies.

    The local side is declared in the child scope (which the loader is about
    to compose); the parent side must already exist at the current scope.
    Either side being unknown is a genuine reference error - never invented.
    """
    findings = []
    known = set()
    for table in (model.supply_nets, model.supply_sets, model.supply_ports):
        known.update(obj.name for obj in table.values())
    for m in model.supply_maps:
        local = m.get("local")
        parent = m.get("parent")
        if not local or not parent:
            continue
        if local not in known or parent not in known:
            findings.append(Finding(
                rule="UPF-099", severity="error",
                message=f"load_upf -supply maps '{local}' -> '{parent}' but one "
                        f"side is not a declared supply (net/port/set).",
                line=m.get("line")))
    return findings


@_register("UPF-100")
def _loaded_upf_missing(model: PowerIntentModel):
    """load_upf names a child UPF file; flag when the file is not part of the
    validated input set (missing child = unresolved hierarchy)."""
    findings = []
    for ev in model.load_upf_events:
        loaded = ev.get("loaded")
        if not loaded:
            continue
        present = loaded in model.record_file_names
        if not present:
            findings.append(Finding(
                rule="UPF-100", severity="warning",
                message=f"load_upf references '{loaded}' which is not among the "
                        f"validated input files - hierarchy is unresolved.",
                line=ev.get("line")))
    return findings


def build_rule_handlers():
    """Return the handler table (kept for API symmetry with sdc-tools)."""
    return RULE_HANDLERS


__all__ = ["RULE_HANDLERS", "build_rule_handlers"]