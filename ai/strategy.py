from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Set, Tuple

from ai.inference import HypothesisSpace, infer_hypothesis_space
from game_model.state import GameSnapshot

ActionType = Literal["ask_could", "ask_is"]


@dataclass(slots=True, frozen=True)
class RecommendedMove:
    action_type: ActionType
    tile_id: int
    target_player_id: Optional[str]
    score: float
    confidence: float
    rationale: Optional[str] = None


@dataclass(slots=True, frozen=True)
class _ScoredMove:
    action_type: ActionType
    tile_id: int
    target_player_id: Optional[str]
    score: float
    rationale: Optional[str]


def recommend_moves(
    snapshot: GameSnapshot,
    top_k: int = 5,
    hypothesis_space: Optional[HypothesisSpace] = None,
    bot_valid_tile_ids: Optional[Set[int]] = None,
    claim_threshold: float = 0.35,
) -> List[RecommendedMove]:
    """Return ranked action candidates for the current board snapshot.

    This first implementation is intentionally heuristic-driven:
    - prefer immediate claim opportunities on tiles without any cube tokens,
      but only on tiles that are valid for the bot's own clue (``bot_valid_tile_ids``).
      If ``bot_valid_tile_ids`` is None the filter is skipped (useful in tests).
    - otherwise propose `ask_could` questions to reduce uncertainty
    """
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")
    if not 0.0 <= claim_threshold <= 1.0:
        raise ValueError("claim_threshold must be between 0 and 1")

    current_hypothesis_space = hypothesis_space or infer_hypothesis_space(
        snapshot=snapshot,
        known_bot_valid_tile_ids=bot_valid_tile_ids,
    )
    scored_moves = _build_scored_moves(
        snapshot=snapshot,
        hypothesis_space=current_hypothesis_space,
        bot_valid_tile_ids=bot_valid_tile_ids,
    )
    if not scored_moves:
        return []

    preferred_action = _preferred_action_type(
        hypothesis_space=current_hypothesis_space,
        claim_threshold=claim_threshold,
    )
    filtered_moves = [move for move in scored_moves if move.action_type == preferred_action]
    if filtered_moves:
        scored_moves = filtered_moves

    scored_moves.sort(key=lambda move: (-move.score, move.tile_id, move.target_player_id or ""))
    selected = scored_moves[:top_k]
    confidences = _softmax([move.score for move in selected])

    return [
        RecommendedMove(
            action_type=move.action_type,
            tile_id=move.tile_id,
            target_player_id=move.target_player_id,
            score=move.score,
            confidence=confidence,
            rationale=move.rationale,
        )
        for move, confidence in zip(selected, confidences)
    ]


