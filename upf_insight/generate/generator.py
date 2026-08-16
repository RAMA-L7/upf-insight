"""UPF generator — deterministic, template-driven power-intent construction.

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


@dataclass
class LevelShifterParam:
    """A level shifter at a domain boundary."""

    domain: str
    location: str = "self"  # self | inout | input | output | fanout
    threshold: str = ""  # optional, e.g. "0.8"
    rule: str = "low_to_high"  # low_to_high | high_to_low | both


@dataclass
class RetentionParam:
    """Retention strategy for a domain."""

    domain: str
    retention_supply: str = "vdd_ret"
    save_signal: str = "save"
    restore_signal: str = "restore"


@dataclass
class RepeaterParam:
    """A signal repeater on a domain boundary (set_repeater)."""

    domain: str
    repeater_supply: str = "vdd_rep"
    signal: str = "rep_en"
    location: str = "self"  # self | parent | fanout
    driver_type: str = "minimal"  # minimal | non_inverting | inverting


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
            PstStateParam("PS_ON", {"vdd": "ON", "vss": "ON"}),
            PstStateParam("PS_OFF", {"vdd": "OFF", "vss": "ON"}),
        ]
    )
    always_on: List[str] = field(default_factory=list)


def _tcl_list(parts: List[str]) -> str:
    """Join identifiers into a braced TCL list (empty -> {})."""
    return "{" + " ".join(parts) + "}"


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
        lines.append(f"create_power_domain {d.name} -elements {elements}")
    lines.append("")
    return lines


def _supply_lines(p: UPFParams) -> List[str]:
    pp, pg = p.primary_power, p.primary_ground
    lines = ["# -- Supply network ----"]
    for s in (pp, pg):
        lines.append(f"create_supply_port {s} -direction in")
        lines.append(f"create_supply_net {s} -resolve port")
        lines.append(f"connect_supply_net {s} -ports {s}")
    lines.append(f"create_supply_set primary -function {{power {pp}}} -function {{ground {pg}}}")
    for d in p.domains:
        lines.append(
            f"set_domain_supply_net {d.name} "
            f"-primary_power_net {d.primary_power or pp} -primary_ground_net {d.primary_ground or pg}"
        )
    lines.append("")
    return lines


def _aux_supply_lines(p: UPFParams) -> List[str]:
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
    seen: set = set()
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
        lines.append(
            f"create_power_switch {s.name} "
            f"-input_supply_port {s.input_supply} -output_supply_port {s.output_supply} "
            f"-control_port {s.control_port} "
            f"-on_state {{{s.on_state} {{{s.input_supply}}} {on_cond}}} "
            f"-off_state {{{s.off_state} {{{s.input_supply}}} {off_cond}}}"
        )
    lines.append("")
    return lines


def _isolation_lines(p: UPFParams) -> List[str]:
    if not p.isolation:
        return []
    lines = ["# -- Isolation ----"]
    for iso in p.isolation:
        parts = [
            f"set_isolation iso_{iso.domain}",
            f"-domain {iso.domain}",
            f"-isolation_supply {iso.isolation_supply}",
        ]
        if iso.clamp_value:
            clamp = iso.clamp_value
            parts.append(f"-clamp_value {clamp}")
        parts.append(f"-isolation_signal {iso.signal}")
        parts.append(f"-location {iso.location}")
        lines.append(" ".join(parts))
    lines.append("")
    return lines


def _level_shifter_lines(p: UPFParams) -> List[str]:
    if not p.level_shifters:
        return []
    lines = ["# -- Level shifters ----"]
    for ls in p.level_shifters:
        parts = [
            f"set_level_shifter ls_{ls.domain}",
            f"-domain {ls.domain}",
            f"-location {ls.location}",
        ]
        if ls.threshold:
            parts.append(f"-threshold {ls.threshold}")
        parts.append(f"-rule {ls.rule}")
        lines.append(" ".join(parts))
    lines.append("")
    return lines


def _pst_lines(p: UPFParams) -> List[str]:
    supplies = [p.primary_power, p.primary_ground]
    lines = ["# -- Power states / PST ----"]
    lines.append(f"add_port_state {p.primary_power} -state {{ON {p.on_voltage}}} -state {{OFF {p.off_voltage}}}")
    lines.append(f"add_port_state {p.primary_ground} -state {{ON {p.off_voltage}}}")
    for s in p.switches:
        lines.append(
            f"add_port_state {s.output_supply} -state {{ON {p.on_voltage}}} -state {{OFF {p.off_voltage}}}"
        )
        supplies.append(s.output_supply)
    lines.append(f"create_pst {p.pst_name} -supplies {{{' '.join(dict.fromkeys(supplies))}}}")
    for st in p.pst_states:
        full = {s: st.states.get(s, "ON") for s in dict.fromkeys(supplies)}
        state = " ".join(f"{k} {v}" for k, v in full.items())
        lines.append(f"add_pst_state {st.name} -pst {p.pst_name} -state {{{state}}}")
    for s in p.switches:
        full = {sup: "ON" for sup in dict.fromkeys(supplies)}
        full[s.output_supply] = "OFF"
        state = " ".join(f"{k} {v}" for k, v in full.items())
        lines.append(f"add_pst_state {s.name}.off -pst {p.pst_name} -state {{{state}}}")
    lines.append("")
    return lines


def _retention_lines(p: UPFParams) -> List[str]:
    if not p.retention:
        return []
    lines = ["# -- Retention ----"]
    lines.append(
        f"create_supply_set retention -function {{power {p.retention[0].retention_supply}}} "
        f"-function {{ground {p.primary_ground}}}"
    )
    for r in p.retention:
        lines.append(
            f"set_retention ret_{r.domain} -domain {r.domain} "
            f"-retention_supply retention -save_signal {r.save_signal} "
            f"-restore_signal {r.restore_signal}"
        )
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
        lines.append(" ".join(parts))
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
    lines += _supply_lines(p)
    lines += _aux_supply_lines(p)
    lines += _switch_lines(p)
    lines += _isolation_lines(p)
    lines += _level_shifter_lines(p)
    lines += _pst_lines(p)
    lines += _retention_lines(p)
    lines += _repeater_lines(p)
    lines += _always_on_lines(p)
    return "\n".join(lines).rstrip() + "\n"


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
    "PstStateParam",
    "generate_upf",
    "generate_skeleton",
]