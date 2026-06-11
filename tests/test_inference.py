from ai.inference import infer_hypothesis_space
from game_model.clues import AtomPredicate, Clue, TargetCategory
from game_model.map import Board
from game_model.state import GameSnapshot
from game_model.tokens import GameState
from game_model.types import TerrainType, TokenType
from typing import Tuple


def _build_two_tile_board() -> Tuple[Board, int, int]:
    board = Board.rectangular(cols=2, rows=1)
    first = board.get(0, 0)
    second = board.get(1, 0)
    if first is None or second is None:
        raise AssertionError("Expected two tiles for the test board")

    first.terrain = TerrainType.FOREST
    second.terrain = TerrainType.WATER
    return board, first.tile_id, second.tile_id


def _terrain_clues() -> Tuple[Clue, Clue]:
    forest = Clue(
        clue_id="forest_only",
        text="In forest",
        predicate=AtomPredicate(target=TargetCategory.TERRAIN, value=TerrainType.FOREST, distance=0),
    )
    water = Clue(
        clue_id="water_only",
        text="In water",
        predicate=AtomPredicate(target=TargetCategory.TERRAIN, value=TerrainType.WATER, distance=0),
    )
    return forest, water


def test_infer_hypothesis_space_filters_clues_from_round_and_cube_tokens() -> None:
    board, forest_tile_id, water_tile_id = _build_two_tile_board()
    forest, water = _terrain_clues()

    state = GameState(board=board)
    state.place_token("p1", 0, 0, TokenType.CUBE)
    state.place_token("p1", 1, 0, TokenType.ROUND)

    snapshot = GameSnapshot(board=board, turn_order=("p1", "p2"))
    space = infer_hypothesis_space(snapshot=snapshot, clues=(forest, water))
    by_player = space.by_player()

    p1 = by_player["p1"]
    assert p1.possible_clue_ids == ("water_only",)
    assert p1.candidate_tiles == (water_tile_id,)
    assert p1.guaranteed_tiles == (water_tile_id,)
    assert p1.eliminated_tiles == (forest_tile_id,)

    p2 = by_player["p2"]
    assert p2.possible_clue_ids == ("forest_only", "water_only")
    assert p2.candidate_tiles == (forest_tile_id, water_tile_id)
    assert p2.guaranteed_tiles == ()


def test_infer_hypothesis_space_exposes_global_candidates_and_unresolved_players() -> None:
    board, _forest_tile_id, water_tile_id = _build_two_tile_board()
    forest, water = _terrain_clues()

    state = GameState(board=board)
    state.place_token("p1", 0, 0, TokenType.CUBE)
    state.place_token("p1", 1, 0, TokenType.ROUND)

    snapshot = GameSnapshot(board=board, turn_order=("p1", "p2"))
    space = infer_hypothesis_space(snapshot=snapshot, clues=(forest, water))

    assert space.global_candidate_tiles() == (water_tile_id,)
    assert space.unresolved_players() == ("p2",)


def test_infer_hypothesis_space_marks_contradictions() -> None:
    board, forest_tile_id, _water_tile_id = _build_two_tile_board()
    forest, _water = _terrain_clues()

    state = GameState(board=board)
    state.place_token("p1", 0, 0, TokenType.CUBE)
    state.place_token("p1", 0, 0, TokenType.ROUND)

    snapshot = GameSnapshot(board=board, turn_order=("p1",))
    space = infer_hypothesis_space(snapshot=snapshot, clues=(forest,))
    player_space = space.by_player()["p1"]

    assert player_space.is_contradictory
    assert player_space.candidate_tiles == ()
    assert forest_tile_id in player_space.eliminated_tiles



