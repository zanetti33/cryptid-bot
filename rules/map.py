"""
Backward compatibility module. Import from game_model.map instead.
"""

from game_model.map import Board, AxialCoord, HexTile

__all__ = ["Board", "AxialCoord", "HexTile"]
