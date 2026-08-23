"""Pragmatic structural Verilog parsing into a :class:`DesignContext`.

UPF-Insight v1 ships no netlist parser; this module adds a stdlib-only,
deterministic reader for *structural* Verilog (ports, nets, instances,
hierarchy) so design-aware rules can run against a real `.v/.sv` file
instead of requiring a hand-written JSON snapshot.

Scope and honesty boundary:

- supports ``module ... endmodule`` with ANSI and non-ANSI port styles;
- expands buses into per-bit names (plus the base name) because
  :class:`DesignContext` stores flat port lists;
- flags sequential content heuristically (flop-like module names or
  ``always @(posedge|negedge ...)`` blocks);
- never raises on malformed input - problems are returned as issues.

Two pieces of richer information cannot live in ``DesignContext`` fields
(the dataclass is intentionally minimal), so they are attached as plain
attributes and consumed via ``getattr``:

- ``context.port_directions``: ``{port_name: "input"|"output"|"inout"|"unknown"}``
- ``context.children``: ``{parent_module: [child_instance_names]}``

Neither affects determinism; both are sorted before returning.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .design_context import DesignContext, Instance

__all__ = ["parse_verilog", "parse_verilog_text", "load_design"]

VERILOG_EXTENSIONS = (".v", ".sv", ".vh")

_SEQ_HINTS = ("dff", "dfx", "_df", "sdf", "fd", "cnf")

_PG_PIN_RE = re.compile(
    r"^(vdd|vddpe|vddce|vcca|vcc|vpp|vss|vsso|gnd|vnw|vpw)$", re.IGNORECASE
)
_RANGE_RE = re.compile(r"\[\s*(-?\d+)\s*:\s*(-?\d+)\s*\]")
_DIRECTION_RE = re.compile(r"^(input|output|inout)\b")
_NET_DECL_RE = re.compile(r"^(wire|reg|logic|tri|tri0|tri1)\b")
_ASSIGN_RE = re.compile(r"^assign\b")
_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")
_LEADING_IDENT_RE = re.compile(r"^([A-Za-z_]\w*)\s*")
_CONNECTION_RE = re.compile(r"\.\s*([A-Za-z_]\w*)\s*\(")
_MODULE_KEYWORD_RE = re.compile(r"\bmodule\b(?!\w)")
_ENDMODULE_KEYWORD_RE = re.compile(r"\bendmodule\b(?!\w)")
_ALWAYS_EDGE_RE = re.compile(r"\balways\s*@?\s*\(\s*(posedge|negedge)\b")

_RESERVED = {
    "assign", "always", "initial", "final", "if", "else", "case", "casex",
    "casez", "endcase", "begin", "end", "for", "foreach", "forever", "while",
    "repeat", "wait", "posedge", "negedge", "or", "and", "not", "buf", "xor",
    "nand", "nor", "generate", "endgenerate", "function", "endfunction",
    "task", "endtask", "module", "endmodule", "macromodule", "parameter",
    "localparam", "defparam", "integer", "real", "realtime", "time", "genvar",
    "input", "output", "inout", "wire", "reg", "logic", "tri", "tri0", "tri1",
    "supply0", "supply1", "default", "disable", "deassign", "force",
    "release", "fork", "join", "join_any", "join_none", "specify",
    "endspecify", "primitive", "endprimitive", "config", "endconfig",
}

_MAX_EXPANDED_BITS = 4096


def _looks_sequential(module_name: str) -> bool:
    low = module_name.lower()
    return any(hint in low for hint in _SEQ_HINTS)


def _blank_segment(out: List[str], segment: str) -> None:
    for ch in segment:
        out.append(ch if ch == "\n" else " ")


def _strip_comments(text: str) -> str:
    """Blank comments and string literals, preserving line/column offsets."""
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            j = text.find("\n", i)
            if j == -1:
                j = n
            _blank_segment(out, text[i:j])
            i = j
        elif ch == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            end = n if j == -1 else j + 2
            _blank_segment(out, text[i:end])
            i = end
        elif ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    j += 1
                j += 1
            _blank_segment(out, text[i:min(j + 1, n)])
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _line_of(clean: str, index: int) -> int:
    return clean.count("\n", 0, index) + 1


def _extract_balanced(s: str, open_idx: int) -> Optional[Tuple[str, int]]:
    """Return ``(inner, close_idx)`` for the paren group opening at open_idx."""
    depth = 0
    for i in range(open_idx, len(s)):
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return s[open_idx + 1:i], i
    return None


def _split_top(s: str, sep: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(s):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append(s[start:i])
            start = i + 1
    parts.append(s[start:])
    return parts


def _expand_bus(name: str, rng: Optional[Tuple[int, int]]) -> List[str]:
    if rng is None:
        return [name]
    lo, hi = min(rng), max(rng)
    if hi - lo > _MAX_EXPANDED_BITS:
        return [name]
    return [name] + [f"{name}[{i}]" for i in range(lo, hi + 1)]


class _ModuleInfo:
    def __init__(self, name: str, line: int) -> None:
        self.name = name
        self.line = line
        self.port_dirs: Dict[str, str] = {}
        self.port_ranges: Dict[str, Optional[Tuple[int, int]]] = {}
        self.nets: Dict[str, Optional[Tuple[int, int]]] = {}
        self.assign_drivers: List[str] = []
        self.instances: List[Tuple[str, str, Dict[str, str]]] = []
        self.has_edge_always: bool = False


def _record_port(info: _ModuleInfo, name: str, direction: str,
                 rng: Optional[Tuple[int, int]]) -> None:
    info.port_dirs.setdefault(name, direction or "unknown")
    info.port_ranges.setdefault(name, rng)


def _parse_port_item(item: str, info: _ModuleInfo, direction: str,
                     rng: Optional[Tuple[int, int]],
                     issues: List[dict], line: int) -> Tuple[str, Optional[Tuple[int, int]]]:
    dm = _DIRECTION_RE.match(item)
    if dm:
        direction = dm.group(1).lower()
        item = item[dm.end():].strip()
    rm = _RANGE_RE.search(item)
    if rm:
        rng = (int(rm.group(1)), int(rm.group(2)))
        item = item[:rm.start()] + item[rm.end():]
    cleaned = re.sub(r"\b(reg|wire|logic|signed|unsigned|supply0|supply1)\b", " ", item)
    for tok in cleaned.split(","):
        name = tok.strip()
        if not name:
            continue
        if not _IDENT_RE.match(name):
            issues.append({
                "kind": "parse",
                "message": f"unrecognized port token '{name}'",
                "line": line,
            })
            continue
        _record_port(info, name, direction, rng)
    return direction, rng


def _parse_header_port_list(header_rest: str, info: _ModuleInfo,
                            issues: List[dict], line: int) -> None:
    rest = header_rest.strip()
    direction = ""
    rng: Optional[Tuple[int, int]] = None
    for raw in _split_top(rest, ","):
        item = raw.strip()
        if not item or item.startswith("."):
            continue
        direction, rng = _parse_port_item(item, info, direction, rng, issues, line)


def _parse_body_statement(stmt: str, info: _ModuleInfo,
                          issues: List[dict], line: int) -> None:
    text = stmt.strip()
    if not text:
        return
    lead = _LEADING_IDENT_RE.match(text)
    if lead is None:
        return
    first = lead.group(1)
    lowered = first.lower()
    if _ALWAYS_EDGE_RE.search(text):
        info.has_edge_always = True
    if _DIRECTION_RE.match(text):
        direction = ""
        rng: Optional[Tuple[int, int]] = None
        for part in _split_top(text[len(first):].lstrip(), ","):
            direction, rng = _parse_port_item(part.strip(), info, direction, rng,
                                              issues, line)
        return
    if _NET_DECL_RE.match(text):
        rm = _RANGE_RE.search(text)
        rng2 = (int(rm.group(1)), int(rm.group(2))) if rm else None
        tail = _RANGE_RE.sub(" ", text, count=1) if rm else text
        tail = re.sub(r"\b(signed|unsigned)\b", " ", tail)
        names_part = _split_top(tail[len(first):], ",")
        for part in names_part:
            name = part.strip().rstrip(")").strip()
            name = name.split()[-1] if name.split() else ""
            if not name:
                continue
            last = name.split("[")[0].strip()
            if _IDENT_RE.match(last):
                info.nets.setdefault(last, rng2)
            else:
                issues.append({
                    "kind": "parse",
                    "message": f"unrecognized net declaration '{part.strip()}'",
                    "line": line,
                })
        return
    if _ASSIGN_RE.match(text):
        am = re.match(r"^assign\s+(.+?)\s*=\s*(.+)$", text, re.DOTALL)
        if am:
            lhs = am.group(1).strip().split("[")[0].strip()
            if lhs:
                info.assign_drivers.append(lhs)
        return
    if lowered in _RESERVED:
        return
    parsed = _try_instance(text)
    if parsed is None:
        return
    mod_name, inst_name, args = parsed
    if args.strip() and not _CONNECTION_RE.search(args):
        return
    conns: Dict[str, str] = {}
    for cm in _CONNECTION_RE.finditer(args):
        got = _extract_balanced(args, cm.end() - 1)
        if got is None:
            issues.append({
                "kind": "parse",
                "message": f"unbalanced connection on instance '{inst_name}'",
                "line": line,
            })
            continue
        sig = got[0].strip()
        if sig:
            conns[cm.group(1)] = sig
    info.instances.append((inst_name, mod_name, conns))


def _try_instance(stmt: str) -> Optional[Tuple[str, str, str]]:
    m = _LEADING_IDENT_RE.match(stmt)
    if m is None:
        return None
    mod_name = m.group(1)
    if mod_name.lower() in _RESERVED:
        return None
    rest = stmt[m.end():].lstrip()
    if rest.startswith("#"):
        op = rest.find("(")
        if op == -1:
            return None
        got = _extract_balanced(rest, op)
        if got is None:
            return None
        rest = rest[got[1] + 1:].lstrip()
    im = re.match(r"^([A-Za-z_]\w*)\s*\(", rest)
    if im is None:
        return None
    got = _extract_balanced(rest, im.end() - 1)
    if got is None:
        return None
    return mod_name, im.group(1), got[0]


def _parse_module_chunk(chunk: str, line: int, issues: List[dict],
                        modules: Dict[str, _ModuleInfo]) -> None:
    hm = _LEADING_IDENT_RE.match(chunk[len("module"):].lstrip())
    if hm is None:
        issues.append({"kind": "parse", "message": "module without a name", "line": line})
        return
    name = hm.group(1)
    if name.lower() in _RESERVED:
        issues.append({"kind": "parse", "message": f"invalid module name '{name}'",
                       "line": line})
        return
    info = _ModuleInfo(name, line)
    rest = chunk[len("module") + hm.end():].lstrip()
    if rest.startswith("#"):
        op = rest.find("(")
        got = _extract_balanced(rest, op) if op != -1 else None
        if got is None:
            issues.append({
                "kind": "parse",
                "message": f"unterminated parameter list on module '{name}'",
                "line": line,
            })
            modules[name] = info
            return
        rest = rest[got[1] + 1:].lstrip()
    if rest.startswith("("):
        got = _extract_balanced(rest, 0)
        if got is None:
            issues.append({
                "kind": "parse",
                "message": f"unterminated port list on module '{name}'",
                "line": line,
            })
            modules[name] = info
            return
        _parse_header_port_list(got[0], info, issues, line)
        body_start = got[1] + 1
    else:
        body_start = 0
    semi = rest.find(";")
    if semi != -1:
        body = rest[semi + 1:]
    else:
        body = rest[body_start:]
    em = _ENDMODULE_KEYWORD_RE.search(body)
    if em is not None:
        body = body[:em.start()]
    else:
        issues.append({
            "kind": "parse",
            "message": f"missing endmodule for '{name}'",
            "line": line,
        })
    for sm in _ALWAYS_EDGE_RE.finditer(body):
        info.has_edge_always = True
        break
    depth = 0
    start = 0
    for i, ch in enumerate(body):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ";" and depth == 0:
            _parse_body_statement(body[start:i], info, issues, line)
            start = i + 1
    _parse_body_statement(body[start:], info, issues, line)
    if name in modules:
        issues.append({
            "kind": "parse",
            "message": f"duplicate module definition '{name}'",
            "line": line,
        })
    else:
        modules[name] = info


def parse_verilog_text(text: str) -> Tuple[DesignContext, List[dict]]:
    """Parse Verilog source text into ``(DesignContext, issues)``."""
    issues: List[dict] = []
    clean = _strip_comments(text)
    modules: Dict[str, _ModuleInfo] = {}
    order: List[str] = []
    for m in _MODULE_KEYWORD_RE.finditer(clean):
        em = _ENDMODULE_KEYWORD_RE.search(clean, m.start())
        end = em.end() if em is not None else len(clean)
        chunk = clean[m.start():end]
        line = _line_of(clean, m.start())
        before = len(modules)
        _parse_module_chunk(chunk, line, issues, modules)
        for name in modules:
            if name not in order:
                order.append(name)
        if len(modules) == before:
            continue
    context = DesignContext()
    instantiated = {im for info in modules.values() for _, im, _ in info.instances}
    roots = [name for name in order if name not in instantiated]
    port_source_names = roots if roots else list(order)

    port_directions: Dict[str, str] = {}
    port_set: Dict[str, None] = {}
    for name in port_source_names:
        info = modules[name]
        for pname in sorted(info.port_dirs):
            direction = info.port_dirs[pname]
            rng = info.port_ranges[pname]
            for expanded in _expand_bus(pname, rng):
                port_set.setdefault(expanded, None)
                port_directions[expanded] = direction
    context.ports = sorted(port_set)

    signal_entries: Dict[str, dict] = {}
    pg_pins: Dict[str, List[str]] = {}
    children: Dict[str, List[str]] = {}

    for mod_name in order:
        info = modules[mod_name]
        sequential_here = info.has_edge_always or _looks_sequential(mod_name)
        for pname, rng in sorted(info.nets.items()):
            for expanded in _expand_bus(pname, rng):
                signal_entries.setdefault(expanded, {"driver": "", "receivers": []})
        for lhs in sorted(set(info.assign_drivers)):
            entry = signal_entries.setdefault(lhs, {"driver": "", "receivers": []})
            if not entry["driver"]:
                entry["driver"] = "assign"
        for inst_name, inst_mod, conns in info.instances:
            sequential = sequential_here or _looks_sequential(inst_mod)
            if inst_mod in modules and modules[inst_mod].has_edge_always:
                sequential = True
            context.instances[inst_name] = Instance(
                name=inst_name, module=inst_mod, sequential=sequential
            )
            children.setdefault(mod_name, []).append(inst_name)
            for conn_port in sorted(conns):
                if _PG_PIN_RE.match(conn_port):
                    pins = pg_pins.setdefault(inst_mod, [])
                    if conn_port not in pins:
                        pins.append(conn_port)
            sub = modules.get(inst_mod)
            if sub is None:
                continue
            for conn_port in sorted(conns):
                sig = conns[conn_port]
                base_sig = sig.split("[")[0].strip()
                direction = sub.port_dirs.get(conn_port, "")
                entry = signal_entries.setdefault(
                    sig, {"driver": "", "receivers": []})
                if direction == "output" and not entry["driver"]:
                    entry["driver"] = inst_name
                elif direction == "input":
                    if inst_name not in entry["receivers"]:
                        entry["receivers"].append(inst_name)
                if base_sig != sig:
                    base_entry = signal_entries.setdefault(
                        base_sig, {"driver": "", "receivers": []})
                    if direction == "output" and not base_entry["driver"]:
                        base_entry["driver"] = inst_name

    for entry in signal_entries.values():
        entry["receivers"] = sorted(entry["receivers"])
    context.signals = {k: signal_entries[k] for k in sorted(signal_entries)}
    context.pg_pins = {k: sorted(v) for k, v in sorted(pg_pins.items())}
    context.port_directions = {k: port_directions[k] for k in sorted(port_directions)}
    context.children = {k: sorted(v) for k, v in sorted(children.items())}
    return context, issues


def parse_verilog(path: str | Path) -> Tuple[DesignContext, List[dict]]:
    """Parse a structural Verilog file into ``(DesignContext, issues)``.

    Never raises: unreadable or malformed files yield an empty context plus
    recorded issues.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return DesignContext(), [{"kind": "io", "message": f"cannot read {p}: {exc}",
                                  "line": None}]
    try:
        return parse_verilog_text(text)
    except Exception as exc:
        return DesignContext(), [{"kind": "parse",
                                  "message": f"unrecoverable parse failure: {exc}",
                                  "line": None}]


def load_design(path: str | Path) -> DesignContext:
    """Load a design context, dispatching by extension.

    ``.json`` delegates to :meth:`DesignContext.load`; everything else
    (``.v`` / ``.sv`` / ``.vh`` and unknown extensions) goes through
    :func:`parse_verilog`. Never raises; failures return an empty context.
    """
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".json":
        try:
            return DesignContext.load(p)
        except Exception:
            return DesignContext()
    context, _issues = parse_verilog(p)
    return context
