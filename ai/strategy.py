from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple

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
) -> List[RecommendedMove]:
    """Return ranked action candidates for the current board snapshot.

    This first implementation is intentionally heuristic-driven:
    - prefer immediate claim opportunities on tiles without any cube tokens
    - otherwise propose `ask_could` questions to reduce uncertainty
    """
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    current_hypothesis_space = hypothesis_space or infer_hypothesis_space(snapshot=snapshot)
    scored_moves = _build_scored_moves(snapshot=snapshot, hypothesis_space=current_hypothesis_space)
    if not scored_moves:
        return []

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


def _build_scored_moves(snapshot: GameSnapshot, hypothesis_space: HypothesisSpace) -> List[_ScoredMove]:
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

        if cube_count == 0 and tile.tile_id not in bot_cube_tiles:
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
        player_candidates = set(player_space.candidate_tiles)
        player_guaranteed = set(player_space.guaranteed_tiles)

        for tile in snapshot.board.tiles.values():
            if tile.tile_id in target_cubes:
                continue

            round_count = len(tile.round_tokens)
            cube_count = len(tile.cube_tokens)
            total_tokens = round_count + cube_count

            balance = 1.0 - (abs(round_count - cube_count) / float(total_tokens + 1))
            novelty = 1.0 / float(total_tokens + 1)
            if tile.tile_id in player_guaranteed:
                informativeness = 0.2
            elif tile.tile_id in player_candidates:
                informativeness = 1.0
            else:
                informativeness = 0.6

            score = 1.0 + (0.5 * balance) + (0.2 * novelty) + (0.6 * informativeness)

            scored.append(
                _ScoredMove(
                    action_type="ask_could",
                    tile_id=tile.tile_id,
                    target_player_id=target_player,
                    score=score,
                    rationale="High-information check for unresolved tile.",
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

