"""
Backward compatibility module. Import from game_model.game instead.
"""

from game_model.game import (
    AskCouldResult,
    AskIsResult,
    Game,
    GamePhase,
    PlayerState,
)

__all__ = [
    "Game",
    "GamePhase",
    "PlayerState",
    "AskCouldResult",
    "AskIsResult",
]
