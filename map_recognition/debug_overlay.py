from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from PIL import Image, ImageDraw

from map_recognition.board_extractor import ExtractedBoard
from map_recognition.layout_recognizer import LayoutRecognitionResult
from map_recognition.tile_classifier import TerrainPrediction
from rules.types import TerrainType

Coord = Tuple[int, int]


TERRAIN_COLORS: Dict[TerrainType, Tuple[int, int, int]] = {
    TerrainType.FOREST: (34, 139, 34),
    TerrainType.MOUNTAIN: (120, 120, 120),
    TerrainType.WATER: (30, 110, 220),
    TerrainType.DESERT: (230, 200, 120),
    TerrainType.SWAMP: (140, 90, 150),
    TerrainType.UNKNOWN: (255, 255, 255),
}


def save_debug_overlay(
    image_path: str | Path,
    extracted: ExtractedBoard,
    terrain_predictions: Dict[Coord, TerrainPrediction],
    layout: LayoutRecognitionResult,
    output_path: str | Path,
) -> Path:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    for sample in extracted.tiles:
        prediction = terrain_predictions.get((sample.q, sample.r))
        if prediction is None:
            continue

        cx, cy = sample.center
        color = TERRAIN_COLORS[prediction.terrain]
        confidence_text = f"{prediction.confidence:.2f}"

        draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), outline=(0, 0, 0), fill=color)
        draw.text((cx + 6, cy - 6), confidence_text, fill=(255, 255, 255))

    for prediction in layout.slot_predictions:
        slot_tiles = [
            tile
            for tile in extracted.tiles
            if prediction.origin_q <= tile.q < prediction.origin_q + 6
            and prediction.origin_r <= tile.r < prediction.origin_r + 3
        ]
        if not slot_tiles:
            continue

        xs = [tile.center[0] for tile in slot_tiles]
        ys = [tile.center[1] for tile in slot_tiles]
        x0 = max(0, min(xs) - 18)
        y0 = max(0, min(ys) - 18)
        x1 = min(image.width - 1, max(xs) + 18)
        y1 = min(image.height - 1, max(ys) + 18)

        draw.rectangle((x0, y0, x1, y1), outline=(255, 255, 255), width=2)
        label = (
            f"slot {prediction.slot_id}: "
            f"{prediction.section_id}/{prediction.orientation} "
            f"({prediction.score:.2f})"
        )
        draw.text((x0 + 4, max(0, y0 - 14)), label, fill=(255, 255, 255))

    summary = f"layout score: {layout.average_score:.3f}"
    draw.text((8, 8), summary, fill=(255, 255, 255))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output

