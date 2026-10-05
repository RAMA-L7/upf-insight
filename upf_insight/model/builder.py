"""Power-intent model builder.

Walks preprocessed UPF command records and mutates a PowerIntentModel,
recording provenance (file:line) on every entity. Commands outside the
supported registry are captured in `unsupported_commands` so the trust /
support boundary can report exactly what was not modeled.
"""

from __future__ import annotations

import os
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
    "map_power_switch",
    "upf_promote",
    "upf_demote",
}

# Legal options per supported command (UPF 2.1/3.0 grammar). Used by UPF-002.
#
# Presence here means "legal UPF", not "fully modelled". Options listed for
# grammar acceptance but not yet read into the model include
# `create_power_domain -atomic` / `-exclude_elements`,
# `create_supply_net -reuse` / `-exclude` / `-direction`, and
# `set_isolation -force_isolation` / `-use_equivalence`. Accepting them stops
# the engine rejecting valid files; the open P1 item on UPF-002 severity is to
# mark accepted-but-unmodelled options UNSUPPORTED rather than VALIDATED.
_LEGAL_OPTIONS = {
    "create_power_domain": {"-elements", "-primary_supply_set", "-supply",
                            "-include_scope", "-scope", "-atomic",
                            "-exclude_elements", "-update"},
    "set_scope": set(),
    "load_upf": {"-scope", "-supply", "-update"},
    # -domain / -reuse / -exclude / -direction are defined by IEEE 1801 for
    # create_supply_net; -resolve takes a resolution function in UPF 3.x.
    "create_supply_net": {"-resolve", "-domain", "-reuse", "-exclude",
                          "-direction", "-update"},
    "create_supply_port": {"-direction", "-domain", "-update"},
    "create_supply_set": {"-function", "-power", "-ground", "-update"},
    "connect_supply_net": {"-ports", "-nets", "-resolve"},
    "create_power_switch": {"-domain", "-input_supply", "-output_supply",
                            "-input_supply_port", "-output_supply_port",
                            "-control_port", "-on_state", "-off_state", "-update"},
    "add_port_state": {"-state", "-update"},
    "add_supply_state": {"-state", "-update"},
    "add_power_state": {"-state", "-update"},
    "create_pst": {"-supplies", "-update"},
    "add_pst_state": {"-pst", "-state", "-is_directed", "-complete", "-update"},
    "add_state_transition": {"-state", "-next_state"},
    "set_isolation": {"-domain", "-elements", "-isolation_supply",
                      "-isolation_power_net", "-isolation_ground_net",
                      "-isolation_supply_set", "-clamp_value", "-location",
                      "-applies_to", "-isolation_signal", "-no_isolation",
                      "-source", "-sink", "-diff_supply_only",
                      "-force_isolation", "-name", "-use_equivalence",
                      "-update"},
    "set_level_shifter": {"-domain", "-elements", "-location", "-threshold",
                          "-rule", "-applies_to", "-update"},
    "set_retention": {"-domain", "-elements", "-retention_supply",
                      "-retention_power_net", "-retention_ground_net",
                      "-save_signal", "-restore_signal", "-update"},
    "set_repeater": {"-domain", "-elements", "-repeater_supply", "-location",
                     "-driver_type", "-sense", "-inverted", "-repeater_signal",
                     "-repeater_isolation_supply", "-update"},
    "set_isolation_control": {"-domain", "-isolation_signal", "-isolation_sense",
                              "-isolation_condition", "-isolation_power_net",
                              "-isolation_ground_net", "-location", "-update"},
    "set_retention_control": {"-domain", "-retention_signal", "-save_signal",
                              "-restore_signal", "-update"},
    "set_level_shifter_control": {"-domain", "-level_shifter_signal",
                                  "-location", "-update"},
    "set_repeater_control": {"-domain", "-repeater_signal", "-location", "-update"},
    "set_domain_supply_net": {"-primary_power_net", "-primary_ground_net", "-update"},
    "set_port_attributes": {"-attribute", "-update"},
    "set_equivalent": {"-nets", "-ports", "-sets", "-update"},
    "update_supply_net": {"-resolve", "-update"},
    "update_supply_set": {"-function", "-power", "-ground", "-update"},
    "map_isolation_cell": {"-domain", "-lib_cells", "-elements", "-update"},
    "map_level_shifter_cell": {"-domain", "-lib_cells", "-elements", "-update"},
    "map_retention_cell": {"-domain", "-lib_cells", "-elements", "-update"},
    "map_power_switch": {"-domain", "-lib_cells", "-elements", "-update"},
    "upf_promote": {"-net", "-port", "-set", "-domain", "-update"},
    "upf_demote": {"-net", "-port", "-set", "-domain", "-update"},
}

