"""UPF rules registry - the canonical list of UPF-Insight rule codes.

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
    #: Prerequisite rule codes. When a prerequisite produces an error finding
    #: on the same subject, this rule's findings on that subject are
    #: downgraded (blocked) instead of emitted as definitive secondary errors.
    #: Example: UPF-070 (switch references undefined supply) is the same
    #: defect as UPF-010 (undefined supply reference), so UPF-010 blocks it.
    depends_on: tuple[str, ...] = ()
    #: The power-intent facts this rule consumes to reach its conclusion
    #: (e.g. "switch output supply", "domain primary power", "PST rows").
    semantic_inputs: tuple[str, ...] = ()
    #: Design-context requirement: which inputs the rule needs to be
    #: definitive. UPF_ONLY = provable from the UPF alone; NETLIST_REQUIRED =
    #: needs the netlist/RTL to establish crossings; PARTIAL = advisory only.
    context: str = "UPF_ONLY"  # UPF_ONLY | NETLIST_REQUIRED | PARTIAL
    #: Name of the regression test that proves this rule fires (positive case)
    #: or stays quiet (negative case). Audit fails when empty.
    test_ref: str = ""


RULES: list[Rule] = [
    # Layer 1 - Syntax & version
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

    # Layer 2 - Reference integrity
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

    # Layer 3 - Supply & domain integrity
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

    # Layer 4 - Power state table
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
    Rule("UPF-039", "error", "PST", "Impossible PST state",
         "A PST row declares a switch output ON while its input supply is OFF - power appearing out of nowhere."),

    # Layer 5 - Strategy lint
    Rule("UPF-040", "error", "STRATEGY", "Isolation on non-always-on supply",
         "Isolation cell uses a switchable (non-always-on) supply.",
         depends_on=("UPF-011",)),
    Rule("UPF-041", "error", "STRATEGY", "Isolation self-located in switchable domain",
         "Isolation -location self in a switchable domain loses power.",
         depends_on=("UPF-011",)),
    Rule("UPF-042", "warning", "STRATEGY", "Missing isolation on crossing",
         "A crossing into/out of a powered-down domain is not isolated.",
         depends_on=("UPF-011",)),
    Rule("UPF-043", "info", "STRATEGY", "Redundant isolation",
         "Isolation applied on an always-on crossing.",
         depends_on=("UPF-011",)),
    Rule("UPF-044", "warning", "STRATEGY", "-applies_to missing inouts",
         "-applies_to outputs misses inouts (bidirectional ports).",
         depends_on=("UPF-011",)),
    Rule("UPF-045", "error", "STRATEGY", "Isolation without control (or reverse)",
         "set_isolation has no matching set_isolation_control, or vice versa.",
         depends_on=("UPF-011",)),
    Rule("UPF-046", "error", "STRATEGY", "Invalid clamp value",
         "clamp_value is invalid for the target state/domain.",
         depends_on=("UPF-011",)),
    Rule("UPF-047", "warning", "STRATEGY", "Isolation control not always-on",
         "Isolation control signal is not driven by always-on logic.",
         depends_on=("UPF-011",)),

    Rule("UPF-050", "error", "STRATEGY", "Retention supply powers down",
         "The retention supply is not always-on.",
         depends_on=("UPF-011",)),
    Rule("UPF-051", "warning", "STRATEGY", "Retention control not always-on",
         "Save/restore control is not driven by always-on logic.",
         depends_on=("UPF-011",)),
    Rule("UPF-052", "warning", "STRATEGY", "Retention without coverage",
         "set_retention references no retention elements.",
         depends_on=("UPF-011",)),
    Rule("UPF-053", "warning", "STRATEGY", "Retention control tied constant",
         "Retention control is tied to a constant and never toggles.",
         depends_on=("UPF-011",)),
    Rule("UPF-054", "error", "STRATEGY", "Retention without control",
         "set_retention has no matching set_retention_control (missing "
         "-save_signal / -restore_signal).",
         depends_on=("UPF-011",)),

    Rule("UPF-060", "info", "STRATEGY", "Unnecessary level shifter",
         "Level shifter between equal-voltage domains (wasted area/power).",
         depends_on=("UPF-011",)),
    Rule("UPF-061", "error", "STRATEGY", "Missing level shifter",
         "A crossing between different-voltage domains lacks a level shifter.",
         depends_on=("UPF-011",)),
    Rule("UPF-062", "error", "STRATEGY", "Wrong level-shifter rule",
         "low_to_high vs high_to_low mismatch for the voltage pair.",
         depends_on=("UPF-011",)),
    Rule("UPF-063", "error", "STRATEGY", "Level shifter self-located in switchable domain",
         "-location self for a level shifter in a switchable domain.",
         depends_on=("UPF-011",)),
    Rule("UPF-064", "warning", "STRATEGY", "Level-shifter control not always-on",
         "set_level_shifter_control signal is not driven by always-on logic.",
         depends_on=("UPF-011",)),

    Rule("UPF-070", "error", "STRATEGY", "Switch references undefined supply",
         "A power switch references a supply net defined after it.",
         depends_on=("UPF-010",)),
    Rule("UPF-071", "warning", "STRATEGY", "Switch control not always-on",
         "Power-switch control signal is not from always-on logic."),
    Rule("UPF-072", "error", "STRATEGY", "Always-on signal into switchable domain",
         "An always-on signal (clk/rst/scan) crosses into a switchable domain un-isolated."),
    Rule("UPF-073", "error", "STRATEGY", "Switch output unused",
         "A power switch output supply is not used by any domain - the switchable domain is not powered by the switch.",
         depends_on=("UPF-010",)),
    Rule("UPF-074", "warning", "STRATEGY", "Switch state condition without control",
         "A power-switch on/off state condition must reference the control port."),
    Rule("UPF-075", "error", "STRATEGY", "Switch cannot toggle",
         "A switch on-state and off-state conditions are identical - it can never change state."),
    Rule("UPF-076", "error", "STRATEGY", "Switch without off-state",
         "A power switch declares an on-state but no off-state - the domain can never power down."),
    Rule("UPF-077", "error", "STRATEGY", "Switch without control port",
         "A power switch declares no control port - the switch can never be toggled."),
    Rule("UPF-078", "error", "STRATEGY", "Retention without supply on switchable domain",
         "Retention on a switchable domain names no retention supply - state cannot be preserved through power-down."),
    Rule("UPF-079", "warning", "STRATEGY", "Level-shifter threshold out of range",
         "A level-shifter threshold lies outside every known supply voltage - implausible trip point for any declared crossing."),
    Rule("UPF-065", "error", "SUPPLY", "Ground on switched supply",
         "A domain uses a power-switch output as its primary ground - the ground reference must be an always-on low rail."),

    # Layer 6 - Design-aware (v2; requires netlist/RTL context)
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

    # Strategy interactions (duplicate/override/conflict analysis)
    Rule("UPF-085", "error", "STRATEGY", "Duplicate strategy",
         "Two identical strategies of the same type target the same domain "
         "and elements - the second is redundant.",
         depends_on=("UPF-011",)),
    Rule("UPF-086", "warning", "STRATEGY", "Overriding or conflicting strategy",
         "A later strategy of the same type silently overrides an earlier "
         "one, or two strategies conflict (overlapping switch outputs, "
         "contradictory locations, redefined retention).",
         depends_on=("UPF-011",)),
    Rule("UPF-087", "warning", "STRATEGY", "Low-specificity wildcard",
         "A wildcard pattern used for elements/targets has low specificity; "
         "matches are resolved at elaboration time and may drift.",
         depends_on=("UPF-011",)),

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

    # Hierarchical supply mapping / load_upf provenance
    Rule("UPF-099", "error", "REFERENCE", "Supply map reference undefined",
         "load_upf -supply maps a local supply to a parent supply; both sides "
         "must resolve to declared supplies."),
    Rule("UPF-100", "warning", "DESIGN", "Loaded UPF file missing",
         "load_upf names a child UPF file that does not exist in the workspace."),
]


#: Per-rule semantic metadata: which power-intent facts the rule consumes
#: (semantic_inputs), whether it is definitive from UPF alone (context), and
#: the regression test that proves it fires / stays quiet (test_ref).
#: The audit (``upf_insight.engine.rules.audit``) fails when a registered
#: rule has no metadata entry or an empty test_ref.
RULE_META: dict[str, dict] = {
    # Layer 1 - Syntax & version
    "UPF-001": dict(semantic_inputs=("command name",), context="UPF_ONLY",
                    test_ref="test_syntax_reference_family_fires_on_bad_fixture"),
    "UPF-002": dict(semantic_inputs=("command options",), context="UPF_ONLY",
                    test_ref="test_syntax_reference_family_fires_on_bad_fixture"),
    "UPF-003": dict(semantic_inputs=("required arguments",), context="UPF_ONLY",
                    test_ref="test_syntax_reference_family_fires_on_bad_fixture"),
    "UPF-004": dict(semantic_inputs=("upf_version",), context="UPF_ONLY",
                    test_ref="test_syntax_reference_family_fires_on_bad_fixture"),
    "UPF-005": dict(semantic_inputs=("command form",), context="UPF_ONLY",
                    test_ref="test_syntax_reference_family_fires_on_bad_fixture"),
    "UPF-006": dict(semantic_inputs=("Tcl token balance",), context="UPF_ONLY",
                    test_ref="test_preprocess_strips_comments_and_joins"),
    # Layer 2 - Reference integrity
    "UPF-010": dict(semantic_inputs=("supply references", "supply definitions"),
                    context="UPF_ONLY", test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-011": dict(semantic_inputs=("strategy domain refs", "domain definitions"),
                    context="UPF_ONLY", test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-012": dict(semantic_inputs=("instance paths",), context="NETLIST_REQUIRED",
                    test_ref="test_design_aware_family_fires_with_netlist"),
    "UPF-013": dict(semantic_inputs=("definition records",), context="UPF_ONLY",
                    test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-014": dict(semantic_inputs=("load order", "definition lines"),
                    context="UPF_ONLY", test_ref="test_syntax_reference_family_fires_on_bad_fixture"),
    "UPF-015": dict(semantic_inputs=("load order graph",), context="PARTIAL",
                    test_ref="test_circular_supply_set_function_fires_upf015"),
    "UPF-016": dict(semantic_inputs=("set_scope targets",), context="NETLIST_REQUIRED",
                    test_ref="test_design_aware_family_fires_with_netlist"),
    # Layer 3 - Supply & domain integrity
    "UPF-020": dict(semantic_inputs=("domain primary supply",), context="UPF_ONLY",
                    test_ref="test_set_domain_supply_net_is_modeled"),
    "UPF-021": dict(semantic_inputs=("domain elements",), context="NETLIST_REQUIRED",
                    test_ref="test_domain_element_overlap_fires"),
    "UPF-022": dict(semantic_inputs=("supply connectivity",), context="UPF_ONLY",
                    test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-023": dict(semantic_inputs=("supply set functions",), context="UPF_ONLY",
                    test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-024": dict(semantic_inputs=("connect_supply_net direction", "ports"),
                    context="UPF_ONLY", test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-025": dict(semantic_inputs=("supply states",), context="UPF_ONLY",
                    test_ref="test_pst_family_fires_on_bad_fixture"),
    # Layer 4 - Power state table
    "UPF-030": dict(semantic_inputs=("declared states", "PST rows"), context="UPF_ONLY",
                    test_ref="test_pst_family_fires_on_bad_fixture"),
    "UPF-031": dict(semantic_inputs=("PST rows", "declared states"), context="UPF_ONLY",
                    test_ref="test_pst_family_fires_on_bad_fixture"),
    "UPF-032": dict(semantic_inputs=("supply states", "PST existence"), context="UPF_ONLY",
                    test_ref="test_pst_family_fires_on_bad_fixture"),
    "UPF-033": dict(semantic_inputs=("PST rows", "transitions"), context="UPF_ONLY",
                    test_ref="test_pst_family_fires_on_bad_fixture"),
    "UPF-034": dict(semantic_inputs=("PST rows",), context="UPF_ONLY",
                    test_ref="test_pst_analysis_golden"),
    "UPF-035": dict(semantic_inputs=("transitions", "PST states"), context="UPF_ONLY",
                    test_ref="test_pst_transition_parsing_multipair"),
    "UPF-036": dict(semantic_inputs=("isolation/LS policy", "PST conditions"),
                    context="PARTIAL", test_ref="test_pst_cross_state_fires_on_bad_fixture"),
    "UPF-037": dict(semantic_inputs=("PST transitions", "isolation state"),
                    context="PARTIAL", test_ref="test_pst_cross_state_fires_on_bad_fixture"),
    "UPF-038": dict(semantic_inputs=("switch outputs", "PST supplies"), context="UPF_ONLY",
                    test_ref="test_pst_family_fires_on_bad_fixture"),
    "UPF-039": dict(semantic_inputs=("switch in/out supplies", "PST rows"),
                    context="UPF_ONLY", test_ref="test_every_mutation_detected_with_expected_rule"),
    # Layer 5 - Strategy lint
    "UPF-040": dict(semantic_inputs=("isolation supply", "switch outputs"),
                    context="PARTIAL", test_ref="test_isolation_family_fires_on_bad_fixture"),
    "UPF-041": dict(semantic_inputs=("isolation location", "domain primary"),
                    context="UPF_ONLY", test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-042": dict(semantic_inputs=("switchable domains", "isolation strategies"),
                    context="NETLIST_REQUIRED", test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-043": dict(semantic_inputs=("isolation domain", "domain primary"),
                    context="UPF_ONLY", test_ref="test_isolation_family_fires_on_bad_fixture"),
    "UPF-044": dict(semantic_inputs=("applies_to",), context="NETLIST_REQUIRED",
                    test_ref="test_isolation_family_fires_on_bad_fixture"),
    "UPF-045": dict(semantic_inputs=("isolation control",), context="UPF_ONLY",
                    test_ref="test_isolation_family_fires_on_bad_fixture"),
    "UPF-046": dict(semantic_inputs=("clamp_value", "supply states"), context="UPF_ONLY",
                    test_ref="test_isolation_family_fires_on_bad_fixture"),
    "UPF-047": dict(semantic_inputs=("isolation control", "port attributes"),
                    context="PARTIAL", test_ref="test_isolation_family_fires_on_bad_fixture"),
    "UPF-050": dict(semantic_inputs=("retention supply", "PST states"),
                    context="PARTIAL", test_ref="test_retention_ls_family_fires_on_bad_fixture"),
    "UPF-051": dict(semantic_inputs=("save/restore controls", "port attributes"),
                    context="PARTIAL", test_ref="test_retention_ls_family_fires_on_bad_fixture"),
    "UPF-052": dict(semantic_inputs=("retention elements",), context="UPF_ONLY",
                    test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-053": dict(semantic_inputs=("save/restore pairs", "sense"), context="UPF_ONLY",
                    test_ref="test_retention_ls_family_fires_on_bad_fixture"),
    "UPF-054": dict(semantic_inputs=("retention control",), context="UPF_ONLY",
                    test_ref="test_retention_ls_family_fires_on_bad_fixture"),
    "UPF-060": dict(semantic_inputs=("LS domain voltage", "other domain voltages"),
                    context="PARTIAL", test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-061": dict(semantic_inputs=("domain voltages", "LS strategies"),
                    context="UPF_ONLY", test_ref="test_level_shifter_voltage_rules"),
    "UPF-062": dict(semantic_inputs=("LS rule", "domain voltages"), context="UPF_ONLY",
                    test_ref="test_level_shifter_voltage_rules"),
    "UPF-063": dict(semantic_inputs=("LS location", "domain primary"), context="UPF_ONLY",
                    test_ref="test_level_shifter_voltage_rules"),
    "UPF-064": dict(semantic_inputs=("LS control", "port attributes"), context="PARTIAL",
                    test_ref="test_retention_ls_family_fires_on_bad_fixture"),
    "UPF-065": dict(semantic_inputs=("domain ground", "switch outputs"), context="UPF_ONLY",
                    test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-070": dict(semantic_inputs=("switch supplies", "supply definitions"),
                    context="UPF_ONLY", test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-071": dict(semantic_inputs=("switch control", "port attributes"),
                    context="PARTIAL", test_ref="test_switch_family_fires_on_bad_fixture"),
    "UPF-072": dict(semantic_inputs=("always-on signals", "switchable domains"),
                    context="NETLIST_REQUIRED", test_ref="test_switch_family_fires_on_bad_fixture"),
    "UPF-073": dict(semantic_inputs=("switch output", "domain primary supplies"),
                    context="UPF_ONLY", test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-074": dict(semantic_inputs=("on/off conditions", "control port"),
                    context="UPF_ONLY", test_ref="test_switch_family_fires_on_bad_fixture"),
    "UPF-075": dict(semantic_inputs=("on/off conditions",), context="UPF_ONLY",
                    test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-076": dict(semantic_inputs=("off-state",), context="UPF_ONLY",
                    test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-077": dict(semantic_inputs=("control port",), context="UPF_ONLY",
                    test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-078": dict(semantic_inputs=("retention supply", "domain primary"),
                    context="UPF_ONLY", test_ref="test_every_mutation_detected_with_expected_rule"),
    "UPF-079": dict(semantic_inputs=("LS threshold", "supply voltages"),
                    context="PARTIAL", test_ref="test_every_mutation_detected_with_expected_rule"),
    # Layer 6 - Design-aware (requires netlist/RTL context)
    "UPF-080": dict(semantic_inputs=("elements instances", "netlist"),
                    context="NETLIST_REQUIRED", test_ref="test_design_aware_family_fires_with_netlist"),
    "UPF-081": dict(semantic_inputs=("control signals", "netlist"),
                    context="NETLIST_REQUIRED", test_ref="test_design_aware_family_fires_with_netlist"),
    "UPF-082": dict(semantic_inputs=("crossing endpoints", "strategies"),
                    context="NETLIST_REQUIRED", test_ref="test_design_aware_family_fires_with_netlist"),
    "UPF-083": dict(semantic_inputs=("sequential elements", "retention coverage"),
                    context="NETLIST_REQUIRED", test_ref="test_design_aware_family_fires_with_netlist"),
    "UPF-084": dict(semantic_inputs=("liberty PG pins", "supply mapping"),
                    context="NETLIST_REQUIRED", test_ref="test_design_aware_family_fires_with_netlist"),
    # Strategy interactions
    "UPF-085": dict(semantic_inputs=("strategy parameters", "strategy domains"),
                    context="UPF_ONLY",
                    test_ref="test_exact_duplicate_isolation_is_upf085_error"),
    "UPF-086": dict(semantic_inputs=("strategy parameters", "switch outputs",
                                     "strategy locations"),
                    context="UPF_ONLY",
                    test_ref="test_differing_parameter_isolation_is_upf086_override"),
    "UPF-087": dict(semantic_inputs=("wildcard patterns", "element targets"),
                    context="PARTIAL", test_ref="test_wildcard_heavy_domain_element_is_high_risk"),
    # Repeater strategies
    "UPF-090": dict(semantic_inputs=("repeater supply",), context="UPF_ONLY",
                    test_ref="test_repeater_happy_path_modeled"),
    "UPF-091": dict(semantic_inputs=("repeater control", "port attributes"),
                    context="PARTIAL", test_ref="test_repeater_happy_path_modeled"),
    "UPF-092": dict(semantic_inputs=("repeater location", "domain primary"),
                    context="UPF_ONLY", test_ref="test_repeater_happy_path_modeled"),
    "UPF-093": dict(semantic_inputs=("repeater elements",), context="UPF_ONLY",
                    test_ref="test_repeater_happy_path_modeled"),
    "UPF-094": dict(semantic_inputs=("repeater control",), context="UPF_ONLY",
                    test_ref="test_repeater_happy_path_modeled"),
    # Hierarchical UPF
    "UPF-095": dict(semantic_inputs=("promoted objects", "child scope"),
                    context="UPF_ONLY", test_ref="test_hierarchical_fixture_architecture_and_ownership"),
    "UPF-096": dict(semantic_inputs=("demotion targets", "netlist"),
                    context="NETLIST_REQUIRED", test_ref="test_hierarchical_fixture_architecture_and_ownership"),
    "UPF-097": dict(semantic_inputs=("load_upf composition", "netlist"),
                    context="NETLIST_REQUIRED", test_ref="test_hierarchical_fixture_architecture_and_ownership"),
    "UPF-098": dict(semantic_inputs=("set_equivalent refs",), context="UPF_ONLY",
                    test_ref="test_syntax_reference_family_fires_on_bad_fixture"),
    "UPF-099": dict(semantic_inputs=("supply map refs",), context="UPF_ONLY",
                    test_ref="test_hierarchical_fixture_architecture_and_ownership"),
    "UPF-100": dict(semantic_inputs=("load_upf file refs", "workspace"),
                    context="NETLIST_REQUIRED", test_ref="test_hierarchical_fixture_architecture_and_ownership"),
}


def registered_rules() -> list[Rule]:
    out: list[Rule] = []
    for r in RULES:
        meta = RULE_META.get(r.code, {})
        out.append(Rule(
            code=r.code,
            severity=r.severity,
            layer=r.layer,
            title=r.title,
            description=r.description,
            depends_on=r.depends_on,
            semantic_inputs=meta.get("semantic_inputs", r.semantic_inputs),
            context=meta.get("context", r.context),
            test_ref=meta.get("test_ref", r.test_ref),
        ))
    # Deterministic, insertion-order-independent registry ordering.
    out.sort(key=lambda r: r.code)
    return out


def get_rule(code: str) -> Rule | None:
    for r in registered_rules():
        if r.code == code:
            return r
    return None


__all__ = ["Rule", "RULES", "RULE_META", "registered_rules", "get_rule"]