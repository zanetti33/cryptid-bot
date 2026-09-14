from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from game_model.clues import Clue, build_clue_catalog
from game_model.state import GameSnapshot


logger = logging.getLogger(__name__)

# Above this, the multi-player CSP solve in _globally_feasible_clue_ids_by_player
# is aborted and infer_hypothesis_space() falls back to local-only filtering (see
# docs/AI_STRATEGY.md, criticality #1 - the solve can blow up combinatorially with
# few observations and 4+ players). Comfortably above every measured legitimate
# case (worst measured: 3 players + 48 clues at start of game, ~150ms).
DEFAULT_HYPOTHESIS_TIME_BUDGET_SECONDS = 1.5


class _BacktrackBudgetExceeded(Exception):
    """Internal sentinel: unwinds the backtracking search once its budget is exceeded."""


@dataclass(slots=True, frozen=True)
class PlayerHypothesisSpace:
    player_id: str
    possible_clue_ids: Tuple[str, ...]
    candidate_tiles: Tuple[int, ...]
    guaranteed_tiles: Tuple[int, ...]
    eliminated_tiles: Tuple[int, ...]

    @property
    def is_contradictory(self) -> bool:
        return len(self.possible_clue_ids) == 0

    @property
    def is_resolved(self) -> bool:
        return len(self.possible_clue_ids) == 1


@dataclass(slots=True, frozen=True)
class HypothesisSpace:
    players: Tuple[PlayerHypothesisSpace, ...]
    known_bot_valid_tile_ids: Tuple[int, ...] = ()
    clue_match_tiles_by_id: Dict[str, Tuple[int, ...]] = field(default_factory=dict)
    is_approximate: bool = False
    """True when the CSP time budget was exceeded and per-player possible_clue_ids
    were computed from local (own-observations-only) filtering instead of the full
    multi-player consistency solve. Sound (never under-counts a true candidate or
    over-counts a guaranteed tile) but less complete - see docs/AI_STRATEGY.md."""

    def by_player(self) -> Dict[str, PlayerHypothesisSpace]:
        return {space.player_id: space for space in self.players}

    def unresolved_players(self) -> Tuple[str, ...]:
        return tuple(space.player_id for space in self.players if not space.is_resolved)

    def global_candidate_tiles(self) -> Tuple[int, ...]:
        if not self.players:
            return ()
        candidate_sets = [set(space.candidate_tiles) for space in self.players]
        if not candidate_sets:
            return ()
        global_candidates = set.intersection(*candidate_sets)
        if self.known_bot_valid_tile_ids:
            global_candidates.intersection_update(self.known_bot_valid_tile_ids)
        return tuple(sorted(global_candidates))

    def global_guaranteed_tiles(self) -> Tuple[int, ...]:
        if not self.players:
            return ()
        guaranteed_sets = [set(space.guaranteed_tiles) for space in self.players]
        if not guaranteed_sets:
            return ()
        global_guaranteed = set.intersection(*guaranteed_sets)
        if self.known_bot_valid_tile_ids:
            global_guaranteed.intersection_update(self.known_bot_valid_tile_ids)
        return tuple(sorted(global_guaranteed))


