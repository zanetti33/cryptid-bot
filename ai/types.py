from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence, Tuple

from game_model.clues import Clue
from game_model.map import Board

ActionType = Literal["ask_could", "ask_is"]


@dataclass(slots=True, frozen=True)
class InitialSetup:
    """Configuration needed to bootstrap the AI engine."""

    board: Board
    turn_order: Tuple[str, ...]
    bot_player_id: str
    bot_clue_id: str
    clues: Optional[Sequence[Clue]] = None
    include_inverse_clues: bool = True


@dataclass(slots=True, frozen=True)
class AIMove:
    """Recommended next action for the bot."""

    action_type: ActionType
    tile_id: int
    target_player_id: Optional[str] = None
    score: float = 0.0
    confidence: float = 0.0
    rationale: Optional[str] = None
    is_approximate: bool = False


@dataclass(slots=True, frozen=True)
class AIResponse:
    """Resolved yes/no answer produced by the bot for a specific tile."""

    tile_id: int
    answered_yes: bool
    rationale: Optional[str] = None


@dataclass(slots=True, frozen=True)
class AICubePlacement:
    """Cube placement chosen by the bot to reveal as little information as possible."""

    tile_id: int
    score: float = 0.0
    rationale: Optional[str] = None


@dataclass(slots=True, frozen=True)
class ObservationRecord:
    """A single yes/no observation applied to the AI knowledge state."""

    player_id: str
    tile_id: int
    answered_yes: bool


@dataclass(slots=True, frozen=True)
class AIDebugState:
    """Compact, serializable view of the AI knowledge state."""

    observations: Tuple[ObservationRecord, ...] = field(default_factory=tuple)
    possible_clue_ids_by_player: Tuple[tuple[str, Tuple[str, ...]], ...] = field(default_factory=tuple)
    resolved_players: Tuple[str, ...] = field(default_factory=tuple)
    contradictory_players: Tuple[str, ...] = field(default_factory=tuple)


