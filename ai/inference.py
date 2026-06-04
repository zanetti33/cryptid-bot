from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from game_model.clues import Clue, build_clue_catalog
from game_model.state import GameSnapshot


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
        return tuple(sorted(set.intersection(*candidate_sets)))

    def global_guaranteed_tiles(self) -> Tuple[int, ...]:
        if not self.players:
            return ()
        guaranteed_sets = [set(space.guaranteed_tiles) for space in self.players]
        if not guaranteed_sets:
            return ()
        return tuple(sorted(set.intersection(*guaranteed_sets)))


def infer_hypothesis_space(
    snapshot: GameSnapshot,
    clues: Optional[Sequence[Clue]] = None,
    include_inverse_clues: bool = False,
) -> HypothesisSpace:
    """Build per-player clue/tile hypothesis spaces from observed round/cube tokens."""
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

    players: List[PlayerHypothesisSpace] = []
    for player_id in _ordered_player_ids(snapshot):
        cube_tiles = cubes_by_player.get(player_id, set())
        round_tiles = rounds_by_player.get(player_id, set())

        possible_clues: List[Clue] = []
        possible_clue_ids: List[str] = []
        for clue in valid_clues:
            matching = clue_match_tiles[clue.clue_id]
            if cube_tiles & matching:
                continue
            if not round_tiles.issubset(matching):
                continue
            possible_clues.append(clue)
            possible_clue_ids.append(clue.clue_id)

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

    return HypothesisSpace(players=tuple(players))


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

