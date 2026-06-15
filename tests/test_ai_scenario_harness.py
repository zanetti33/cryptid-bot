from __future__ import annotations

from pathlib import Path

from ai.scenario_harness import (
    build_board_for_scenario,
    evaluate_scenario_file,
    format_evaluation_report,
    generate_synthetic_observations,
    load_scenario_definition,
)
from game_model.clues import clues_by_id


SCENARIO_PATH = Path("data/ai_scenarios/default_layout.json")


def test_generate_synthetic_observations_is_deterministic() -> None:
    scenario = load_scenario_definition(SCENARIO_PATH)

    first = generate_synthetic_observations(scenario)
    second = generate_synthetic_observations(scenario)

    assert first == second
    assert len(first) == scenario.simulation.observation_count


def test_generated_observations_match_true_clues() -> None:
    scenario = load_scenario_definition(SCENARIO_PATH)
    board = build_board_for_scenario(scenario.board)
    clue_catalog = clues_by_id(include_inverse=scenario.include_inverse_clues)
    observations = generate_synthetic_observations(scenario)
    tiles_by_id = {tile.tile_id: tile for tile in board.tiles.values()}
    players_by_id = {player.player_id: player for player in scenario.players}

    assert observations
    for observation in observations:
        clue = clue_catalog[players_by_id[observation.player_id].clue_id]
        tile = tiles_by_id[observation.tile_id]
        assert observation.answered_yes is clue.matches(tile, board)


def test_evaluate_scenario_file_returns_readable_report() -> None:
    result = evaluate_scenario_file(SCENARIO_PATH)
    report = format_evaluation_report(result)

    assert result.recommended_moves
    assert len(result.observations) == len(result.debug_state.observations)
    assert result.ground_truth_candidate_tiles
    assert all(retained for _player_id, retained in result.true_clue_retained_by_player)
    assert "Scenario: my-default-layout" in report
    assert "Recommended moves:" in report
    assert "Ground-truth candidate tiles:" in report

