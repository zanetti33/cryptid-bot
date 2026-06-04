from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from game_model.map import Board
from game_model.types import TokenType


@dataclass(slots=True, frozen=True)
class ObservedToken:
    player_id: str
    tile_id: int
    token_type: TokenType


@dataclass(slots=True)
class GameSnapshot:
    """State snapshot used by the bot decision engine.

    The board geometry and tile metadata are stable across turns.
    Snapshot updates are represented by the current token placements.
    """

    board: Board
    turn_order: Tuple[str, ...] = ()
    bot_player_id: Optional[str] = None

    def observed_tokens(self) -> List[ObservedToken]:
        tokens: List[ObservedToken] = []
        for tile in self.board.tiles.values():
            tokens.extend(
                ObservedToken(player_id=player_id, tile_id=tile.tile_id, token_type=TokenType.CUBE)
                for player_id in tile.cube_tokens
            )
            tokens.extend(
                ObservedToken(player_id=player_id, tile_id=tile.tile_id, token_type=TokenType.ROUND)
                for player_id in tile.round_tokens
            )
        return tokens

    def player_ids(self) -> Tuple[str, ...]:
        ordered: List[str] = list(self.turn_order)
        known: Set[str] = set(ordered)
        for token in self.observed_tokens():
            if token.player_id not in known:
                ordered.append(token.player_id)
                known.add(token.player_id)
        return tuple(ordered)

    def cubes_by_player(self) -> Dict[str, Set[int]]:
        cubes: Dict[str, Set[int]] = {}
        for token in self.observed_tokens():
            if token.token_type is not TokenType.CUBE:
                continue
            cubes.setdefault(token.player_id, set()).add(token.tile_id)
        return cubes

    def rounds_by_player(self) -> Dict[str, Set[int]]:
        rounds: Dict[str, Set[int]] = {}
        for token in self.observed_tokens():
            if token.token_type is not TokenType.ROUND:
                continue
            rounds.setdefault(token.player_id, set()).add(token.tile_id)
        return rounds