def _build_scored_moves(
    snapshot: GameSnapshot,
    hypothesis_space: HypothesisSpace,
    bot_valid_tile_ids: Optional[Set[int]] = None,
) -> List[_ScoredMove]:
    scored: List[_ScoredMove] = []
    cubes_by_player = snapshot.cubes_by_player()
    bot_cube_tiles = cubes_by_player.get(snapshot.bot_player_id or "", set())
    global_candidates = set(hypothesis_space.global_candidate_tiles())
    global_guaranteed = set(hypothesis_space.global_guaranteed_tiles())

    for tile in snapshot.board.tiles.values():
        if global_candidates and tile.tile_id not in global_candidates:
            continue

        round_count = len(tile.round_tokens)
        cube_count = len(tile.cube_tokens)

        # ask_is is only valid on tiles where the bot's own clue is satisfied.
        # If bot_valid_tile_ids is None (e.g. in unit tests without a known clue)
        # the check is skipped so existing test helpers keep working.
        bot_clue_valid = bot_valid_tile_ids is None or tile.tile_id in bot_valid_tile_ids

        if cube_count == 0 and tile.tile_id not in bot_cube_tiles and bot_clue_valid:
            score = 2.0 + (1.5 * round_count)
            if tile.tile_id in global_guaranteed:
                score += 1.0
            scored.append(
                _ScoredMove(
                    action_type="ask_is",
                    tile_id=tile.tile_id,
                    target_player_id=None,
                    score=score,
                    rationale="No cube seen on this tile; claim candidate.",
                )
            )

    target_players = _target_players(snapshot=snapshot, hypothesis_space=hypothesis_space)
    hypothesis_by_player = hypothesis_space.by_player()
    for target_player in target_players:
        player_space = hypothesis_by_player.get(target_player)
        if player_space is None:
            continue

        target_cubes = cubes_by_player.get(target_player, set())

        for tile in snapshot.board.tiles.values():
            if tile.tile_id in target_cubes:
                continue

            metrics = _expected_clue_elimination_metrics(
                player_space=player_space,
                clue_match_tiles_by_id=hypothesis_space.clue_match_tiles_by_id,
                tile_id=tile.tile_id,
            )
            score = metrics["expected_eliminated_clues"]

            scored.append(
                _ScoredMove(
                    action_type="ask_could",
                    tile_id=tile.tile_id,
                    target_player_id=target_player,
                    score=score,
                    rationale=(
                        "Expected clue reduction: "
                        f"{metrics['expected_eliminated_clues']:.3f} "
                        f"(P(yes)={metrics['yes_probability']:.3f}, "
                        f"drop_yes={metrics['eliminated_if_yes']}, "
                        f"drop_no={metrics['eliminated_if_no']})."
                    ),
                )
            )

    return scored


def _target_players(snapshot: GameSnapshot, hypothesis_space: HypothesisSpace) -> Tuple[str, ...]:
    hypothesis_by_player = hypothesis_space.by_player()
    players = [
        player_id
        for player_id in snapshot.player_ids()
        if player_id != snapshot.bot_player_id
        and player_id in hypothesis_by_player
        and not hypothesis_by_player[player_id].is_resolved
    ]
    return tuple(players)


def _softmax(scores: Sequence[float]) -> List[float]:
    if not scores:
        return []

    max_score = max(scores)
    exps = [math.exp(score - max_score) for score in scores]
    total = sum(exps)
    if total == 0:
        return [1.0 / float(len(scores)) for _ in scores]
    return [value / total for value in exps]


def _preferred_action_type(hypothesis_space: HypothesisSpace, claim_threshold: float) -> ActionType:
    global_candidates = hypothesis_space.global_candidate_tiles()
    if not global_candidates:
        return "ask_could"
    win_probability = 1.0 / float(len(global_candidates))
    if len(global_candidates) == 1 or win_probability >= claim_threshold:
        return "ask_is"
    return "ask_could"


def _expected_clue_elimination_metrics(
    player_space,
    clue_match_tiles_by_id,
    tile_id: int,
) -> dict[str, float | int]:
    possible_clue_ids = tuple(player_space.possible_clue_ids)
    clue_count = len(possible_clue_ids)
    if clue_count == 0:
        return {
            "yes_probability": 0.0,
            "no_probability": 0.0,
            "eliminated_if_yes": 0,
            "eliminated_if_no": 0,
            "expected_eliminated_clues": 0.0,
        }

    yes_count = 0
    no_count = 0
    for clue_id in possible_clue_ids:
        matching_tiles = set(clue_match_tiles_by_id.get(clue_id, ()))
        if tile_id in matching_tiles:
            yes_count += 1
        else:
            no_count += 1

    yes_probability = yes_count / float(clue_count)
    no_probability = no_count / float(clue_count)
    eliminated_if_yes = no_count
    eliminated_if_no = yes_count
    expected_eliminated_clues = (yes_probability * eliminated_if_yes) + (no_probability * eliminated_if_no)

    return {
        "yes_probability": yes_probability,
        "no_probability": no_probability,
        "eliminated_if_yes": eliminated_if_yes,
        "eliminated_if_no": eliminated_if_no,
        "expected_eliminated_clues": expected_eliminated_clues,
    }


