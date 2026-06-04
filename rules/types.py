"""
Backward compatibility module. Import from game_model.types instead.
"""

from game_model.types import (
    AnimalTerritory,
    StructureColor,
    StructureType,
    TerrainType,
    TokenType,
)

__all__ = [
    "TerrainType",
    "AnimalTerritory",
    "StructureType",
    "StructureColor",
    "TokenType",
]

