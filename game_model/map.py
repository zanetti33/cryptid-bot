from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from game_model.types import AnimalTerritory, StructureColor, StructureType, TerrainType

AxialCoord = Tuple[int, int]


@dataclass(slots=True)
class HexTile:
    tile_id: int
    q: int
    r: int
    terrain: TerrainType = TerrainType.UNKNOWN
    animal: Optional[AnimalTerritory] = None
    structure_type: Optional[StructureType] = None
    structure_color: Optional[StructureColor] = None
    section_id: Optional[str] = None
    local_id: Optional[int] = None
    cube_tokens: List[str] = field(default_factory=list)
    round_tokens: List[str] = field(default_factory=list)

    @property
    def coord(self) -> AxialCoord:
        return (self.q, self.r)


@dataclass(slots=True)
class Board:
    tiles: Dict[AxialCoord, HexTile]

    # Neighbors follow module rules: same-row left/right, same-column up/down,
    # and upper-row diagonals left/right.
    _DIRECTIONS: Tuple[AxialCoord, ...] = (
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
        (-1, -1),
        (1, -1),
    )

    def get(self, q: int, r: int) -> Optional[HexTile]:
        return self.tiles.get((q, r))

    def neighbors(self, q: int, r: int) -> List[HexTile]:
        found: List[HexTile] = []
        for dq, dr in self._DIRECTIONS:
            tile = self.tiles.get((q + dq, r + dr))
            if tile is not None:
                found.append(tile)
        return found

    def within_distance(self, origin: AxialCoord, distance: int) -> Iterable[HexTile]:
        if distance < 0:
            return

        if origin not in self.tiles:
            return

        seen: Set[AxialCoord] = {origin}
        queue = deque([(origin, 0)])
        while queue:
            (q, r), steps = queue.popleft()
            tile = self.tiles.get((q, r))
            if tile is not None:
                yield tile
            if steps == distance:
                continue
            for dq, dr in self._DIRECTIONS:
                nxt = (q + dq, r + dr)
                if nxt in seen or nxt not in self.tiles:
                    continue
                seen.add(nxt)
                queue.append((nxt, steps + 1))

    def bounds(self) -> Tuple[int, int]:
        if not self.tiles:
            return (0, 0)
        max_q = max(coord[0] for coord in self.tiles)
        max_r = max(coord[1] for coord in self.tiles)
        return max_q + 1, max_r + 1

    @classmethod
    def rectangular(cls, cols: int = 12, rows: int = 9) -> "Board":
        tiles: Dict[AxialCoord, HexTile] = {}
        tile_id = 0
        for r in range(rows):
            for q in range(cols):
                tiles[(q, r)] = HexTile(tile_id=tile_id, q=q, r=r)
                tile_id += 1
        return cls(tiles=tiles)

