"""Power-intent model builder.

Walks preprocessed UPF command records and mutates a PowerIntentModel,
recording provenance (file:line) on every entity. Commands outside the
supported registry are captured in `unsupported_commands` so the trust /
support boundary can report exactly what was not modeled.
"""

from __future__ import annotations

from typing import List, Optional

from ..preprocess.upf_preprocess import CommandRecord
from .power_model import (
    PowerIntentModel,
    PowerDomain,
    PowerSwitch,
    Pst,
    SupplyNet,
    SupplyPort,
    SupplySet,
    RepeaterStrategy,
)

# Subset of the UPF command grammar supported by the v1 model builder.
_SUPPORTED = {
    "upf_version",
    "set_design_top",
    "set_scope",
    "create_power_domain",
    "create_supply_net",
    "create_supply_port",
    "create_supply_set",
    "connect_supply_net",
    "create_power_switch",
    "add_port_state",
    "add_supply_state",
    "add_power_state",
    "create_pst",
    "add_pst_state",
    "add_state_transition",
    "set_isolation",
    "set_level_shifter",
    "set_retention",
    "set_repeater",
    "set_isolation_control",
    "set_retention_control",
    "set_level_shifter_control",
    "set_repeater_control",
    "load_upf",
    "set_domain_supply_net",
    "set_port_attributes",
    "set_equivalent",
    "update_supply_net",
    "update_supply_set",
    "map_isolation_cell",
    "map_level_shifter_cell",
    "map_retention_cell",
    "upf_promote",
    "upf_demote",
}

# Legal options per supported command (UPF 2.1/3.0 grammar). Used by UPF-002.
_LEGAL_OPTIONS = {
    "create_power_domain": {"-elements", "-primary_supply_set", "-supply", "-update"},
    "create_supply_net": {"-resolve", "-update"},
    "create_supply_port": {"-direction", "-domain", "-update"},
    "create_supply_set": {"-function", "-power", "-ground", "-update"},
    "connect_supply_net": {"-ports", "-nets", "-resolve"},
    "create_power_switch": {"-input_supply_port", "-output_supply_port",
                            "-control_port", "-on_state", "-off_state", "-update"},
    "add_port_state": {"-state", "-update"},
    "add_supply_state": {"-state", "-update"},
    "add_power_state": {"-state", "-update"},
    "create_pst": {"-supplies", "-update"},
    "add_pst_state": {"-pst", "-state", "-is_directed", "-complete", "-update"},
    "add_state_transition": {"-state", "-next_state"},
    "set_isolation": {"-domain", "-elements", "-isolation_supply", "-clamp_value",
                      "-location", "-applies_to", "-isolation_signal",
                      "-no_isolation", "-source", "-sink", "-update"},
    "set_level_shifter": {"-domain", "-elements", "-location", "-threshold",
                          "-rule", "-applies_to", "-update"},
    "set_retention": {"-domain", "-elements", "-retention_supply",
                      "-save_signal", "-restore_signal", "-update"},
    "set_repeater": {"-domain", "-elements", "-repeater_supply", "-location",
                     "-driver_type", "-sense", "-inverted", "-repeater_signal",
                     "-repeater_isolation_supply", "-update"},
    "set_isolation_control": {"-domain", "-isolation_signal", "-isolation_sense",
                              "-isolation_condition", "-update"},
    "set_retention_control": {"-domain", "-retention_signal", "-update"},
    "set_level_shifter_control": {"-domain", "-level_shifter_signal", "-update"},
    "set_repeater_control": {"-domain", "-repeater_signal", "-update"},
    "set_domain_supply_net": {"-primary_power_net", "-primary_ground_net", "-update"},
    "set_port_attributes": {"-attribute", "-update"},
    "set_equivalent": {"-nets", "-ports", "-sets", "-update"},
    "update_supply_net": {"-resolve", "-update"},
    "update_supply_set": {"-function", "-power", "-ground", "-update"},
    "map_isolation_cell": {"-domain", "-lib_cells", "-elements", "-update"},
    "map_level_shifter_cell": {"-domain", "-lib_cells", "-elements", "-update"},
    "map_retention_cell": {"-domain", "-lib_cells", "-elements", "-update"},
    "upf_promote": {"-net", "-port", "-set", "-domain", "-update"},
    "upf_demote": {"-net", "-port", "-set", "-domain", "-update"},
}

