from __future__ import annotations

import json
import random
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ai.engine import CryptidAIEngine
from ai.events import PlayerResponseEvent
from ai.inference import infer_hypothesis_space
from ai.strategy import RecommendedMove, recommend_moves
from ai.types import AIDebugState, AIMove, InitialSetup
from data.board_loader import load_default_board, load_layout_instance, load_module_templates, load_slots
from game_model.clues import Clue, clues_by_id
from game_model.map import Board, HexTile
from game_model.state import GameSnapshot
from game_model.types import AnimalTerritory, StructureColor, StructureType, TerrainType


@dataclass(slots=True, frozen=True)
class ScenarioPlayer:
    player_id: str
    clue_id: str


@dataclass(slots=True, frozen=True)
class ScenarioSimulationConfig:
    seed: int = 0
    observation_count: int = 8
    include_bot_observations: bool = False
    ensure_player_polarity_coverage: bool = True


@dataclass(slots=True, frozen=True)
class ScenarioEvaluationConfig:
    top_k: int = 5


@dataclass(slots=True, frozen=True)
class ScenarioBoardSpec:
    kind: str
    placements: Tuple[Dict[str, Any], ...] = ()
    structures: Tuple[Dict[str, Any], ...] = ()
    include_structure_markers: bool = True
    tile_overrides: Tuple[Dict[str, Any], ...] = ()


@dataclass(slots=True, frozen=True)
class ScenarioDefinition:
    scenario_id: str
    description: str
    board: ScenarioBoardSpec
    players: Tuple[ScenarioPlayer, ...]
    turn_order: Tuple[str, ...]
    bot_player_id: str
    include_inverse_clues: bool = False
    simulation: ScenarioSimulationConfig = ScenarioSimulationConfig()
    evaluation: ScenarioEvaluationConfig = ScenarioEvaluationConfig()


@dataclass(slots=True, frozen=True)
class SyntheticObservation:
    player_id: str
    tile_id: int
    answered_yes: bool
    clue_id: str


@dataclass(slots=True, frozen=True)
class RecommendedMoveTruth:
    action_type: str
    tile_id: int
    target_player_id: Optional[str]
    truth_answer: Optional[bool]
    blocking_players: Tuple[str, ...]
    matches_all_true_clues: bool


@dataclass(slots=True, frozen=True)
class ScenarioEvaluationResult:
    scenario: ScenarioDefinition
    used_seed: int
    used_observation_count: int
    used_top_k: int
    snapshot: GameSnapshot
    observations: Tuple[SyntheticObservation, ...]
    ground_truth_candidate_tiles: Tuple[int, ...]
    debug_state: AIDebugState
    next_move: Optional[AIMove]
    recommended_moves: Tuple[RecommendedMove, ...]
    true_clue_retained_by_player: Tuple[Tuple[str, bool], ...]
    recommended_move_truths: Tuple[RecommendedMoveTruth, ...]


def load_scenario_definition(path: str | Path) -> ScenarioDefinition:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return scenario_definition_from_dict(payload)


