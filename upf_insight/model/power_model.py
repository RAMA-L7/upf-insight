"""Power-intent model - the in-memory object graph built from UPF commands.

UPF is hierarchical and stateful, so validation runs against a model rather
than against raw text. This module defines the core entities:

- Scope (hierarchy position)
- Power domains (with their element sets)
- Supply ports / nets / sets (and their functions and connectivity)
- Power switches (control + supply mapping)
- Power states, supply states, and the Power State Table (PST)
- Strategies: isolation, level shifting, retention (with control/clamp/location)

Entities are deliberately plain data objects; rules live in the checker.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PowerDomain:
    name: str
    scope: str
    elements: List[str] = field(default_factory=list)
    primary_supply_sets: Dict[str, str] = field(default_factory=dict)
    declared_line: Optional[int] = None
    declared_file: Optional[str] = None


@dataclass
class SupplyPort:
    name: str
    scope: str
    direction: str = "inout"  # in | out | inout
    declared_line: Optional[int] = None
    declared_file: Optional[str] = None


@dataclass
class SupplyNet:
    name: str
    scope: str
    connected_to: List[str] = field(default_factory=list)  # resolve_net identifiers
    declared_line: Optional[int] = None
    declared_file: Optional[str] = None


@dataclass
class SupplySet:
    name: str
    scope: str
    functions: Dict[str, str] = field(default_factory=dict)  # power/ground -> supply
    declared_line: Optional[int] = None
    declared_file: Optional[str] = None


@dataclass
class PowerSwitch:
    name: str
    scope: str
    input_supply: Optional[str] = None
    output_supply: Optional[str] = None
    control_port: Optional[str] = None
    #: Role half of a ``-control_port {role signal}`` pair (e.g. ``ctrl``).
    #: Retained because on/off-state conditions may legitimately reference the
    #: role rather than the signal: ``-on_state {on_s vin {ctrl}}``.
    control_port_role: Optional[str] = None
    #: Role halves of the supply-port pairs, e.g. ``{vout VDD_SW}`` yields
    #: ``("vout", "vin")``. IEEE 1801 lets ``create_pst -supplies`` name a
    #: switched supply by its *port path* (``SW/vout``) as well as by its net
    #: name, so the role is needed to recognise a supply the PST does model.
    output_port_role: Optional[str] = None
    input_port_role: Optional[str] = None
    on_state: Optional[str] = None      # on-state name (from -on_state triple)
    off_state: Optional[str] = None     # off-state name (from -off_state triple)
    on_state_supply: Optional[str] = None       # supply port in the on-state triple
    on_state_condition: List[str] = field(default_factory=list)
    off_state_condition: List[str] = field(default_factory=list)
    declared_line: Optional[int] = None
    declared_file: Optional[str] = None


@dataclass
class SupplyState:
    """A legal state of one supply (net/set), e.g. ON / OFF / VDD_0_9."""

    name: str
    parent: str
    type: str = "supply_state"  # supply_state | port_state
    voltage: Optional[float] = None  # nominal voltage in volts, if declared
    declared_line: Optional[int] = None


@dataclass
class PowerState:
    """One row of a Power State Table."""

    name: str
    supply_states: Dict[str, str] = field(default_factory=dict)
    is_directed: bool = False
    declared_line: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "supply_states": self.supply_states,
            "is_directed": self.is_directed,
            "declared_line": self.declared_line,
        }


@dataclass
class Pst:
    name: str
    scope: str
    states: List[PowerState] = field(default_factory=list)
    transitions: List[tuple] = field(default_factory=list)  # (src, dst)
    declared_line: Optional[int] = None
    #: File this table was declared in. Several independent fragments each
    #: declare a complete, scope-less table of the same name; the declaring
    #: file is what tells those objects apart, matching the `declared_file`
    #: convention already carried by the strategy classes.
    declared_file: Optional[str] = None
    #: Supply names from ``create_pst -supplies``, in declaration order.
    #: IEEE 1801 maps ``add_pst_state -state`` entries *positionally* onto this
    #: list, so it must be retained — without it the positional form is
    #: unresolvable and every state reads as unreferenced.
    supply_list: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "scope": self.scope,
            "states": [s.to_dict() for s in self.states],
            "transitions": [list(t) for t in self.transitions],
            "declared_line": self.declared_line,
            "declared_file": self.declared_file,
            "supply_list": list(self.supply_list),
        }


@dataclass
class IsolationStrategy:
    domain: str
    elements: List[str] = field(default_factory=list)
    clamp_value: Optional[str] = None
    location: str = "self"  # self | parent | fanout
    isolation_supply: Optional[str] = None
    control_signal: Optional[str] = None
    control_sense: Optional[str] = None        # from set_isolation_control -isolation_sense
    control_condition: Optional[str] = None    # from set_isolation_control -isolation_condition
    applies_to: str = "outputs"  # outputs | inputs | internal | inout | outputs,inputs
    declared_line: Optional[int] = None
    declared_file: Optional[str] = None
    scope: str = "."


@dataclass
class LevelShifterStrategy:
    domain: str
    elements: List[str] = field(default_factory=list)
    location: str = "self"  # self | parent | fanout
    threshold: Optional[float] = None
    rule: str = "low_to_high"  # low_to_high | high_to_low | both
    applies_to: str = ""      # inputs | outputs | internal | inout (empty = unspecified)
    control_signal: Optional[str] = None  # from set_level_shifter_control
    declared_line: Optional[int] = None
    declared_file: Optional[str] = None
    scope: str = "."


@dataclass
class RetentionStrategy:
    domain: str
    elements: List[str] = field(default_factory=list)
    retention_supply: Optional[str] = None
    save_signal: Optional[str] = None
    restore_signal: Optional[str] = None
    #: Signal halves of ``-save_signal {sig sense}`` / ``-restore_signal``, with
    #: the polarity split off. ``save_signal`` keeps the raw token for
    #: provenance; these carry the bare signal so design-aware rules can
    #: resolve it against real design objects instead of comparing against the
    #: literal string ``'{save high}'``.
    save_signal_name: Optional[str] = None
    save_signal_sense: Optional[str] = None
    restore_signal_name: Optional[str] = None
    restore_signal_sense: Optional[str] = None
    control_signal: Optional[str] = None  # from set_retention_control -retention_signal
    declared_line: Optional[int] = None
    declared_file: Optional[str] = None
    scope: str = "."


@dataclass
class RepeaterStrategy:
    """A signal repeater inserted on a domain boundary (IEEE 1801 set_repeater).

    Repeaters are the buffering counterpart of isolation: they re-drive signals
    crossing a domain boundary while the source domain is powered down or for
    fanout, using an independent repeater supply and an enable signal.
    """

    domain: str
    elements: List[str] = field(default_factory=list)
    repeater_supply: Optional[str] = None
    location: str = "self"  # self | parent | fanout
    driver_type: str = ""   # minimal | non_inverting | inverting
    sense: Optional[str] = None
    inverted: bool = False
    signal: Optional[str] = None        # -repeater_signal
    isolation_supply: Optional[str] = None  # -repeater_isolation_supply
    control_signal: Optional[str] = None    # from set_repeater_control
    declared_line: Optional[int] = None
    declared_file: Optional[str] = None


@dataclass
class PowerIntentModel:
    """Aggregate power-intent model for one design scope."""

    upf_version: Optional[str] = None
    design_top: Optional[str] = None
    current_scope: str = "."
    domains: Dict[str, PowerDomain] = field(default_factory=dict)
    supply_ports: Dict[str, SupplyPort] = field(default_factory=dict)
    supply_nets: Dict[str, SupplyNet] = field(default_factory=dict)
    supply_sets: Dict[str, SupplySet] = field(default_factory=dict)
    switches: Dict[str, PowerSwitch] = field(default_factory=dict)
    supply_states: List[SupplyState] = field(default_factory=list)
    psts: Dict[str, Pst] = field(default_factory=dict)
    isolation: List[IsolationStrategy] = field(default_factory=list)
    level_shifters: List[LevelShifterStrategy] = field(default_factory=list)
    retentions: List[RetentionStrategy] = field(default_factory=list)
    repeaters: List[RepeaterStrategy] = field(default_factory=list)
    port_attributes: Dict[str, List[str]] = field(default_factory=dict)
    #: strategy->control bindings collected from set_*_control commands
    isolation_controls: Dict[str, dict] = field(default_factory=dict)
    retention_controls: Dict[str, dict] = field(default_factory=dict)
    level_shifter_controls: Dict[str, dict] = field(default_factory=dict)
    repeater_controls: Dict[str, dict] = field(default_factory=dict)
    #: supply maps declared by load_upf -supply (local supply -> parent supply)
    supply_maps: List[dict] = field(default_factory=list)
    #: hierarchical UPF events (promote/demote) and nested loads
    hierarchy_events: List[dict] = field(default_factory=list)
    load_upf_events: List[dict] = field(default_factory=list)
    #: supply equivalence pairs (set_equivalent) and library cell mappings
    equivalences: List[dict] = field(default_factory=list)
    library_mappings: List[dict] = field(default_factory=list)
    commands_seen: int = 0
    #: provenance index: source line -> distinct files that declared it.
    #: Built from the authoritative CommandRecord stream so findings can carry
    #: file provenance without each model object retaining it.
    record_files: Dict[int, List[str]] = field(default_factory=dict)
    #: Every command record keyed by ``"<file>::<line>"`` -> verbatim text.
    #: Line numbers repeat across files, so a global line index cannot say
    #: *which* file a finding came from. This map can, and is what finding
    #: provenance is resolved from (see ``resolve_provenance``).
    record_texts: Dict[str, str] = field(default_factory=dict)
    #: basenames of every validated input file (for load_upf resolution)
    record_file_names: set = field(default_factory=set)
    unsupported_commands: List[str] = field(default_factory=list)
    # --- Syntax & reference layer bookkeeping (populated by the builder) ---
    syntax_issues: List[dict] = field(default_factory=list)      # {rule, message, line, support}
    duplicate_definitions: List[dict] = field(default_factory=list)  # {name, kind, old_line, new_line}
    definitions: Dict[str, dict] = field(default_factory=dict)   # scoped key -> {kind, line}
    references: List[dict] = field(default_factory=list)         # {kind, name, key, line}
    scope_changes: List[dict] = field(default_factory=list)      # {scope, line}
    design: Optional[object] = None  # DesignContext (netlist snapshot), if supplied

    def scope_key(self, name: str, scope: Optional[str] = None,
                  origin: Optional[str] = None) -> str:
        """Fully-qualified identifier: ``<scope>/<name>``, optionally origin-qualified.

        ``origin`` names the file a declaration came from. It is needed because
        scope alone does not identify an object in a corpus of *independent
        fragments*: several files may each declare a complete, scope-less
        definition of the same name (``Core_OOO_PST`` is declared by nine AnyCore
        files with nine different supply lists, none of which call ``set_scope``).
        Those are distinct objects, not redefinitions of one object.

        When ``origin`` is None the result is exactly what it always was, so
        single-file behaviour is unchanged.
        """
        s = (scope or self.current_scope).rstrip("/")
        base = name if s in (".", "") else f"{s}/{name}"
        if origin:
            base = f"{base}@{os.path.basename(str(origin))}"
        return base

    def store(self, table: Dict[str, object], name: str, obj: object,
              scope: Optional[str] = None, origin: Optional[str] = None) -> str:
        """Insert ``obj`` under its fully-qualified identity, and return that key.

        Identity is ``<scope>/<name>`` — sufficient when the name is unique in
        its scope. When a *different file* has already claimed that same name
        in the same scope, scope alone cannot tell the two declarations apart,
        so the declaring file is appended to disambiguate.

        This happens in real corpora: nine AnyCore fragments each declare a
        complete, scope-less ``Core_OOO_PST`` with nine different supply lists.
        Those are nine distinct objects, not nine redefinitions of one, and
        collapsing them loses eight.

        The unqualified key is kept whenever it is unambiguous, so a name that
        appears once is stored exactly as before and single-file behaviour is
        unchanged. A redefinition *within* the same file keeps the bare key, so
        it is still reported as a duplicate rather than silently split.
        """
        key = self.scope_key(name, scope)
        if key in table and origin:
            existing = table.get(key)
            existing_origin = getattr(existing, "declared_file", None)
            if existing_origin and existing_origin != origin:
                key = self.scope_key(name, scope, origin)
        table[key] = obj
        return key

    def resolve(self, name: str, table: Dict[str, object],
                scope: Optional[str] = None,
                origin: Optional[str] = None) -> Optional[str]:
        """Find the key under which ``name`` was declared, widening in order.

        Exact ``(scope, origin)`` first, then the same scope from any origin,
        then a bare-name match for objects declared at top scope. Returns the
        matching key, or None. The widening order matters: a reference inside a
        child scope must bind to that child's object before any top-scope
        namesake, and a reference from a top-level fragment must not silently
        bind to a child-scoped object.
        """
        if origin:
            k = self.scope_key(name, scope, origin)
            if k in table:
                return k
        if scope and scope not in (".", ""):
            k = self.scope_key(name, scope)
            if k in table:
                return k
            # Same scope, different origin: a fragment-scoped declaration.
            prefix = self.scope_key(name, scope) + "@"
            for existing in table:
                if existing.startswith(prefix):
                    return existing
        if name in table:
            return name
        return None

    def to_dict(self) -> dict:
        """Serialize the model for `upf-insight model` JSON output."""
        return {
            "upf_version": self.upf_version,
            "design_top": self.design_top,
            "current_scope": self.current_scope,
            "domains": {k: vars(v) for k, v in self.domains.items()},
            "supply_ports": {k: vars(v) for k, v in self.supply_ports.items()},
            "supply_nets": {k: vars(v) for k, v in self.supply_nets.items()},
            "supply_sets": {k: vars(v) for k, v in self.supply_sets.items()},
            "switches": {k: vars(v) for k, v in self.switches.items()},
            "supply_states": [vars(s) for s in self.supply_states],
            "psts": {k: v.to_dict() for k, v in self.psts.items()},
            "isolation": [vars(s) for s in self.isolation],
            "level_shifters": [vars(s) for s in self.level_shifters],
            "retentions": [vars(s) for s in self.retentions],
            "repeaters": [vars(s) for s in self.repeaters],
            "port_attributes": self.port_attributes,
            "isolation_controls": self.isolation_controls,
            "retention_controls": self.retention_controls,
            "level_shifter_controls": self.level_shifter_controls,
            "repeater_controls": self.repeater_controls,
            "hierarchy_events": self.hierarchy_events,
            "load_upf_events": self.load_upf_events,
            "supply_maps": self.supply_maps,
            "equivalences": self.equivalences,
            "library_mappings": self.library_mappings,
            "commands_seen": self.commands_seen,
            "unsupported_commands": self.unsupported_commands,
            "syntax_issues": self.syntax_issues,
            "duplicate_definitions": self.duplicate_definitions,
            "definitions": self.definitions,
            "references": self.references,
            "scope_changes": self.scope_changes,
            "design": self.design.to_dict() if (self.design is not None and hasattr(self.design, "to_dict")) else (self.design if self.design is not None else None),
        }


__all__ = [
    "PowerDomain",
    "SupplyPort",
    "SupplyNet",
    "SupplySet",
    "PowerSwitch",
    "SupplyState",
    "PowerState",
    "Pst",
    "IsolationStrategy",
    "LevelShifterStrategy",
    "RetentionStrategy",
    "RepeaterStrategy",
    "PowerIntentModel",
]