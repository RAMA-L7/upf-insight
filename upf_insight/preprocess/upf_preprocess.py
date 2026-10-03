"""UPF preprocessing - Tcl lexical preprocessing for IEEE 1801 (UPF) files.

UPF is a Tcl dialect. This module strips comments, joins line continuations,
preserves command boundaries, and emits clean command records suitable for the
power-intent model builder.

The design mirrors the sdc-tools ``sdc_preprocess.py`` module: deterministic,
no execution, and every emitted record carries its provenance (file, line).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List

#: Command names that can legitimately start a new logical command while the
#: lexer is inside an unbalanced brace. Used for recovery only — a line that
#: begins with one of these is treated as a fresh command, which stops a single
#: stray ``{`` from swallowing the remainder of the file.
#:
#: This is what lets the lexer honour multi-line ``-elements { ... }`` lists
#: *and* still survive malformed input. The unbalanced construct is preserved
#: in the record text, so UPF-006 still reports it.
_COMMAND_START = re.compile(
    r"^(?:upf_version|set_design_top|set_scope|create_\w+|connect_\w+|"
    r"add_\w+|set_\w+|update_\w+|map_\w+|load_upf|upf_\w+)\b"
)


@dataclass(frozen=True)
class CommandRecord:
    """One preprocessed UPF command with source provenance."""

    text: str
    file: str
    line: int

    @property
    def command_name(self) -> str:
        """The leading Tcl command name (lowercased)."""
        first = self.text.lstrip().split(None, 1)
        return first[0].lower() if first else ""


def preprocess(text: str, file: str = "<string>") -> List[CommandRecord]:
    """Split UPF/Tcl text into command records.

    A single character-by-character lexer handles, in one pass:
      * brace ``{}``, bracket ``[]``, and double-quote ``"..."`` state;
      * ``#`` comments -- only stripped when outside ``{}``, ``[]`` and ``""``,
        and only when the ``#`` begins a logical line or follows whitespace
        (so ``foo#bar`` and a ``#`` inside a construct are preserved);
      * line continuations (``\\`` at end of line, outside quotes/braces/brackets)
        joined with a single space, for both ``\\n`` and ``\\r\\n``;
      * per-physical-line command splitting when no continuation is present, so an
        unbalanced brace on one line cannot swallow subsequent commands.

    Command text is kept verbatim (no tokenization here); tokenization is the
    model builder's job. Each emitted record carries the *first* physical line
    number of its logical command.
    """
    records: List[CommandRecord] = []
    buf: List[str] = []            # characters of the current logical command
    start_line: int | None = None  # first physical line of the current command
    brace = 0
    bracket = 0
    dq = False
    line = 1
    n = len(text)
    i = 0

    def flush() -> None:
        nonlocal buf, start_line, brace, bracket, dq
        s = "".join(buf).strip()
        ln = start_line
        buf = []
        start_line = None
        brace = bracket = 0
        dq = False
        if s:
            records.append(CommandRecord(text=s, file=file, line=ln))

    def mark() -> None:
        nonlocal start_line
        if start_line is None:
            start_line = line

    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        # --- carriage returns are inert whitespace ---
        if c == "\r":
            i += 1
            continue

        # --- physical end of line ---
        #
        # A newline terminates a command only at depth zero. Inside braces,
        # brackets, or a double-quoted string it is ordinary whitespace, so a
        # multi-line `-elements { ... }` list stays one logical command.
        #
        # Recovery: if we are inside a construct that never closes and the next
        # line begins with a real UPF command, the brace was unbalanced. Emit
        # what we have (UPF-006 reports the imbalance) and resume at depth 0,
        # rather than swallowing the rest of the file.
        if c == "\n":
            if brace == 0 and bracket == 0 and not dq:
                flush()
            elif _COMMAND_START.match(text[i + 1:].lstrip()) and not dq:
                flush()
                brace = bracket = 0
            else:
                buf.append(" ")
                mark()
            line += 1
            i += 1
            continue

        # --- line continuation: backslash before (optional spaces and) EOL ---
        #
        # A backslash standing for whitespace before a newline is a line
        # continuation *everywhere*, including inside braces. Real UPF relies
        # on this in multi-line lists, e.g.
        #
        #     connect_supply_net VSS -ports { VSS  \
        #                                      dom0/VSS  \
        #                                      dom1/VSS }
        #
        # Preserving the backslash put a literal '\' into the port list, which
        # then surfaced as a bogus "unknown target '\'" (UPF-024) once per
        # continuation. Some files emit "…  \ " with a trailing space *after*
        # the backslash, so the run of spaces/tabs between the backslash and
        # the newline is consumed too — the backslash means "this is
        # whitespace", and the spaces it introduces are the same whitespace.
        if c == "\\":
            j = i + 1
            while j < n and text[j] in (" ", "\t"):
                j += 1
            if j < n and (text[j] == "\n" or
                          (text[j] == "\r" and j + 1 < n and text[j + 1] == "\n")):
                buf.append(" ")
                i = j + 2 if text[j] == "\r" else j + 1
                line += 1
                continue

        # --- comment: '#' outside braces/brackets/quotes, at command start or
        #     preceded by whitespace (so 'foo#bar' and '#' inside {} [] "" survive) ---
        prev_ws = (not buf) or buf[-1] in (" ", "\t")
        if c == "#" and brace == 0 and bracket == 0 and not dq and prev_ws:
            while i < n and text[i] not in ("\n", "\r"):
                i += 1
            flush()
            continue

        # --- inside a double-quoted string ---
        if dq:
            if c == "\\" and nxt != "":
                mark()
                buf.append(c)
                buf.append(nxt)
                i += 2
                continue
            if c == '"':
                dq = False
            mark()
            buf.append(c)
            i += 1
            continue

        # --- double-quote opener ---
        if c == '"':
            dq = True
            mark()
            buf.append(c)
            i += 1
            continue

        # --- brace / bracket depth ---
        if c == "{":
            brace += 1
            mark()
            buf.append(c)
            i += 1
            continue
        if c == "}":
            if brace > 0:
                brace -= 1
            mark()
            buf.append(c)
            i += 1
            continue
        if c == "[":
            bracket += 1
            mark()
            buf.append(c)
            i += 1
            continue
        if c == "]":
            if bracket > 0:
                bracket -= 1
            mark()
            buf.append(c)
            i += 1
            continue

        # --- ordinary character ---
        mark()
        buf.append(c)
        i += 1

    flush()
    return records


def preprocess_file(path: str | Path) -> List[CommandRecord]:
    """Preprocess a single .upf file into command records."""
    p = Path(path)
    return preprocess(p.read_text(encoding="utf-8", errors="replace"), str(p))


def preprocess_many(paths: Iterable[str | Path]) -> List[CommandRecord]:
    """Preprocess multiple files in load order into one command stream."""
    records: List[CommandRecord] = []
    for path in paths:
        records.extend(preprocess_file(path))
    return records


__all__ = [
    "CommandRecord",
    "preprocess",
    "preprocess_file",
    "preprocess_many",
]