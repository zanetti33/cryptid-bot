from __future__ import annotations

from game_model.clues import AtomPredicate, Clue, TargetCategory
from game_model.game import Game, GamePhase, PlayerState
from game_model.map import Board
from game_model.types import TerrainType, TokenType


def _build_board() -> Board:
    board = Board.rectangular(cols=3, rows=1)
    first = board.get(0, 0)
    second = board.get(1, 0)
    third = board.get(2, 0)
    if first is None or second is None or third is None:
        raise AssertionError("Missing tiles on test board")

    first.terrain = TerrainType.FOREST
    second.terrain = TerrainType.WATER
    third.terrain = TerrainType.MOUNTAIN
    return board


def _tile_id(board: Board, q: int, r: int) -> int:
    tile = board.get(q, r)
    if tile is None:
        raise AssertionError(f"Missing tile {(q, r)}")
    return tile.tile_id


def _terrain_clue(clue_id: str, terrain: TerrainType) -> Clue:
    return Clue(
        clue_id=clue_id,
        text=f"On {terrain.value}",
        predicate=AtomPredicate(target=TargetCategory.TERRAIN, value=terrain, distance=0),
    )


def _catalog() -> dict[str, Clue]:
    return {
        "forest_only": _terrain_clue("forest_only", TerrainType.FOREST),
        "water_only": _terrain_clue("water_only", TerrainType.WATER),
        "mountain_only": _terrain_clue("mountain_only", TerrainType.MOUNTAIN),
    }


def test_ask_could_yes_places_round_and_advances_turn() -> None:
    board = _build_board()
    forest_tile_id = _tile_id(board, 0, 0)
    game = Game(
        board=board,
        players=(
            PlayerState("p1", "water_only"),
            PlayerState("p2", "forest_only"),
        ),
        clue_catalog=_catalog(),
    )

    result = game.ask_could(asker_id="p1", target_player_id="p2", tile_id=forest_tile_id)

    assert result.answered_yes
    assert result.target_token.token_type is TokenType.ROUND
    assert result.asker_cube_token is None
    assert game.current_player_id == "p2"



def test_ask_could_no_places_target_cube_and_forced_asker_cube() -> None:
    board = _build_board()
    forest_tile_id = _tile_id(board, 0, 0)
    water_tile_id = _tile_id(board, 1, 0)
    game = Game(
        board=board,
        players=(
            PlayerState("p1", "forest_only"),
            PlayerState("p2", "water_only"),
        ),
        clue_catalog=_catalog(),
    )

    result = game.ask_could(
        asker_id="p1",
        target_player_id="p2",
        tile_id=forest_tile_id,
        asker_cube_tile_id=water_tile_id,
    )

    assert not result.answered_yes
    assert result.target_token.token_type is TokenType.CUBE
    assert result.asker_cube_token is not None
    assert result.asker_cube_token.token_type is TokenType.CUBE
    assert result.asker_cube_token.tile_id == water_tile_id
    assert game.current_player_id == "p2"



def test_ask_is_all_yes_declares_winner() -> None:
    board = _build_board()
    forest_tile_id = _tile_id(board, 0, 0)
    game = Game(
        board=board,
        players=(
            PlayerState("p1", "forest_only"),
            PlayerState("p2", "forest_only"),
        ),
        clue_catalog=_catalog(),
    )

    result = game.ask_is(asker_id="p1", tile_id=forest_tile_id)

    assert result.winner_id == "p1"
    assert result.disproved_by_player_id is None
    assert all(item.token_type is TokenType.ROUND for item in result.placements)
    assert game.phase is GamePhase.RESOLVED
    assert game.winner_id == "p1"



def test_ask_is_stops_on_first_cube_and_game_continues() -> None:
    board = _build_board()
    forest_tile_id = _tile_id(board, 0, 0)
    game = Game(
        board=board,
        players=(
            PlayerState("p1", "forest_only"),
            PlayerState("p2", "water_only"),
        ),
        clue_catalog=_catalog(),
    )

    result = game.ask_is(asker_id="p1", tile_id=forest_tile_id)

    assert result.winner_id is None
    assert result.disproved_by_player_id == "p2"
    assert result.placements[0].token_type is TokenType.ROUND
    assert result.placements[1].token_type is TokenType.CUBE
    assert game.phase is GamePhase.PLAYING
    assert game.current_player_id == "p2"



def test_validate_token_consistency_rejects_invalid_token() -> None:
    board = _build_board()
    water_tile_id = _tile_id(board, 1, 0)
    game = Game(
        board=board,
        players=(
            PlayerState("p1", "forest_only"),
            PlayerState("p2", "water_only"),
        ),
        clue_catalog=_catalog(),
    )

    try:
        game.validate_token_consistency("p1", water_tile_id, TokenType.ROUND)
    except ValueError as exc:
        assert "Invalid round token" in str(exc)
    else:
        raise AssertionError("Expected invalid round token to be rejected")



def test_game_serialization_roundtrip_preserves_state() -> None:
    board = _build_board()
    forest_tile_id = _tile_id(board, 0, 0)
    water_tile_id = _tile_id(board, 1, 0)
    clue_catalog = _catalog()
    game = Game(
        board=board,
        players=(
            PlayerState("p1", "forest_only"),
            PlayerState("p2", "water_only"),
        ),
        clue_catalog=clue_catalog,
    )

    game.ask_could(
        asker_id="p1",
        target_player_id="p2",
        tile_id=forest_tile_id,
        asker_cube_tile_id=water_tile_id,
    )
    payload = game.to_dict()

    fresh_board = _build_board()
    restored = Game.from_dict(payload=payload, board=fresh_board, clue_catalog=clue_catalog)

    assert restored.phase is GamePhase.PLAYING
    assert restored.winner_id is None
    assert restored.current_player_id == "p2"
    token_counts = restored.state.token_counts()
    assert token_counts == {"round": 0, "cube": 2}

