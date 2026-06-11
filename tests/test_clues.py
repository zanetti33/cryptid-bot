from data.board_loader import load_default_board
from game_model.clues import OrPredicate, build_base_clues, build_clue_catalog, clues_by_id


def _any_tile(board, predicate):
    for tile in board.tiles.values():
        if predicate(tile):
            return tile
    raise AssertionError("No tile found matching predicate")


def test_base_clue_catalog_has_expected_size() -> None:
    clues = build_base_clues()
    assert len(clues) == 24


def test_clue_catalog_with_inverse_doubles_size() -> None:
    clues = build_clue_catalog(include_inverse=True)
    assert len(clues) == 48


def test_terrain_pair_clue_matches_by_terrain() -> None:
    board = load_default_board()
    clue = clues_by_id()["terrain_pair_forest_desert"]

    matching_tile = _any_tile(board, lambda t: t.terrain.value in {"forest", "desert"})
    non_matching_tile = _any_tile(board, lambda t: t.terrain.value in {"water", "swamp", "mountain"})

    assert isinstance(clue.predicate, OrPredicate)
    assert clue.matches(matching_tile, board) is True
    assert clue.matches(non_matching_tile, board) is False


def test_inverse_clue_flips_result() -> None:
    board = load_default_board()
    base = clues_by_id()["within_two_bear_territory"]
    inverse = clues_by_id(include_inverse=True)["not_within_two_bear_territory"]

    target_tile = _any_tile(board, lambda t: True)
    assert inverse.matches(target_tile, board) is (not base.matches(target_tile, board))


def test_within_three_structure_color_has_at_least_one_match() -> None:
    board = load_default_board()
    clue = clues_by_id()["within_three_white_structure"]

    assert any(clue.matches(tile, board) for tile in board.tiles.values())


def test_within_one_either_animal_has_at_least_one_match() -> None:
    board = load_default_board()
    clue = clues_by_id()["within_one_either_animal_territory"]

    assert any(clue.matches(tile, board) for tile in board.tiles.values())