# Options whose absence is a hard error (UPF-003).
#
# Each entry is a tuple of *requirements*; each requirement is a tuple of
# interchangeable spellings, and satisfying any one of them is enough. A bare
# string is a single-spelling requirement. IEEE 1801 defines both the 2.1/3.0
# and the 3.1+ spelling for several switch options, so demanding one exact
# token would reject a legal file.
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
    "create_power_switch": (
        ("-input_supply", "-input_supply_port"),
        ("-output_supply", "-output_supply_port"),
    ),
}

#: UPF versions the model builder understands (UPF-004).
_SUPPORTED_VERSIONS = ("2.1", "3.0", "3.1", "4.0")

#: Plain Tcl that may legitimately appear in a ``.upf`` file. A UPF file *is* a
#: Tcl script, and real-world power intent uses shell constructs to build it:
#:
#:     set CURRENT_SCOPE [set_scope btb]
#:     load_upf BTB.upf
#:     set_scope ${CURRENT_SCOPE}
#:
#: None of these are UPF commands. Reporting them via UPF-001 manufactures an
#: error on a valid file, so they are skipped rather than modelled.
_TCL_NOT_UPF = frozenset({
    "set", "unset", "expr", "if", "else", "elseif", "foreach", "for", "while",
    "proc", "return", "break", "continue", "source", "puts", "puts_stderr",
    "list", "lindex", "llength", "lappend", "lset", "lrange", "lsearch",
    "lreverse", "lsort", "lunique", "join", "split", "concat", "string",
    "regexp", "regsub", "format", "incr", "append", "subst", "eval",
    "uplevel", "namespace", "variable", "array", "dict", "info", "catch",
    "file", "glob", "open", "close", "gets", "read", "exec", "error",
    "package", "apply", "switch", "trace", "global", "exit",
})

#: Legacy UPF 1.0/2.0 command forms (UPF-005).
_DEPRECATED_FORMS = {
    "add_power_state": "UPF 2.1 replaced add_power_state with create_pst + add_pst_state",
}


def _track_definition(model: PowerIntentModel, kind: str, name: str, line: int,
                      origin: Optional[str] = None) -> None:
    """Record a declaration, flagging genuine redefinitions.

    Two declarations are a redefinition only when they describe the *same*
    object: same name, same scope, and same declaring file. Two files each
    declaring a scope-less object of the same name are declaring two distinct
    objects — the pattern real fragment corpora use — so they are tracked
    separately instead of being reported as one overwriting the other.
    """
    key = model.scope_key(name)
    prev = model.definitions.get(key)
    if prev is not None and prev["kind"] == kind:
        prev_origin = prev.get("file")
        if origin and prev_origin and prev_origin != origin:
            # Distinct declaration site: a separate object, not a redefinition.
            qualified = model.scope_key(name, None, origin)
            model.definitions[qualified] = {"kind": kind, "line": line,
                                            "file": origin}
            return
        model.duplicate_definitions.append({
            "name": name, "kind": kind,
            "old_line": prev["line"], "new_line": line,
            # Scope and declaring file, so a duplicate in one scope can be told
            # apart from an identically named object in another. The bare name
            # alone made two unrelated findings indistinguishable.
            "scope": model.current_scope,
            "file": origin,
        })
        return
    if prev is None:
        model.definitions[key] = {"kind": kind, "line": line, "file": origin}


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


