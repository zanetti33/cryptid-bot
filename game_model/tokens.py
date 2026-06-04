from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from game_model.map import Board, HexTile
from game_model.types import TokenType


@dataclass(slots=True)
class TokenPlacement:
    player_id: str
    tile_id: int
    token_type: TokenType


@dataclass(slots=True)
class GameState:
    board: Board
    current_player_id: Optional[str] = None
    turn_index: int = 0

    def place_token(self, player_id: str, q: int, r: int, token_type: TokenType) -> TokenPlacement:
        tile = self.board.get(q, r)
        if tile is None:
            raise ValueError(f"Cannot place token: missing tile at {(q, r)}")

        if token_type is TokenType.ROUND:
            tile.round_tokens.append(player_id)
        elif token_type is TokenType.CUBE:
            tile.cube_tokens.append(player_id)
        else:
            raise ValueError(f"Unsupported token type: {token_type}")

        return TokenPlacement(player_id=player_id, tile_id=tile.tile_id, token_type=token_type)

    def place_token_by_tile_id(self, player_id: str, tile_id: int, token_type: TokenType) -> TokenPlacement:
        tile = self._tile_by_id(tile_id)
        return self.place_token(player_id=player_id, q=tile.q, r=tile.r, token_type=token_type)

    def token_counts(self) -> Dict[str, int]:
        round_count = 0
        cube_count = 0
        for tile in self.board.tiles.values():
            round_count += len(tile.round_tokens)
            cube_count += len(tile.cube_tokens)
        return {"round": round_count, "cube": cube_count}

    def to_dict(self) -> Dict[str, object]:
        tiles = []
        for tile in sorted(self.board.tiles.values(), key=lambda item: item.tile_id):
            if not tile.round_tokens and not tile.cube_tokens:
                continue
            tiles.append(
                {
                    "tile_id": tile.tile_id,
                    "round_tokens": list(tile.round_tokens),
                    "cube_tokens": list(tile.cube_tokens),
                }
            )

        return {
            "current_player_id": self.current_player_id,
            "turn_index": self.turn_index,
            "tiles": tiles,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object], board: Board) -> "GameState":
        state = cls(
            board=board,
            current_player_id=payload.get("current_player_id") if isinstance(payload, dict) else None,
            turn_index=int(payload.get("turn_index", 0)) if isinstance(payload, dict) else 0,
        )
        state._clear_tokens()

        raw_tiles = payload.get("tiles", []) if isinstance(payload, dict) else []
        if not isinstance(raw_tiles, list):
            raise ValueError("Invalid serialized game state: 'tiles' must be a list")

        for entry in raw_tiles:
            if not isinstance(entry, dict):
                raise ValueError("Invalid serialized game state: tile entry must be an object")
            tile = state._tile_by_id(int(entry["tile_id"]))
            round_tokens = entry.get("round_tokens", [])
            cube_tokens = entry.get("cube_tokens", [])
            if not isinstance(round_tokens, list) or not isinstance(cube_tokens, list):
                raise ValueError("Invalid serialized game state: token lists must be arrays")

            tile.round_tokens.extend(str(player_id) for player_id in round_tokens)
            tile.cube_tokens.extend(str(player_id) for player_id in cube_tokens)

        return state

    def _tile_by_id(self, tile_id: int) -> HexTile:
        for tile in self.board.tiles.values():
            if tile.tile_id == tile_id:
                return tile
        raise ValueError(f"Cannot place token: missing tile_id {tile_id}")

    def _clear_tokens(self) -> None:
        for tile in self.board.tiles.values():
            tile.round_tokens.clear()
            tile.cube_tokens.clear()

