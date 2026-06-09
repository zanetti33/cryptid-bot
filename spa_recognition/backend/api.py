from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from ai.inference import HypothesisSpace, infer_hypothesis_space
from ai.strategy import RecommendedMove, recommend_moves
from game_model.map import Board, HexTile
from game_model.state import GameSnapshot
from game_model.types import StructureColor, StructureType, TokenType
from spa_recognition.backend.models import (
    AiState,
    ApiResult,
    CluesState,
    MapState,
    SessionState,
    SetupState,
    StructuresState,
    WarningItem,
    merge_warnings,
)
from spa_recognition.backend.session_store import SessionStore


class SpaRecognitionApi:
    """Permissive API facade for SPA recognition workflows."""

    def __init__(self, session_store: Optional[SessionStore] = None) -> None:
        self._store = session_store or SessionStore()

    def post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        if path == "/setup":
            return self.post_setup(payload)
        if path == "/map":
            return self.post_map(payload)
        if path == "/structures":
            return self.post_structures(payload)
        if path == "/clues":
            return self.post_clues(payload)
        if path == "/recalculate":
            return self.post_recalculate(payload)
        raise ValueError(f"Unknown path: {path}")

    def post_setup(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        player_ids = _string_tuple(data.get("player_ids"), current.setup.player_ids, local_warnings, "setup", "player_ids")
        turn_order = _string_tuple(data.get("turn_order"), current.setup.turn_order, local_warnings, "setup", "turn_order")
        bot_player_id = _optional_string(data.get("bot_player_id"), current.setup.bot_player_id)

        if not player_ids:
            local_warnings.append(_warning("PLAYER_COUNT_UNUSUAL", "No players configured yet.", "setup", "warn"))

        if bot_player_id is not None and player_ids and bot_player_id not in player_ids:
            local_warnings.append(
                _warning(
                    "TURN_ORDER_MISSING_BOT",
                    "bot_player_id is not present in player_ids.",
                    "setup",
                    "warn",
                )
            )

        if turn_order and player_ids:
            unknown = [player_id for player_id in turn_order if player_id not in player_ids]
            if unknown:
                local_warnings.append(
                    _warning(
                        "TURN_ORDER_UNKNOWN_PLAYER",
                        f"turn_order contains unknown players: {', '.join(unknown)}",
                        "setup",
                        "warn",
                    )
                )

        updated_setup = SetupState(player_ids=player_ids, turn_order=turn_order, bot_player_id=bot_player_id)
        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(setup=updated_setup, phase="map", warnings=merged_warnings)
        self._store.upsert(updated)
        return ApiResult(session=updated, warnings=merged_warnings)

    def post_map(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        cols = _positive_int(data.get("cols"), current.map_state.cols, local_warnings, "map", "cols")
        rows = _positive_int(data.get("rows"), current.map_state.rows, local_warnings, "map", "rows")
        max_tile_id = (cols * rows) - 1

        observed_tokens: List[Dict[str, Any]] = []
        raw_tokens = data.get("observed_tokens", [])
        if raw_tokens is None:
            raw_tokens = []
        if not isinstance(raw_tokens, list):
            local_warnings.append(_warning("MAP_TOKENS_INVALID", "observed_tokens must be a list.", "map", "error"))
            raw_tokens = []

        for entry in raw_tokens:
            if not isinstance(entry, dict):
                local_warnings.append(_warning("MAP_TOKEN_ENTRY_INVALID", "Token entry must be an object.", "map", "warn"))
                continue

            tile_id = _coerce_int(entry.get("tile_id"), -1)
            if tile_id < 0 or tile_id > max_tile_id:
                local_warnings.append(
                    _warning(
                        "TOKEN_TILE_OUT_OF_RANGE",
                        f"tile_id {tile_id} is out of range for {cols}x{rows} board.",
                        "map",
                        "warn",
                    )
                )
                continue

            player_id = entry.get("player_id")
            if not isinstance(player_id, str) or not player_id.strip():
                local_warnings.append(_warning("TOKEN_PLAYER_MISSING", "Token entry requires player_id.", "map", "warn"))
                continue

            token_type = _coerce_token_type(entry.get("token_type"))
            if token_type is None:
                local_warnings.append(_warning("TOKEN_TYPE_UNKNOWN", "token_type must be round or cube.", "map", "warn"))
                continue

            observed_tokens.append(
                {
                    "tile_id": tile_id,
                    "player_id": player_id.strip(),
                    "token_type": token_type.value,
                }
            )

        updated_map = MapState(cols=cols, rows=rows, observed_tokens=tuple(observed_tokens))
        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(map_state=updated_map, phase="structures", warnings=merged_warnings)
        self._store.upsert(updated)
        return ApiResult(session=updated, warnings=merged_warnings)

    def post_structures(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        max_tile_id = (current.map_state.cols * current.map_state.rows) - 1
        next_map = dict(current.structures_state.by_tile_id)

        raw_structures = data.get("structures", [])
        if raw_structures is None:
            raw_structures = []
        if not isinstance(raw_structures, list):
            local_warnings.append(_warning("STRUCTURES_INVALID", "structures must be a list.", "structures", "error"))
            raw_structures = []

        used_signatures = set()
        for entry in raw_structures:
            if not isinstance(entry, dict):
                local_warnings.append(_warning("STRUCTURE_ENTRY_INVALID", "Each structure must be an object.", "structures", "warn"))
                continue

            tile_id = _coerce_int(entry.get("tile_id"), -1)
            if tile_id < 0 or tile_id > max_tile_id:
                local_warnings.append(
                    _warning(
                        "STRUCTURE_TILE_OUT_OF_RANGE",
                        f"tile_id {tile_id} is out of range for current map.",
                        "structures",
                        "warn",
                    )
                )
                continue

            structure_type = _coerce_structure_type(entry.get("structure_type"))
            structure_color = _coerce_structure_color(entry.get("structure_color"))
            if structure_type is None or structure_color is None:
                local_warnings.append(
                    _warning(
                        "STRUCTURE_VALUE_INVALID",
                        "structure_type and structure_color must be valid enum values.",
                        "structures",
                        "warn",
                    )
                )
                continue

            signature = (structure_type.value, structure_color.value)
            if signature in used_signatures:
                local_warnings.append(
                    _warning(
                        "STRUCTURE_COLOR_DUPLICATE",
                        f"Duplicate structure signature detected: {signature[0]}/{signature[1]}",
                        "structures",
                        "warn",
                    )
                )
            used_signatures.add(signature)

            next_map[tile_id] = {
                "structure_type": structure_type.value,
                "structure_color": structure_color.value,
            }

        updated_structures = StructuresState(by_tile_id=next_map)
        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(structures_state=updated_structures, phase="clues", warnings=merged_warnings)
        self._store.upsert(updated)
        return ApiResult(session=updated, warnings=merged_warnings)

    def post_clues(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        raw_by_player = data.get("by_player_id", {})
        if raw_by_player is None:
            raw_by_player = {}
        if not isinstance(raw_by_player, dict):
            local_warnings.append(_warning("CLUE_PAYLOAD_INVALID", "by_player_id must be an object.", "clues", "error"))
            raw_by_player = {}

        normalized: Dict[str, Dict[str, Any]] = {}
        for player_id, info in raw_by_player.items():
            if not isinstance(player_id, str) or not player_id.strip():
                local_warnings.append(_warning("CLUE_PLAYER_INVALID", "Player id must be a non-empty string.", "clues", "warn"))
                continue
            if not isinstance(info, dict):
                local_warnings.append(
                    _warning(
                        "CLUE_ENTRY_INVALID",
                        f"Clue entry for {player_id} must be an object.",
                        "clues",
                        "warn",
                    )
                )
                continue
            normalized[player_id] = dict(info)

        if not normalized:
            local_warnings.append(_warning("CLUE_SET_INCOMPLETE", "No clue information provided yet.", "clues", "warn"))

        merged_state = dict(current.clues_state.by_player_id)
        merged_state.update(normalized)
        updated_clues = CluesState(by_player_id=merged_state)

        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(clues_state=updated_clues, phase="review", warnings=merged_warnings)
        self._store.upsert(updated)
        return ApiResult(session=updated, warnings=merged_warnings)

    def post_recalculate(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        top_k = _positive_int(data.get("top_k"), 5, local_warnings, "recalculate", "top_k")

        snapshot, adapter_warnings = _build_snapshot_from_session(current)
        local_warnings.extend(adapter_warnings)

        if not snapshot.player_ids():
            local_warnings.append(
                _warning(
                    "AI_INPUT_PARTIAL",
                    "No known players in snapshot; results may be low quality.",
                    "recalculate",
                    "warn",
                )
            )

        try:
            hypothesis_space = infer_hypothesis_space(snapshot=snapshot)
            moves = recommend_moves(snapshot=snapshot, hypothesis_space=hypothesis_space, top_k=top_k)
            ai_state = AiState(
                hypothesis_space_raw=_serialize_hypothesis_space(hypothesis_space),
                recommended_moves_raw=tuple(_serialize_recommended_move(move) for move in moves),
                ui_payload={
                    "global_candidate_tiles": list(hypothesis_space.global_candidate_tiles()),
                    "global_guaranteed_tiles": list(hypothesis_space.global_guaranteed_tiles()),
                    "top_move": _serialize_recommended_move(moves[0]) if moves else None,
                },
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            local_warnings.append(
                _warning(
                    "AI_RECALCULATE_FAILED",
                    f"AI recalculation failed: {exc}",
                    "recalculate",
                    "error",
                )
            )
            ai_state = current.ai_state

        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(ai_state=ai_state, phase="review", warnings=merged_warnings)
        self._store.upsert(updated)

        return ApiResult(
            session=updated,
            warnings=merged_warnings,
            data={
                "hypothesis_space": ai_state.hypothesis_space_raw,
                "recommended_moves": [dict(move) for move in ai_state.recommended_moves_raw],
                "ui_payload": dict(ai_state.ui_payload),
            },
        )


def _build_snapshot_from_session(session: SessionState) -> Tuple[GameSnapshot, List[WarningItem]]:
    warnings: List[WarningItem] = []
    board = Board.rectangular(cols=session.map_state.cols, rows=session.map_state.rows)
    tiles_by_id = {tile.tile_id: tile for tile in board.tiles.values()}

    for tile_id, structure in session.structures_state.by_tile_id.items():
        tile = tiles_by_id.get(tile_id)
        if tile is None:
            warnings.append(
                _warning(
                    "STRUCTURE_TILE_NOT_FOUND",
                    f"Structure tile_id {tile_id} is outside board bounds.",
                    "session",
                    "warn",
                )
            )
            continue
        structure_type = _coerce_structure_type(structure.get("structure_type"))
        structure_color = _coerce_structure_color(structure.get("structure_color"))
        if structure_type is None or structure_color is None:
            warnings.append(
                _warning(
                    "STRUCTURE_VALUE_INVALID",
                    f"Invalid structure values on tile_id {tile_id}.",
                    "session",
                    "warn",
                )
            )
            continue
        tile.structure_type = structure_type
        tile.structure_color = structure_color

    for token in session.map_state.observed_tokens:
        tile = tiles_by_id.get(_coerce_int(token.get("tile_id"), -1))
        if tile is None:
            warnings.append(_warning("TOKEN_PATTERN_SUSPICIOUS", "Token references a missing tile.", "session", "warn"))
            continue

        player_id = token.get("player_id")
        token_type = _coerce_token_type(token.get("token_type"))
        if not isinstance(player_id, str) or token_type is None:
            warnings.append(_warning("TOKEN_PATTERN_SUSPICIOUS", "Malformed token entry found.", "session", "warn"))
            continue

        if token_type is TokenType.CUBE:
            tile.cube_tokens.append(player_id)
        else:
            tile.round_tokens.append(player_id)

    snapshot = GameSnapshot(
        board=board,
        turn_order=session.setup.turn_order or session.setup.player_ids,
        bot_player_id=session.setup.bot_player_id,
    )
    return snapshot, warnings


def _serialize_hypothesis_space(space: HypothesisSpace) -> Dict[str, Any]:
    return {
        "players": [
            {
                "player_id": player_space.player_id,
                "possible_clue_ids": list(player_space.possible_clue_ids),
                "candidate_tiles": list(player_space.candidate_tiles),
                "guaranteed_tiles": list(player_space.guaranteed_tiles),
                "eliminated_tiles": list(player_space.eliminated_tiles),
                "is_contradictory": player_space.is_contradictory,
                "is_resolved": player_space.is_resolved,
            }
            for player_space in space.players
        ],
        "global_candidate_tiles": list(space.global_candidate_tiles()),
        "global_guaranteed_tiles": list(space.global_guaranteed_tiles()),
        "unresolved_players": list(space.unresolved_players()),
    }


def _serialize_recommended_move(move: RecommendedMove) -> Dict[str, Any]:
    return {
        "action_type": move.action_type,
        "tile_id": move.tile_id,
        "target_player_id": move.target_player_id,
        "score": move.score,
        "confidence": move.confidence,
        "rationale": move.rationale,
    }


def _warning(code: str, message: str, scope: str, severity: str) -> WarningItem:
    return WarningItem(code=code, message=message, scope=scope, severity=severity)


def _string_tuple(
    value: Any,
    fallback: Tuple[str, ...],
    warnings: List[WarningItem],
    scope: str,
    field_name: str,
) -> Tuple[str, ...]:
    if value is None:
        return fallback
    if not isinstance(value, list):
        warnings.append(_warning("SETUP_FIELD_INVALID", f"{field_name} must be a list of strings.", scope, "error"))
        return fallback
    items = []
    for entry in value:
        if isinstance(entry, str) and entry.strip():
            items.append(entry.strip())
    return tuple(items)


def _optional_string(value: Any, fallback: Optional[str]) -> Optional[str]:
    if value is None:
        return fallback
    if not isinstance(value, str):
        return fallback
    trimmed = value.strip()
    return trimmed or fallback


def _positive_int(value: Any, fallback: int, warnings: List[WarningItem], scope: str, field_name: str) -> int:
    if value is None:
        return fallback
    parsed = _coerce_int(value, fallback)
    if parsed <= 0:
        warnings.append(_warning("VALUE_OUT_OF_RANGE", f"{field_name} must be greater than zero.", scope, "warn"))
        return fallback
    return parsed


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_token_type(value: Any) -> Optional[TokenType]:
    if isinstance(value, TokenType):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        for token_type in TokenType:
            if token_type.value == lowered:
                return token_type
    return None


def _coerce_structure_type(value: Any) -> Optional[StructureType]:
    if isinstance(value, StructureType):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        for structure_type in StructureType:
            if structure_type.value == lowered:
                return structure_type
    return None


def _coerce_structure_color(value: Any) -> Optional[StructureColor]:
    if isinstance(value, StructureColor):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        for structure_color in StructureColor:
            if structure_color.value == lowered:
                return structure_color
    return None

