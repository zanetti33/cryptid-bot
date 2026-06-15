from dataclasses import dataclass

from ai.inference import HypothesisSpace, PlayerHypothesisSpace, infer_hypothesis_space
from ai.strategy import recommend_moves
from game_model.clues import Clue
from game_model.map import Board
from game_model.state import GameSnapshot
from game_model.tokens import GameState
from game_model.types import TerrainType, TokenType


def _tile_id(board: Board, q: int, r: int) -> int:
    tile = board.get(q, r)
    if tile is None:
        raise AssertionError(f"Missing tile {(q, r)}")
    return tile.tile_id


@dataclass(frozen=True)
class _TileIdPredicate:
    allowed_tile_ids: frozenset[int]

    def matches(self, tile, board) -> bool:
        return tile.tile_id in self.allowed_tile_ids


def test_recommend_moves_returns_ranked_candidates_with_confidence() -> None:
    board = Board.rectangular(cols=2, rows=2)
    state = GameState(board=board)

    state.place_token("bot", 0, 0, TokenType.CUBE)
    state.place_token("p1", 1, 0, TokenType.ROUND)
    state.place_token("p2", 1, 1, TokenType.CUBE)

    snapshot = GameSnapshot(board=board, turn_order=("bot", "p1", "p2"), bot_player_id="bot")
    moves = recommend_moves(snapshot=snapshot, top_k=4)

    assert moves
    assert len(moves) <= 4
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


def test_recommend_moves_validates_claim_threshold() -> None:
    board = Board.rectangular(cols=1, rows=1)
    snapshot = GameSnapshot(board=board)

    try:
        recommend_moves(snapshot=snapshot, top_k=1, claim_threshold=1.1)
    except ValueError as exc:
        assert str(exc) == "claim_threshold must be between 0 and 1"
    else:
        raise AssertionError("Expected ValueError for invalid claim_threshold")


def test_recommend_moves_ask_is_only_on_bot_valid_tiles() -> None:
    """ask_is must never be proposed on a tile excluded by the bot's own clue."""
    # 1x2 board: tile at (0,0)=FOREST, tile at (1,0)=WATER
    board = Board.rectangular(cols=2, rows=1)
    forest_tile = board.get(0, 0)
    water_tile = board.get(1, 0)
    assert forest_tile is not None and water_tile is not None

    forest_tile.terrain = TerrainType.FOREST
    water_tile.terrain = TerrainType.WATER

    snapshot = GameSnapshot(board=board, turn_order=("bot", "p1"), bot_player_id="bot")

    # Bot's clue is valid only for the FOREST tile.
    bot_valid = {forest_tile.tile_id}
    moves = recommend_moves(snapshot=snapshot, top_k=10, bot_valid_tile_ids=bot_valid)

    ask_is_tiles = {m.tile_id for m in moves if m.action_type == "ask_is"}
    assert water_tile.tile_id not in ask_is_tiles, (
        "ask_is should never target a tile excluded by the bot's own clue"
    )
    assert forest_tile.tile_id in ask_is_tiles, (
        "ask_is should be proposed for the tile valid for the bot's clue"
    )


def test_recommend_moves_bot_included_in_hypothesis_space() -> None:
    """The bot's token placements must narrow down global candidate tiles."""
    # 1x2 board: tile at (0,0)=FOREST, tile at (1,0)=WATER
    board = Board.rectangular(cols=2, rows=1)
    forest_tile = board.get(0, 0)
    water_tile = board.get(1, 0)
    assert forest_tile is not None and water_tile is not None

    forest_tile.terrain = TerrainType.FOREST
    water_tile.terrain = TerrainType.WATER

    state = GameState(board=board)
    # Bot places a cube on the WATER tile → its clue cannot include water.
    # From the hypothesis space perspective the bot's candidate tiles exclude water,
    # so the global intersection should exclude it too.
    state.place_token("bot", 1, 0, TokenType.CUBE)

    snapshot = GameSnapshot(board=board, turn_order=("bot", "p1"), bot_player_id="bot")

    # Without bot_valid_tile_ids, ask_is moves come purely from hypothesis inference.
    moves = recommend_moves(snapshot=snapshot, top_k=10)
    ask_is_tiles = {m.tile_id for m in moves if m.action_type == "ask_is"}

    # Water tile is excluded by the bot's own cube, so ask_is should not target it.
    assert water_tile.tile_id not in ask_is_tiles


def test_recommend_moves_prefers_question_with_higher_expected_clue_elimination() -> None:
    board = Board.rectangular(cols=3, rows=1)
    left = board.get(0, 0)
    middle = board.get(1, 0)
    right = board.get(2, 0)
    assert left is not None and middle is not None and right is not None

    snapshot = GameSnapshot(board=board, turn_order=("bot", "p1"), bot_player_id="bot")
    clues = (
        Clue("c1", "tile 0", _TileIdPredicate(frozenset({left.tile_id}))),
        Clue("c2", "tile 0 or 1", _TileIdPredicate(frozenset({left.tile_id, middle.tile_id}))),
        Clue("c3", "tile 0 or 2", _TileIdPredicate(frozenset({left.tile_id, right.tile_id}))),
        Clue("c4", "tile 1 or 2", _TileIdPredicate(frozenset({middle.tile_id, right.tile_id}))),
    )
    hypothesis_space = infer_hypothesis_space(snapshot=snapshot, clues=clues)
    moves = recommend_moves(snapshot=snapshot, hypothesis_space=hypothesis_space, top_k=10)

    ask_could_moves = [move for move in moves if move.action_type == "ask_could" and move.target_player_id == "p1"]
    assert ask_could_moves

    best_ask_could = ask_could_moves[0]
    # tile 1 gives a 2/2 split of the four possible clues, so its expected clue
    # elimination is higher than tile 0, which gives a 3/1 split.
    assert best_ask_could.tile_id == middle.tile_id


def test_recommend_moves_threshold_switches_between_ask_could_and_ask_is() -> None:
    board = Board.rectangular(cols=3, rows=1)
    snapshot = GameSnapshot(board=board, turn_order=("bot", "p1"), bot_player_id="bot")

    hypothesis_space = HypothesisSpace(
        players=(
            PlayerHypothesisSpace(
                player_id="bot",
                possible_clue_ids=("b",),
                candidate_tiles=(0, 1, 2),
                guaranteed_tiles=(),
                eliminated_tiles=(),
            ),
            PlayerHypothesisSpace(
                player_id="p1",
                possible_clue_ids=("c1", "c2"),
                candidate_tiles=(0, 1, 2),
                guaranteed_tiles=(),
                eliminated_tiles=(),
            ),
        ),
        clue_match_tiles_by_id={
            "b": (0, 1, 2),
            "c1": (0, 1),
            "c2": (1, 2),
        },
    )

    ask_could_moves = recommend_moves(
        snapshot=snapshot,
        hypothesis_space=hypothesis_space,
        top_k=3,
        claim_threshold=0.6,
    )
    assert ask_could_moves
    assert all(move.action_type == "ask_could" for move in ask_could_moves)

    ask_is_moves = recommend_moves(
        snapshot=snapshot,
        hypothesis_space=hypothesis_space,
        top_k=3,
        claim_threshold=0.2,
    )
    assert ask_is_moves
    assert all(move.action_type == "ask_is" for move in ask_is_moves)