# Options whose absence is a hard error (UPF-003).
_REQUIRED_OPTIONS = {
    "set_isolation": ("-domain",),
    "set_level_shifter": ("-domain",),
    "set_retention": ("-domain",),
    "set_repeater": ("-domain",),
    "set_isolation_control": ("-domain",),
    "set_retention_control": ("-domain",),
    "set_level_shifter_control": ("-domain",),
    "set_repeater_control": ("-domain",),
    "add_pst_state": ("-pst",),
    "add_state_transition": ("-next_state",),
    "create_power_switch": ("-input_supply_port", "-output_supply_port"),
}

#: UPF versions the model builder understands (UPF-004).
_SUPPORTED_VERSIONS = ("2.1", "3.0", "3.1", "4.0")

#: Legacy UPF 1.0/2.0 command forms (UPF-005).
_DEPRECATED_FORMS = {
    "add_power_state": "UPF 2.1 replaced add_power_state with create_pst + add_pst_state",
}


def _track_definition(model: PowerIntentModel, kind: str, name: str, line: int) -> None:
    key = model.scope_key(name)
    prev = model.definitions.get(key)
    if prev is not None and prev["kind"] == kind:
        model.duplicate_definitions.append({
            "name": name, "kind": kind,
            "old_line": prev["line"], "new_line": line,
        })
        return
    if prev is None:
        model.definitions[key] = {"kind": kind, "line": line}


def _track_reference(model: PowerIntentModel, kind: str, name: str, line: int) -> None:
    if not name:
        return
    model.references.append({
        "kind": kind, "name": name,
        "key": model.scope_key(name), "line": line,
    })


def _tokenize(record: CommandRecord) -> List[str]:
    """Tokenize a command record with a bounded Tcl-aware splitter.

    Keeps brace/bracket groups together so multi-word arguments like
    ``{cpu1 cpu2}`` remain one token.
    """
    text = record.text.strip()
    # Fast path: no grouping characters.
    if not any(c in text for c in "{}[]\""):
        return text.split()
    # Bounded Tcl-aware split: keep brace/bracket/double-quote groups together
    # while treating whitespace as a separator outside groups.
    tokens: List[str] = []
    buf: List[str] = []
    depth = 0
    quote = None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "{[":
            depth += 1
            buf.append(ch)
            continue
        if ch in "}]":
            depth -= 1
            buf.append(ch)
            continue
        if ch.isspace() and depth == 0:
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def build_model(records: List[CommandRecord]) -> PowerIntentModel:
    """Build a power-intent model from preprocessed command records."""
    model = PowerIntentModel()
    for rec in records:
        model.commands_seen += 1
        files = model.record_files.setdefault(rec.line, [])
        if rec.file not in files:
            files.append(rec.file)
        try:
            tokens = _tokenize(rec)
        except Exception:
            tokens = []
        if not tokens:
            continue
        cmd = tokens[0].lower()
        args = tokens[1:]
        if cmd not in _SUPPORTED:
            model.unsupported_commands.append(f"{cmd} ({rec.file}:{rec.line})")
            continue
        _syntax_check(model, cmd, tokens, rec)
        _dispatch(model, cmd, args, rec)
    _apply_control_bindings(model)
    return model


def _apply_control_bindings(model: PowerIntentModel) -> None:
    """Merge set_*_control bindings into the strategies they control.

    Control commands may legally precede or follow their strategy, so bindings
    are collected separately and applied after the full walk.
    """
    for iso in model.isolation:
        ctl = model.isolation_controls.get(iso.domain)
        if not ctl:
            continue
        if ctl.get("signal"):
            iso.control_signal = ctl["signal"]
        if ctl.get("sense"):
            iso.control_sense = ctl["sense"]
        if ctl.get("condition"):
            iso.control_condition = ctl["condition"]
    for ret in model.retentions:
        ctl = model.retention_controls.get(ret.domain)
        if ctl and ctl.get("signal"):
            ret.control_signal = ctl["signal"]
    for ls in model.level_shifters:
        ctl = model.level_shifter_controls.get(ls.domain)
        if ctl and ctl.get("signal"):
            ls.control_signal = ctl["signal"]
    for rep in model.repeaters:
        ctl = model.repeater_controls.get(rep.domain)
        if ctl and ctl.get("signal"):
            rep.control_signal = ctl["signal"]


