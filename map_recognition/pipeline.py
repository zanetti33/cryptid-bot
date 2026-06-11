from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from data.board_loader import load_module_templates, load_slots
from map_recognition.board_extractor import ExtractedBoard, extract_tiles
from map_recognition.debug_overlay import save_debug_overlay
from map_recognition.layout_recognizer import (
    LayoutRecognitionResult,
    apply_recognized_layout_to_board,
    recognize_layout_from_terrains,
    recognize_layout_with_cnn,
)
from map_recognition.module_classifier import ModuleClassifier
from map_recognition.tile_classifier import TerrainPrediction, classify_terrain_with_confidence
from game_model.map import Board
from game_model.types import TerrainType

Coord = Tuple[int, int]


@dataclass(frozen=True, slots=True)
class MapRecognitionArtifacts:
    layout: LayoutRecognitionResult
    terrain_predictions: Dict[Coord, TerrainPrediction]


def image_to_board_state(
    image_path: str | Path,
    normalize_light: bool = True,
    normalize_terrain: bool = True,
    debug_output_path: str | Path | None = None,
    use_cnn: bool = False,
    cnn_model_path: str | Path | None = None,
    cnn_weight: float = 0.5,
) -> Board:
    board, artifacts, extracted = _recognize_map(
        image_path=image_path,
        normalize_light=normalize_light,
        normalize_terrain=normalize_terrain,
        use_cnn=use_cnn,
        cnn_model_path=cnn_model_path,
        cnn_weight=cnn_weight,
    )

    if debug_output_path is not None:
        save_debug_overlay(
            image_path=image_path,
            extracted=extracted,
            terrain_predictions=artifacts.terrain_predictions,
            layout=artifacts.layout,
            output_path=debug_output_path,
        )
    return board


def recognize_image(
    image_path: str | Path,
    normalize_light: bool = True,
    normalize_terrain: bool = True,
    use_cnn: bool = False,
    cnn_model_path: str | Path | None = None,
    cnn_weight: float = 0.5,
) -> tuple[Board, MapRecognitionArtifacts]:
    board, artifacts, _ = _recognize_map(
        image_path=image_path,
        normalize_light=normalize_light,
        normalize_terrain=normalize_terrain,
        use_cnn=use_cnn,
        cnn_model_path=cnn_model_path,
        cnn_weight=cnn_weight,
    )
    return board, artifacts


def _recognize_map(
    image_path: str | Path,
    normalize_light: bool,
    normalize_terrain: bool,
    use_cnn: bool = False,
    cnn_model_path: str | Path | None = None,
    cnn_weight: float = 0.5,
) -> tuple[Board, MapRecognitionArtifacts, ExtractedBoard]:
    templates = load_module_templates()
    slots = load_slots()
    cols = max(slot["origin_q"] for slot in slots.values()) + 6
    rows = max(slot["origin_r"] for slot in slots.values()) + 3

    board = Board.rectangular(cols=cols, rows=rows)
    extracted = extract_tiles(
        image_path=image_path,
        cols=cols,
        rows=rows,
        normalize_light=normalize_light,
    )

    terrains_by_coord: Dict[Coord, TerrainType] = {}
    terrain_predictions: Dict[Coord, TerrainPrediction] = {}
    for sample in extracted.tiles:
        tile = board.get(sample.q, sample.r)
        if tile is None:
            continue

        prediction = classify_terrain_with_confidence(
            sample.rgb_mean,
            normalize_input=normalize_terrain,
        )
        terrain_predictions[(sample.q, sample.r)] = prediction
        terrains_by_coord[(sample.q, sample.r)] = prediction.terrain
        tile.terrain = prediction.terrain

    # Choose layout recognition strategy
    if use_cnn:
        # Try to use CNN-based recognition (hybrid with terrain matching)
        classifier = None
        if cnn_model_path is not None and Path(cnn_model_path).exists():
            try:
                classifier = ModuleClassifier(model_path=cnn_model_path)
            except Exception as e:
                print(f"⚠️  Failed to load CNN model: {e}, falling back to terrain-only matching")

        layout_result = recognize_layout_with_cnn(
            image_path=image_path,
            terrains_by_coord=terrains_by_coord,
            classifier=classifier,
            templates=templates,
            slots=slots,
            cnn_weight=cnn_weight,
        )
    else:
        # Use terrain-only matching (original method)
        layout_result = recognize_layout_from_terrains(
            terrains_by_coord=terrains_by_coord,
            templates=templates,
            slots=slots,
        )

    apply_recognized_layout_to_board(
        board=board,
        recognition=layout_result,
        templates=templates,
    )

    artifacts = MapRecognitionArtifacts(
        layout=layout_result,
        terrain_predictions=terrain_predictions,
    )
    return board, artifacts, extracted