def scenario_definition_from_dict(payload: Dict[str, Any]) -> ScenarioDefinition:
    scenario_id = str(payload.get("scenario_id", "unnamed-scenario")).strip() or "unnamed-scenario"
    description = str(payload.get("description", "")).strip()

    raw_players = payload.get("players", [])
    if not isinstance(raw_players, list) or not raw_players:
        raise ValueError("Scenario must define a non-empty players list.")

    players: List[ScenarioPlayer] = []
    seen_player_ids = set()
    for raw_player in raw_players:
        if not isinstance(raw_player, dict):
            raise ValueError("Each player entry must be an object.")
        player_id = str(raw_player.get("player_id", "")).strip()
        clue_id = str(raw_player.get("clue_id", "")).strip()
        if not player_id or not clue_id:
            raise ValueError("Each player entry must include player_id and clue_id.")
        if player_id in seen_player_ids:
            raise ValueError(f"Duplicate player_id in scenario: {player_id}")
        players.append(ScenarioPlayer(player_id=player_id, clue_id=clue_id))
        seen_player_ids.add(player_id)

    turn_order_raw = payload.get("turn_order") or [player.player_id for player in players]
    if not isinstance(turn_order_raw, list) or not turn_order_raw:
        raise ValueError("turn_order must be a non-empty list.")
    turn_order = tuple(str(player_id).strip() for player_id in turn_order_raw if str(player_id).strip())
    if set(turn_order) != {player.player_id for player in players}:
        raise ValueError("turn_order must contain every player exactly once.")

    bot_player_id = str(payload.get("bot_player_id", "")).strip()
    if not bot_player_id:
        raise ValueError("bot_player_id is required.")
    if bot_player_id not in seen_player_ids:
        raise ValueError("bot_player_id must be present in players.")

    board_payload = payload.get("board", {})
    board = _scenario_board_from_dict(board_payload)

    simulation_payload = payload.get("simulation", {})
    if not isinstance(simulation_payload, dict):
        raise ValueError("simulation must be an object if provided.")
    simulation = ScenarioSimulationConfig(
        seed=int(simulation_payload.get("seed", 0)),
        observation_count=max(0, int(simulation_payload.get("observation_count", 8))),
        include_bot_observations=bool(simulation_payload.get("include_bot_observations", False)),
        ensure_player_polarity_coverage=bool(simulation_payload.get("ensure_player_polarity_coverage", True)),
    )

    evaluation_payload = payload.get("evaluation", {})
    if not isinstance(evaluation_payload, dict):
        raise ValueError("evaluation must be an object if provided.")
    evaluation = ScenarioEvaluationConfig(
        top_k=max(1, int(evaluation_payload.get("top_k", 5))),
    )

    include_inverse_clues = bool(payload.get("include_inverse_clues", False))
    _validate_clue_ids(players=players, include_inverse_clues=include_inverse_clues)

    return ScenarioDefinition(
        scenario_id=scenario_id,
        description=description,
        board=board,
        players=tuple(players),
        turn_order=turn_order,
        bot_player_id=bot_player_id,
        include_inverse_clues=include_inverse_clues,
        simulation=simulation,
        evaluation=evaluation,
    )


def generate_synthetic_observations(
    scenario: ScenarioDefinition,
    seed: Optional[int] = None,
    observation_count: Optional[int] = None,
) -> Tuple[SyntheticObservation, ...]:
    rng = random.Random(scenario.simulation.seed if seed is None else seed)
    board = build_board_for_scenario(scenario.board)
    clue_catalog = clues_by_id(include_inverse=scenario.include_inverse_clues)
    active_players = [player for player in scenario.players if scenario.simulation.include_bot_observations or player.player_id != scenario.bot_player_id]

    candidate_pool: List[SyntheticObservation] = []
    by_player_and_polarity: Dict[Tuple[str, bool], List[SyntheticObservation]] = {}
    for player in active_players:
        clue = clue_catalog[player.clue_id]
        for tile in sorted(board.tiles.values(), key=lambda current_tile: current_tile.tile_id):
            answered_yes = clue.matches(tile, board)
            observation = SyntheticObservation(
                player_id=player.player_id,
                tile_id=tile.tile_id,
                answered_yes=answered_yes,
                clue_id=player.clue_id,
            )
            candidate_pool.append(observation)
            by_player_and_polarity.setdefault((player.player_id, answered_yes), []).append(observation)

    target_count = min(
        len(candidate_pool),
        scenario.simulation.observation_count if observation_count is None else max(0, observation_count),
    )
    if target_count == 0:
        return ()

    selected: List[SyntheticObservation] = []
    selected_keys = set()

    if scenario.simulation.ensure_player_polarity_coverage:
        coverage_candidates: List[Tuple[str, bool]] = []
        for player in active_players:
            if by_player_and_polarity.get((player.player_id, True)):
                coverage_candidates.append((player.player_id, True))
            if by_player_and_polarity.get((player.player_id, False)):
                coverage_candidates.append((player.player_id, False))
        rng.shuffle(coverage_candidates)

        for player_id, polarity in coverage_candidates:
            if len(selected) >= target_count:
                break
            available = [
                observation
                for observation in by_player_and_polarity.get((player_id, polarity), [])
                if (observation.player_id, observation.tile_id) not in selected_keys
            ]
            if not available:
                continue
            chosen = rng.choice(available)
            selected.append(chosen)
            selected_keys.add((chosen.player_id, chosen.tile_id))

    remaining = [
        observation
        for observation in candidate_pool
        if (observation.player_id, observation.tile_id) not in selected_keys
    ]
    rng.shuffle(remaining)
    for observation in remaining:
        if len(selected) >= target_count:
            break
        selected.append(observation)

    return tuple(selected)