def _syntax_check(model: PowerIntentModel, cmd: str, tokens: List[str], rec: CommandRecord) -> None:
    """Record deterministic syntax-layer issues (UPF-002/003/004/005/006)."""
    line = rec.line
    text = rec.text

    # UPF-006 — unbalanced braces / brackets / unterminated quote.
    balance = {"{": 0, "[": 0, '"': 0}
    for ch in text:
        if ch in balance:
            balance[ch] += 1
        elif ch == "}":
            balance["{"] -= 1
        elif ch == "]":
            balance["["] -= 1
    if balance["{"] or balance["["] or balance['"']:
        model.syntax_issues.append({
            "rule": "UPF-006", "support": "VALIDATED", "line": line,
            "message": f"Malformed Tcl: unbalanced braces/brackets/quotes in "
                       f"'{cmd}' (balance {balance}).",
        })

    # UPF-002 — illegal option.
    legal = _LEGAL_OPTIONS.get(cmd, set())
    for tok in tokens[1:]:
        if tok.startswith("-") and tok not in legal and not tok[1:2].isdigit():
            model.syntax_issues.append({
                "rule": "UPF-002", "support": "VALIDATED", "line": line,
                "message": f"Illegal option '{tok}' for command '{cmd}'.",
            })

    # UPF-003 — missing required argument.
    for opt in _REQUIRED_OPTIONS.get(cmd, ()):
        if opt not in tokens:
            model.syntax_issues.append({
                "rule": "UPF-003", "support": "VALIDATED", "line": line,
                "message": f"Missing required argument '{opt}' for command "
                           f"'{cmd}'.",
            })

    # UPF-004 — unsupported version.
    if cmd == "upf_version":
        version = tokens[1] if len(tokens) > 1 else ""
        if version not in _SUPPORTED_VERSIONS:
            model.syntax_issues.append({
                "rule": "UPF-004", "support": "VALIDATED", "line": line,
                "message": f"UPF version '{version or '(none)'}' is not "
                           f"supported (supported: {', '.join(_SUPPORTED_VERSIONS)}).",
            })

    # UPF-005 — deprecated legacy syntax.
    if cmd in _DEPRECATED_FORMS:
        model.syntax_issues.append({
            "rule": "UPF-005", "support": "VALIDATED", "line": line,
            "message": f"'{cmd}' is deprecated: {_DEPRECATED_FORMS[cmd]}.",
        })


def _get_opt(args: List[str], opt: str, default: Optional[str] = None) -> Optional[str]:
    for i, a in enumerate(args):
        if a == opt and i + 1 < len(args):
            return args[i + 1]
    return default


def _get_flag(args: List[str], flag: str) -> bool:
    return flag in args


