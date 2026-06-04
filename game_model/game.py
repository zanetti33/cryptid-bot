from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional, Tuple

from game_model.clues import Clue, clues_by_id
from game_model.map import Board, HexTile
from game_model.tokens import GameState, TokenPlacement
from game_model.types import TokenType


class GamePhase(str, Enum):
    SETUP = "setup"
    PLAYING = "playing"
    RESOLVED = "resolved"


@dataclass(slots=True, frozen=True)
class PlayerState:
    player_id: str
    clue_id: str


@dataclass(slots=True, frozen=True)
class AskCouldResult:
    asked_tile_id: int
    target_player_id: str
    answered_yes: bool
    target_token: TokenPlacement
    asker_cube_token: Optional[TokenPlacement]


@dataclass(slots=True, frozen=True)
class AskIsResult:
    asked_tile_id: int
    winner_id: Optional[str]
    disproved_by_player_id: Optional[str]
    placements: Tuple[TokenPlacement, ...]


class Game:
    """Core turn-resolution engine for Cryptid interactions."""

    def __init__(
        self,
        board: Board,
        players: Iterable[PlayerState],
        clue_catalog: Optional[Dict[str, Clue]] = None,
    ) -> None:

        player_list = tuple(players)
        if len(player_list) < 2:
            raise ValueError("A game requires at least two players")

        self._players = player_list
        self._player_index = {player.player_id: index for index, player in enumerate(self._players)}
        if len(self._player_index) != len(self._players):
            raise ValueError("Duplicate player_id in game setup")

        self._clues = clue_catalog or clues_by_id(include_inverse=True)
        for player in self._players:
            if player.clue_id not in self._clues:
                raise ValueError(f"Unknown clue_id for player {player.player_id}: {player.clue_id}")

        self.state = GameState(board=board, current_player_id=self._players[0].player_id, turn_index=0)
        self.phase = GamePhase.PLAYING
        self.winner_id: Optional[str] = None

    @property
    def players(self) -> Tuple[PlayerState, ...]:
        return self._players

    @property
    def current_player_id(self) -> str:
        current = self.state.current_player_id
        if current is not None:
            return current
        return self._players[self.state.turn_index % len(self._players)].player_id

    def ask_could(
        self,
        asker_id: str,
        target_player_id: str,
        tile_id: int,
        asker_cube_tile_id: Optional[int] = None,
    ) -> AskCouldResult:
        self._require_playing()
        self._require_current_turn(asker_id)
        self._require_known_player(target_player_id)

        if asker_id == target_player_id:
            raise ValueError("asker_id and target_player_id must be different")

        asked_tile = self._tile_by_id(tile_id)
        target_says_yes = self._clue_matches(target_player_id, asked_tile)

        if target_says_yes:
            target_token = self.state.place_token_by_tile_id(target_player_id, tile_id, TokenType.ROUND)
            self._advance_turn()
            return AskCouldResult(
                asked_tile_id=tile_id,
                target_player_id=target_player_id,
                answered_yes=True,
                target_token=target_token,
                asker_cube_token=None,
            )

        target_token = self.state.place_token_by_tile_id(target_player_id, tile_id, TokenType.CUBE)

        resolved_cube_tile_id = asker_cube_tile_id
        if resolved_cube_tile_id is None:
            resolved_cube_tile_id = self._find_invalid_tile_for_player(asker_id)

        if resolved_cube_tile_id is None:
            raise ValueError(f"Player {asker_id} has no invalid tile for a forced cube placement")

        self._validate_token_consistency(asker_id, resolved_cube_tile_id, TokenType.CUBE)
        asker_cube_token = self.state.place_token_by_tile_id(asker_id, resolved_cube_tile_id, TokenType.CUBE)
        self._advance_turn()

        return AskCouldResult(
            asked_tile_id=tile_id,
            target_player_id=target_player_id,
            answered_yes=False,
            target_token=target_token,
            asker_cube_token=asker_cube_token,
        )

    def ask_is(self, asker_id: str, tile_id: int) -> AskIsResult:
        self._require_playing()
        self._require_current_turn(asker_id)

        placements = [self._place_validated(asker_id, tile_id, TokenType.ROUND)]

        for player_id in self._players_after(asker_id):
            if self._clue_matches(player_id, self._tile_by_id(tile_id)):
                placements.append(self._place_validated(player_id, tile_id, TokenType.ROUND))
                continue

            placements.append(self._place_validated(player_id, tile_id, TokenType.CUBE))
            self._advance_turn()
            return AskIsResult(
                asked_tile_id=tile_id,
                winner_id=None,
                disproved_by_player_id=player_id,
                placements=tuple(placements),
            )

        self.phase = GamePhase.RESOLVED
        self.winner_id = asker_id
        return AskIsResult(
            asked_tile_id=tile_id,
            winner_id=asker_id,
            disproved_by_player_id=None,
            placements=tuple(placements),
        )

    def validate_token_consistency(self, player_id: str, tile_id: int, token_type: TokenType) -> bool:
        self._require_known_player(player_id)
        self._validate_token_consistency(player_id, tile_id, token_type)
        return True

    def to_dict(self) -> Dict[str, object]:
        return {
            "phase": self.phase.value,
            "winner_id": self.winner_id,
            "players": [
                {
                    "player_id": player.player_id,
                    "clue_id": player.clue_id,
                }
                for player in self._players
            ],
            "state": self.state.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        payload: Dict[str, object],
        board: Board,
        clue_catalog: Optional[Dict[str, Clue]] = None,
    ) -> "Game":
        raw_players = payload.get("players", []) if isinstance(payload, dict) else []
        if not isinstance(raw_players, list):
            raise ValueError("Invalid serialized game: 'players' must be a list")

        players = []
        for entry in raw_players:
            if not isinstance(entry, dict):
                raise ValueError("Invalid serialized game: player entry must be an object")
            players.append(PlayerState(player_id=str(entry["player_id"]), clue_id=str(entry["clue_id"])))

        game = cls(board=board, players=players, clue_catalog=clue_catalog)

        raw_state = payload.get("state", {}) if isinstance(payload, dict) else {}
        if not isinstance(raw_state, dict):
            raise ValueError("Invalid serialized game: 'state' must be an object")
        game.state = GameState.from_dict(raw_state, board=board)

        raw_phase = payload.get("phase", GamePhase.PLAYING.value) if isinstance(payload, dict) else GamePhase.PLAYING.value
        game.phase = GamePhase(str(raw_phase))
        winner = payload.get("winner_id") if isinstance(payload, dict) else None
        game.winner_id = str(winner) if winner is not None else None
        return game

    def _place_validated(self, player_id: str, tile_id: int, token_type: TokenType) -> TokenPlacement:
        self._validate_token_consistency(player_id, tile_id, token_type)
        return self.state.place_token_by_tile_id(player_id, tile_id, token_type)

    def _validate_token_consistency(self, player_id: str, tile_id: int, token_type: TokenType) -> None:
        tile = self._tile_by_id(tile_id)
        matches = self._clue_matches(player_id, tile)

        if token_type is TokenType.ROUND and not matches:
            raise ValueError(f"Invalid round token: tile {tile_id} is incompatible with clue of {player_id}")
        if token_type is TokenType.CUBE and matches:
            raise ValueError(f"Invalid cube token: tile {tile_id} matches clue of {player_id}")

    def _clue_matches(self, player_id: str, tile: HexTile) -> bool:
        clue_id = self._clue_id_for(player_id)
        return self._clues[clue_id].matches(tile, self.state.board)

    def _clue_id_for(self, player_id: str) -> str:
        self._require_known_player(player_id)
        return self._players[self._player_index[player_id]].clue_id

    def _players_after(self, player_id: str) -> Tuple[str, ...]:
        start = self._player_index[player_id]
        ordered = []
        for offset in range(1, len(self._players)):
            ordered.append(self._players[(start + offset) % len(self._players)].player_id)
        return tuple(ordered)

    def _find_invalid_tile_for_player(self, player_id: str) -> Optional[int]:
        for tile in sorted(self.state.board.tiles.values(), key=lambda item: item.tile_id):
            if not self._clue_matches(player_id, tile):
                return tile.tile_id
        return None

    def _tile_by_id(self, tile_id: int) -> HexTile:
        for tile in self.state.board.tiles.values():
            if tile.tile_id == tile_id:
                return tile
        raise ValueError(f"Unknown tile_id: {tile_id}")

    def _require_playing(self) -> None:
        if self.phase is not GamePhase.PLAYING:
            raise ValueError(f"Cannot play actions while game phase is '{self.phase.value}'")

    def _require_known_player(self, player_id: str) -> None:
        if player_id not in self._player_index:
            raise ValueError(f"Unknown player_id: {player_id}")

    def _require_current_turn(self, player_id: str) -> None:
        if player_id != self.current_player_id:
            raise ValueError(f"It is not {player_id}'s turn")

    def _advance_turn(self) -> None:
        self.state.turn_index += 1
        next_player = self._players[self.state.turn_index % len(self._players)].player_id
        self.state.current_player_id = next_player

