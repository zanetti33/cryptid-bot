from dataclasses import dataclass

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


@dataclass(frozen=True)
class _TileIdPredicate:
    allowed_tile_ids: frozenset[int]

    def matches(self, tile, board) -> bool:
        return tile.tile_id in self.allowed_tile_ids


def _three_tile_board() -> Tuple[Board, int, int, int]:
    board = Board.rectangular(cols=3, rows=1)
    first = board.get(0, 0)
    second = board.get(1, 0)
    third = board.get(2, 0)
    if first is None or second is None or third is None:
        raise AssertionError("Expected three tiles for the test board")
    return board, first.tile_id, second.tile_id, third.tile_id


def _three_tile_clues(tile0: int, tile1: int, tile2: int) -> Tuple[Clue, Clue, Clue]:
    clue_a = Clue(
        clue_id="clue_a",
        text="tile 0 or 1",
        predicate=_TileIdPredicate(frozenset({tile0, tile1})),
    )
    clue_b = Clue(
        clue_id="clue_b",
        text="tile 1",
        predicate=_TileIdPredicate(frozenset({tile1})),
    )
    clue_c = Clue(
        clue_id="clue_c",
        text="tile 1 or 2",
        predicate=_TileIdPredicate(frozenset({tile1, tile2})),
    )
    return clue_a, clue_b, clue_c


def test_infer_hypothesis_space_filters_clues_from_round_and_cube_tokens() -> None:
    board, tile0, tile1, tile2 = _three_tile_board()
    clue_a, clue_b, clue_c = _three_tile_clues(tile0=tile0, tile1=tile1, tile2=tile2)

    state = GameState(board=board)
    state.place_token("p1", 2, 0, TokenType.CUBE)
    state.place_token("p1", 1, 0, TokenType.ROUND)

    snapshot = GameSnapshot(board=board, turn_order=("p1", "p2"))
    space = infer_hypothesis_space(snapshot=snapshot, clues=(clue_a, clue_b, clue_c))
    by_player = space.by_player()

    p1 = by_player["p1"]
    assert p1.possible_clue_ids == ("clue_a", "clue_b")
    assert p1.candidate_tiles == (tile0, tile1)
    assert p1.guaranteed_tiles == (tile1,)
    assert p1.eliminated_tiles == (tile2,)

    p2 = by_player["p2"]
    assert p2.possible_clue_ids == ("clue_a", "clue_b", "clue_c")
    assert p2.candidate_tiles == (tile0, tile1, tile2)
    assert p2.guaranteed_tiles == (tile1,)


def test_infer_hypothesis_space_exposes_global_candidates_and_unresolved_players() -> None:
    board, tile0, tile1, tile2 = _three_tile_board()
    clue_a, clue_b, clue_c = _three_tile_clues(tile0=tile0, tile1=tile1, tile2=tile2)

    state = GameState(board=board)
    state.place_token("p1", 0, 0, TokenType.CUBE)
    state.place_token("p1", 1, 0, TokenType.ROUND)

    snapshot = GameSnapshot(board=board, turn_order=("p1", "p2"))
    space = infer_hypothesis_space(snapshot=snapshot, clues=(clue_a, clue_b, clue_c))

    assert space.global_candidate_tiles() == (tile1, tile2)
    assert space.unresolved_players() == ("p1", "p2")


def test_infer_hypothesis_space_enforces_unique_clue_per_match() -> None:
    board, tile0, tile1, tile2 = _three_tile_board()
    clue_a, clue_b, clue_c = _three_tile_clues(tile0=tile0, tile1=tile1, tile2=tile2)

    state = GameState(board=board)
    # p1 can only be clue_b
    state.place_token("p1", 0, 0, TokenType.CUBE)
    state.place_token("p1", 2, 0, TokenType.CUBE)
    state.place_token("p1", 1, 0, TokenType.ROUND)
    # p2 local candidates are clue_b and clue_c
    state.place_token("p2", 0, 0, TokenType.CUBE)

    snapshot = GameSnapshot(board=board, turn_order=("p1", "p2"))
    space = infer_hypothesis_space(snapshot=snapshot, clues=(clue_a, clue_b, clue_c))
    by_player = space.by_player()

    assert by_player["p1"].possible_clue_ids == ("clue_b",)
    assert by_player["p2"].possible_clue_ids == ("clue_c",)


def test_infer_hypothesis_space_requires_single_global_solution_tile() -> None:
    board, tile0, tile1, _tile2 = _three_tile_board()
    clue_x = Clue(
        clue_id="clue_x",
        text="tile 0 or 1",
        predicate=_TileIdPredicate(frozenset({tile0, tile1})),
    )
    clue_y = Clue(
        clue_id="clue_y",
        text="tile 0 or 1",
        predicate=_TileIdPredicate(frozenset({tile0, tile1})),
    )

    state = GameState(board=board)
    # Resolve p1 to clue_x and p2 to clue_y using exclusive round/cube evidence.
    state.place_token("p1", 0, 0, TokenType.ROUND)
    state.place_token("p1", 1, 0, TokenType.ROUND)
    state.place_token("p2", 0, 0, TokenType.ROUND)
    state.place_token("p2", 1, 0, TokenType.ROUND)

    snapshot = GameSnapshot(board=board, turn_order=("p1", "p2"))
    space = infer_hypothesis_space(snapshot=snapshot, clues=(clue_x, clue_y))
    by_player = space.by_player()

    # The only clue assignment has an intersection of two tiles, so it is rejected.
    assert by_player["p1"].is_contradictory
    assert by_player["p2"].is_contradictory


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