def build_model(records: List[CommandRecord],
                by_file: Optional[Dict[str, List[CommandRecord]]] = None) -> PowerIntentModel:
    """Build a power-intent model from preprocessed command records.

    Scope is per-file state. A file that never issues ``set_scope`` starts at
    the top scope rather than inheriting the previous file's cursor, and a
    file pulled in by ``load_upf <f> -scope <s>`` starts in ``<s>`` — IEEE 1801
    lets a child inherit the scope it is loaded into instead of repeating
    ``set_scope``. Without this, the model depended on the order files were
    listed on the command line.

    ``load_upf`` is expanded **at the load site**: the child is processed
    inline, in the scope it is loaded into. This matters because the same child
    is routinely loaded into *many* scopes — AnyCore loads ``PipeLineReg.upf``
    thirty times under thirty distinct scopes, all of them real. A previous
    implementation kept one entry per child basename, so only the last load
    survived and the rest were silently dropped, which is what made identically
    named objects appear to "collide". Expansion is still strictly ordered:
    ``set_scope`` stays positional and reordering the stream still changes the
    result.

    ``by_file`` maps a file basename to its records, enabling expansion. It is
    a parameter rather than an internal lookup so the caller controls which
    files are visible; when omitted, ``load_upf`` records the event and the
    child contributes nothing, preserving the historical behaviour exactly.
    """
    model = PowerIntentModel()
    # (basename, scope) pairs currently being expanded, for cycle detection.
    # `load_upf` nests in real corpora, so recursion is expected and must be
    # bounded rather than assumed absent.
    active_loads: set = set()
    # Files reached by `load_upf` from an entry file are *included* by their
    # parent, not validated in their own right. Walking them again as
    # top-level entries would process the same declarations twice and register
    # them as duplicates of themselves. Entry files are therefore identified
    # by their position in the supplied order, and a file that is pulled in by
    # a parent is walked only from the parent's load site.
    included: Dict[str, List[str]] = {}
    _mark_included(records, by_file or {}, included)
    entry_files = _entry_files(records, included)
    _walk(model, records, by_file or {}, ".", active_loads, entry_files)
    _apply_control_bindings(model)
    return model


def _mark_included(records: List[CommandRecord],
                   by_file: Dict[str, List[CommandRecord]],
                   included: Dict[str, List[str]]) -> None:
    """Record, per file, the basenames it pulls in via ``load_upf``.

    Resolved by walking each file's records once rather than by scanning for
    the `load_upf` command, so this does not depend on dispatch order.
    """
    for rec in records:
        toks = (rec.text or "").split()
        if len(toks) >= 2 and toks[0].lower() == "load_upf":
            included.setdefault(os.path.basename(rec.file or ""), []).append(
                os.path.basename(toks[1]))


def _entry_files(records: List[CommandRecord],
                 included: Dict[str, List[str]]) -> set:
    """The files that are entry points rather than another file's include."""
    referenced = {t for targets in included.values() for t in targets}
    out = set()
    for rec in records:
        base = os.path.basename(rec.file or "")
        if base and base not in referenced:
            out.add(base)
    return out


