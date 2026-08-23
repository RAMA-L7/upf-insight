"""UPF converters - deterministic dict/JSON/YAML views of a UPF file.

Reuses the engine's own preprocessing and Tcl-aware tokenizer so the emitted
structure matches what the model builder actually sees (no re-implementation,
no side effects).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ..model.builder import _tokenize
from ..preprocess.upf_preprocess import CommandRecord, preprocess_file

_VERSION_COMMANDS = frozenset({"upf_version", "set_upf_version"})


def _split_args(tokens: List[str]) -> tuple[List[str], Dict[str, List[str]]]:
    args: List[str] = []
    options: Dict[str, List[str]] = {}
    i = 0
    n = len(tokens)
    while i < n:
        token = tokens[i]
        if token.startswith("-") and len(token) > 1:
            values: List[str] = []
            i += 1
            while i < n and not tokens[i].startswith("-"):
                values.append(tokens[i])
                i += 1
            options[token] = values
        else:
            args.append(token)
            i += 1
    return args, options


def _record_entry(record: CommandRecord) -> Dict[str, Any]:
    tokens = _tokenize(record)
    command = tokens[0].lower() if tokens else ""
    args, options = _split_args(tokens[1:])
    return {
        "line": record.line,
        "command": command,
        "args": args,
        "options": options,
    }


def upf_to_dict(path: str | Path) -> dict:
    """Convert a UPF file into a structured, provenance-carrying dict."""
    p = Path(path)
    records: List[CommandRecord] = preprocess_file(p)
    commands = [_record_entry(r) for r in records]
    upf_version: str | None = None
    for entry in commands:
        if entry["command"] in _VERSION_COMMANDS:
            version_args: List[str] = entry["args"]
            if version_args:
                upf_version = version_args[0]
            break
    return {
        "file": str(p),
        "upf_version": upf_version,
        "commands": commands,
    }


def upf_to_json(path: str | Path) -> str:
    """Serialize the structured view as sorted-key JSON."""
    return json.dumps(upf_to_dict(path), indent=2, sort_keys=True)


def upf_to_yaml(path: str | Path) -> str:
    """Serialize the structured view as YAML."""
    import yaml

    return yaml.safe_dump(upf_to_dict(path), sort_keys=False, allow_unicode=True)


__all__ = ["upf_to_dict", "upf_to_json", "upf_to_yaml"]
