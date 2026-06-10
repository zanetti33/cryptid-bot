from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Tuple

WarningScope = Literal["setup", "board_layout", "map", "structures", "clues", "recalculate", "session"]
WarningSeverity = Literal["info", "warn", "error"]
SessionPhase = Literal["setup", "board_layout", "map", "structures", "clues", "review"]


@dataclass(slots=True, frozen=True)
class WarningItem:
    code: str
    message: str
    scope: WarningScope
    severity: WarningSeverity

    def dedupe_key(self) -> Tuple[str, str, str]:
        return (self.code, self.scope, self.message)

    def to_dict(self) -> Dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "scope": self.scope,
            "severity": self.severity,
        }


@dataclass(slots=True)
class SetupState:
    player_ids: Tuple[str, ...] = ()
    turn_order: Tuple[str, ...] = ()
    bot_player_id: Optional[str] = None
    bot_clue_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_ids": list(self.player_ids),
            "turn_order": list(self.turn_order),
            "bot_player_id": self.bot_player_id,
            "bot_clue_id": self.bot_clue_id,
        }


@dataclass(slots=True)
class MapState:
    cols: int = 12
    rows: int = 9
    observed_tokens: Tuple[Dict[str, Any], ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cols": self.cols,
            "rows": self.rows,
            "observed_tokens": [dict(entry) for entry in self.observed_tokens],
        }


@dataclass(slots=True)
class BoardLayoutState:
    placements: Tuple[Dict[str, Any], ...] = ()
    board_tiles: Tuple[Dict[str, Any], ...] = ()
    cols: int = 12
    rows: int = 9
    is_complete: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "placements": [dict(entry) for entry in self.placements],
            "board_tiles": [dict(entry) for entry in self.board_tiles],
            "cols": self.cols,
            "rows": self.rows,
            "is_complete": self.is_complete,
        }


@dataclass(slots=True)
class StructuresState:
    by_tile_id: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "by_tile_id": {str(tile_id): dict(value) for tile_id, value in self.by_tile_id.items()},
        }


@dataclass(slots=True)
class CluesState:
    by_player_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "by_player_id": {player_id: dict(value) for player_id, value in self.by_player_id.items()},
        }


@dataclass(slots=True)
class AiState:
    hypothesis_space_raw: Dict[str, Any] = field(default_factory=dict)
    recommended_moves_raw: Tuple[Dict[str, Any], ...] = ()
    ui_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_space_raw": dict(self.hypothesis_space_raw),
            "recommended_moves_raw": [dict(move) for move in self.recommended_moves_raw],
            "ui_payload": dict(self.ui_payload),
        }


@dataclass(slots=True)
class SessionState:
    session_id: str
    phase: SessionPhase = "setup"
    setup: SetupState = field(default_factory=SetupState)
    board_layout_state: BoardLayoutState = field(default_factory=BoardLayoutState)
    map_state: MapState = field(default_factory=MapState)
    structures_state: StructuresState = field(default_factory=StructuresState)
    clues_state: CluesState = field(default_factory=CluesState)
    ai_state: AiState = field(default_factory=AiState)
    warnings: Tuple[WarningItem, ...] = ()
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def with_updates(self, **kwargs: Any) -> "SessionState":
        data = {
            "session_id": self.session_id,
            "phase": self.phase,
            "setup": self.setup,
            "board_layout_state": self.board_layout_state,
            "map_state": self.map_state,
            "structures_state": self.structures_state,
            "clues_state": self.clues_state,
            "ai_state": self.ai_state,
            "warnings": self.warnings,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        data.update(kwargs)
        return SessionState(**data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "phase": self.phase,
            "setup": self.setup.to_dict(),
            "board_layout_state": self.board_layout_state.to_dict(),
            "map_state": self.map_state.to_dict(),
            "structures_state": self.structures_state.to_dict(),
            "clues_state": self.clues_state.to_dict(),
            "ai_state": self.ai_state.to_dict(),
            "warnings": [warning.to_dict() for warning in self.warnings],
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class ApiResult:
    session: SessionState
    warnings: Tuple[WarningItem, ...]
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session": self.session.to_dict(),
            "warnings": [warning.to_dict() for warning in self.warnings],
            "data": dict(self.data),
        }


def merge_warnings(*warning_groups: Tuple[WarningItem, ...]) -> Tuple[WarningItem, ...]:
    by_key: Dict[Tuple[str, str, str], WarningItem] = {}
    for group in warning_groups:
        for warning in group:
            by_key[warning.dedupe_key()] = warning
    ordered = sorted(by_key.values(), key=lambda item: (item.scope, item.code, item.message))
    return tuple(ordered)

