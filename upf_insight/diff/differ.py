"""Semantic UPF diff.

Compares two power-intent models (old vs new) and reports structural changes:
domains added/removed, supply set changes, strategy changes, PST changes.
Mirrors the sdc-tools constraint_diff approach: model-level comparison rather
than raw line diff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..engine.engine import validate


@dataclass
class Change:
    kind: str  # ADD | REMOVE | MODIFY
    what: str  # domain | supply | switch | pst | strategy
    name: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.kind} {self.what} '{self.name}' {self.detail}".strip()


def diff_files(old_path: str, new_path: str) -> List[Change]:
    old = validate([old_path])
    new = validate([new_path])
    return diff_models(old.check.model, new.check.model)


#: Model fields that are provenance, not semantics. Comparing them would mark
#: every object MODIFY whenever unrelated edits shift source line numbers.
_PROVENANCE_FIELDS = frozenset({"declared_line", "declared_file"})


def _semantic_eq(a, b) -> bool:
    """Deep equality ignoring provenance fields (declared_line/file) at any
    depth. Model objects, dicts, lists, and scalars are all handled so that
    purely textual edits never surface as semantic MODIFY changes."""
    if a is b:
        return True
    if hasattr(a, "__dict__") and hasattr(b, "__dict__"):
        return _semantic_eq(vars(a), vars(b))
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return False
        return all(
            k in _PROVENANCE_FIELDS or _semantic_eq(a[k], b[k])
            for k in a
        )
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(
            _semantic_eq(x, y) for x, y in zip(a, b)
        )
    return a == b


def diff_models(old, new) -> List[Change]:
    changes: List[Change] = []

    def _dict_diff(old_map, new_map, what):
        for name in sorted(set(new_map) - set(old_map)):
            changes.append(Change("ADD", what, name))
        for name in sorted(set(old_map) - set(new_map)):
            changes.append(Change("REMOVE", what, name))
        for name in sorted(set(old_map) & set(new_map)):
            o, n = old_map[name], new_map[name]
            if not _semantic_eq(o, n):
                changes.append(Change("MODIFY", what, name))

    _dict_diff(old.domains, new.domains, "domain")
    _dict_diff(old.supply_nets, new.supply_nets, "supply_net")
    _dict_diff(old.supply_sets, new.supply_sets, "supply_set")
    _dict_diff(old.switches, new.switches, "switch")
    _dict_diff(old.psts, new.psts, "pst")

    if len(old.isolation) != len(new.isolation):
        changes.append(Change("MODIFY", "strategy",
                              "isolation",
                              f"count {len(old.isolation)} -> {len(new.isolation)}"))
    if len(old.level_shifters) != len(new.level_shifters):
        changes.append(Change("MODIFY", "strategy",
                              "level_shifter",
                              f"count {len(old.level_shifters)} -> "
                              f"{len(new.level_shifters)}"))
    if len(old.retentions) != len(new.retentions):
        changes.append(Change("MODIFY", "strategy",
                              "retention",
                              f"count {len(old.retentions)} -> "
                              f"{len(new.retentions)}"))
    return changes


__all__ = ["Change", "diff_files", "diff_models"]