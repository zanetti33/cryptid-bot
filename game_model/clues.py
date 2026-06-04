from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, List, Protocol, Sequence

from data.clue_loader import load_clue_definitions
from game_model.map import Board, HexTile
from game_model.types import AnimalTerritory, StructureColor, StructureType, TerrainType


class TargetCategory(str, Enum):
    TERRAIN = "terrain"
    ANIMAL = "animal"
    STRUCTURE_TYPE = "structure_type"
    STRUCTURE_COLOR = "structure_color"


class Predicate(Protocol):
    def matches(self, tile: HexTile, board: Board) -> bool:
        ...


@dataclass(slots=True, frozen=True)
class AtomPredicate:
    target: TargetCategory
    value: TerrainType | AnimalTerritory | StructureType | StructureColor
    distance: int

    def matches(self, tile: HexTile, board: Board) -> bool:
        return any(self._target_matches(sample) for sample in _tiles_within(board, tile, self.distance))

    def _target_matches(self, tile: HexTile) -> bool:
        if self.target is TargetCategory.TERRAIN:
            return tile.terrain is self.value
        if self.target is TargetCategory.ANIMAL:
            return tile.animal is self.value
        if self.target is TargetCategory.STRUCTURE_TYPE:
            return tile.structure_type is self.value
        if self.target is TargetCategory.STRUCTURE_COLOR:
            return tile.structure_color is self.value
        raise ValueError(f"Unsupported target category: {self.target}")


@dataclass(slots=True, frozen=True)
class AndPredicate:
    args: Sequence[Predicate]

    def matches(self, tile: HexTile, board: Board) -> bool:
        return all(arg.matches(tile, board) for arg in self.args)


@dataclass(slots=True, frozen=True)
class OrPredicate:
    args: Sequence[Predicate]

    def matches(self, tile: HexTile, board: Board) -> bool:
        return any(arg.matches(tile, board) for arg in self.args)


@dataclass(slots=True, frozen=True)
class NotPredicate:
    arg: Predicate

    def matches(self, tile: HexTile, board: Board) -> bool:
        return not self.arg.matches(tile, board)


@dataclass(slots=True, frozen=True)
class Clue:
    clue_id: str
    text: str
    predicate: Predicate

    def matches(self, tile: HexTile, board: Board) -> bool:
        return self.predicate.matches(tile, board)

    def inverted(self) -> "Clue":
        if self.clue_id.startswith("not_"):
            clue_id = self.clue_id[4:]
            text = self.text.replace("Not ", "", 1)
            predicate = _unwrap_not(self.predicate)
            return Clue(clue_id=clue_id, text=text, predicate=predicate)

        return Clue(
            clue_id=f"not_{self.clue_id}",
            text=f"Not {self.text}",
            predicate=NotPredicate(arg=self.predicate),
        )


def _unwrap_not(predicate: Predicate) -> Predicate:
    if isinstance(predicate, NotPredicate):
        return predicate.arg
    return predicate


def _tiles_within(board: Board, tile: HexTile, distance: int) -> Iterable[HexTile]:
    if distance < 0:
        raise ValueError("distance must be >= 0")
    return board.within_distance(tile.coord, distance=distance)


def _parse_predicate(payload: dict[str, Any]) -> Predicate:
    op = payload["op"]

    if op == "atom":
        target = TargetCategory(payload["target"])
        distance = int(payload["distance"])
        value = _parse_target_value(target=target, raw_value=payload["value"])
        return AtomPredicate(target=target, value=value, distance=distance)

    if op == "and":
        return AndPredicate(args=[_parse_predicate(arg) for arg in payload["args"]])

    if op == "or":
        return OrPredicate(args=[_parse_predicate(arg) for arg in payload["args"]])

    if op == "not":
        return NotPredicate(arg=_parse_predicate(payload["arg"]))

    raise ValueError(f"Unsupported predicate operation: {op}")


def _parse_target_value(
    target: TargetCategory,
    raw_value: str,
) -> TerrainType | AnimalTerritory | StructureType | StructureColor:
    if target is TargetCategory.TERRAIN:
        return TerrainType(raw_value)
    if target is TargetCategory.ANIMAL:
        return AnimalTerritory(raw_value)
    if target is TargetCategory.STRUCTURE_TYPE:
        return StructureType(raw_value)
    if target is TargetCategory.STRUCTURE_COLOR:
        return StructureColor(raw_value)
    raise ValueError(f"Unsupported target category: {target}")


def build_base_clues() -> List[Clue]:
    definitions = load_clue_definitions()
    clues: List[Clue] = []
    for item in definitions:
        clues.append(
            Clue(
                clue_id=item["clue_id"],
                text=item["text"],
                predicate=_parse_predicate(item["predicate"]),
            )
        )
    return clues


def build_clue_catalog(include_inverse: bool = False) -> List[Clue]:
    base = build_base_clues()
    if not include_inverse:
        return base
    return [*base, *[clue.inverted() for clue in base]]


def clues_by_id(include_inverse: bool = False) -> dict[str, Clue]:
    return {clue.clue_id: clue for clue in build_clue_catalog(include_inverse=include_inverse)}