def build_board_for_scenario(board_spec: ScenarioBoardSpec) -> Board:
    if board_spec.kind == "default_layout":
        board = load_default_board()
    elif board_spec.kind == "placements":
        if not board_spec.placements:
            raise ValueError("placements board requires at least one placement.")
        board = _compose_board_from_placements(
            board_spec.placements,
            include_structure_markers=board_spec.include_structure_markers,
        )
    else:
        raise ValueError(f"Unsupported board kind: {board_spec.kind}")

    _apply_tile_overrides(board, board_spec.tile_overrides)
    if board_spec.structures:
        _apply_structures(board, board_spec.structures)
    return board


def evaluate_scenario(
    scenario: ScenarioDefinition,
    seed: Optional[int] = None,
    observation_count: Optional[int] = None,
    top_k: Optional[int] = None,
) -> ScenarioEvaluationResult:
    effective_seed = scenario.simulation.seed if seed is None else seed
    effective_observation_count = scenario.simulation.observation_count if observation_count is None else max(0, observation_count)
    effective_top_k = scenario.evaluation.top_k if top_k is None else max(1, top_k)
    board = build_board_for_scenario(scenario.board)
    observations = generate_synthetic_observations(
        scenario=scenario,
        seed=effective_seed,
        observation_count=effective_observation_count,
    )
    snapshot = _snapshot_from_observations(board=board, observations=observations, turn_order=scenario.turn_order, bot_player_id=scenario.bot_player_id)

    engine = CryptidAIEngine.from_initial_setup(
        InitialSetup(
            board=build_board_for_scenario(scenario.board),
            turn_order=scenario.turn_order,
            bot_player_id=scenario.bot_player_id,
            bot_clue_id=_bot_player(scenario).clue_id,
            clues=None,
            include_inverse_clues=scenario.include_inverse_clues,
        )
    )
    for observation in observations:
        engine.apply_observation(
            PlayerResponseEvent(player_id=observation.player_id, tile_id=observation.tile_id, answered_yes=observation.answered_yes)
        )

    hypothesis_space = infer_hypothesis_space(snapshot=snapshot, include_inverse_clues=scenario.include_inverse_clues)
    recommended_moves = tuple(recommend_moves(snapshot=snapshot, hypothesis_space=hypothesis_space, top_k=effective_top_k))
    next_move = engine.next_move(snapshot=snapshot, top_k=effective_top_k)
    debug_state = engine.get_debug_state()
    true_clues = _true_clues_by_player(scenario)
    ground_truth_candidate_tiles = _ground_truth_candidate_tiles(board=board, clues_by_player=true_clues)

    true_clue_retained_by_player = tuple(
        (player.player_id, player.clue_id in dict(debug_state.possible_clue_ids_by_player).get(player.player_id, ()))
        for player in scenario.players
        if player.player_id != scenario.bot_player_id
    )
    recommended_move_truths = tuple(
        _evaluate_recommended_move_truth(board=board, move=move, clues_by_player=true_clues)
        for move in recommended_moves
    )

    return ScenarioEvaluationResult(
        scenario=scenario,
        used_seed=effective_seed,
        used_observation_count=effective_observation_count,
        used_top_k=effective_top_k,
        snapshot=snapshot,
        observations=observations,
        ground_truth_candidate_tiles=ground_truth_candidate_tiles,
        debug_state=debug_state,
        next_move=next_move,
        recommended_moves=recommended_moves,
        true_clue_retained_by_player=true_clue_retained_by_player,
        recommended_move_truths=recommended_move_truths,
    )


