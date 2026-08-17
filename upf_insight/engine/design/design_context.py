"""Design context - the netlist/design snapshot UPF-080…084 validate against.

v1 is UPF-only, so design-aware rules (layer 6) are silent unless a design
context is supplied. The context is a minimal, deterministic JSON description
of the design:

.. code-block:: json

    {
      "instances": {
        "u_cpu": {"module": "cpu_core", "sequential": true},
        "u_io":  {"module": "io_block",  "sequential": false}
      },
      "ports": ["clk", "reset_n", "iso_en"],
      "signals": {
        "req_a": {"driver": "u_cpu", "receivers": ["u_io"]}
      },
      "pg_pins": {
        "cpu_core": ["VDD", "VSS"],
        "io_block": ["VDD_IO", "VSS"]
      }
    }

No netlist parser is bundled; tools can emit this shape (or the workspace can
capture it). Rules consult :class:`DesignContext` and stay silent when it is
absent, keeping the honest support boundary (NETLIST_REQUIRED).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Instance:
    name: str
    module: str = ""
    sequential: bool = False


@dataclass
class DesignContext:
    """Netlist snapshot used by the design-aware rule layer."""

    instances: Dict[str, Instance] = field(default_factory=dict)
    ports: List[str] = field(default_factory=list)
    signals: Dict[str, dict] = field(default_factory=dict)  # name -> {driver, receivers}
    pg_pins: Dict[str, List[str]] = field(default_factory=dict)  # module -> pins

    def has_instance(self, name: str) -> bool:
        return name in self.instances

    def has_signal(self, name: str) -> bool:
        if name in self.ports or name in self.signals:
            return True
        return False

    def domain_instances(self, elements: List[str]) -> List[Instance]:
        return [self.instances[e] for e in elements if e in self.instances]

    def to_dict(self) -> dict:
        return {
            "instances": {n: {"module": i.module, "sequential": i.sequential}
                          for n, i in self.instances.items()},
            "ports": self.ports,
            "signals": self.signals,
            "pg_pins": self.pg_pins,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DesignContext":
        instances = {
            name: Instance(name=name,
                           module=spec.get("module", ""),
                           sequential=bool(spec.get("sequential", False)))
            for name, spec in (data.get("instances") or {}).items()
        }
        return cls(
            instances=instances,
            ports=list(data.get("ports") or []),
            signals=dict(data.get("signals") or {}),
            pg_pins={k: list(v) for k, v in (data.get("pg_pins") or {}).items()},
        )

    @classmethod
    def load(cls, path: str | Path) -> "DesignContext":
        p = Path(path)
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)


def load_optional(path: Optional[str]) -> Optional[DesignContext]:
    """Load a design context if a path was supplied, else None."""
    if not path:
        return None
    return DesignContext.load(path)


__all__ = ["DesignContext", "Instance", "load_optional"]