def infer_hypothesis_space(
    snapshot: GameSnapshot,
    clues: Optional[Sequence[Clue]] = None,
    include_inverse_clues: bool = False,
    known_bot_valid_tile_ids: Optional[Iterable[int]] = None,
    time_budget_seconds: Optional[float] = None,
) -> HypothesisSpace:
    """Build per-player clue/tile hypothesis spaces from observed round/cube tokens.

    The bot itself is always included in the hypothesis space as an observed player,
    i.e. its possible clues are inferred from its own token placements exactly like
    any other player – without using the known bot_clue_id. This allows the AI to
    reason about what its opponents can deduce about its hidden information.

    When ``known_bot_valid_tile_ids`` is provided, only the *global* candidate /
    guaranteed tile computations are additionally restricted by the bot's real clue.
    The bot's own per-player hypothesis space is intentionally left untouched.

    ``time_budget_seconds`` bounds the multi-player CSP solve that computes each
    player's globally-feasible clues; ``None`` uses ``DEFAULT_HYPOTHESIS_TIME_BUDGET_SECONDS``.
    If the budget is exceeded, falls back to local-only filtering (own observations
    only, no cross-player consistency) and sets ``HypothesisSpace.is_approximate``.
    """
    logger.debug(
        "[AI][infer] input players=%s board_tiles=%s include_inverse_clues=%s explicit_clues=%s",
        list(snapshot.player_ids()),
        len(snapshot.board.tiles),
        include_inverse_clues,
        clues is not None,
    )
    clue_catalog = tuple(clues) if clues is not None else tuple(build_clue_catalog(include_inverse=include_inverse_clues))
    board = snapshot.board
    all_tile_ids = tuple(sorted(tile.tile_id for tile in board.tiles.values()))

    clue_match_tiles: Dict[str, Set[int]] = {}
    valid_clues: List[Clue] = []
    for clue in clue_catalog:
        match_tiles = {tile.tile_id for tile in board.tiles.values() if clue.matches(tile, board)}
        # Skip clues with empty support on this board instance.
        if not match_tiles:
            continue
        clue_match_tiles[clue.clue_id] = match_tiles
        valid_clues.append(clue)

    cubes_by_player = snapshot.cubes_by_player()
    rounds_by_player = snapshot.rounds_by_player()

    player_ids = _ordered_player_ids(snapshot)
    local_possible_clue_ids_by_player: Dict[str, Tuple[str, ...]] = {}
    for player_id in player_ids:
        cube_tiles = cubes_by_player.get(player_id, set())
        round_tiles = rounds_by_player.get(player_id, set())

        possible_clue_ids: List[str] = []
        for clue in valid_clues:
            matching = clue_match_tiles[clue.clue_id]
            if cube_tiles & matching:
                continue
            if not round_tiles.issubset(matching):
                continue
            possible_clue_ids.append(clue.clue_id)
        local_possible_clue_ids_by_player[player_id] = tuple(sorted(possible_clue_ids))

    effective_budget = (
        DEFAULT_HYPOTHESIS_TIME_BUDGET_SECONDS if time_budget_seconds is None else time_budget_seconds
    )
    deadline = time.monotonic() + effective_budget

    globally_feasible_clue_ids_by_player = _globally_feasible_clue_ids_by_player(
        player_ids=player_ids,
        local_possible_clue_ids_by_player=local_possible_clue_ids_by_player,
        clue_match_tiles=clue_match_tiles,
        deadline=deadline,
    )

    is_approximate = globally_feasible_clue_ids_by_player is None
    if is_approximate:
        logger.warning(
            "[AI][infer] CSP solve exceeded %.2fs budget (players=%s) - falling back to local-only filtering",
            effective_budget,
            len(player_ids),
        )
        feasible_clue_ids_by_player: Dict[str, Set[str]] = {
            player_id: set(local_possible_clue_ids_by_player.get(player_id, ()))
            for player_id in player_ids
        }
    else:
        feasible_clue_ids_by_player = globally_feasible_clue_ids_by_player

    players: List[PlayerHypothesisSpace] = []
    clue_by_id = {clue.clue_id: clue for clue in valid_clues}
    for player_id in player_ids:
        possible_clue_ids = tuple(sorted(feasible_clue_ids_by_player.get(player_id, set())))
        possible_clues = [clue_by_id[clue_id] for clue_id in possible_clue_ids if clue_id in clue_by_id]

        candidate_tiles = _union_tiles(possible_clues, clue_match_tiles)
        guaranteed_tiles = _intersection_tiles(possible_clues, clue_match_tiles)
        eliminated_tiles = tuple(tile_id for tile_id in all_tile_ids if tile_id not in candidate_tiles)

        players.append(
            PlayerHypothesisSpace(
                player_id=player_id,
                possible_clue_ids=tuple(sorted(possible_clue_ids)),
                candidate_tiles=candidate_tiles,
                guaranteed_tiles=guaranteed_tiles,
                eliminated_tiles=eliminated_tiles,
            )
        )

    result = HypothesisSpace(
        players=tuple(players),
        known_bot_valid_tile_ids=tuple(sorted(set(known_bot_valid_tile_ids or ()))),
        clue_match_tiles_by_id={
            clue_id: tuple(sorted(tile_ids))
            for clue_id, tile_ids in clue_match_tiles.items()
        },
        is_approximate=is_approximate,
    )
    logger.debug(
        "[AI][infer] output players=%s unresolved=%s global_candidates=%s global_guaranteed=%s is_approximate=%s",
        len(result.players),
        len(result.unresolved_players()),
        len(result.global_candidate_tiles()),
        len(result.global_guaranteed_tiles()),
        result.is_approximate,
    )
    return result


