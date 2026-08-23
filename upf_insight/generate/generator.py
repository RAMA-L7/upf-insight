"""UPF generator - deterministic, template-driven power-intent construction.

Mirrors the sdc-tools constraint generator: a parameter dataclass driving
ordered section builders that emit structurally valid IEEE 1801 (UPF)
commands. Generated output is designed to round-trip through the validator
with zero errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

_DEFAULT_UPF_VERSION = "3.0"


@dataclass
class DomainParam:
    """One power domain."""

    name: str
    elements: str = ""  # e.g. "u_core u_sram" (joined into a TCL list)
    primary_power: str = "vdd"
    primary_ground: str = "vss"
    domain_type: str = ""  # "" | "always_on" | "switchable" - explicit, never inferred
    voltage: str = ""  # e.g. "0.8" or "1.0" - voltage of the domain's primary supply; empty = unknown


@dataclass
class SwitchParam:
    """A power switch between an input supply port and a switchable net."""

    name: str
    domain: str  # informational; the switch is scoped to the current scope
    input_supply: str  # port, e.g. vdd_sw_in
    output_supply: str  # net, e.g. vdd_sw_out
    control_port: str  # e.g. iso_ctrl
    on_state: str = "on"
    off_state: str = "off"


@dataclass
class IsolationParam:
    """An isolation strategy attached to a domain boundary."""

    domain: str
    clamp_value: str = "0"  # 0, 1, or a declared supply state; empty -> omit (validator flags)
    isolation_supply: str = "vdd_iso"
    signal: str = "iso_en"
    location: str = "self"  # self | parent | fanout
    applies_to: str = "outputs"  # inputs | outputs | both - which boundary direction this isolation covers


@dataclass
class LevelShifterParam:
    """A level shifter at a domain boundary."""

    domain: str
    location: str = "self"  # self | inout | input | output | fanout
    threshold: str = ""  # optional, e.g. "0.8"
    rule: str = "low_to_high"  # low_to_high | high_to_low | both
    applies_to: str = "both"  # inputs | outputs | both - which boundary direction this LS covers


@dataclass
class RetentionParam:
    """Retention strategy for a domain."""

    domain: str
    retention_supply: str = "vdd_ret"
    save_signal: str = "save"
    restore_signal: str = "restore"
    save_sense: str = "high"  # high | low - active sense of save signal
    restore_sense: str = "low"  # high | low - active sense of restore signal
    elements: str = ""  # e.g. "regA regB" - the state elements to retain; empty = domain-wide inference


@dataclass
class RepeaterParam:
    """A signal repeater on a domain boundary (set_repeater)."""

    domain: str
    repeater_supply: str = "vdd_rep"
    signal: str = "rep_en"
    location: str = "self"  # self | parent | fanout
    driver_type: str = "minimal"  # minimal | non_inverting | inverting


@dataclass
class RelationParam:
    """An explicit domain-to-domain relationship for the power-intent topology.

    ``kinds`` is a subset of isolation | level_shift | retention | supply |
    switch | control. The relation is emitted as a documented comment in the
    generated UPF; the constructs that make it true (isolation strategies,
    level shifters, switches) are emitted separately by the same parameters,
    so validation always operates on real commands.
    """

    from_domain: str
    to_domain: str
    kinds: str = "isolation"  # comma-separated: isolation,level_shift,...

    @property
    def kind_list(self) -> List[str]:
        return [k.strip() for k in self.kinds.split(",") if k.strip()]


@dataclass
class PstStateParam:
    """One Power State Table row."""

    name: str
    states: Dict[str, str] = field(default_factory=dict)  # supply -> ON|OFF


@dataclass
class UPFParams:
    """All knobs for :func:`generate_upf`."""

    design_top: str = "top"
    upf_version: str = _DEFAULT_UPF_VERSION
    primary_power: str = "vdd"
    primary_ground: str = "vss"
    on_voltage: float = 1.0
    off_voltage: float = 0.0
    domains: List[DomainParam] = field(default_factory=lambda: [DomainParam("core")])
    switches: List[SwitchParam] = field(default_factory=list)
    isolation: List[IsolationParam] = field(default_factory=list)
    level_shifters: List[LevelShifterParam] = field(default_factory=list)
    retention: List[RetentionParam] = field(default_factory=list)
    repeaters: List[RepeaterParam] = field(default_factory=list)
    pst_name: str = "pst_top"
    pst_states: List[PstStateParam] = field(
        default_factory=lambda: [
            PstStateParam("ALL_ON", {"vdd": "ON", "vss": "ON"}),
        ]
    )
    always_on: List[str] = field(default_factory=list)
    relations: List[RelationParam] = field(default_factory=list)
    #: hierarchical mode: name of the design root UPF file, plus child UPF
    #: scopes. When ``hierarchy`` is non-empty the generator emits a project
    #: (root + child files) instead of a single flat file.
    architecture: str = "flat"  # flat | hierarchical
    hierarchy: List[str] = field(default_factory=list)  # e.g. ["core_a", "core_b"]


def _tcl_list(parts: List[str]) -> str:
    """Join identifiers into a braced TCL list (empty -> {})."""
    return "{" + " ".join(parts) + "}"


def _cont(first: str, *opts: str) -> str:
    """Render a command across multiple lines (Tcl line continuation).

    Each option is placed on its own line ending in a backslash so engineers
    can read every argument of a long command without horizontal scrolling.
    The UPF preprocessor joins continuations, so the validator sees exactly
    the same logical command as the single-line form.

    >>> _cont("create_power_switch sw", "-input_supply_port vdd")
    'create_power_switch sw \\n    -input_supply_port vdd'
    """
    if not opts:
        return first
    return first + " \\\n    " + " \\\n    ".join(opts)


def _validate(p: UPFParams) -> None:
    if not p.design_top.strip():
        raise ValueError("design_top must not be empty")
    if not p.primary_power.strip() or not p.primary_ground.strip():
        raise ValueError("primary power/ground supplies must not be empty")
    if not p.domains:
        raise ValueError("at least one power domain is required")
    seen: set = set()
    for d in p.domains:
        n = d.name.strip()
        if not n:
            raise ValueError("domain names must not be empty")
        if n in seen:
            raise ValueError(f"duplicate domain {n!r}")
        seen.add(n)
    domain_names = {d.name.strip() for d in p.domains}
    sw_names: set = set()
    for s in p.switches:
        n = s.name.strip()
        if not n:
            raise ValueError("switch name must not be empty")
        if n in sw_names:
            raise ValueError(f"duplicate switch {n!r}")
        sw_names.add(n)
        if s.domain.strip() not in domain_names:
            raise ValueError(f"switch {n!r} references unknown domain {s.domain!r}")
        if not s.input_supply.strip() or not s.output_supply.strip() or not s.control_port.strip():
            raise ValueError(f"switch {n!r} needs input_supply, output_supply and control_port")
    for kind, items in (
        ("isolation", p.isolation),
        ("level shifter", p.level_shifters),
        ("retention", p.retention),
        ("repeater", p.repeaters),
    ):
        for item in items:
            dom = item.domain.strip()
            if not dom:
                raise ValueError(f"{kind} must name a domain")
            if dom not in domain_names:
                raise ValueError(f"{kind} on {dom!r} references unknown domain")
    for r in p.relations:
        if r.from_domain.strip() not in domain_names:
            raise ValueError(f"relation references unknown from-domain {r.from_domain!r}")
        if r.to_domain.strip() not in domain_names:
            raise ValueError(f"relation references unknown to-domain {r.to_domain!r}")
        if r.from_domain == r.to_domain:
            raise ValueError("a relation cannot connect a domain to itself")
    if p.architecture not in ("flat", "hierarchical"):
        raise ValueError(f"architecture must be 'flat' or 'hierarchical', got {p.architecture!r}")
    if p.architecture == "hierarchical" and not p.hierarchy:
        raise ValueError("hierarchical architecture requires at least one child scope")
    if not p.pst_states:
        raise ValueError("at least one PST state is required")


def _header(p: UPFParams) -> List[str]:
    return [
        "# Generated by upf-insight generate",
        f"upf_version {p.upf_version}",
        "",
        f"set_design_top {p.design_top}",
        "",
    ]


def _domain_lines(p: UPFParams) -> List[str]:
    lines = ["# -- Power domains ----"]
    for d in p.domains:
        elements = _tcl_list([e for e in d.elements.replace(",", " ").split() if e])
        if elements.strip("{}"):
            lines.append(_cont(f"create_power_domain {d.name}",
                               f"-elements {elements}"))
        else:
            lines.append(f"create_power_domain {d.name}")
        if d.domain_type == "always_on":
            lines.append(f"set_port_attributes {d.name} -attribute {{always_on true}}")
    lines.append("")
    return lines


def _supply_lines(p: UPFParams) -> List[str]:
    pp, pg = p.primary_power, p.primary_ground
    lines = ["# -- Supply network ----"]
    for s in (pp, pg):
        lines.append(f"create_supply_port {s} -direction in")
        lines.append(f"create_supply_net {s} -resolve port")
        lines.append(f"connect_supply_net {s} -ports {s}")
    lines.append(_cont("create_supply_set primary",
                       f"-function {{power {pp}}}",
                       f"-function {{ground {pg}}}"))
    # Distinct per-domain power/ground nets must be declared so strategies
    # (isolation/retention) can reference them and the round-trip stays clean.
    declared: set = set()
    for d in p.domains:
        for net in (d.primary_power or pp, d.primary_ground or pg):
            if net in (pp, pg) or net in declared:
                continue
            declared.add(net)
            lines.append(f"create_supply_net {net} -resolve net")
            lines.append(f"connect_supply_net {net} -ports {pp}")
        lines.append(_cont(f"set_domain_supply_net {d.name}",
                           f"-primary_power_net {d.primary_power or pp}",
                           f"-primary_ground_net {d.primary_ground or pg}"))
    lines.append("")
    return lines


def _aux_supply_lines(p: UPFParams, already_declared: set) -> List[str]:
    """Auxiliary supplies (switch ports/nets, isolation/retention/repeater
    supplies). ``already_declared`` carries every name emitted by the supply
    network section so nothing is declared twice - the round-trip stays free
    of duplicate-definition findings."""
    lines: List[str] = []
    aux: List[str] = []
    for iso in p.isolation:
        if iso.isolation_supply:
            aux.append(iso.isolation_supply)
    for ret in p.retention:
        if ret.retention_supply:
            aux.append(ret.retention_supply)
    for rep in p.repeaters:
        if rep.repeater_supply:
            aux.append(rep.repeater_supply)
    seen: set = set(already_declared)
    for s in p.switches:
        if s.input_supply not in seen:
            seen.add(s.input_supply)
            lines.append(f"create_supply_port {s.input_supply} -direction in")
        if s.output_supply not in seen:
            seen.add(s.output_supply)
            lines.append(f"create_supply_net {s.output_supply} -resolve net")
            lines.append(f"connect_supply_net {s.output_supply} -ports {s.input_supply}")
    for net in aux:
        if net not in seen:
            seen.add(net)
            lines.append(f"create_supply_net {net} -resolve net")
            lines.append(f"connect_supply_net {net} -ports {p.primary_power}")
    if lines:
        lines.insert(0, "# -- Auxiliary supplies ----")
        lines.append("")
    return lines


def _switch_lines(p: UPFParams) -> List[str]:
    if not p.switches:
        return []
    lines = ["# -- Power switches ----"]
    for s in p.switches:
        # Canonical IEEE 1801 state triples: {state supply_port {condition}}.
        on_cond = f"{{{s.control_port}}}" if s.control_port else "{}"
        off_cond = f"{{!{s.control_port}}}" if s.control_port else "{}"
        lines.append(_cont(
            f"create_power_switch {s.name}",
            f"-input_supply_port {s.input_supply}",
            f"-output_supply_port {s.output_supply}",
            f"-control_port {s.control_port}",
            f"-on_state {{{s.on_state} {{{s.input_supply}}} {on_cond}}}",
            f"-off_state {{{s.off_state} {{{s.input_supply}}} {off_cond}}}",
        ))
    lines.append("")
    return lines


def _isolation_lines(p: UPFParams) -> List[str]:
    if not p.isolation:
        return []
    lines = ["# -- Isolation ----"]
    dom = {d.name: d for d in p.domains}
    for iso in p.isolation:
        # Isolation cells on a switchable domain live in the always-on parent
        # so the clamp logic keeps its supply when the domain powers down.
        location = iso.location
        d = dom.get(iso.domain)
        if location == "self" and d and d.domain_type == "switchable":
            location = "parent"
        parts = [
            f"set_isolation iso_{iso.domain}",
            f"-domain {iso.domain}",
            f"-isolation_supply {iso.isolation_supply}",
        ]
        if iso.clamp_value:
            parts.append(f"-clamp_value {iso.clamp_value}")
        parts.append(f"-applies_to {iso.applies_to}")
        parts.append(f"-location {location}")
        lines.append(_cont(*parts))
        # The control signal is a separate command (IEEE 1801
        # set_isolation_control) so the strategy and its control stay clear.
        if iso.signal:
            lines.append(_cont(
                f"set_isolation_control iso_{iso.domain}",
                f"-domain {iso.domain}",
                f"-isolation_signal {iso.signal}",
                f"-isolation_sense high",
            ))
    lines.append("")
    return lines


def _level_shifter_lines(p: UPFParams) -> List[str]:
    if not p.level_shifters:
        return []
    lines = ["# -- Level shifters ----"]
    dom = {d.name: d for d in p.domains}
    for ls in p.level_shifters:
        # A level shifter on a switchable domain must sit in the always-on
        # parent - at `self` it would lose its supply when the domain powers
        # down (UPF-063).
        location = ls.location
        d = dom.get(ls.domain)
        if location == "self" and d and d.domain_type == "switchable":
            location = "parent"
        parts = [
            f"set_level_shifter ls_{ls.domain}",
            f"-domain {ls.domain}",
            f"-location {location}",
        ]
        if ls.threshold:
            parts.append(f"-threshold {ls.threshold}")
        parts.append(f"-applies_to {ls.applies_to}")
        parts.append(f"-rule {ls.rule}")
        lines.append(_cont(*parts))
    lines.append("")
    return lines


def _pst_lines(p: UPFParams) -> List[str]:
    # Supplies that appear in the PST (order is deterministic).
    supplies = [p.primary_power, p.primary_ground]
    for s in p.switches:
        supplies.append(s.output_supply)
    supplies = list(dict.fromkeys(supplies))

    def _resolve(st: PstStateParam) -> dict:
        """Map base names (vdd/vss) onto the actual supply names so state
        rows always reference a supply declared in the PST."""
        full = {}
        for s in supplies:
            if s in st.states:
                full[s] = st.states[s]
            elif s == p.primary_power and "vdd" in st.states:
                full[s] = st.states["vdd"]
            elif s == p.primary_ground and "vss" in st.states:
                full[s] = st.states["vss"]
            else:
                full[s] = "ON"
        return full

    # Author rows first (deterministic order), then the auto-generated
    # per-switch OFF rows.
    rows: List[tuple] = []
    for st in p.pst_states:
        rows.append((st.name, _resolve(st)))
    for s in p.switches:
        full = {sup: "ON" for sup in supplies}
        full[s.output_supply] = "OFF"
        rows.append((f"{s.name}.off", full))

    # Determine exactly which (supply, state) pairs are referenced so we
    # declare only those port states - declaring an unused state would fire
    # UPF-030 (declared state never used by the PST).
    off_supplies: set = {sup for _, row in rows for sup, val in row.items()
                         if val == "OFF"}
    # Ground the ON voltage in real domain voltage where the engineer
    # declared it, so level-shifter thresholds are meaningful.  A supply may
    # be a domain's primary power directly, or a switch output that feeds a
    # switchable domain - both resolve to that domain's voltage.
    switch_out_to_domain = {s.output_supply: s.domain for s in p.switches}

    def _on_voltage(sup: str) -> float:
        for d in p.domains:
            if d.primary_power == sup and d.voltage:
                try:
                    return float(d.voltage)
                except ValueError:
                    pass
        owner = switch_out_to_domain.get(sup)
        if owner:
            for d in p.domains:
                if d.name == owner and d.voltage:
                    try:
                        return float(d.voltage)
                    except ValueError:
                        pass
        return p.on_voltage

    lines = ["# -- Power states / PST ----"]
    for sup in supplies:
        # Ground is always present and its ON value is 0V; every other
        # supply carries the domain voltage (or the project default).
        if sup == p.primary_ground:
            on_val = p.off_voltage
        else:
            on_val = _on_voltage(sup)
        parts = [f"add_port_state {sup}",
                 f"-state {{ON {on_val}}}"]
        if sup in off_supplies:
            parts.append(f"-state {{OFF {p.off_voltage}}}")
        lines.append(_cont(*parts))
    lines.append(_cont(f"create_pst {p.pst_name}",
                       f"-supplies {{{' '.join(supplies)}}}"))
    for name, full in rows:
        state = " ".join(f"{k} {v}" for k, v in full.items())
        lines.append(_cont(f"add_pst_state {name}",
                           f"-pst {p.pst_name}",
                           f"-state {{{state}}}"))
    lines.append("")
    return lines


def _retention_lines(p: UPFParams) -> List[str]:
    if not p.retention:
        return []
    lines = ["# -- Retention ----"]
    lines.append(_cont(
        "create_supply_set retention",
        f"-function {{power {p.retention[0].retention_supply}}}",
        f"-function {{ground {p.primary_ground}}}",
    ))
    for r in p.retention:
        parts = [
            f"set_retention ret_{r.domain}",
            f"-domain {r.domain}",
            f"-retention_supply retention",
        ]
        # Retention elements are explicit when the engineer names them; this
        # is the difference between "domain has a retention strategy" and
        # "these specific registers are retained through power-down".
        if r.elements:
            parts.append(f"-elements {{{r.elements}}}")
        lines.append(_cont(*parts))
        # Save/restore live in the dedicated control command (IEEE 1801
        # set_retention_control), never folded into set_retention.
        lines.append(_cont(
            f"set_retention_control ret_{r.domain}",
            f"-domain {r.domain}",
            f"-save_signal {{{r.save_signal} {r.save_sense}}}",
            f"-restore_signal {{{r.restore_signal} {r.restore_sense}}}",
        ))
    lines.append("")
    return lines


def _repeater_lines(p: UPFParams) -> List[str]:
    if not p.repeaters:
        return []
    lines = ["# -- Repeaters ----"]
    for r in p.repeaters:
        parts = [
            f"set_repeater rep_{r.domain}",
            f"-domain {r.domain}",
            f"-repeater_supply {r.repeater_supply}",
            f"-location {r.location}",
        ]
        if r.driver_type:
            parts.append(f"-driver_type {r.driver_type}")
        parts.append(f"-repeater_signal {r.signal}")
        lines.append(_cont(*parts))
    lines.append("")
    return lines


def _relation_lines(p: UPFParams) -> List[str]:
    """Emit the domain relations as documented topology AND as the real
    strategy commands that make each selected semantics true.

    The relation editor picks the semantics (isolation, level shifter,
    retention); the generator synthesizes the corresponding IEEE 1801 command
    on the from-domain so validation sees real evidence with provenance.
    Switch/control kinds are documented only - the switches that create them
    are generated from the dedicated switch parameters.
    """
    if not p.relations:
        return []
    lines = ["# -- Domain relations (topology; enforced by the strategies below) ----"]
    dom = {d.name: d for d in p.domains}
    for r in p.relations:
        lines.append(f"# relation {r.from_domain} -> {r.to_domain}: {', '.join(r.kind_list)}")
        # Isolation clamps via the TO domain's supply - the boundary's other
        # side - so validation records the cross-domain isolation evidence.
        to_power = dom.get(r.to_domain).primary_power if r.to_domain in dom else ""
        iso_supply = to_power or p.primary_power
        for kind in r.kind_list:
            if kind == "isolation":
                iso_name = f"iso_{r.from_domain}_to_{r.to_domain}"
                lines.append(_cont(
                    f"set_isolation {iso_name}",
                    f"-domain {r.from_domain}",
                    f"-isolation_supply {iso_supply}",
                    f"-applies_to outputs",
                    f"-location parent",
                ))
                lines.append(_cont(
                    f"set_isolation_control {iso_name}",
                    f"-domain {r.from_domain}",
                    f"-isolation_signal iso_en",
                    f"-isolation_sense high",
                ))
            elif kind == "level_shift":
                lines.append(_cont(
                    f"set_level_shifter ls_{r.from_domain}_to_{r.to_domain}",
                    f"-domain {r.from_domain}",
                    f"-location parent",
                    f"-applies_to both",
                    f"-rule both",
                ))
            elif kind == "retention":
                ret_name = f"ret_{r.from_domain}_to_{r.to_domain}"
                lines.append(_cont(
                    f"set_retention {ret_name}",
                    f"-domain {r.from_domain}",
                    f"-retention_supply {iso_supply}",
                ))
                lines.append(_cont(
                    f"set_retention_control {ret_name}",
                    f"-domain {r.from_domain}",
                    f"-save_signal {{save high}}",
                    f"-restore_signal {{restore low}}",
                ))
    lines.append("")
    return lines


def _always_on_lines(p: UPFParams) -> List[str]:
    if not p.always_on:
        return []
    return [
        "# -- Always-on signals ----",
        f"set_port_attributes {', '.join(p.always_on)} -attribute {{always_on true}}",
        "",
    ]


def generate_upf(p: UPFParams) -> str:
    """Render a complete UPF file from :class:`UPFParams`.

    Raises ``ValueError`` for invalid parameters before emitting anything.
    """
    _validate(p)
    lines: List[str] = []
    lines += _header(p)
    lines += _domain_lines(p)
    supply_lines = _supply_lines(p)
    lines += supply_lines
    declared = {p.primary_power, p.primary_ground}
    for d in p.domains:
        declared.add(d.primary_power or p.primary_power)
        declared.add(d.primary_ground or p.primary_ground)
    lines += _aux_supply_lines(p, declared)
    lines += _switch_lines(p)
    lines += _isolation_lines(p)
    lines += _level_shifter_lines(p)
    lines += _pst_lines(p)
    lines += _retention_lines(p)
    lines += _repeater_lines(p)
    lines += _relation_lines(p)
    lines += _always_on_lines(p)
    return "\n".join(lines).rstrip() + "\n"


def generate_project(p: UPFParams) -> Dict[str, str]:
    """Generate a multi-file UPF project (hierarchical mode).

    Returns ``{file_name: content}`` with a deterministic top.upf that loads
    each child UPF under its own scope via ``set_scope`` + ``load_upf`` and a
    ``-supply`` mapping from the child's local supply to the parent supply.

    Ownership is explicit: a domain belongs to the child whose name matches
    the domain (or whose element list contains the child instance), so each
    child file owns its own domain(s), supplies, switches, strategies and
    always-on declarations. Domains not owned by any child stay in the top
    scope. No object is defined twice and the project round-trips through the
    validator as a hierarchy (architecture reported as HIERARCHICAL, with
    per-file provenance).
    """
    if p.architecture != "hierarchical":
        return {"top.upf": generate_upf(p)}
    child_names = list(p.hierarchy)
    if not child_names:
        child_names = [d.name for d in p.domains]

    def _owner(d: DomainParam) -> str:
        """The child scope owning this domain, or '' for top level."""
        for c in child_names:
            if d.name == c or c in d.elements.split():
                return c
        return ""

    files: Dict[str, str] = {}
    top_lines = [
        "# Generated by upf-insight generate (hierarchical)",
        f"upf_version {p.upf_version}",
        "",
        f"set_design_top {p.design_top}",
        "",
    ]
    # Supplies that must be declared at the top scope: primary pair plus any
    # switch input supplies (so the child load_upf -supply mappings resolve
    # against real top-level supplies).
    top_supplies = [p.primary_power, p.primary_ground]
    for s in p.switches:
        if s.input_supply and s.input_supply not in top_supplies:
            top_supplies.append(s.input_supply)
    for sup in top_supplies:
        top_lines.append(f"create_supply_port {sup} -direction in")
        top_lines.append(f"create_supply_net {sup} -resolve port")
        top_lines.append(f"connect_supply_net {sup} -ports {sup}")
    top_lines.append(_cont("create_supply_set primary",
                           f"-function {{power {p.primary_power}}}",
                           f"-function {{ground {p.primary_ground}}}"))
    top_lines.append("")

    top_domains = [d for d in p.domains if not _owner(d)]
    for d in top_domains:
        top_lines.append(f"create_power_domain {d.name} -elements "
                         f"{_tcl_list([e for e in d.elements.replace(',', ' ').split() if e])}")
        if d.domain_type == "always_on":
            top_lines.append(f"set_port_attributes {d.name} -attribute {{always_on true}}")
        top_lines.append(_cont(f"set_domain_supply_net {d.name}",
                               f"-primary_power_net {d.primary_power or p.primary_power}",
                               f"-primary_ground_net {d.primary_ground or p.primary_ground}"))
    if top_domains:
        top_lines.append("")
    for s in p.switches:
        if _owner(_domain_for(p, s.domain)):
            continue
        top_lines.append(_cont(
            f"create_power_switch {s.name}",
            f"-input_supply_port {s.input_supply}",
            f"-output_supply_port {s.output_supply}",
            f"-control_port {s.control_port}",
            f"-on_state {{{s.on_state} {{{s.input_supply}}} {{{s.control_port}}}}}",
            f"-off_state {{{s.off_state} {{{s.input_supply}}} {{!{s.control_port}}}}}",
        ))
    if top_domains or p.switches:
        top_lines.append("")

    child_domain_map: Dict[str, List[DomainParam]] = {c: [] for c in child_names}
    for d in p.domains:
        owner = _owner(d)
        if owner:
            child_domain_map[owner].append(d)

    for child in child_names:
        doms = child_domain_map[child]
        child_lines = [
            "# Generated by upf-insight generate (hierarchical)",
            f"upf_version {p.upf_version}",
            "",
            f"set_scope {child}",
            "",
        ]
        # Per-domain primary power/ground nets (explicit or the project pair)
        # plus switch input supplies, declared in the child scope so every
        # referenced net exists and relations resolve to the real supplies.
        child_sw = [s for s in p.switches if _owner(_domain_for(p, s.domain)) == child]
        declared: List[str] = []
        for d in doms:
            pw = d.primary_power or p.primary_power
            gnd = d.primary_ground or p.primary_ground
            for sup in (pw, gnd):
                if sup not in declared:
                    declared.append(sup)
        for s in child_sw:
            for sup in (s.input_supply, s.output_supply):
                if sup not in declared:
                    declared.append(sup)
        for sup in declared:
            child_lines.append(f"create_supply_port {sup} -direction in")
            child_lines.append(f"create_supply_net {sup} -resolve port")
            child_lines.append(f"connect_supply_net {sup} -ports {sup}")
        child_lines.append("")
        for d in doms:
            child_elements = _tcl_list(
                [e for e in d.elements.replace(',', ' ').split() if e])
            if child_elements.strip("{}"):
                child_lines.append(_cont(f"create_power_domain {d.name}",
                                         f"-elements {child_elements}"))
            else:
                child_lines.append(f"create_power_domain {d.name}")
            if d.domain_type == "always_on":
                child_lines.append(f"set_port_attributes {d.name} -attribute {{always_on true}}")
            child_lines.append(_cont(
                f"set_domain_supply_net {d.name}",
                f"-primary_power_net {d.primary_power or p.primary_power}",
                f"-primary_ground_net {d.primary_ground or p.primary_ground}",
            ))
        child_lines.append("")
        for s in child_sw:
            child_lines.append(_cont(
                f"create_power_switch {s.name}",
                f"-input_supply_port {s.input_supply}",
                f"-output_supply_port {s.output_supply}",
                f"-control_port {s.control_port}",
                f"-on_state {{{s.on_state} {{{s.input_supply}}} {{{s.control_port}}}}}",
                f"-off_state {{{s.off_state} {{{s.input_supply}}} {{!{s.control_port}}}}}",
            ))
        if child_sw:
            child_lines.append("")
        # Relations owned by this child: emit the real strategy commands (the
        # same synthesis the flat path uses) so validation sees the evidence.
        child_rels = [r for r in p.relations
                      if _owner(_domain_for(p, r.from_domain)) == child]
        if child_rels:
            # Pass the FULL domain set so cross-scope relations resolve the
            # to-domain's supply (e.g. core_a -> sram clamps via vdd_sram).
            child_lines.extend(_relation_lines(UPFParams(
                domains=list(p.domains),
                primary_power=p.primary_power,
                primary_ground=p.primary_ground,
                relations=child_rels,
            )))
        files[f"{child}.upf"] = "\n".join(child_lines)

        # load_upf runs in the TOP scope: the -scope option scopes the child
        # UPF, and each -supply {local parent} pair maps the child's local
        # supply onto a same-named supply in this (parent) scope. Keeping the
        # reference scope at top means the parent supplies resolve and the
        # hierarchical integration stays clean.
        mapped = [p.primary_power, p.primary_ground]
        for s in p.switches:
            if _owner(_domain_for(p, s.domain)) == child and s.input_supply:
                mapped.append(s.input_supply)
        maps = [f"-supply {{{sup} {sup}}}" for sup in dict.fromkeys(mapped)]
        top_lines.append(_cont(f"load_upf {child}.upf", f"-scope {child}", *maps))
        top_lines.append("")
    files["top.upf"] = "\n".join(top_lines)
    return files


def _domain_for(p: UPFParams, name: str) -> DomainParam:
    """Return the domain parameter with the given name (or a sentinel)."""
    for d in p.domains:
        if d.name == name:
            return d
    return DomainParam(name)


def generate_skeleton(domains: List[str], always_on: List[str], retention: List[str]) -> str:
    """Scaffold a minimal power-intent skeleton (backwards-compatible API)."""
    if not domains:
        domains = ["core"]
    params = UPFParams(
        domains=[DomainParam(d) for d in domains],
        always_on=list(always_on),
        retention=[RetentionParam(d) for d in retention],
    )
    return generate_upf(params)


__all__ = [
    "UPFParams",
    "DomainParam",
    "SwitchParam",
    "IsolationParam",
    "LevelShifterParam",
    "RetentionParam",
    "RepeaterParam",
    "RelationParam",
    "PstStateParam",
    "generate_upf",
    "generate_project",
    "generate_skeleton",
]