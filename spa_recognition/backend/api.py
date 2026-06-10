from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from ai.inference import HypothesisSpace, infer_hypothesis_space
from ai.strategy import RecommendedMove, recommend_moves
from data.board_loader import load_layout_instance, load_module_templates, load_slots
from data.clue_loader import load_clue_definitions
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
        if path == "/recalculate":
            return self.post_recalculate(payload)
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
                board = _compose_board_from_placements(ordered_placements)
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
        )
        merged_warnings = merge_warnings(current.warnings, tuple(local_warnings))
        updated = current.with_updates(
            board_layout_state=updated_layout,
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


def _compose_board_from_placements(placements: Iterable[Dict[str, Any]]) -> Board:
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

