from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import logging
from typing import List, Optional, Sequence, Tuple

from ai.inference import HypothesisSpace, infer_hypothesis_space
from ai.types import ObservationRecord
from game_model.clues import Clue, build_clue_catalog
from game_model.map import Board
from game_model.state import GameSnapshot


logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class KnowledgeUpdateResult:
    hypothesis_space: HypothesisSpace
    observations: Tuple[ObservationRecord, ...]


class KnowledgeTracker:
    """Incremental knowledge state for the AI.

    The tracker keeps a history of yes/no answers and can rebuild a fresh
    hypothesis space when needed. This keeps the implementation simple and
    deterministic while still exposing an incremental API.
    """

    def __init__(
        self,
        board: Board,
        turn_order: Sequence[str],
        bot_player_id: str,
        clues: Optional[Sequence[Clue]] = None,
        include_inverse_clues: bool = True,
    ) -> None:
        self._board = board
        self._turn_order = tuple(turn_order)
        self._bot_player_id = bot_player_id
        self._clues = tuple(clues) if clues is not None else tuple(build_clue_catalog(include_inverse=include_inverse_clues))
        self._observations: List[ObservationRecord] = []

    def apply_observation(self, player_id: str, tile_id: int, answered_yes: bool) -> KnowledgeUpdateResult:
        logger.debug(
            "[AI][knowledge] apply_observation player_id=%s tile_id=%s answered_yes=%s before_count=%s",
            player_id,
            tile_id,
            answered_yes,
            len(self._observations),
        )
        self._observations = [
            observation
            for observation in self._observations
            if not (observation.player_id == player_id and observation.tile_id == tile_id)
        ]
        self._observations.append(
            ObservationRecord(player_id=player_id, tile_id=tile_id, answered_yes=answered_yes)
        )
        hypothesis = self.rebuild_hypothesis_space()
        logger.debug(
            "[AI][knowledge] after_observation count=%s unresolved_players=%s",
            len(self._observations),
            list(hypothesis.unresolved_players()),
        )
        return KnowledgeUpdateResult(hypothesis_space=hypothesis, observations=tuple(self._observations))

    def rebuild_hypothesis_space(self) -> HypothesisSpace:
        snapshot = self._snapshot_from_observations()
        logger.debug(
            "[AI][knowledge] rebuild_hypothesis observations=%s board_tiles=%s",
            len(self._observations),
            len(snapshot.board.tiles),
        )
        return infer_hypothesis_space(snapshot=snapshot, clues=self._clues)

    def debug_observations(self) -> Tuple[ObservationRecord, ...]:
        return tuple(self._observations)

    def current_snapshot(self) -> GameSnapshot:
        return self._snapshot_from_observations()

    def _snapshot_from_observations(self) -> GameSnapshot:
        board = deepcopy(self._board)
        snapshot = GameSnapshot(board=board, turn_order=self._turn_order, bot_player_id=self._bot_player_id)
        for observation in self._observations:
            tile = board.get(*self._tile_coord_by_id(observation.tile_id))
            if tile is None:
                continue
            if observation.answered_yes:
                tile.round_tokens.append(observation.player_id)
            else:
                tile.cube_tokens.append(observation.player_id)
        return snapshot

    def _tile_coord_by_id(self, tile_id: int) -> Tuple[int, int]:
        for coord, tile in self._board.tiles.items():
            if tile.tile_id == tile_id:
                return coord
        raise ValueError(f"Unknown tile_id: {tile_id}")


