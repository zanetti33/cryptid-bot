from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
import logging
from typing import Optional

from ai.events import PlayerResponseEvent
from ai.inference import PlayerHypothesisSpace, infer_hypothesis_space
from ai.knowledge_update import KnowledgeTracker
from ai.strategy import RecommendedMove, recommend_moves
from ai.types import AICubePlacement, AIDebugState, AIMove, AIResponse, InitialSetup
from game_model.clues import Clue, clues_by_id
from game_model.state import GameSnapshot


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CryptidAIEngine:
    """High-level AI facade for move selection and knowledge updates."""

    _setup: InitialSetup
    _tracker: KnowledgeTracker

    @classmethod
    def from_initial_setup(cls, setup: InitialSetup) -> "CryptidAIEngine":
        tracker = KnowledgeTracker(
            board=setup.board,
            turn_order=setup.turn_order,
            bot_player_id=setup.bot_player_id,
            clues=setup.clues,
            include_inverse_clues=setup.include_inverse_clues,
        )
        return cls(_setup=setup, _tracker=tracker)

    def next_move(self, snapshot: Optional[GameSnapshot] = None, top_k: int = 5) -> Optional[AIMove]:
        current_snapshot = snapshot or self._tracker.current_snapshot()
        logger.debug(
            "[AI][engine] next_move input players=%s board_tiles=%s top_k=%s",
            list(current_snapshot.player_ids()),
            len(current_snapshot.board.tiles),
            top_k,
        )

        bot_valid_tile_ids = self._bot_valid_tile_ids(current_snapshot)
        moves = recommend_moves(
            snapshot=current_snapshot,
            top_k=top_k,
            bot_valid_tile_ids=bot_valid_tile_ids,
        )
        if not moves:
            logger.info("[AI][engine] next_move output no_move")
            return None
        best = moves[0]
        logger.info(
            "[AI][engine] next_move output action=%s tile_id=%s target_player_id=%s score=%.3f confidence=%.3f",
            best.action_type,
            best.tile_id,
            best.target_player_id,
            best.score,
            best.confidence,
        )
        return AIMove(
            action_type=best.action_type,
            tile_id=best.tile_id,
            target_player_id=best.target_player_id,
            score=best.score,
            confidence=best.confidence,
            rationale=best.rationale,
            is_approximate=best.is_approximate,
        )

    def is_cell_valid_for_me(self, tile_id: int) -> bool:
        answered_yes = self._matches_bot_clue(tile_id)
        self.apply_observation(
            PlayerResponseEvent(
                player_id=self._setup.bot_player_id,
                tile_id=tile_id,
                answered_yes=answered_yes,
            )
        )
        return answered_yes

    def answer_for_tile(self, tile_id: int) -> AIResponse:
        answered_yes = self._matches_bot_clue(tile_id)
        rationale = (
            "Tile matches the bot clue; round recorded in the AI model."
            if answered_yes
            else "Tile does not match the bot clue; cube recorded in the AI model."
        )
        self.is_cell_valid_for_me(tile_id)
        return AIResponse(tile_id=tile_id, answered_yes=answered_yes, rationale=rationale)

    def place_least_informative_cube(self) -> AICubePlacement:
        snapshot = self._tracker.current_snapshot()
        candidate_tile_ids = sorted(
            tile.tile_id
            for tile in snapshot.board.tiles.values()
            if not self._matches_bot_clue(tile.tile_id)
        )
        if not candidate_tile_ids:
            raise ValueError("No valid cube placement available for the bot.")

        # Computed once: identical for every candidate tile, independent of which one is being scored.
        current_hypothesis = infer_hypothesis_space(snapshot=snapshot, clues=self._setup.clues)
        current_bot_space = current_hypothesis.by_player().get(self._setup.bot_player_id)

        # If the CSP solve already timed out once for this snapshot, don't let each of the
        # (potentially ~100) per-tile simulated calls below independently re-attempt and
        # re-time-out the same expensive solve - go straight to the cheap local-only path.
        # A zero budget doesn't reliably force an immediate fallback on trivially
        # small searches (the deadline may not be exceeded before the first check);
        # a negative budget guarantees the deadline is already in the past.
        per_tile_time_budget = -1.0 if current_hypothesis.is_approximate else None

        best_tile_id = candidate_tile_ids[0]
        best_score = float("inf")
        best_rationale: Optional[str] = None
        for tile_id in candidate_tile_ids:
            score = self._cube_information_score(
                snapshot=snapshot,
                tile_id=tile_id,
                current_bot_space=current_bot_space,
                time_budget_seconds=per_tile_time_budget,
            )
            if score < best_score or (score == best_score and tile_id < best_tile_id):
                best_tile_id = tile_id
                best_score = score
                best_rationale = (
                    "Chosen among invalid tiles because this cube eliminates the fewest"
                    " currently possible clues for the bot."
                )

        self.apply_observation(
            PlayerResponseEvent(
                player_id=self._setup.bot_player_id,
                tile_id=best_tile_id,
                answered_yes=False,
            )
        )
        return AICubePlacement(tile_id=best_tile_id, score=best_score, rationale=best_rationale)

    def apply_observation(self, event: PlayerResponseEvent) -> None:
        logger.debug(
            "[AI][engine] apply_observation player_id=%s tile_id=%s answered_yes=%s",
            event.player_id,
            event.tile_id,
            event.answered_yes,
        )
        self._tracker.apply_observation(
            player_id=event.player_id,
            tile_id=event.tile_id,
            answered_yes=event.answered_yes,
        )

    def get_debug_state(self) -> AIDebugState:
        hypothesis = self._tracker.rebuild_hypothesis_space()
        by_player = hypothesis.by_player()
        possible_ids = tuple((player_id, space.possible_clue_ids) for player_id, space in by_player.items())
        resolved = tuple(player_id for player_id, space in by_player.items() if space.is_resolved)
        contradictory = tuple(player_id for player_id, space in by_player.items() if space.is_contradictory)
        debug_state = AIDebugState(
            observations=self._tracker.debug_observations(),
            possible_clue_ids_by_player=possible_ids,
            resolved_players=resolved,
            contradictory_players=contradictory,
        )
        logger.debug(
            "[AI][engine] debug_state observations=%s resolved=%s contradictory=%s",
            len(debug_state.observations),
            list(debug_state.resolved_players),
            list(debug_state.contradictory_players),
        )
        return debug_state

    def _base_snapshot(self) -> GameSnapshot:
        return GameSnapshot(board=self._setup.board, turn_order=self._setup.turn_order, bot_player_id=self._setup.bot_player_id)

    def _bot_clue(self) -> Clue:
        if self._setup.clues is not None:
            for clue in self._setup.clues:
                if clue.clue_id == self._setup.bot_clue_id:
                    return clue

        clue_catalog = clues_by_id(include_inverse=self._setup.include_inverse_clues)
        return clue_catalog[self._setup.bot_clue_id]

    def _bot_valid_tile_ids(self, snapshot: GameSnapshot) -> set[int]:
        bot_clue = self._bot_clue()
        return {
            tile.tile_id
            for tile in snapshot.board.tiles.values()
            if bot_clue.matches(tile, snapshot.board)
        }

    def _matches_bot_clue(self, tile_id: int) -> bool:
        my_clue = self._bot_clue()
        tile = self._tile_by_id(tile_id)
        return my_clue.matches(tile, self._setup.board)

    def _cube_information_score(
        self,
        snapshot: GameSnapshot,
        tile_id: int,
        current_bot_space: Optional[PlayerHypothesisSpace],
        time_budget_seconds: Optional[float] = None,
    ) -> float:
        if current_bot_space is None:
            return float("inf")

        simulated_snapshot = self._snapshot_with_bot_observation(snapshot=snapshot, tile_id=tile_id, answered_yes=False)
        hypothesis = infer_hypothesis_space(
            snapshot=simulated_snapshot,
            clues=self._setup.clues,
            time_budget_seconds=time_budget_seconds,
        )
        bot_space = hypothesis.by_player().get(self._setup.bot_player_id)
        if bot_space is None:
            return float("inf")

        eliminated_clues = len(current_bot_space.possible_clue_ids) - len(bot_space.possible_clue_ids)
        return float(eliminated_clues)

    def _snapshot_with_bot_observation(self, snapshot: GameSnapshot, tile_id: int, answered_yes: bool) -> GameSnapshot:
        board = deepcopy(snapshot.board)
        for tile in board.tiles.values():
            tile.cube_tokens = [player_id for player_id in tile.cube_tokens if player_id != self._setup.bot_player_id]
            tile.round_tokens = [player_id for player_id in tile.round_tokens if player_id != self._setup.bot_player_id]

        target_tile = None
        for tile in board.tiles.values():
            if tile.tile_id == tile_id:
                target_tile = tile
                break
        if target_tile is None:
            raise ValueError(f"Unknown tile_id: {tile_id}")

        if answered_yes:
            target_tile.round_tokens.append(self._setup.bot_player_id)
        else:
            target_tile.cube_tokens.append(self._setup.bot_player_id)

        return GameSnapshot(
            board=board,
            turn_order=snapshot.turn_order,
            bot_player_id=snapshot.bot_player_id,
        )

    def _tile_by_id(self, tile_id: int):
        for tile in self._setup.board.tiles.values():
            if tile.tile_id == tile_id:
                return tile
        raise ValueError(f"Unknown tile_id: {tile_id}")



