"""Finding - the shared validation-finding data type.

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
    #: The object this finding is about (domain/supply/switch/strategy name).
    #: Used by cascade suppression: when a prerequisite rule (e.g. UPF-010
    #: undefined supply) errors on the same subject, dependent findings on
    #: that subject are downgraded instead of emitted as definitive errors.
    subject: str = ""
    #: Set by the cascade pass: the rule code that blocked this finding.
    blocked_by: str = ""

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "support": self.support,
            "subject": self.subject,
            "blocked_by": self.blocked_by,
        }


__all__ = ["Finding"]