def evaluate_scenario_file(
    path: str | Path,
    seed: Optional[int] = None,
    observation_count: Optional[int] = None,
    top_k: Optional[int] = None,
) -> ScenarioEvaluationResult:
    scenario = load_scenario_definition(path)
    return evaluate_scenario(scenario=scenario, seed=seed, observation_count=observation_count, top_k=top_k)


def format_evaluation_report(result: ScenarioEvaluationResult) -> str:
    scenario = result.scenario
    lines = [
        f"Scenario: {scenario.scenario_id}",
        f"Description: {scenario.description or '-'}",
        f"Board kind: {scenario.board.kind}",
        f"Players: {', '.join(f'{player.player_id}={player.clue_id}' for player in scenario.players)}",
        f"Turn order: {', '.join(scenario.turn_order)}",
        f"Bot player: {scenario.bot_player_id}",
        f"Generated observations: {len(result.observations)} (seed={result.used_seed}, requested={result.used_observation_count})",
        f"Top-k moves requested: {result.used_top_k}",
        f"Ground-truth candidate tiles: {list(result.ground_truth_candidate_tiles)}",
        "",
        "Observations:",
    ]

    if result.observations:
        for index, observation in enumerate(result.observations, start=1):
            token_name = "round" if observation.answered_yes else "cube"
            lines.append(
                f"  {index:02d}. player={observation.player_id:<8} tile={observation.tile_id:<3} answer={'yes' if observation.answered_yes else 'no ':<3} token={token_name}"
            )
    else:
        lines.append("  (none)")

    lines.extend([
        "",
        "Hypothesis summary:",
    ])
    possible_by_player = dict(result.debug_state.possible_clue_ids_by_player)
    for player in scenario.players:
        if player.player_id == scenario.bot_player_id:
            continue
        possible = possible_by_player.get(player.player_id, ())
        retained = player.clue_id in possible
        lines.append(
            f"  - {player.player_id}: {len(possible)} possible clues | true clue retained={retained}"
        )

    lines.extend([
        "",
        "Recommended moves:",
    ])
    if result.recommended_moves:
        for index, (move, truth) in enumerate(zip(result.recommended_moves, result.recommended_move_truths), start=1):
            lines.append(
                "  "
                f"{index}. {move.action_type} tile={move.tile_id}"
                f" target={move.target_player_id or '-'}"
                f" score={move.score:.3f}"
                f" confidence={move.confidence:.3f}"
                f" | truth_answer={truth.truth_answer}"
                f" | blocking_players={list(truth.blocking_players)}"
                f" | matches_all_true_clues={truth.matches_all_true_clues}"
            )
            if move.rationale:
                lines.append(f"     rationale: {move.rationale}")
    else:
        lines.append("  (none)")

    lines.extend([
        "",
        "Next move:",
        f"  {result.next_move if result.next_move is not None else 'None'}",
    ])
    return "\n".join(lines)


def _scenario_board_from_dict(payload: Any) -> ScenarioBoardSpec:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("board must be an object.")

    kind = str(payload.get("kind", "default_layout")).strip() or "default_layout"
    if kind not in {"default_layout", "placements"}:
        raise ValueError("board.kind must be either 'default_layout' or 'placements'.")
    placements = payload.get("placements", [])
    structures = payload.get("structures", [])
    tile_overrides = payload.get("tile_overrides", [])

    if not isinstance(placements, list):
        raise ValueError("board.placements must be a list.")
    if not isinstance(structures, list):
        raise ValueError("board.structures must be a list.")
    if not isinstance(tile_overrides, list):
        raise ValueError("board.tile_overrides must be a list.")

    return ScenarioBoardSpec(
        kind=kind,
        placements=tuple(dict(entry) for entry in placements if isinstance(entry, dict)),
        structures=tuple(dict(entry) for entry in structures if isinstance(entry, dict)),
        include_structure_markers=bool(payload.get("include_structure_markers", True)),
        tile_overrides=tuple(dict(entry) for entry in tile_overrides if isinstance(entry, dict)),
    )


