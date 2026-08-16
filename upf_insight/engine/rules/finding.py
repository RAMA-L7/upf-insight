"""Finding — the shared validation-finding data type.

Defined in its own module to break the import cycle between the checker
(which dispatches) and the rule implementations (which produce findings).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Finding:
    """One validation finding with provenance."""

    rule: str  # e.g. UPF-040
    severity: str  # error | warning | info
    message: str
    file: str = ""
    line: Optional[int] = None
    support: str = "VALIDATED"

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "support": self.support,
        }


__all__ = ["Finding"]