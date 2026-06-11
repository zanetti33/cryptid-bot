from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from game_model.types import TerrainType


TerrainPalette = Dict[TerrainType, Tuple[int, int, int]]


DEFAULT_TERRAIN_PALETTE: TerrainPalette = {
    TerrainType.FOREST: (65, 120, 70),
    TerrainType.MOUNTAIN: (125, 125, 125),
    TerrainType.WATER: (70, 110, 170),
    TerrainType.DESERT: (185, 165, 95),
    TerrainType.SWAMP: (120, 85, 130),
}


@dataclass(frozen=True, slots=True)
class TerrainPrediction:
    terrain: TerrainType
    distance: float
    confidence: float


def _distance(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def normalize_rgb(rgb_mean: Tuple[int, int, int], target_luminance: float = 128.0) -> Tuple[int, int, int]:
    r, g, b = rgb_mean
    luminance = (r + g + b) / 3.0
    if luminance <= 1e-6:
        return rgb_mean
    scale = target_luminance / luminance
    return (
        int(max(0, min(255, round(r * scale)))),
        int(max(0, min(255, round(g * scale)))),
        int(max(0, min(255, round(b * scale)))),
    )


def classify_terrain_with_confidence(
    rgb_mean: Tuple[int, int, int],
    palette: TerrainPalette | None = None,
    normalize_input: bool = False,
) -> TerrainPrediction:
    palette = palette or DEFAULT_TERRAIN_PALETTE
    sample_rgb = normalize_rgb(rgb_mean) if normalize_input else rgb_mean

    ranked = []
    for terrain, terrain_rgb in palette.items():
        reference_rgb = normalize_rgb(terrain_rgb) if normalize_input else terrain_rgb
        ranked.append((terrain, _distance(sample_rgb, reference_rgb)))
    ranked.sort(key=lambda item: item[1])

    best_terrain, best_distance = ranked[0]
    denominator = sum(1.0 / (distance + 1e-6) for _, distance in ranked)
    confidence = (1.0 / (best_distance + 1e-6)) / denominator
    return TerrainPrediction(terrain=best_terrain, distance=best_distance, confidence=confidence)


def classify_terrain(
    rgb_mean: Tuple[int, int, int],
    palette: TerrainPalette | None = None,
    normalize_input: bool = False,
) -> TerrainType:
    return classify_terrain_with_confidence(
        rgb_mean=rgb_mean,
        palette=palette,
        normalize_input=normalize_input,
    ).terrain