def _ordered_player_ids(snapshot: GameSnapshot) -> Tuple[str, ...]:
    players = list(snapshot.player_ids())
    if snapshot.bot_player_id and snapshot.bot_player_id not in players:
        players.insert(0, snapshot.bot_player_id)
    return tuple(players)


def _union_tiles(clues: Iterable[Clue], clue_match_tiles: Dict[str, Set[int]]) -> Tuple[int, ...]:
    merged: Set[int] = set()
    for clue in clues:
        merged.update(clue_match_tiles[clue.clue_id])
    return tuple(sorted(merged))


def _intersection_tiles(clues: Sequence[Clue], clue_match_tiles: Dict[str, Set[int]]) -> Tuple[int, ...]:
    if not clues:
        return ()
    intersection: Set[int] = set(clue_match_tiles[clues[0].clue_id])
    for clue in clues[1:]:
        intersection.intersection_update(clue_match_tiles[clue.clue_id])
    return tuple(sorted(intersection))


def _globally_feasible_clue_ids_by_player(
    player_ids: Sequence[str],
    local_possible_clue_ids_by_player: Dict[str, Tuple[str, ...]],
    clue_match_tiles: Dict[str, Set[int]],
    deadline: Optional[float] = None,
) -> Optional[Dict[str, Set[str]]]:
    """Returns None (instead of raising) if the search exceeds ``deadline``
    (a ``time.monotonic()`` value) - the caller decides how to fall back."""
    for player_id in player_ids:
        if not local_possible_clue_ids_by_player.get(player_id):
            return {key: set() for key in player_ids}

    ordered_players = tuple(sorted(player_ids, key=lambda pid: len(local_possible_clue_ids_by_player[pid])))
    feasible_by_player: Dict[str, Set[str]] = {player_id: set() for player_id in player_ids}

    def backtrack(
        index: int,
        used_clues: Set[str],
        intersection: Optional[Set[int]],
        selected_clues: Dict[str, str],
    ) -> None:
        if deadline is not None and time.monotonic() > deadline:
            raise _BacktrackBudgetExceeded()

        if index == len(ordered_players):
            if intersection is not None and len(intersection) == 1:
                for player_id, clue_id in selected_clues.items():
                    feasible_by_player[player_id].add(clue_id)
            return

        player_id = ordered_players[index]
        for clue_id in local_possible_clue_ids_by_player[player_id]:
            if clue_id in used_clues:
                continue
            clue_tiles = clue_match_tiles.get(clue_id, set())
            next_intersection = set(clue_tiles) if intersection is None else (intersection & clue_tiles)
            if not next_intersection:
                continue

            if not _remaining_players_can_match(
                ordered_players=ordered_players,
                start_index=index + 1,
                used_clues=used_clues | {clue_id},
                intersection=next_intersection,
                local_possible_clue_ids_by_player=local_possible_clue_ids_by_player,
                clue_match_tiles=clue_match_tiles,
            ):
                continue

            selected_clues[player_id] = clue_id
            backtrack(index + 1, used_clues | {clue_id}, next_intersection, selected_clues)
            selected_clues.pop(player_id, None)

    try:
        backtrack(index=0, used_clues=set(), intersection=None, selected_clues={})
    except _BacktrackBudgetExceeded:
        return None
    return feasible_by_player


def _remaining_players_can_match(
    ordered_players: Sequence[str],
    start_index: int,
    used_clues: Set[str],
    intersection: Set[int],
    local_possible_clue_ids_by_player: Dict[str, Tuple[str, ...]],
    clue_match_tiles: Dict[str, Set[int]],
) -> bool:
    for idx in range(start_index, len(ordered_players)):
        player_id = ordered_players[idx]
        found = False
        for clue_id in local_possible_clue_ids_by_player[player_id]:
            if clue_id in used_clues:
                continue
            if intersection & clue_match_tiles.get(clue_id, set()):
                found = True
                break
        if not found:
            return False
    return True