def _walk(model: PowerIntentModel, records: List[CommandRecord],
          by_file: Dict[str, List[CommandRecord]], entry_scope: str,
          active_loads: set, entry_files: set) -> None:
    """Process ``records`` sequentially, expanding ``load_upf`` at each site.

    Recurses into a child file rather than reordering the stream, so the model
    is built in exactly the sequence the UPF describes. Only entry files are
    walked at this level; a file included by a parent is walked from the
    parent's load site, in that parent's scope.
    """
    last_file: Optional[str] = None
    # Name of the most recent create_pst — the "current table" context that
    # add_state_transition applies to (IEEE 1801 gives it no -pst option).
    last_pst_name: Optional[str] = None
    first = True
    for rec in records:
        if entry_files and os.path.basename(rec.file or "") not in entry_files:
            # Top level only (entry_files is empty once we are inside a child):
            # a file included by a parent is walked at the parent's load site,
            # so walking it here too would declare everything twice.
            continue
        if rec.file != last_file:
            # A file enters in the scope it was loaded into; a top-level file
            # that was never loaded enters at the scope its caller established.
            model.current_scope = entry_scope if first else "."
            first = False
            last_file = rec.file
            last_pst_name = None
        model.commands_seen += 1
        files = model.record_files.setdefault(rec.line, [])
        if rec.file not in files:
            files.append(rec.file)
        if rec.file:
            model.record_file_names.add(os.path.basename(rec.file))
            # Unambiguous (file, line) -> command text, for provenance.
            model.record_texts.setdefault(f"{rec.file}::{rec.line}", rec.text)
        try:
            tokens = _tokenize(rec)
        except Exception:
            tokens = []
        if not tokens:
            continue
        cmd = tokens[0].lower()
        args = tokens[1:]
        # Ordinary Tcl that appears inside a real .upf file: variable
        # assignment, `source`, `puts`, loop/list constructs, and so on. These
        # are not UPF commands and not defects — reporting them as UPF-001
        # "unknown command" invents a finding on legal input. Real files use
        # them (e.g. `set SCOPE [set_scope btb]` / `source ./common.upf`).
        if cmd in _TCL_NOT_UPF:
            continue
        if cmd not in _SUPPORTED:
            model.unsupported_commands.append(f"{cmd} ({rec.file}:{rec.line})")
            continue
        _syntax_check(model, cmd, tokens, rec)
        seen_loads = len(model.load_upf_events)
        last_pst_name = _dispatch(model, cmd, args, rec, last_pst_name)
        # `load_upf` pulls the child in *here*: expand it at this site, in the
        # scope it is loaded into, rather than remembering one scope per file.
        for ev in model.load_upf_events[seen_loads:]:
            loaded = ev.get("loaded")
            if not loaded:
                continue
            base = os.path.basename(loaded)
            child_records = by_file.get(base)
            if not child_records:
                # Referenced but not supplied (real corpora reference files
                # outside the validated set, e.g. AnyCore's Dispatch.upf). The
                # event is already recorded, so this is visible, not silent.
                continue
            child_scope = ev.get("child_scope") or "."
            marker = (base, child_scope)
            if marker in active_loads:
                # Cycle: this file is already being expanded into this scope.
                continue
            saved = model.current_scope
            active_loads.add(marker)
            try:
                _walk(model, child_records, by_file, child_scope,
                      active_loads, set())
            finally:
                active_loads.discard(marker)
                model.current_scope = saved


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

    # UPF-006 - unbalanced braces / brackets / unterminated quote.
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

    # UPF-002 - illegal option.
    legal = _LEGAL_OPTIONS.get(cmd, set())
    for tok in tokens[1:]:
        if tok.startswith("-") and tok not in legal and not tok[1:2].isdigit():
            model.syntax_issues.append({
                "rule": "UPF-002", "support": "VALIDATED", "line": line,
                "message": f"Illegal option '{tok}' for command '{cmd}'.",
            })

    # UPF-003 - missing required argument.
    for requirement in _REQUIRED_OPTIONS.get(cmd, ()):
        # A requirement is either a single option or a group of interchangeable
        # spellings; the group passes if any member is present.
        spellings = (requirement,) if isinstance(requirement, str) else requirement
        if not any(opt in tokens for opt in spellings):
            # Report the first (canonical) spelling so the message stays stable.
            model.syntax_issues.append({
                "rule": "UPF-003", "support": "VALIDATED", "line": line,
                "message": f"Missing required argument '{spellings[0]}' for "
                           f"command '{cmd}'.",
            })

    # UPF-004 - unsupported version.
    if cmd == "upf_version":
        version = tokens[1] if len(tokens) > 1 else ""
        if version not in _SUPPORTED_VERSIONS:
            model.syntax_issues.append({
                "rule": "UPF-004", "support": "VALIDATED", "line": line,
                "message": f"UPF version '{version or '(none)'}' is not "
                           f"supported (supported: {', '.join(_SUPPORTED_VERSIONS)}).",
            })

    # UPF-005 - deprecated legacy syntax.
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


def _supply_value(args: List[str], *opts: str) -> Optional[str]:
    """Resolve a supply reference, trying each option spelling in order.

    A value may be a bare name (``VDD``) or a Tcl pair carrying a port and a
    supply (``{vin VDD}``). The pair's *supply* is what later rules compare
    against declared nets and sets, so the braces are unwrapped here rather
    than being carried forward as a literal token.
    """
    for opt in opts:
        val = _get_opt(args, opt)
        if val is None:
            continue
        cleaned = val.strip()
        if cleaned.startswith("{") and cleaned.endswith("}"):
            parts = cleaned.strip("{}").split()
            if parts:
                return parts[-1] if len(parts) > 1 else parts[0]
            return None
        return cleaned or None
    return None


def _signal_pair(value: Optional[str]) -> tuple:
    """Split a retention/isolation control into ``(signal, sense)``.

    IEEE 1801 writes these as ``{sig polarity}`` — e.g.
    ``-save_signal {ret_en high}``. The signal half is what must resolve
    against the design; keeping the braced token means a lookup for the
    literal ``'{ret_en high}'`` can never match, so every such control read as
    "not a real signal". A bare name has no explicit polarity.
    """
    if value is None:
        return None, None
    cleaned = value.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        parts = cleaned.strip("{}").split()
        if not parts:
            return None, None
        return parts[0], (parts[1] if len(parts) > 1 else None)
    return cleaned or None, None


