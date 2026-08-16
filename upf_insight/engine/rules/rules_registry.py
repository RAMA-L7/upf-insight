"""UPF rules registry — the canonical list of UPF-Insight rule codes.

Mirrors the sdc-tools `rules_registry.py`: a single source of truth for every
rule code, its severity, layer, and description. The registry is the contract
between the checker, reports, the web UI, and CI policy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    code: str
    severity: str  # error | warning | info
    layer: str  # SYNTAX | REFERENCE | SUPPLY_DOMAIN | PST | STRATEGY | DESIGN
    title: str
    description: str


RULES: list[Rule] = [
    # Layer 1 — Syntax & version
    Rule("UPF-001", "error", "SYNTAX", "Unknown UPF command",
         "The leading command name is not a known UPF command."),
    Rule("UPF-002", "error", "SYNTAX", "Illegal option",
         "An option used with a command is not legal for that command."),
    Rule("UPF-003", "error", "SYNTAX", "Missing required argument",
         "A required argument (e.g. -domain, -elements) is absent."),
    Rule("UPF-004", "warning", "SYNTAX", "Unsupported upf_version",
         "Requested UPF version is not supported or conflicts with features used."),
    Rule("UPF-005", "warning", "SYNTAX", "Deprecated/legacy syntax",
         "A deprecated UPF 1.0/2.0 form is used."),
    Rule("UPF-006", "error", "SYNTAX", "Malformed Tcl",
         "Unbalanced braces/brackets or unterminated continuation."),

    # Layer 2 — Reference integrity
    Rule("UPF-010", "error", "REFERENCE", "Undefined supply reference",
         "A supply net/port/set is referenced before it is defined."),
    Rule("UPF-011", "error", "REFERENCE", "Undefined power domain",
         "A power domain is referenced but never created."),
    Rule("UPF-012", "warning", "REFERENCE", "Undefined instance / bad path",
         "An instance or hierarchical path does not resolve."),
    Rule("UPF-013", "error", "REFERENCE", "Duplicate definition",
         "A domain, supply, switch, strategy or PST name is defined twice."),
    Rule("UPF-014", "warning", "REFERENCE", "Use-before-definition",
         "An object is used before its defining command (load-order issue)."),
    Rule("UPF-015", "warning", "REFERENCE", "Circular dependency",
         "Cyclic load order / domain boundary dependency."),
    Rule("UPF-016", "warning", "REFERENCE", "Invalid set_scope target",
         "set_scope names a module/instance that does not exist."),

    # Layer 3 — Supply & domain integrity
    Rule("UPF-020", "error", "SUPPLY_DOMAIN", "Domain missing primary supply",
         "A power domain has no set_domain_supply_net / -primary_supply_set."),
    Rule("UPF-021", "error", "SUPPLY_DOMAIN", "Domain element overlap",
         "An instance belongs to two power domains."),
    Rule("UPF-022", "warning", "SUPPLY_DOMAIN", "Unconnected supply",
         "A supply port/net/set is not connected to any supply set."),
    Rule("UPF-023", "error", "SUPPLY_DOMAIN", "Supply set missing power/ground",
         "A supply set has no power or ground function."),
    Rule("UPF-024", "error", "SUPPLY_DOMAIN", "Supply connectivity mismatch",
         "connect_supply_net direction/port mismatch in hierarchy."),
    Rule("UPF-025", "info", "SUPPLY_DOMAIN", "Unused supply state",
         "A supply state/voltage is declared but never referenced."),

    # Layer 4 — Power state table
    Rule("UPF-030", "error", "PST", "Declared state never used in PST",
         "add_port_state/add_power_state declares a state never used by the PST."),
    Rule("UPF-031", "error", "PST", "PST references undeclared state",
         "A PST row uses a state that was never declared."),
    Rule("UPF-032", "warning", "PST", "Missing PST",
         "Power states exist but no create_pst was issued."),
    Rule("UPF-033", "warning", "PST", "Empty/unreachable PST state",
         "A PST state covers no legal power combination."),
    Rule("UPF-034", "warning", "PST", "Duplicate/overlapping PST state",
         "Two PST rows declare the same power combination."),
    Rule("UPF-035", "warning", "PST", "Undeclared transition",
         "add_state_transition names an undeclared source/target state."),
    Rule("UPF-036", "warning", "PST", "Isolation/LS not PST-conditioned",
         "Isolation or level-shifter policy is not a mandatory/sufficient condition of the PST."),
    Rule("UPF-037", "warning", "PST", "Un-isolated power-down crossing",
         "A cross-state transition powers a switchable domain down while a receiver stays on, with no active isolation/clamp."),
    Rule("UPF-038", "warning", "PST", "Switchable net not modeled by PST",
         "A power-switch output supplying a domain never appears in the PST; tri-state/floating behavior is unverifiable."),

    # Layer 5 — Strategy lint
    Rule("UPF-040", "error", "STRATEGY", "Isolation on non-always-on supply",
         "Isolation cell uses a switchable (non-always-on) supply."),
    Rule("UPF-041", "error", "STRATEGY", "Isolation self-located in switchable domain",
         "Isolation -location self in a switchable domain loses power."),
    Rule("UPF-042", "warning", "STRATEGY", "Missing isolation on crossing",
         "A crossing into/out of a powered-down domain is not isolated."),
    Rule("UPF-043", "info", "STRATEGY", "Redundant isolation",
         "Isolation applied on an always-on crossing."),
    Rule("UPF-044", "warning", "STRATEGY", "-applies_to missing inouts",
         "-applies_to outputs misses inouts (bidirectional ports)."),
    Rule("UPF-045", "error", "STRATEGY", "Isolation without control (or reverse)",
         "set_isolation has no matching set_isolation_control, or vice versa."),
    Rule("UPF-046", "error", "STRATEGY", "Invalid clamp value",
         "clamp_value is invalid for the target state/domain."),
    Rule("UPF-047", "warning", "STRATEGY", "Isolation control not always-on",
         "Isolation control signal is not driven by always-on logic."),

    Rule("UPF-050", "error", "STRATEGY", "Retention supply powers down",
         "The retention supply is not always-on."),
    Rule("UPF-051", "warning", "STRATEGY", "Retention control not always-on",
         "Save/restore control is not driven by always-on logic."),
    Rule("UPF-052", "warning", "STRATEGY", "Retention without coverage",
         "set_retention references no retention elements."),
    Rule("UPF-053", "warning", "STRATEGY", "Retention control tied constant",
         "Retention control is tied to a constant and never toggles."),
    Rule("UPF-054", "error", "STRATEGY", "Retention without control",
         "set_retention has no matching set_retention_control (missing "
         "-save_signal / -restore_signal)."),

    Rule("UPF-060", "info", "STRATEGY", "Unnecessary level shifter",
         "Level shifter between equal-voltage domains (wasted area/power)."),
    Rule("UPF-061", "error", "STRATEGY", "Missing level shifter",
         "A crossing between different-voltage domains lacks a level shifter."),
    Rule("UPF-062", "error", "STRATEGY", "Wrong level-shifter rule",
         "low_to_high vs high_to_low mismatch for the voltage pair."),
    Rule("UPF-063", "error", "STRATEGY", "Level shifter self-located in switchable domain",
         "-location self for a level shifter in a switchable domain."),
    Rule("UPF-064", "warning", "STRATEGY", "Level-shifter control not always-on",
         "set_level_shifter_control signal is not driven by always-on logic."),

    Rule("UPF-070", "error", "STRATEGY", "Switch references undefined supply",
         "A power switch references a supply net defined after it."),
    Rule("UPF-071", "warning", "STRATEGY", "Switch control not always-on",
         "Power-switch control signal is not from always-on logic."),
    Rule("UPF-072", "error", "STRATEGY", "Always-on signal into switchable domain",
         "An always-on signal (clk/rst/scan) crosses into a switchable domain un-isolated."),
    Rule("UPF-073", "info", "STRATEGY", "Switch output unused",
         "A power switch output supply is not used by any domain."),
    Rule("UPF-074", "warning", "STRATEGY", "Switch state condition without control",
         "A power-switch on/off state condition must reference the control port."),

    # Layer 6 — Design-aware (v2; requires netlist/RTL context)
    Rule("UPF-080", "warning", "DESIGN", "Unknown -elements instance",
         "An instance in -elements does not exist in the netlist."),
    Rule("UPF-081", "warning", "DESIGN", "Unknown control signal",
         "An isolation/retention/switch control signal is not in the design."),
    Rule("UPF-082", "warning", "DESIGN", "Uncovered crossing (endpoint-based)",
         "A cross-domain signal lacks a strategy when considering endpoints."),
    Rule("UPF-083", "warning", "DESIGN", "Retention coverage gap",
         "Retention coverage does not cover the sequential elements present."),
    Rule("UPF-084", "warning", "DESIGN", "Library PG mismatch",
         "UPF supply mapping conflicts with liberty PG pin declarations."),

    # Repeater strategies (IEEE 1801 set_repeater / set_repeater_control)
    Rule("UPF-090", "error", "STRATEGY", "Repeater supply not always-on",
         "The repeater supply is not declared or is not always-on."),
    Rule("UPF-091", "warning", "STRATEGY", "Repeater control not always-on",
         "Repeater enable control is not driven by always-on logic."),
    Rule("UPF-092", "error", "STRATEGY", "Repeater self-located in switchable domain",
         "-location self for a repeater in a switchable domain loses power."),
    Rule("UPF-093", "warning", "STRATEGY", "Repeater without elements",
         "set_repeater references no repeater elements (-elements empty)."),
    Rule("UPF-094", "error", "STRATEGY", "Repeater without control",
         "set_repeater has no matching set_repeater_control (missing "
         "-repeater_signal)."),

    # Hierarchical UPF (promotion/demotion + composition)
    Rule("UPF-095", "error", "REFERENCE", "Promoted entity not defined",
         "upf_promote names an object that is not defined in the child scope."),
    Rule("UPF-096", "warning", "DESIGN", "Demotion not verifiable",
         "upf_demote resolution requires the netlist hierarchy."),
    Rule("UPF-097", "warning", "DESIGN", "Hierarchical composition unverified",
         "load_upf composes hierarchical UPF; resolution requires a netlist."),

    # Supply equivalence / library mapping
    Rule("UPF-098", "error", "REFERENCE", "Equivalent supply undefined",
         "set_equivalent names a supply that is not declared as net/port/set."),
]


def registered_rules() -> list[Rule]:
    return list(RULES)


def get_rule(code: str) -> Rule | None:
    for r in RULES:
        if r.code == code:
            return r
    return None


__all__ = ["Rule", "RULES", "registered_rules", "get_rule"]