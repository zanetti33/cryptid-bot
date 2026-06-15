from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True, frozen=True)
class ObservationEvent:
    kind: str


@dataclass(slots=True, frozen=True)
class PlayerResponseEvent(ObservationEvent):
    kind: Literal["player_response"] = "player_response"
    player_id: str = ""
    tile_id: int = 0
    answered_yes: bool = False