def _opt_any(args: List[str], *opts: str) -> Optional[str]:
    """First present value among ``opts``, respecting spelling order.

    ``_get_opt`` takes a single option (its third argument is a *default*,
    which is an easy way to silently mis-read an alias as a fallback value).
    """
    for opt in opts:
        val = _get_opt(args, opt)
        if val is not None:
            return val
    return None


def _pair_role(value: Optional[str]) -> Optional[str]:
    """Return the *role* (first) half of a ``{role name}`` pair, or None.

    A bare single-word value has no role half.
    """
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        parts = cleaned.strip("{}").split()
        if len(parts) > 1:
            return parts[0]
    return None


def _pair_value(value: Optional[str]) -> Optional[str]:
    """Reduce a ``{role name}`` pair to the *name* half.

    IEEE 1801 writes several switch/strategy arguments as a two-element Tcl
    list giving a port role and the signal at that port::

        -control_port {ctrl alPartitionActive_i[2] }

    The role (``ctrl``) names the *kind* of port, not the signal. Rules that
    check a control signal against the design must see ``alPartitionActive_i[2]``;
    keeping the braced pair intact made every such lookup miss and produced
    findings quoting ``{ctrl alPartitionActive_i[2]      }`` as if it were a
    signal name. A bare value (no braces, or a single word) passes through
    unchanged, so ``-control_port iso_en`` still works.
    """
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        parts = cleaned.strip("{}").split()
        if len(parts) > 1:
            return parts[-1]
        if parts:
            return parts[0]
        return None
    return cleaned or None


