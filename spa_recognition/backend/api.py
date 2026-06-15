from __future__ import annotations

from copy import deepcopy
import logging
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ai import CryptidAIEngine, InitialSetup
from ai.events import PlayerResponseEvent
from ai.inference import HypothesisSpace, infer_hypothesis_space
from ai.strategy import RecommendedMove, recommend_moves
from data.board_loader import load_layout_instance, load_module_templates, load_slots
from data.clue_loader import load_clue_definitions
from game_model.clues import clues_by_id
from game_model.map import Board, HexTile
from game_model.state import GameSnapshot
from game_model.types import AnimalTerritory, StructureColor, StructureType, TerrainType, TokenType
from spa_recognition.backend.models import (
    AiState,
    ApiResult,
    BoardLayoutState,
    CluesState,
    MapState,
    SessionState,
    SetupState,
    StructuresState,
    WarningItem,
    merge_warnings,
)
from spa_recognition.backend.session_store import SessionStore


logger = logging.getLogger(__name__)


class SpaRecognitionApi:
    """Permissive API facade for SPA recognition workflows."""

    def __init__(self, session_store: Optional[SessionStore] = None) -> None:
        self._store = session_store or SessionStore()

    def post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        if path == "/catalog":
            return self.post_catalog(payload)
        if path == "/setup":
            return self.post_setup(payload)
        if path == "/board-layout":
            return self.post_board_layout(payload)
        if path == "/map":
            return self.post_map(payload)
        if path == "/structures":
            return self.post_structures(payload)
        if path == "/clues":
            return self.post_clues(payload)
        if path == "/ask-ai":
            return self.post_ask_ai(payload)
        if path == "/ai-answer":
            return self.post_ai_answer(payload)
        if path == "/ai-place-cube":
            return self.post_ai_place_cube(payload)
        if path == "/recalculate":
            return self.post_recalculate(payload)
        if path == "/simulate-observations":
            return self.post_simulate_observations(payload)
        raise ValueError(f"Unknown path: {path}")

    def post_catalog(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        return ApiResult(
            session=current,
            warnings=current.warnings,
            data={
                "board_layout_catalog": _build_board_layout_catalog(),
                "clues_catalog": _build_clues_catalog(),
            },
        )

    def post_setup(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        player_ids = _string_tuple(data.get("player_ids"), current.setup.player_ids, local_warnings, "setup", "player_ids")
        turn_order = _string_tuple(data.get("turn_order"), current.setup.turn_order, local_warnings, "setup", "turn_order")
        bot_player_id = _optional_string(data.get("bot_player_id"), current.setup.bot_player_id)
        bot_clue_id = _optional_string(data.get("bot_clue_id"), current.setup.bot_clue_id)

        clue_definitions = load_clue_definitions()
        valid_clue_ids = {entry.get("clue_id") for entry in clue_definitions if isinstance(entry.get("clue_id"), str)}

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

        if bot_clue_id is not None and bot_clue_id not in valid_clue_ids:
            local_warnings.append(
                _warning(
                    "SETUP_CLUE_UNKNOWN",
                    f"bot_clue_id is not a known clue: {bot_clue_id}",
                    "setup",
                    "warn",
                )
            )

        updated_setup = SetupState(
            player_ids=player_ids,
            turn_order=turn_order,
            bot_player_id=bot_player_id,
            bot_clue_id=bot_clue_id,
        )
        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(setup=updated_setup, phase="board_layout", warnings=merged_warnings)
        self._store.upsert(updated)
        return ApiResult(
            session=updated,
            warnings=merged_warnings,
            data={
                "board_layout_catalog": _build_board_layout_catalog(),
                "clues_catalog": _build_clues_catalog(),
            },
        )

    def post_board_layout(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        raw_layout_mode = data.get("layout_mode", current.board_layout_state.layout_mode)
        layout_mode = "bootstrap" if raw_layout_mode == "bootstrap" else "manual"
        raw_placements = data.get("placements", [])
        if raw_placements is None:
            raw_placements = []
        if not isinstance(raw_placements, list):
            local_warnings.append(_warning("BOARD_LAYOUT_INVALID", "placements must be a list.", "board_layout", "error"))
            raw_placements = []

        templates = load_module_templates()
        slots = load_slots()
        valid_orientations = {"normal", "flipped"}
        placements_by_slot: Dict[int, Dict[str, Any]] = {}
        used_sections = set()

        for entry in raw_placements:
            if not isinstance(entry, dict):
                local_warnings.append(
                    _warning("BOARD_LAYOUT_ENTRY_INVALID", "Each placement must be an object.", "board_layout", "warn")
                )
                continue

            slot_id = _coerce_int(entry.get("slot_id"), -1)
            section_id = entry.get("section_id")
            orientation = entry.get("orientation")

            if slot_id not in slots:
                local_warnings.append(
                    _warning("BOARD_LAYOUT_UNKNOWN_SLOT", f"Unknown slot_id: {slot_id}", "board_layout", "warn")
                )
                continue
            if not isinstance(section_id, str) or section_id not in templates:
                local_warnings.append(
                    _warning(
                        "BOARD_LAYOUT_UNKNOWN_SECTION",
                        f"Unknown section_id for slot {slot_id}: {section_id}",
                        "board_layout",
                        "warn",
                    )
                )
                continue
            if not isinstance(orientation, str) or orientation not in valid_orientations:
                local_warnings.append(
                    _warning(
                        "BOARD_LAYOUT_UNKNOWN_ORIENTATION",
                        f"Unknown orientation for slot {slot_id}: {orientation}",
                        "board_layout",
                        "warn",
                    )
                )
                continue
            if slot_id in placements_by_slot:
                local_warnings.append(
                    _warning(
                        "BOARD_LAYOUT_DUPLICATE_SLOT",
                        f"Duplicate slot placement detected: {slot_id}",
                        "board_layout",
                        "warn",
                    )
                )
                continue
            if section_id in used_sections:
                local_warnings.append(
                    _warning(
                        "BOARD_LAYOUT_DUPLICATE_SECTION",
                        f"Duplicate section placement detected: {section_id}",
                        "board_layout",
                        "warn",
                    )
                )
                continue

            placements_by_slot[slot_id] = {
                "slot_id": slot_id,
                "section_id": section_id,
                "orientation": orientation,
            }
            used_sections.add(section_id)

        ordered_placements = tuple(placements_by_slot[slot_id] for slot_id in sorted(placements_by_slot))
        is_complete = len(ordered_placements) == len(slots) and len(used_sections) == len(templates)

        board_tiles: Tuple[Dict[str, Any], ...] = current.board_layout_state.board_tiles
        board_cols = current.board_layout_state.cols
        board_rows = current.board_layout_state.rows

        if not is_complete:
            local_warnings.append(
                _warning(
                    "BOARD_LAYOUT_INCOMPLETE",
                    f"Board layout is incomplete: configured {len(ordered_placements)} of {len(slots)} slots.",
                    "board_layout",
                    "warn",
                )
            )
        else:
            try:
                board = _compose_board_from_placements(
                    ordered_placements,
                    include_structure_markers=layout_mode == "bootstrap",
                )
                board_tiles = tuple(_serialize_board_tile(tile) for tile in _sorted_tiles(board))
                board_cols, board_rows = board.bounds()
            except Exception as exc:  # pragma: no cover - defensive fallback
                local_warnings.append(
                    _warning(
                        "BOARD_LAYOUT_BUILD_FAILED",
                        f"Board layout composition failed: {exc}",
                        "board_layout",
                        "error",
                    )
                )

        updated_layout = BoardLayoutState(
            placements=ordered_placements,
            board_tiles=board_tiles,
            cols=board_cols,
            rows=board_rows,
            is_complete=is_complete and bool(board_tiles),
            layout_mode=layout_mode,
        )
        reset_structures_state = StructuresState(by_tile_id={})
        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(
            board_layout_state=updated_layout,
            structures_state=reset_structures_state,
            phase="map" if updated_layout.is_complete else "board_layout",
            warnings=merged_warnings,
        )
        self._store.upsert(updated)
        return ApiResult(
            session=updated,
            warnings=merged_warnings,
            data={
                "board_layout_catalog": _build_board_layout_catalog(),
                "board_tiles": [dict(tile) for tile in updated_layout.board_tiles],
            },
        )

    def post_map(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        board_tile_count = len(current.board_layout_state.board_tiles)
        if board_tile_count > 0:
            cols = current.board_layout_state.cols
            rows = current.board_layout_state.rows
            max_tile_id = board_tile_count - 1
        else:
            cols = _positive_int(data.get("cols"), current.map_state.cols, local_warnings, "map", "cols")
            rows = _positive_int(data.get("rows"), current.map_state.rows, local_warnings, "map", "rows")
            max_tile_id = (cols * rows) - 1

        observed_tokens_by_tile_player: Dict[Tuple[int, str], Dict[str, Any]] = {}
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

            normalized_player_id = player_id.strip()
            observed_tokens_by_tile_player[(tile_id, normalized_player_id)] = {
                "tile_id": tile_id,
                "player_id": normalized_player_id,
                "token_type": token_type.value,
            }

        observed_tokens = list(observed_tokens_by_tile_player.values())

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
        if current.board_layout_state.layout_mode == "bootstrap":
            local_warnings.append(
                _warning(
                    "STRUCTURES_LOCKED",
                    "Structure editing is disabled for bootstrap layout mode.",
                    "structures",
                    "warn",
                )
            )
            merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
            updated = current.with_updates(warnings=merged_warnings)
            self._store.upsert(updated)
            return ApiResult(session=updated, warnings=merged_warnings)

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

            if entry.get("remove") is True:
                next_map[tile_id] = {
                    "structure_type": None,
                    "structure_color": None,
                }
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

    def post_ask_ai(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        tile_id = _coerce_int(data.get("tile_id"), -1)
        if tile_id < 0:
            local_warnings.append(_warning("AI_TILE_INVALID", "tile_id must be valid.", "recalculate", "warn"))

        player_id = _optional_string(data.get("player_id"), None)
        if player_id is None:
            local_warnings.append(_warning("AI_PLAYER_MISSING", "player_id is required.", "recalculate", "warn"))

        logger.info(
            "[AI][ask] input session_id=%s tile_id=%s player_id=%s observed_tokens=%s structures=%s",
            session_id,
            tile_id,
            player_id,
            len(current.map_state.observed_tokens),
            len(current.structures_state.by_tile_id),
        )

        snapshot, adapter_warnings = _build_snapshot_from_session(current)
        local_warnings.extend(adapter_warnings)
        logger.debug("[AI][ask] snapshot=%s", _snapshot_debug_summary(snapshot))

        token_type = TokenType.CUBE
        rationale = "No candidate matched; cube placed as a conservative answer."
        updated_map = current.map_state
        if tile_id >= 0 and player_id is not None:
            try:
                if player_id == current.setup.bot_player_id:
                    engine = _build_engine_from_session(current)
                    response = engine.answer_for_tile(tile_id=tile_id)
                    token_type = TokenType.ROUND if response.answered_yes else TokenType.CUBE
                    rationale = response.rationale or rationale
                else:
                    hypothesis_space = infer_hypothesis_space(snapshot=snapshot)
                    logger.debug("[AI][ask] hypothesis=%s", _hypothesis_debug_summary(hypothesis_space))
                    if tile_id in set(hypothesis_space.global_candidate_tiles()):
                        token_type = TokenType.ROUND
                        rationale = "Tile is compatible with the current hypothesis space; round placed."
                    else:
                        rationale = "Tile is not compatible with the current hypothesis space; cube placed."

                updated_map = _upsert_token(
                    map_state=current.map_state,
                    tile_id=tile_id,
                    player_id=player_id,
                    token_type=token_type,
                )
            except Exception as exc:  # pragma: no cover - defensive fallback
                local_warnings.append(
                    _warning(
                        "AI_RECALCULATE_FAILED",
                        f"AI evaluation failed: {exc}",
                        "recalculate",
                        "error",
                    )
                )

        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(map_state=updated_map, phase=current.phase, warnings=merged_warnings)
        self._store.upsert(updated)
        logger.info(
            "[AI][ask] output tile_id=%s player_id=%s token_type=%s warnings=%s",
            tile_id,
            player_id,
            token_type.value,
            len(local_warnings),
        )
        return ApiResult(
            session=updated,
            warnings=merged_warnings,
            data={
                "tile_id": tile_id,
                "player_id": player_id,
                "token_type": token_type.value,
                "rationale": rationale,
            },
        )

    def post_ai_answer(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        tile_id = _coerce_int(data.get("tile_id"), -1)
        if tile_id < 0:
            local_warnings.append(_warning("AI_TILE_INVALID", "tile_id must be valid.", "recalculate", "warn"))

        try:
            engine = _build_engine_from_session(current)
            response = engine.answer_for_tile(tile_id=tile_id)
            updated_map = _upsert_token(
                map_state=current.map_state,
                tile_id=response.tile_id,
                player_id=current.setup.bot_player_id,
                token_type=TokenType.ROUND if response.answered_yes else TokenType.CUBE,
            )
            rationale = response.rationale
            token_type = TokenType.ROUND if response.answered_yes else TokenType.CUBE
        except Exception as exc:  # pragma: no cover - defensive fallback
            local_warnings.append(
                _warning(
                    "AI_RECALCULATE_FAILED",
                    f"AI evaluation failed: {exc}",
                    "recalculate",
                    "error",
                )
            )
            updated_map = current.map_state
            rationale = None
            token_type = None

        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(map_state=updated_map, phase=current.phase, warnings=merged_warnings)
        self._store.upsert(updated)
        return ApiResult(
            session=updated,
            warnings=merged_warnings,
            data={
                "tile_id": tile_id,
                "player_id": current.setup.bot_player_id,
                "token_type": token_type.value if token_type is not None else None,
                "rationale": rationale,
            },
        )

    def post_ai_place_cube(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        try:
            engine = _build_engine_from_session(current)
            placement = engine.place_least_informative_cube()
            updated_map = _upsert_token(
                map_state=current.map_state,
                tile_id=placement.tile_id,
                player_id=current.setup.bot_player_id,
                token_type=TokenType.CUBE,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            local_warnings.append(
                _warning(
                    "AI_RECALCULATE_FAILED",
                    f"AI cube placement failed: {exc}",
                    "recalculate",
                    "error",
                )
            )
            updated_map = current.map_state
            placement = None

        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(map_state=updated_map, phase=current.phase, warnings=merged_warnings)
        self._store.upsert(updated)
        return ApiResult(
            session=updated,
            warnings=merged_warnings,
            data={
                "tile_id": placement.tile_id if placement is not None else None,
                "player_id": current.setup.bot_player_id,
                "token_type": TokenType.CUBE.value if placement is not None else None,
                "score": placement.score if placement is not None else None,
                "rationale": placement.rationale if placement is not None else None,
            },
        )

    def post_recalculate(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        top_k = _positive_int(data.get("top_k"), 5, local_warnings, "recalculate", "top_k")

        logger.info(
            "[AI][recalculate] input session_id=%s top_k=%s observed_tokens=%s structures=%s",
            session_id,
            top_k,
            len(current.map_state.observed_tokens),
            len(current.structures_state.by_tile_id),
        )

        snapshot, adapter_warnings = _build_snapshot_from_session(current)
        local_warnings.extend(adapter_warnings)
        logger.debug("[AI][recalculate] snapshot=%s", _snapshot_debug_summary(snapshot))

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
            logger.debug("[AI][recalculate] hypothesis=%s", _hypothesis_debug_summary(hypothesis_space))
            logger.debug("[AI][recalculate] moves=%s", _moves_debug_summary(moves))
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
        logger.info(
            "[AI][recalculate] output recommended_moves=%s warnings=%s",
            len(ai_state.recommended_moves_raw),
            len(local_warnings),
        )

        return ApiResult(
            session=updated,
            warnings=merged_warnings,
            data={
                "hypothesis_space": ai_state.hypothesis_space_raw,
                "recommended_moves": [dict(move) for move in ai_state.recommended_moves_raw],
                "ui_payload": dict(ai_state.ui_payload),
            },
        )

    def post_simulate_observations(self, payload: Optional[Dict[str, Any]] = None) -> ApiResult:
        data = payload or {}
        session_id = str(data.get("session_id", "default"))
        current = self._store.create_or_get(session_id)

        local_warnings: List[WarningItem] = []
        board, board_warnings = _board_from_session(current)
        local_warnings.extend(board_warnings)

        raw_player_clues = data.get("player_clues", [])
        if not isinstance(raw_player_clues, list):
            local_warnings.append(_warning("SIMULATION_PLAYER_CLUES_INVALID", "player_clues must be a list.", "simulation", "error"))
            raw_player_clues = []

        player_clues: List[Tuple[str, str]] = []
        for entry in raw_player_clues:
            if not isinstance(entry, dict):
                local_warnings.append(_warning("SIMULATION_PLAYER_CLUE_ENTRY_INVALID", "Each player_clues entry must be an object.", "simulation", "warn"))
                continue
            player_id = _optional_string(entry.get("player_id"), None)
            clue_id = _optional_string(entry.get("clue_id"), None)
            if player_id is None or clue_id is None:
                local_warnings.append(_warning("SIMULATION_PLAYER_CLUE_MISSING", "Each player_clues entry must include player_id and clue_id.", "simulation", "warn"))
                continue
            player_clues.append((player_id, clue_id))

        observation_count = max(0, _coerce_int(data.get("observation_count"), 0))
        include_bot_observations = bool(data.get("include_bot_observations", False))
        ensure_player_polarity_coverage = bool(data.get("ensure_player_polarity_coverage", True))
        distribution_mode = str(data.get("distribution_mode", "random")).strip().lower()
        if distribution_mode not in {"random", "equal_per_player"}:
            local_warnings.append(_warning("SIMULATION_DISTRIBUTION_INVALID", "distribution_mode must be random or equal_per_player.", "simulation", "warn"))
            distribution_mode = "random"

        explicit_seed = data.get("seed")
        if explicit_seed is None:
            seed = random.SystemRandom().randrange(0, 2**32)
        else:
            seed = _coerce_int(explicit_seed, random.SystemRandom().randrange(0, 2**32))

        generated_tokens, simulation_warnings = _generate_simulated_tokens(
            board=board,
            player_clues=player_clues,
            bot_player_id=current.setup.bot_player_id,
            include_bot_observations=include_bot_observations,
            observation_count=observation_count,
            ensure_player_polarity_coverage=ensure_player_polarity_coverage,
            distribution_mode=distribution_mode,
            seed=seed,
        )
        local_warnings.extend(simulation_warnings)

        updated_map = MapState(
            cols=current.map_state.cols,
            rows=current.map_state.rows,
            observed_tokens=tuple(generated_tokens),
        )
        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(map_state=updated_map, phase=current.phase, warnings=merged_warnings)
        self._store.upsert(updated)
        return ApiResult(
            session=updated,
            warnings=merged_warnings,
            data={
                "used_seed": seed,
                "generated_count": len(generated_tokens),
            },
        )


def _build_snapshot_from_session(session: SessionState) -> Tuple[GameSnapshot, List[WarningItem]]:
    warnings: List[WarningItem] = []
    if session.board_layout_state.board_tiles:
        board = _deserialize_board_tiles(session.board_layout_state.board_tiles)
    else:
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
        structure_type_value = structure.get("structure_type")
        structure_color_value = structure.get("structure_color")
        if structure_type_value is None and structure_color_value is None:
            tile.structure_type = None
            tile.structure_color = None
            continue

        structure_type = _coerce_structure_type(structure_type_value)
        structure_color = _coerce_structure_color(structure_color_value)
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


def _board_from_session(session: SessionState) -> Tuple[Board, List[WarningItem]]:
    snapshot, warnings = _build_snapshot_from_session(session)
    return deepcopy(snapshot.board), warnings


def _generate_simulated_tokens(
    board: Board,
    player_clues: Sequence[Tuple[str, str]],
    bot_player_id: Optional[str],
    include_bot_observations: bool,
    observation_count: int,
    ensure_player_polarity_coverage: bool,
    distribution_mode: str,
    seed: int,
) -> Tuple[List[Dict[str, Any]], List[WarningItem]]:
    warnings: List[WarningItem] = []
    clue_catalog = clues_by_id(include_inverse=False)
    rng = random.Random(seed)

    normalized_players = []
    seen_players = set()
    for player_id, clue_id in player_clues:
        if player_id in seen_players:
            continue
        seen_players.add(player_id)
        if not include_bot_observations and bot_player_id is not None and player_id == bot_player_id:
            continue
        if clue_id not in clue_catalog:
            warnings.append(_warning("SIMULATION_CLUE_UNKNOWN", f"Unknown clue_id for player {player_id}: {clue_id}", "simulation", "warn"))
            continue
        normalized_players.append((player_id, clue_catalog[clue_id]))

    if not normalized_players or observation_count <= 0:
        return [], warnings

    candidates_by_player: Dict[str, List[Tuple[int, bool]]] = {}
    by_player_and_polarity: Dict[Tuple[str, bool], List[Tuple[int, bool]]] = {}
    for player_id, clue in normalized_players:
        matches_for_player: List[Tuple[int, bool]] = []
        for tile in sorted(board.tiles.values(), key=lambda item: item.tile_id):
            answered_yes = clue.matches(tile, board)
            item = (tile.tile_id, answered_yes)
            matches_for_player.append(item)
            by_player_and_polarity.setdefault((player_id, answered_yes), []).append(item)
        candidates_by_player[player_id] = matches_for_player

    max_available = sum(len(items) for items in candidates_by_player.values())
    target_count = min(max_available, observation_count)

    selected: List[Tuple[str, int, bool]] = []
    selected_keys = set()
    player_ids = [player_id for player_id, _ in normalized_players]

    if distribution_mode == "equal_per_player":
        base_quota = target_count // len(player_ids)
        remainder = target_count % len(player_ids)
        shuffled_players = player_ids[:]
        rng.shuffle(shuffled_players)
        extra_players = set(shuffled_players[:remainder])
        for player_id in player_ids:
            quota = base_quota + (1 if player_id in extra_players else 0)
            _select_player_samples(
                rng=rng,
                player_id=player_id,
                quota=quota,
                selected=selected,
                selected_keys=selected_keys,
                by_player_and_polarity=by_player_and_polarity,
                candidates_by_player=candidates_by_player,
                ensure_player_polarity_coverage=ensure_player_polarity_coverage,
            )
    else:
        if ensure_player_polarity_coverage:
            for player_id in player_ids:
                for polarity in [True, False]:
                    if len(selected) >= target_count:
                        break
                    candidates = [
                        sample
                        for sample in by_player_and_polarity.get((player_id, polarity), [])
                        if (player_id, sample[0]) not in selected_keys
                    ]
                    if not candidates:
                        continue
                    tile_id, answered_yes = rng.choice(candidates)
                    selected.append((player_id, tile_id, answered_yes))
                    selected_keys.add((player_id, tile_id))
        remaining = []
        for player_id in player_ids:
            for tile_id, answered_yes in candidates_by_player.get(player_id, []):
                if (player_id, tile_id) in selected_keys:
                    continue
                remaining.append((player_id, tile_id, answered_yes))
        rng.shuffle(remaining)
        for player_id, tile_id, answered_yes in remaining:
            if len(selected) >= target_count:
                break
            selected.append((player_id, tile_id, answered_yes))

    normalized_tokens = [
        {
            "tile_id": tile_id,
            "player_id": player_id,
            "token_type": TokenType.ROUND.value if answered_yes else TokenType.CUBE.value,
        }
        for player_id, tile_id, answered_yes in selected[:target_count]
    ]
    return normalized_tokens, warnings


def _select_player_samples(
    rng: random.Random,
    player_id: str,
    quota: int,
    selected: List[Tuple[str, int, bool]],
    selected_keys: set,
    by_player_and_polarity: Dict[Tuple[str, bool], List[Tuple[int, bool]]],
    candidates_by_player: Dict[str, List[Tuple[int, bool]]],
    ensure_player_polarity_coverage: bool,
) -> None:
    if quota <= 0:
        return

    if ensure_player_polarity_coverage:
        for polarity in [True, False]:
            if sum(1 for current in selected if current[0] == player_id) >= quota:
                break
            candidates = [
                sample
                for sample in by_player_and_polarity.get((player_id, polarity), [])
                if (player_id, sample[0]) not in selected_keys
            ]
            if not candidates:
                continue
            tile_id, answered_yes = rng.choice(candidates)
            selected.append((player_id, tile_id, answered_yes))
            selected_keys.add((player_id, tile_id))

    remaining = [
        (tile_id, answered_yes)
        for tile_id, answered_yes in candidates_by_player.get(player_id, [])
        if (player_id, tile_id) not in selected_keys
    ]
    rng.shuffle(remaining)
    for tile_id, answered_yes in remaining:
        if sum(1 for current in selected if current[0] == player_id) >= quota:
            break
        selected.append((player_id, tile_id, answered_yes))
        selected_keys.add((player_id, tile_id))


def _build_engine_from_session(session: SessionState) -> CryptidAIEngine:
    snapshot, _warnings = _build_snapshot_from_session(session)
    if session.setup.bot_player_id is None:
        raise ValueError("bot_player_id is required to build the AI engine.")
    if session.setup.bot_clue_id is None:
        raise ValueError("bot_clue_id is required to build the AI engine.")

    engine = CryptidAIEngine.from_initial_setup(
        InitialSetup(
            board=deepcopy(snapshot.board),
            turn_order=snapshot.turn_order,
            bot_player_id=session.setup.bot_player_id,
            bot_clue_id=session.setup.bot_clue_id,
            include_inverse_clues=False,
        )
    )

    for token in session.map_state.observed_tokens:
        player_id = token.get("player_id")
        tile_id = _coerce_int(token.get("tile_id"), -1)
        token_type = _coerce_token_type(token.get("token_type"))
        if not isinstance(player_id, str) or tile_id < 0 or token_type is None:
            continue
        engine.apply_observation(
            PlayerResponseEvent(
                player_id=player_id,
                tile_id=tile_id,
                answered_yes=token_type is TokenType.ROUND,
            )
        )
    return engine


def _upsert_token(map_state: MapState, tile_id: int, player_id: Optional[str], token_type: TokenType) -> MapState:
    if not isinstance(player_id, str) or not player_id.strip():
        return map_state

    normalized_player_id = player_id.strip()
    filtered_tokens = [
        token
        for token in map_state.observed_tokens
        if not (
            _coerce_int(token.get("tile_id"), -1) == tile_id
            and _optional_string(token.get("player_id"), None) == normalized_player_id
        )
    ]
    filtered_tokens.append(
        {
            "tile_id": tile_id,
            "player_id": normalized_player_id,
            "token_type": token_type.value,
        }
    )
    return MapState(
        cols=map_state.cols,
        rows=map_state.rows,
        observed_tokens=tuple(filtered_tokens),
    )


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


def _snapshot_debug_summary(snapshot: GameSnapshot) -> Dict[str, Any]:
    round_count = 0
    cube_count = 0
    structure_count = 0
    for tile in snapshot.board.tiles.values():
        round_count += len(tile.round_tokens)
        cube_count += len(tile.cube_tokens)
        if tile.structure_type is not None and tile.structure_color is not None:
            structure_count += 1
    return {
        "tiles": len(snapshot.board.tiles),
        "players": list(snapshot.player_ids()),
        "turn_order": list(snapshot.turn_order),
        "bot_player_id": snapshot.bot_player_id,
        "round_tokens": round_count,
        "cube_tokens": cube_count,
        "structures": structure_count,
    }


def _hypothesis_debug_summary(space: HypothesisSpace) -> Dict[str, Any]:
    return {
        "players": len(space.players),
        "unresolved_players": list(space.unresolved_players()),
        "global_candidate_tiles": len(space.global_candidate_tiles()),
        "global_guaranteed_tiles": len(space.global_guaranteed_tiles()),
        "possible_clues_by_player": {
            player_space.player_id: len(player_space.possible_clue_ids)
            for player_space in space.players
        },
    }


def _moves_debug_summary(moves: Sequence[RecommendedMove]) -> List[Dict[str, Any]]:
    return [
        {
            "action_type": move.action_type,
            "tile_id": move.tile_id,
            "target_player_id": move.target_player_id,
            "score": move.score,
            "confidence": move.confidence,
        }
        for move in moves[:3]
    ]


def _warning(code: str, message: str, scope: str, severity: str) -> WarningItem:
    return WarningItem(code=code, message=message, scope=scope, severity=severity)


def _build_board_layout_catalog() -> Dict[str, Any]:
    slots = load_slots()
    templates = load_module_templates()
    return {
        "slots": [{"slot_id": slot_id, **slot} for slot_id, slot in sorted(slots.items())],
        "sections": sorted(templates.keys()),
        "orientations": ["normal", "flipped"],
        "default_layout": load_layout_instance()["placements"],
    }


def _build_clues_catalog() -> List[Dict[str, str]]:
    clues = []
    for definition in load_clue_definitions():
        clue_id = definition.get("clue_id")
        text = definition.get("text")
        if not isinstance(clue_id, str) or not isinstance(text, str):
            continue
        clues.append({"clue_id": clue_id, "text": text})
    return clues


def _compose_board_from_placements(
    placements: Iterable[Dict[str, Any]],
    include_structure_markers: bool = True,
) -> Board:
    templates = load_module_templates()
    slots = load_slots()
    layout_instance = load_layout_instance()
    structure_markers = layout_instance.get("structure_markers", [])

    tiles = {}
    tile_id = 0
    section_local_index: Dict[Tuple[str, int], HexTile] = {}

    for placement in placements:
        slot_id = int(placement["slot_id"])
        section_id = str(placement["section_id"])
        orientation = str(placement["orientation"])

        slot_origin = slots[slot_id]
        section_tiles = templates[section_id][orientation]

        for local_id, tile_data in section_tiles.items():
            q = slot_origin["origin_q"] + tile_data["q"]
            r = slot_origin["origin_r"] + tile_data["r"]
            coord = (q, r)
            if coord in tiles:
                raise ValueError(f"Overlapping coordinate in composed board: {coord}")

            tile = HexTile(
                tile_id=tile_id,
                q=q,
                r=r,
                terrain=tile_data["terrain"],
                animal=tile_data["animal"],
                structure_type=None,
                structure_color=None,
                section_id=section_id,
                local_id=local_id,
            )
            tiles[coord] = tile
            section_local_index[(section_id, local_id)] = tile
            tile_id += 1

    if include_structure_markers:
        for marker in structure_markers:
            key = (marker["section_id"], marker["local_id"])
            tile = section_local_index.get(key)
            if tile is None:
                continue
            tile.structure_type = marker["structure_type"]
            tile.structure_color = marker["structure_color"]

    return Board(tiles=tiles)


def _sorted_tiles(board: Board) -> List[HexTile]:
    return sorted(board.tiles.values(), key=lambda tile: tile.tile_id)


def _serialize_board_tile(tile: HexTile) -> Dict[str, Any]:
    return {
        "tile_id": tile.tile_id,
        "q": tile.q,
        "r": tile.r,
        "terrain": tile.terrain.value,
        "animal": tile.animal.value if tile.animal is not None else None,
        "structure_type": tile.structure_type.value if tile.structure_type is not None else None,
        "structure_color": tile.structure_color.value if tile.structure_color is not None else None,
        "section_id": tile.section_id,
        "local_id": tile.local_id,
    }


def _deserialize_board_tiles(raw_tiles: Iterable[Dict[str, Any]]) -> Board:
    tiles = {}
    for entry in raw_tiles:
        terrain_value = entry.get("terrain")
        animal_value = entry.get("animal")
        structure_type_value = entry.get("structure_type")
        structure_color_value = entry.get("structure_color")
        tile = HexTile(
            tile_id=_coerce_int(entry.get("tile_id"), -1),
            q=_coerce_int(entry.get("q"), 0),
            r=_coerce_int(entry.get("r"), 0),
            terrain=TerrainType(terrain_value) if isinstance(terrain_value, str) else TerrainType.UNKNOWN,
            animal=AnimalTerritory(animal_value) if isinstance(animal_value, str) and animal_value else None,
            structure_type=StructureType(structure_type_value) if isinstance(structure_type_value, str) and structure_type_value else None,
            structure_color=StructureColor(structure_color_value) if isinstance(structure_color_value, str) and structure_color_value else None,
            section_id=entry.get("section_id"),
            local_id=_coerce_int(entry.get("local_id"), 0) or None,
        )
        tiles[(tile.q, tile.r)] = tile
    return Board(tiles=tiles)


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