def _validate_clue_ids(players: Sequence[ScenarioPlayer], include_inverse_clues: bool) -> None:
    catalog = clues_by_id(include_inverse=include_inverse_clues)
    missing = [player.clue_id for player in players if player.clue_id not in catalog]
    if missing:
        raise ValueError(f"Unknown clue ids in scenario: {', '.join(sorted(missing))}")


def _apply_tile_overrides(board: Board, overrides: Iterable[Dict[str, Any]]) -> None:
    tiles_by_id = {tile.tile_id: tile for tile in board.tiles.values()}
    for override in overrides:
        tile_id = int(override.get("tile_id", -1))
        tile = tiles_by_id.get(tile_id)
        if tile is None:
            raise ValueError(f"Unknown tile_id in override: {tile_id}")

        if "terrain" in override and override["terrain"] is not None:
            tile.terrain = TerrainType(str(override["terrain"]).strip().lower())
        if "animal" in override:
            animal_value = override["animal"]
            tile.animal = AnimalTerritory(str(animal_value).strip().lower()) if animal_value else None
        if "structure_type" in override:
            structure_type_value = override["structure_type"]
            tile.structure_type = StructureType(str(structure_type_value).strip().lower()) if structure_type_value else None
        if "structure_color" in override:
            structure_color_value = override["structure_color"]
            tile.structure_color = StructureColor(str(structure_color_value).strip().lower()) if structure_color_value else None


def _apply_structures(board: Board, structures: Iterable[Dict[str, Any]]) -> None:
    tiles_by_id = {tile.tile_id: tile for tile in board.tiles.values()}
    tiles_by_section_local = {
        (tile.section_id, tile.local_id): tile
        for tile in board.tiles.values()
        if tile.section_id is not None and tile.local_id is not None
    }

    for tile in board.tiles.values():
        tile.structure_type = None
        tile.structure_color = None

    resolved_targets = set()
    for structure in structures:
        tile = _resolve_structure_tile(
            structure=structure,
            tiles_by_id=tiles_by_id,
            tiles_by_section_local=tiles_by_section_local,
        )
        target_key = (tile.tile_id,)
        if target_key in resolved_targets:
            raise ValueError(f"Duplicate structure target in scenario: tile_id={tile.tile_id}")
        resolved_targets.add(target_key)

        structure_type_value = structure.get("structure_type")
        structure_color_value = structure.get("structure_color")
        if not structure_type_value or not structure_color_value:
            raise ValueError("Each board structure must include structure_type and structure_color.")

        tile.structure_type = StructureType(str(structure_type_value).strip().lower())
        tile.structure_color = StructureColor(str(structure_color_value).strip().lower())


def _resolve_structure_tile(
    structure: Dict[str, Any],
    tiles_by_id: Dict[int, HexTile],
    tiles_by_section_local: Dict[Tuple[str, int], HexTile],
) -> HexTile:
    if "tile_id" in structure and structure.get("tile_id") is not None:
        tile_id = int(structure["tile_id"])
        tile = tiles_by_id.get(tile_id)
        if tile is None:
            raise ValueError(f"Unknown tile_id in board.structures: {tile_id}")
        return tile

    section_id = structure.get("section_id")
    local_id = structure.get("local_id")
    if section_id is None or local_id is None:
        raise ValueError("Each board structure must define either tile_id or section_id + local_id.")

    key = (str(section_id), int(local_id))
    tile = tiles_by_section_local.get(key)
    if tile is None:
        raise ValueError(f"Unknown section/local target in board.structures: {key}")
    return tile


