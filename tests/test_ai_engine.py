from typing import Tuple, cast

from ai import CryptidAIEngine, InitialSetup
from ai.events import PlayerResponseEvent
from game_model.clues import AtomPredicate, Clue, Predicate, TargetCategory
from game_model.map import Board
from game_model.state import GameSnapshot
from game_model.tokens import GameState
from game_model.types import TerrainType
from game_model.types import TokenType


def _board() -> Board:
    board = Board.rectangular(cols=2, rows=1)
    first = board.get(0, 0)
    second = board.get(1, 0)
    if first is None or second is None:
        raise RuntimeError("Missing tiles")
    first.terrain = TerrainType.FOREST
    second.terrain = TerrainType.WATER
    return board


def _clues() -> Tuple[Clue, Clue]:
    forest = Clue(
        clue_id="forest_only",
        text="In forest",
        predicate=cast(
            Predicate,
            AtomPredicate(target=TargetCategory.TERRAIN, value=TerrainType.FOREST, distance=0),
        ),
    )
    water = Clue(
        clue_id="water_only",
        text="In water",
        predicate=cast(
            Predicate,
            AtomPredicate(target=TargetCategory.TERRAIN, value=TerrainType.WATER, distance=0),
        ),
    )
    return forest, water


def test_engine_initialization_and_cell_validation() -> None:
    board = _board()
    engine = CryptidAIEngine.from_initial_setup(
        InitialSetup(
            board=board,
            turn_order=("bot", "p1"),
            bot_player_id="bot",
            bot_clue_id="forest_only",
            clues=_clues(),
            include_inverse_clues=False,
        )
    )

    assert engine.is_cell_valid_for_me(0)
    assert not engine.is_cell_valid_for_me(1)

    debug_state = engine.get_debug_state()
    assert debug_state.observations[0].player_id == "bot"
    assert debug_state.observations[0].tile_id == 0
    assert debug_state.observations[0].answered_yes is True
    assert debug_state.observations[1].player_id == "bot"
    assert debug_state.observations[1].tile_id == 1
    assert debug_state.observations[1].answered_yes is False


def test_engine_applies_observation_and_exposes_debug_state() -> None:
    board = _board()
    engine = CryptidAIEngine.from_initial_setup(
        InitialSetup(
            board=board,
            turn_order=("bot", "p1"),
            bot_player_id="bot",
            bot_clue_id="forest_only",
            clues=_clues(),
            include_inverse_clues=False,
        )
    )

    engine.apply_observation(PlayerResponseEvent(player_id="p1", tile_id=0, answered_yes=True))
    debug_state = engine.get_debug_state()

    assert debug_state.observations
    assert debug_state.observations[0].player_id == "p1"
    assert debug_state.possible_clue_ids_by_player


def test_engine_answer_for_tile_updates_own_model() -> None:
    board = _board()
    engine = CryptidAIEngine.from_initial_setup(
        InitialSetup(
            board=board,
            turn_order=("bot", "p1"),
            bot_player_id="bot",
            bot_clue_id="forest_only",
            clues=_clues(),
            include_inverse_clues=False,
        )
    )

    response = engine.answer_for_tile(1)
    debug_state = engine.get_debug_state()

    assert response.tile_id == 1
    assert response.answered_yes is False
    assert debug_state.observations[-1].player_id == "bot"
    assert debug_state.observations[-1].tile_id == 1
    assert debug_state.observations[-1].answered_yes is False


def test_engine_place_least_informative_cube_updates_own_model() -> None:
    board = _board()
    engine = CryptidAIEngine.from_initial_setup(
        InitialSetup(
            board=board,
            turn_order=("bot", "p1"),
            bot_player_id="bot",
            bot_clue_id="forest_only",
            clues=_clues(),
            include_inverse_clues=False,
        )
    )

    placement = engine.place_least_informative_cube()
    debug_state = engine.get_debug_state()

    assert placement.tile_id == 1
    assert debug_state.observations[-1].player_id == "bot"
    assert debug_state.observations[-1].tile_id == 1
    assert debug_state.observations[-1].answered_yes is False
    assert placement.score >= 0.0


def test_engine_next_move_uses_real_bot_clue_to_restrict_global_candidates() -> None:
    board = _board()
    state = GameState(board=board)
    state.place_token("p1", 0, 0, TokenType.ROUND)

    engine = CryptidAIEngine.from_initial_setup(
        InitialSetup(
            board=board,
            turn_order=("bot", "p1"),
            bot_player_id="bot",
            bot_clue_id="forest_only",
            clues=_clues(),
            include_inverse_clues=False,
        )
    )

    snapshot = GameSnapshot(board=board, turn_order=("bot", "p1"), bot_player_id="bot")
    move = engine.next_move(snapshot=snapshot, top_k=5)

    assert move is not None
    assert move.action_type == "ask_is"
    assert move.tile_id == 0