def _dispatch(model: PowerIntentModel, cmd: str, args: List[str], rec: CommandRecord) -> None:
    line = rec.line
    if cmd == "upf_version":
        model.upf_version = args[0] if args else None
    elif cmd == "set_design_top":
        model.design_top = args[0] if args else None
    elif cmd == "set_scope":
        model.current_scope = args[0] if args else "."
        model.scope_changes.append({"scope": model.current_scope, "line": line})
    elif cmd == "create_power_domain":
        name = args[0] if args else "?"
        scope = model.current_scope
        elements = _get_opt(args, "-elements", "")
        dom = PowerDomain(name=name, scope=scope, declared_line=line)
        if elements:
            cleaned = elements.strip().strip("{}")
            dom.elements = [e.strip() for e in cleaned.split() if e.strip()]
        primary = _get_opt(args, "-primary_supply_set")
        if primary:
            dom.primary_supply_sets["primary"] = primary
            _track_reference(model, "supply", primary, line)
        # -supply {function ...} assignments
        for i, a in enumerate(args):
            if a == "-supply" and i + 1 < len(args):
                pair = _split_pair(args[i + 1])
                if len(pair) == 2:
                    dom.primary_supply_sets[pair[0]] = pair[1]
                    _track_reference(model, "supply", pair[1], line)
        _track_definition(model, "domain", name, line)
        model.domains[model.scope_key(name, scope)] = dom
    elif cmd == "create_supply_net":
        name = args[0] if args else "?"
        net = SupplyNet(name=name, scope=model.current_scope, declared_line=line)
        net.connected_to = []
        _track_definition(model, "net", name, line)
        model.supply_nets[model.scope_key(name, model.current_scope)] = net
    elif cmd == "create_supply_port":
        name = args[0] if args else "?"
        direction = _get_opt(args, "-direction", "inout")
        _track_definition(model, "port", name, line)
        model.supply_ports[model.scope_key(name, model.current_scope)] = SupplyPort(
            name=name, scope=model.current_scope, direction=direction, declared_line=line
        )
    elif cmd == "create_supply_set":
        name = args[0] if args else "?"
        funcs: dict = {}
        for i, a in enumerate(args):
            if a == "-function" and i + 1 < len(args):
                pair = _split_pair(args[i + 1])
                if len(pair) == 2:
                    funcs[pair[0]] = pair[1]
                    _track_reference(model, "supply", pair[1], line)
        for opt in ("-power", "-ground"):
            val = _get_opt(args, opt)
            if val:
                funcs[opt.lstrip("-")] = val
                _track_reference(model, "supply", val, line)
        _track_definition(model, "set", name, line)
        model.supply_sets[model.scope_key(name, model.current_scope)] = SupplySet(
            name=name, scope=model.current_scope, functions=funcs, declared_line=line
        )
    elif cmd == "connect_supply_net":
        net = args[0] if args else None
        target = _get_opt(args, "-ports") or _get_opt(args, "-nets")
        if net:
            key = model.scope_key(net, model.current_scope)
            entry = model.supply_nets.get(key)
            if entry is None:
                entry = SupplyNet(name=net, scope=model.current_scope, declared_line=line)
                model.supply_nets[key] = entry
            if target:
                for t in _split_opt(args, "-ports") or _split_opt(args, "-nets"):
                    _track_reference(model, "connect", t, line)
                entry.connected_to.append(target)
    elif cmd == "create_power_switch":
        name = args[0] if args else "?"
        on_name, on_supply, on_cond = _split_state_expr(_get_opt(args, "-on_state") or "")
        off_name, _off_supply, off_cond = _split_state_expr(_get_opt(args, "-off_state") or "")
        switch = PowerSwitch(
            name=name,
            scope=model.current_scope,
            input_supply=_get_opt(args, "-input_supply_port"),
            output_supply=_get_opt(args, "-output_supply_port"),
            control_port=_get_opt(args, "-control_port"),
            on_state=on_name or None,
            off_state=off_name or None,
            on_state_supply=on_supply or None,
            on_state_condition=on_cond,
            off_state_condition=off_cond,
            declared_line=line,
        )
        for opt in ("-input_supply_port", "-output_supply_port"):
            v = _get_opt(args, opt)
            if v:
                _track_reference(model, "supply", v, line)
        _track_definition(model, "switch", name, line)
        model.switches[model.scope_key(name, model.current_scope)] = switch
    elif cmd == "create_pst":
        name = args[0] if args else "?"
        _track_definition(model, "pst", name, line)
        model.psts[model.scope_key(name, model.current_scope)] = Pst(
            name=name, scope=model.current_scope, declared_line=line
        )
    elif cmd == "add_pst_state":
        pst_name = _get_opt(args, "-pst")
        state_name = args[0] if args else None
        if pst_name and state_name:
            key = model.scope_key(pst_name, model.current_scope)
            pst = model.psts.get(key)
            if pst is None:
                pst = Pst(name=pst_name, scope=model.current_scope, declared_line=line)
                _track_definition(model, "pst", pst_name, line)
                model.psts[key] = pst
            from .power_model import PowerState

            supply_states: dict = {}
            for i, a in enumerate(args):
                if a == "-state" and i + 1 < len(args):
                    tokens = _split_pair(args[i + 1])
                    # -state {vdd ON vss ON} → consecutive (supply, state) pairs
                    for j in range(0, len(tokens) - 1, 2):
                        supply_states[tokens[j]] = tokens[j + 1]
            pst.states.append(PowerState(
                name=state_name, supply_states=supply_states, declared_line=line
            ))
    # Isolation / level shifter / retention are recorded as strategies.
    elif cmd == "set_isolation":
        from .power_model import IsolationStrategy

        domain = _get_opt(args, "-domain") or ""
        _track_reference(model, "domain", domain, line)
        model.isolation.append(
            IsolationStrategy(
                domain=domain,
                elements=_split_opt(args, "-elements"),
                clamp_value=_get_opt(args, "-clamp_value"),
                location=_get_opt(args, "-location", "self"),
                isolation_supply=_get_opt(args, "-isolation_supply"),
                control_signal=_get_opt(args, "-isolation_signal"),
                applies_to=_get_opt(args, "-applies_to", "outputs"),
                declared_line=line,
            )
        )
    elif cmd == "set_level_shifter":
        from .power_model import LevelShifterStrategy

        domain = _get_opt(args, "-domain") or ""
        _track_reference(model, "domain", domain, line)
        model.level_shifters.append(
            LevelShifterStrategy(
                domain=domain,
                elements=_split_opt(args, "-elements"),
                location=_get_opt(args, "-location", "self"),
                threshold=_float_opt(args, "-threshold"),
                rule=_get_opt(args, "-rule", "low_to_high"),
                applies_to=_get_opt(args, "-applies_to", ""),
                declared_line=line,
            )
        )
    elif cmd == "set_repeater":
        from .power_model import RepeaterStrategy

        domain = _get_opt(args, "-domain") or ""
        _track_reference(model, "domain", domain, line)
        model.repeaters.append(
            RepeaterStrategy(
                domain=domain,
                elements=_split_opt(args, "-elements"),
                repeater_supply=_get_opt(args, "-repeater_supply"),
                location=_get_opt(args, "-location", "self"),
                driver_type=_get_opt(args, "-driver_type", ""),
                sense=_get_opt(args, "-sense"),
                inverted=_get_flag(args, "-inverted"),
                signal=_get_opt(args, "-repeater_signal"),
                isolation_supply=_get_opt(args, "-repeater_isolation_supply"),
                declared_line=line,
            )
        )
    elif cmd == "set_retention":
        from .power_model import RetentionStrategy

        domain = _get_opt(args, "-domain") or ""
        _track_reference(model, "domain", domain, line)
        model.retentions.append(
            RetentionStrategy(
                domain=domain,
                elements=_split_opt(args, "-elements"),
                retention_supply=_get_opt(args, "-retention_supply"),
                save_signal=_get_opt(args, "-save_signal"),
                restore_signal=_get_opt(args, "-restore_signal"),
                declared_line=line,
            )
        )
    # add_port_state / add_supply_state / add_power_state / add_state_transition
    elif cmd in ("add_port_state", "add_supply_state"):
        from .power_model import SupplyState

        parent = args[0] if args else ""
        _track_reference(model, "supply", parent, line)
        for i, a in enumerate(args):
            if a == "-state" and i + 1 < len(args):
                pair = _split_pair(args[i + 1])
                if pair:
                    voltage = None
                    if len(pair) >= 2:
                        try:
                            voltage = float(pair[1])
                        except ValueError:
                            voltage = None
                    model.supply_states.append(
                        SupplyState(name=pair[0], parent=parent, voltage=voltage,
                                    declared_line=line)
                    )
    elif cmd == "add_state_transition":
        src = args[0] if args else _get_opt(args, "-state")
        dst = _get_opt(args, "-next_state")
        if src and dst:
            for pst in model.psts.values():
                pst.transitions.append((src, dst))
    # load_upf is followed in load order; nested loads recorded for scoping.
    elif cmd == "load_upf":
        model.load_upf_events.append({"scope": model.current_scope, "line": line})
    elif cmd == "set_isolation_control":
        domain = _get_opt(args, "-domain") or ""
        ctl = model.isolation_controls.setdefault(domain, {})
        if _get_opt(args, "-isolation_signal"):
            ctl["signal"] = _get_opt(args, "-isolation_signal")
        if _get_opt(args, "-isolation_sense"):
            ctl["sense"] = _get_opt(args, "-isolation_sense")
        if _get_opt(args, "-isolation_condition"):
            ctl["condition"] = _get_opt(args, "-isolation_condition")
    elif cmd == "set_retention_control":
        domain = _get_opt(args, "-domain") or ""
        ctl = model.retention_controls.setdefault(domain, {})
        if _get_opt(args, "-retention_signal"):
            ctl["signal"] = _get_opt(args, "-retention_signal")
    elif cmd == "set_level_shifter_control":
        domain = _get_opt(args, "-domain") or ""
        ctl = model.level_shifter_controls.setdefault(domain, {})
        if _get_opt(args, "-level_shifter_signal"):
            ctl["signal"] = _get_opt(args, "-level_shifter_signal")
    elif cmd == "set_repeater_control":
        domain = _get_opt(args, "-domain") or ""
        ctl = model.repeater_controls.setdefault(domain, {})
        if _get_opt(args, "-repeater_signal"):
            ctl["signal"] = _get_opt(args, "-repeater_signal")
    elif cmd == "set_equivalent":
        names = [n.strip("{}") for n in
                 (_split_opt(args, "-nets") or _split_opt(args, "-ports")
                  or _split_opt(args, "-sets"))]
        model.equivalences.append({"names": names, "line": line})
    elif cmd == "update_supply_net":
        name = args[0] if args else None
        if name:
            key = model.scope_key(name, model.current_scope)
            if key not in model.supply_nets:
                _track_definition(model, "net", name, line)
                model.supply_nets[key] = SupplyNet(
                    name=name, scope=model.current_scope, declared_line=line)
    elif cmd == "update_supply_set":
        name = args[0] if args else None
        if name:
            key = model.scope_key(name, model.current_scope)
            entry = model.supply_sets.get(key)
            if entry is None:
                entry = SupplySet(name=name, scope=model.current_scope,
                                  declared_line=line)
                _track_definition(model, "set", name, line)
                model.supply_sets[key] = entry
            for i, a in enumerate(args):
                if a == "-function" and i + 1 < len(args):
                    pair = _split_pair(args[i + 1])
                    if len(pair) == 2:
                        entry.functions[pair[0]] = pair[1]
                        _track_reference(model, "supply", pair[1], line)
            for opt in ("-power", "-ground"):
                val = _get_opt(args, opt)
                if val:
                    entry.functions[opt.lstrip("-")] = val
                    _track_reference(model, "supply", val, line)
    elif cmd in ("map_isolation_cell", "map_level_shifter_cell", "map_retention_cell"):
        model.library_mappings.append({"cmd": cmd, "line": line})
    elif cmd in ("upf_promote", "upf_demote"):
        name = (_get_opt(args, "-net") or _get_opt(args, "-port")
                or _get_opt(args, "-set") or _get_opt(args, "-domain")
                or (args[0] if args else ""))
        model.hierarchy_events.append({
            "op": cmd[4:], "name": name,
            "scope": model.current_scope, "line": line,
        })
    elif cmd == "set_domain_supply_net":
        name = args[0] if args else None
        if name:
            key = model.scope_key(name, model.current_scope)
            dom = model.domains.get(key)
            if dom is None:
                dom = PowerDomain(name=name, scope=model.current_scope,
                                  declared_line=line)
                _track_definition(model, "domain", name, line)
                model.domains[key] = dom
            pp = _get_opt(args, "-primary_power_net")
            pg = _get_opt(args, "-primary_ground_net")
            if pp:
                dom.primary_supply_sets["primary_power_net"] = pp
                _track_reference(model, "supply", pp, line)
            if pg:
                dom.primary_supply_sets["primary_ground_net"] = pg
                _track_reference(model, "supply", pg, line)
    elif cmd == "set_port_attributes":
        targets = args[0] if args else ""
        attr = _get_opt(args, "-attribute")
        for name in targets.replace(",", " ").split():
            if not name:
                continue
            model.port_attributes.setdefault(name, []).append(attr or "")


