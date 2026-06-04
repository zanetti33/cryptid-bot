"""
Backward compatibility module. Import from game_model.clues instead.
"""

from game_model.clues import (
    AndPredicate,
    AtomPredicate,
    Clue,
    NotPredicate,
    OrPredicate,
    TargetCategory,
    build_base_clues,
    build_clue_catalog,
    clues_by_id,
)

__all__ = [
    "TargetCategory",
    "AtomPredicate",
    "AndPredicate",
    "OrPredicate",
    "NotPredicate",
    "Clue",
    "build_base_clues",
    "build_clue_catalog",
    "clues_by_id",
]

