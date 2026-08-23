"""Cross-record analysis modules over the built PowerIntentModel.

These analyzers run after model construction and are independent of the
checker's rule dispatch; each returns a deterministic, serializable result
dataclass. Rule codes UPF-085..UPF-087 originate here.
"""

from __future__ import annotations

from .strategy_interactions import (
    Interaction,
    InteractionResult,
    analyze_strategy_interactions,
)
from .wildcard_analyzer import (
    WildcardAssessment,
    WildcardResult,
    analyze_wildcards,
)

__all__ = [
    "Interaction",
    "InteractionResult",
    "analyze_strategy_interactions",
    "WildcardAssessment",
    "WildcardResult",
    "analyze_wildcards",
]