def _split_pair(value: str) -> List[str]:
    """Split a brace group like ``{power vdd}`` or ``{ON 1.0}`` into tokens."""
    cleaned = value.strip().strip("{}")
    return cleaned.split()


def _split_state_expr(value: str):
    """Parse a power-switch state triple ``{name supply {condition}}``.

    Returns ``(state_name, supply_port, condition_tokens)``. A bare state name
    (no supply/condition) is tolerated and yields empty supply/condition.
    """
    s = (value or "").strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1].strip()
    parts = s.split(None, 2)
    if not parts:
        return "", "", []
    name, supply = parts[0].strip("{}"), (parts[1].strip("{}") if len(parts) > 1 else "")
    cond = parts[2] if len(parts) > 2 else ""
    cond_tokens = [t for t in cond.replace("{", " ").replace("}", " ").split() if t]
    return name, supply, cond_tokens


def _split_opt(args: List[str], opt: str) -> List[str]:
    val = _get_opt(args, opt)
    if not val:
        return []
    # Strip the enclosing braces of a Tcl list so ``{u1 u2}`` yields
    # ``["u1", "u2"]`` (mirrors the create_power_domain -elements fix).
    cleaned = val.strip().strip("{}")
    return [e.strip() for e in cleaned.replace(",", " ").split() if e.strip()]


def _float_opt(args: List[str], opt: str) -> Optional[float]:
    val = _get_opt(args, opt)
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


__all__ = ["build_model"]