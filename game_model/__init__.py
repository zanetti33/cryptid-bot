"""
Game model module for Cryptid.

This module contains the core game logic, board model, rules, types, and game state.
It is independent from recognition, AI decision-making, and Discord integration.
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
from game_model.game import AskCouldResult, AskIsResult, Game, GamePhase, PlayerState
from game_model.map import Board, HexTile
from game_model.state import GameSnapshot, ObservedToken
from game_model.tokens import GameState, TokenPlacement
from game_model.types import AnimalTerritory, StructureColor, StructureType, TerrainType, TokenType

__all__ = [
    # Game core
    "Game",
    "GamePhase",
    "PlayerState",
    "AskCouldResult",
    "AskIsResult",
    # Board & tiles
    "Board",
    "HexTile",
    "GameState",
    "TokenPlacement",
    # Game snapshot (observation)
    "GameSnapshot",
    "ObservedToken",
    # Types
    "TerrainType",
    "AnimalTerritory",
    "StructureType",
    "StructureColor",
    "TokenType",
    # Clues & predicates
    "Clue",
    "AtomPredicate",
    "AndPredicate",
    "OrPredicate",
    "NotPredicate",
    "TargetCategory",
    "build_base_clues",
    "build_clue_catalog",
    "clues_by_id",
]


