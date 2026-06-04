from ai.strategy import recommend_moves
from rules.map import Board
from rules.state import GameSnapshot
from rules.tokens import GameState
from rules.types import TokenType


def _tile_id(board: Board, q: int, r: int) -> int:
    tile = board.get(q, r)
    if tile is None:
        raise AssertionError(f"Missing tile {(q, r)}")
    return tile.tile_id


def test_recommend_moves_returns_ranked_candidates_with_confidence() -> None:
    board = Board.rectangular(cols=2, rows=2)
    state = GameState(board=board)

    state.place_token("bot", 0, 0, TokenType.CUBE)
    state.place_token("p1", 1, 0, TokenType.ROUND)
    state.place_token("p2", 1, 1, TokenType.CUBE)

    snapshot = GameSnapshot(board=board, turn_order=("bot", "p1", "p2"), bot_player_id="bot")
    moves = recommend_moves(snapshot=snapshot, top_k=4)

    assert moves
    assert len(moves) == 4
    assert moves == sorted(moves, key=lambda item: item.score, reverse=True)
    assert all(0.0 <= move.confidence <= 1.0 for move in moves)
    assert abs(sum(move.confidence for move in moves) - 1.0) < 1e-9

    blocked_tile_id = _tile_id(board, 0, 0)
    assert all(not (move.action_type == "ask_is" and move.tile_id == blocked_tile_id) for move in moves)


def test_recommend_moves_returns_single_claim_when_only_one_option_exists() -> None:
    board = Board.rectangular(cols=1, rows=1)
    snapshot = GameSnapshot(board=board)

    moves = recommend_moves(snapshot=snapshot, top_k=5)

    assert len(moves) == 1
    assert moves[0].action_type == "ask_is"
    assert moves[0].confidence == 1.0


def test_recommend_moves_validates_top_k() -> None:
    board = Board.rectangular(cols=1, rows=1)
    snapshot = GameSnapshot(board=board)

    try:
        recommend_moves(snapshot=snapshot, top_k=0)
    except ValueError as exc:
        assert str(exc) == "top_k must be greater than 0"
    else:
        raise AssertionError("Expected ValueError for invalid top_k")