def _compose_board_from_placements(
    placements: Iterable[Dict[str, Any]],
    include_structure_markers: bool,
) -> Board:
    templates = load_module_templates()
    slots = load_slots()
    layout_instance = load_layout_instance()
    structure_markers = layout_instance.get("structure_markers", [])

    tiles: Dict[Tuple[int, int], HexTile] = {}
    tile_id = 0
    section_local_index: Dict[Tuple[str, int], HexTile] = {}

    for placement in placements:
        slot_id = int(placement["slot_id"])
        section_id = str(placement["section_id"])
        orientation = str(placement["orientation"])
        if slot_id not in slots:
            raise ValueError(f"Unknown slot_id in scenario board: {slot_id}")
        if section_id not in templates:
            raise ValueError(f"Unknown section_id in scenario board: {section_id}")
        if orientation not in {"normal", "flipped"}:
            raise ValueError(f"Unknown orientation in scenario board: {orientation}")

        slot_origin = slots[slot_id]
        section_tiles = templates[section_id][orientation]
        for local_id, tile_data in section_tiles.items():
            q = slot_origin["origin_q"] + tile_data["q"]
            r = slot_origin["origin_r"] + tile_data["r"]
            coord = (q, r)
            if coord in tiles:
                raise ValueError(f"Overlapping coordinate in scenario board: {coord}")
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
            tile = section_local_index.get((marker["section_id"], marker["local_id"]))
            if tile is None:
                continue
            tile.structure_type = marker["structure_type"]
            tile.structure_color = marker["structure_color"]

    return Board(tiles=tiles)


def _snapshot_from_observations(
    board: Board,
    observations: Sequence[SyntheticObservation],
    turn_order: Tuple[str, ...],
    bot_player_id: str,
) -> GameSnapshot:
    board_copy = deepcopy(board)
    tiles_by_id = {tile.tile_id: tile for tile in board_copy.tiles.values()}
    for observation in observations:
        tile = tiles_by_id[observation.tile_id]
        if observation.answered_yes:
            tile.round_tokens.append(observation.player_id)
        else:
            tile.cube_tokens.append(observation.player_id)
    return GameSnapshot(board=board_copy, turn_order=turn_order, bot_player_id=bot_player_id)


def _ground_truth_candidate_tiles(board: Board, clues_by_player: Dict[str, Clue]) -> Tuple[int, ...]:
    matched_sets = []
    for clue in clues_by_player.values():
        matched_sets.append({tile.tile_id for tile in board.tiles.values() if clue.matches(tile, board)})
    if not matched_sets:
        return ()
    return tuple(sorted(set.intersection(*matched_sets)))


def _true_clues_by_player(scenario: ScenarioDefinition) -> Dict[str, Clue]:
    catalog = clues_by_id(include_inverse=scenario.include_inverse_clues)
    return {player.player_id: catalog[player.clue_id] for player in scenario.players}


def _evaluate_recommended_move_truth(
    board: Board,
    move: RecommendedMove,
    clues_by_player: Dict[str, Clue],
) -> RecommendedMoveTruth:
    tile = _tile_by_id(board, move.tile_id)
    blocking_players = tuple(
        sorted(player_id for player_id, clue in clues_by_player.items() if not clue.matches(tile, board))
    )

    truth_answer: Optional[bool] = None
    if move.target_player_id is not None:
        clue = clues_by_player.get(move.target_player_id)
        if clue is not None:
            truth_answer = clue.matches(tile, board)

    return RecommendedMoveTruth(
        action_type=move.action_type,
        tile_id=move.tile_id,
        target_player_id=move.target_player_id,
        truth_answer=truth_answer,
        blocking_players=blocking_players,
        matches_all_true_clues=len(blocking_players) == 0,
    )


def _tile_by_id(board: Board, tile_id: int) -> HexTile:
    for tile in board.tiles.values():
        if tile.tile_id == tile_id:
            return tile
    raise ValueError(f"Unknown tile_id: {tile_id}")


def _bot_player(scenario: ScenarioDefinition) -> ScenarioPlayer:
    for player in scenario.players:
        if player.player_id == scenario.bot_player_id:
            return player
    raise ValueError(f"Scenario bot player not found: {scenario.bot_player_id}")