def _dispatch(model: PowerIntentModel, cmd: str, args: List[str], rec: CommandRecord,
              last_pst_name: Optional[str] = None) -> Optional[str]:
    """Apply one command. Returns the updated current-PST name.

    ``add_state_transition`` has no ``-pst`` option in IEEE 1801 — it adds
    to the table currently being defined, so the ``create_pst`` that set
    that context has to be carried between commands.
    """
    line = rec.line
    if cmd == "upf_version":
        model.upf_version = args[0] if args else None
    elif cmd == "set_design_top":
        model.design_top = args[0] if args else None
    elif cmd == "set_scope":
        # A relative scope composes onto the scope in effect; an absolute one
        # (leading '/') replaces it, and '.' resets to the top.
        #
        # Real hierarchical UPF relies on the relative form:
        #
        #     set_scope /fs1
        #     load_upf FetchStage1.upf        # child enters scope /fs1
        #     # ...inside the child:
        #     set_scope btb                    # -> /fs1/btb, not /btb
        #
        # Assigning absolutely dropped the parent prefix, so supplies declared
        # in the child were keyed 'btb/VDD' while the parent referenced
        # 'fs1/btb/VDD' — a UPF-024 false positive on every hierarchically
        # loaded block.
        #
        # A child file that merely *restates* the scope it was loaded into
        # (``set_scope core_a`` in core_a.upf) is an idempotent restatement,
        # not a descent, so it must not compose to 'core_a/core_a'.
        target = args[0] if args else "."
        current = (model.current_scope or ".").rstrip("/")
        if target in (".", "") or target.startswith("/"):
            model.current_scope = target
        elif current in (".", ""):
            model.current_scope = target
        elif target == current or current.endswith("/" + target):
            # Already in this scope (or a child of it): the child file is
            # restating the scope it was loaded into, which is idempotent.
            model.current_scope = current
        else:
            model.current_scope = f"{current}/{target}"
        model.scope_changes.append({"scope": model.current_scope, "line": line})
    elif cmd == "create_power_domain":
        # The domain name is the first *positional* argument. Real UPF puts
        # flags before it (`create_power_domain -include_scope PD_RAM`), so
        # taking args[0] blindly named the domain "-include_scope" and the real
        # name was lost.
        name = next((a for a in args if not a.startswith("-")), "?")
        scope = model.current_scope
        elements = _get_opt(args, "-elements", "")
        dom = PowerDomain(name=name, scope=scope, declared_line=line,
                          declared_file=rec.file)
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
        _track_definition(model, "domain", name, line, origin=rec.file)
        model.store(model.domains, name, dom, scope, rec.file)
    elif cmd == "create_supply_net":
        name = args[0] if args else "?"
        net = SupplyNet(name=name, scope=model.current_scope, declared_line=line,
                        declared_file=rec.file)
        net.connected_to = []
        _track_definition(model, "net", name, line, origin=rec.file)
        model.store(model.supply_nets, name, net, model.current_scope, rec.file)
    elif cmd == "create_supply_port":
        name = args[0] if args else "?"
        direction = _get_opt(args, "-direction", "inout")
        _track_definition(model, "port", name, line, origin=rec.file)
        model.store(model.supply_ports, name, SupplyPort(
            name=name, scope=model.current_scope, direction=direction,
            declared_line=line, declared_file=rec.file
        ), model.current_scope, rec.file)
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
        _track_definition(model, "set", name, line, origin=rec.file)
        model.store(model.supply_sets, name, SupplySet(
            name=name, scope=model.current_scope, functions=funcs,
            declared_line=line, declared_file=rec.file
        ), model.current_scope, rec.file)
    elif cmd == "connect_supply_net":
        net = args[0] if args else None
        targets = _split_opt(args, "-ports") or _split_opt(args, "-nets")
        if net:
            key = model.scope_key(net, model.current_scope)
            entry = model.supply_nets.get(key)
            if entry is None:
                entry = SupplyNet(name=net, scope=model.current_scope, declared_line=line,
                                  declared_file=rec.file)
                model.supply_nets[key] = entry
            # One record per resolved target, so `-ports { A B }` connects to
            # both A and B. Appending the raw option value would carry the
            # braces into the model and make UPF-024 see one unknown target
            # named '{ A B }' instead of two known ports.
            for t in targets:
                _track_reference(model, "connect", t, line)
                entry.connected_to.append(t)
    elif cmd == "create_power_switch":
        name = args[0] if args else "?"
        on_name, on_supply, on_cond = _split_state_expr(_get_opt(args, "-on_state") or "")
        off_name, _off_supply, off_cond = _split_state_expr(_get_opt(args, "-off_state") or "")
        # IEEE 1801 defines two spellings: UPF 2.1/3.0 use -input_supply /
        # -output_supply (optionally a {-port supply} pair); UPF 3.1+ use
        # -input_supply_port / -output_supply_port. Accept either.
        in_supply = _supply_value(args, "-input_supply", "-input_supply_port")
        out_supply = _supply_value(args, "-output_supply", "-output_supply_port")
        switch = PowerSwitch(
            name=name,
            scope=model.current_scope,
            input_supply=in_supply,
            output_supply=out_supply,
            control_port=_pair_value(_get_opt(args, "-control_port")),
            control_port_role=_pair_role(_get_opt(args, "-control_port")),
            output_port_role=_pair_role(
                _opt_any(args, "-output_supply", "-output_supply_port")),
            input_port_role=_pair_role(
                _opt_any(args, "-input_supply", "-input_supply_port")),
            on_state=on_name or None,
            off_state=off_name or None,
            on_state_supply=on_supply or None,
            on_state_condition=on_cond,
            off_state_condition=off_cond,
            declared_line=line,
            declared_file=rec.file,
        )
        if in_supply:
            _track_reference(model, "supply", in_supply, line)
        if out_supply:
            _track_reference(model, "supply", out_supply, line)
        _track_definition(model, "switch", name, line)
        model.store(model.switches, name, switch, model.current_scope, rec.file)
    elif cmd == "create_pst":
        name = args[0] if args else "?"
        _track_definition(model, "pst", name, line, origin=rec.file)
        model.store(model.psts, name, Pst(
            name=name, scope=model.current_scope, declared_line=line,
            declared_file=rec.file,
            supply_list=_split_opt(args, "-supplies"),
        ), model.current_scope, rec.file)
        last_pst_name = name
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
            # IEEE 1801 defines two accepted spellings for -state:
            #
            #   positional (real files, AnyCore):
            #       create_pst P -supplies { VDD VSS sw/vout }
            #       add_pst_state ON -pst P -state {ACTIVE ACTIVE OFF }
            #     -> entries map *by position* onto the -supplies list.
            #
            #   explicit pairs (also legal, used by this project's fixtures):
            #       add_pst_state ON -pst P -state {vdd ACTIVE vss ACTIVE}
            #     -> each entry names its supply.
            #
            # Reading the positional form as (name, value) pairs put a state
            # name in the supply slot, which made every state look
            # unreferenced (UPF-025/030) and produced self-referential findings
            # like "state 'ACTIVE' on supply 'ACTIVE'" (UPF-031).
            raw_states = []
            for i, a in enumerate(args):
                if a == "-state" and i + 1 < len(args):
                    raw_states.extend(_split_pair(args[i + 1]))

            pst_supplies = _split_opt(args, "-supplies") or \
                list(pst.supply_list)

            if len(raw_states) == 2 * len(pst_supplies) and pst_supplies:
                # Even count with no supply names given => explicit pairs.
                for j in range(0, len(raw_states) - 1, 2):
                    supply_states[raw_states[j]] = raw_states[j + 1]
            elif pst_supplies and len(raw_states) == len(pst_supplies):
                # Positional: one state per supply, in -supplies order.
                for supply, st in zip(pst_supplies, raw_states):
                    supply_states[supply] = st
            else:
                # No usable -supplies list (e.g. a bare fixture): fall back to
                # the historical pairwise reading rather than inventing a key.
                for j in range(0, len(raw_states) - 1, 2):
                    supply_states[raw_states[j]] = raw_states[j + 1]
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
                isolation_supply=_supply_value(
                    args, "-isolation_supply",
                    "-isolation_power_net"),
                control_signal=_get_opt(args, "-isolation_signal"),
                applies_to=_get_opt(args, "-applies_to", "outputs"),
                declared_line=line,
                declared_file=rec.file,
                scope=model.current_scope,
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
                declared_file=rec.file,
                scope=model.current_scope,
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
                isolation_supply=_supply_value(
                    args, "-repeater_isolation_supply"),
                declared_line=line,
                declared_file=rec.file,
            )
        )
    elif cmd == "set_retention":
        from .power_model import RetentionStrategy

        domain = _get_opt(args, "-domain") or ""
        _track_reference(model, "domain", domain, line)
        save_raw = _get_opt(args, "-save_signal")
        restore_raw = _get_opt(args, "-restore_signal")
        save_name, save_sense = _signal_pair(save_raw)
        restore_name, restore_sense = _signal_pair(restore_raw)
        model.retentions.append(
            RetentionStrategy(
                domain=domain,
                elements=_split_opt(args, "-elements"),
                retention_supply=_supply_value(
                    args, "-retention_supply", "-retention_power_net"),
                save_signal=save_raw,
                restore_signal=restore_raw,
                save_signal_name=save_name,
                save_signal_sense=save_sense,
                restore_signal_name=restore_name,
                restore_signal_sense=restore_sense,
                declared_line=line,
                declared_file=rec.file,
                scope=model.current_scope,
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
            # IEEE 1801: add_state_transition carries no -pst option; it adds
            # to the table currently being defined (the most recent
            # create_pst in load order). Appending to every table would put
            # one designer's transition on unrelated power-state tables.
            key = model.scope_key(last_pst_name, model.current_scope) \
                if last_pst_name else None
            pst = model.psts.get(key) if key else None
            if pst is None:
                # No table in context: record on the most recently created
                # one, which is what a single-table file means.
                for candidate in reversed(list(model.psts.values())):
                    if candidate.scope == model.current_scope:
                        pst = candidate
                        break
            if pst is not None:
                pst.transitions.append((src, dst))
    # load_upf is followed in load order; nested loads recorded for scoping.
    # The loaded file name and any -supply mapping (local supply -> parent
    # supply) are recorded so hierarchical ownership and supply maps resolve.
    elif cmd == "load_upf":
        loaded = args[0] if args else None
        # -scope gives the scope the child UPF is loaded INTO; the -supply
        # mapping pairs the child's local supply with a supply in the parent
        # scope (the scope load_upf executes in). References are therefore
        # keyed to the parent scope, not the child scope, so the parent supply
        # resolves and the mapping is traceable.
        parent_scope = model.current_scope
        child_scope = _get_opt(args, "-scope", parent_scope) or parent_scope
        ev = {"scope": parent_scope, "line": line, "file": rec.file,
              "loaded": loaded, "child_scope": child_scope}
        for i, a in enumerate(args):
            if a == "-supply" and i + 1 < len(args):
                pair = _split_pair(args[i + 1])
                if len(pair) == 2:
                    ev["supply_map"] = {"local": pair[0], "parent": pair[1]}
                    model.supply_maps.append({
                        "scope": parent_scope,
                        "local_scope": child_scope,
                        "local": pair[0], "parent": pair[1], "line": line,
                        "file": rec.file,
                    })
                    # The parent supply must exist in the parent scope; the
                    # local supply is defined by the child UPF itself.
                    _track_reference(model, "supply", pair[1], line)
        model.load_upf_events.append(ev)
    elif cmd == "set_isolation_control":
        domain = _get_opt(args, "-domain") or ""
        ctl = model.isolation_controls.setdefault(domain, {})
        if _get_opt(args, "-isolation_signal"):
            ctl["signal"] = _get_opt(args, "-isolation_signal")
        if _get_opt(args, "-isolation_sense"):
            ctl["sense"] = _get_opt(args, "-isolation_sense")
        if _get_opt(args, "-isolation_condition"):
            ctl["condition"] = _get_opt(args, "-isolation_condition")
        # Merge onto the strategy so rules see the control signal even when
        # the generator emits set_isolation_control as a separate command.
        for iso in reversed(model.isolation):
            if iso.domain == domain:
                iso.control_signal = ctl.get("signal") or iso.control_signal
                if ctl.get("sense"):
                    iso.control_sense = ctl["sense"]
                if ctl.get("condition"):
                    iso.control_condition = ctl["condition"]
                break
    elif cmd == "set_retention_control":
        domain = _get_opt(args, "-domain") or ""
        ctl = model.retention_controls.setdefault(domain, {})
        if _get_opt(args, "-retention_signal"):
            ctl["signal"] = _get_opt(args, "-retention_signal")
        if _get_opt(args, "-save_signal"):
            ctl["save_signal"] = _get_opt(args, "-save_signal")
        if _get_opt(args, "-restore_signal"):
            ctl["restore_signal"] = _get_opt(args, "-restore_signal")
        # Merge onto the strategy: save/restore belong to set_retention_control
        # in IEEE 1801, but rules read them from the strategy object.
        for ret in reversed(model.retentions):
            if ret.domain == domain:
                if ctl.get("signal"):
                    ret.control_signal = ctl["signal"]
                if ctl.get("save_signal"):
                    ret.save_signal = ctl["save_signal"]
                    ret.save_signal_name, ret.save_signal_sense = _signal_pair(
                        ctl["save_signal"])
                if ctl.get("restore_signal"):
                    ret.restore_signal = ctl["restore_signal"]
                    ret.restore_signal_name, ret.restore_signal_sense = \
                        _signal_pair(ctl["restore_signal"])
                break
    elif cmd == "set_level_shifter_control":
        domain = _get_opt(args, "-domain") or ""
        ctl = model.level_shifter_controls.setdefault(domain, {})
        if _get_opt(args, "-level_shifter_signal"):
            ctl["signal"] = _get_opt(args, "-level_shifter_signal")
        for ls in reversed(model.level_shifters):
            if ls.domain == domain and ctl.get("signal"):
                ls.control_signal = ctl["signal"]
                break
    elif cmd == "set_repeater_control":
        domain = _get_opt(args, "-domain") or ""
        ctl = model.repeater_controls.setdefault(domain, {})
        if _get_opt(args, "-repeater_signal"):
            ctl["signal"] = _get_opt(args, "-repeater_signal")
        for rep in reversed(model.repeaters):
            if rep.domain == domain and ctl.get("signal"):
                rep.control_signal = ctl["signal"]
                break
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
    elif cmd in ("map_isolation_cell", "map_level_shifter_cell", "map_retention_cell",
                "map_power_switch"):
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
        # Collect every leading non-option token as a target; a single
        # command may name several ports: "set_port_attributes clk, rst,
        # save -attribute {always_on true}".  Stopping at the first option
        # ("-attribute") keeps option values from being mis-read as names.
        attr = _get_opt(args, "-attribute")
        targets: List[str] = []
        for tok in args:
            if tok.startswith("-"):
                break
            targets.append(tok)
        for name in " ".join(targets).replace(",", " ").split():
            if not name:
                continue
            model.port_attributes.setdefault(name, []).append(attr or "")

    return last_pst_name


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