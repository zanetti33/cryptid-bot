from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from PIL import Image

from data.board_loader import load_module_templates, load_slots
from recognition.module_classifier import ModuleClassifier, SectionModuleClassification
from game_model.map import Board
from game_model.types import TerrainType

Coord = Tuple[int, int]
SectionId = str
Orientation = str


@dataclass(frozen=True, slots=True)
class SlotLayoutPrediction:
    slot_id: int
    origin_q: int
    origin_r: int
    section_id: SectionId
    orientation: Orientation
    matched_tiles: int
    total_tiles: int
    cnn_confidence: float = 0.0  # Confidence from CNN classifier (0.0 if not used)

    @property
    def score(self) -> float:
        if self.total_tiles == 0:
            return 0.0
        return self.matched_tiles / self.total_tiles

    @property
    def combined_score(self, cnn_weight: float = 0.5) -> float:
        """Combine terrain matching score with CNN confidence."""
        terrain_score = self.score
        return (1 - cnn_weight) * terrain_score + cnn_weight * self.cnn_confidence


@dataclass(frozen=True, slots=True)
class LayoutRecognitionResult:
    slot_predictions: Tuple[SlotLayoutPrediction, ...]

    @property
    def total_matches(self) -> int:
        return sum(prediction.matched_tiles for prediction in self.slot_predictions)

    @property
    def total_tiles(self) -> int:
        return sum(prediction.total_tiles for prediction in self.slot_predictions)

    @property
    def average_score(self) -> float:
        if self.total_tiles == 0:
            return 0.0
        return self.total_matches / self.total_tiles


def recognize_layout_from_terrains(
    terrains_by_coord: Dict[Coord, TerrainType],
    templates: Dict[str, Dict[str, Dict[int, Dict[str, object]]]] | None = None,
    slots: Dict[int, Dict[str, int]] | None = None,
) -> LayoutRecognitionResult:
    templates = templates or load_module_templates()
    slots = slots or load_slots()

    section_ids = sorted(templates.keys())
    slot_ids = sorted(slots.keys())
    if len(section_ids) != len(slot_ids):
        raise ValueError("Number of sections and slots must match for layout recognition")

    candidate_matches: Dict[int, Dict[Tuple[SectionId, Orientation], int]] = {}
    for slot_id in slot_ids:
        origin_q = slots[slot_id]["origin_q"]
        origin_r = slots[slot_id]["origin_r"]
        per_candidate: Dict[Tuple[SectionId, Orientation], int] = {}
        for section_id in section_ids:
            for orientation in ("normal", "flipped"):
                section_tiles = templates[section_id][orientation]
                matches = 0
                for tile_data in section_tiles.values():
                    q = origin_q + int(tile_data["q"])
                    r = origin_r + int(tile_data["r"])
                    terrain = terrains_by_coord.get((q, r), TerrainType.UNKNOWN)
                    if terrain == tile_data["terrain"]:
                        matches += 1
                per_candidate[(section_id, orientation)] = matches
        candidate_matches[slot_id] = per_candidate

    best_total_matches = -1
    best_predictions: List[SlotLayoutPrediction] = []

    for sections_per_slot in _section_assignments(section_ids, len(slot_ids)):
        for orientations in product(("normal", "flipped"), repeat=len(slot_ids)):
            total_matches = 0
            current_predictions: List[SlotLayoutPrediction] = []
            for index, slot_id in enumerate(slot_ids):
                section_id = sections_per_slot[index]
                orientation = orientations[index]
                matches = candidate_matches[slot_id][(section_id, orientation)]
                total_tiles = len(templates[section_id][orientation])
                total_matches += matches
                current_predictions.append(
                    SlotLayoutPrediction(
                        slot_id=slot_id,
                        origin_q=slots[slot_id]["origin_q"],
                        origin_r=slots[slot_id]["origin_r"],
                        section_id=section_id,
                        orientation=orientation,
                        matched_tiles=matches,
                        total_tiles=total_tiles,
                    )
                )

            if total_matches > best_total_matches:
                best_total_matches = total_matches
                best_predictions = current_predictions

    return LayoutRecognitionResult(slot_predictions=tuple(best_predictions))


def apply_recognized_layout_to_board(
    board: Board,
    recognition: LayoutRecognitionResult,
    templates: Dict[str, Dict[str, Dict[int, Dict[str, object]]]] | None = None,
) -> None:
    templates = templates or load_module_templates()

    # Structures are recognized in a separate stage; clear stale values.
    for tile in board.tiles.values():
        tile.structure_type = None
        tile.structure_color = None

    for prediction in recognition.slot_predictions:
        section_tiles = templates[prediction.section_id][prediction.orientation]
        for local_id, tile_data in section_tiles.items():
            q = prediction.origin_q + int(tile_data["q"])
            r = prediction.origin_r + int(tile_data["r"])
            tile = board.get(q, r)
            if tile is None:
                continue
            tile.section_id = prediction.section_id
            tile.local_id = int(local_id)
            tile.animal = tile_data["animal"]


def recognize_layout_with_cnn(
    image_path: str | Path,
    terrains_by_coord: Dict[Coord, TerrainType],
    classifier: Optional[ModuleClassifier] = None,
    templates: Dict[str, Dict[str, Dict[int, Dict[str, object]]]] | None = None,
    slots: Dict[int, Dict[str, int]] | None = None,
    extract_module_patches_fn=None,
    cnn_weight: float = 0.5,
) -> LayoutRecognitionResult:
    """
    Recognize board layout using both CNN and terrain pattern matching.

    This hybrid approach:
    1. Extracts module patches from the image
    2. Uses CNN to classify each patch (if classifier is provided)
    3. Combines CNN predictions with terrain matching scores

    Args:
        image_path: Path to the board screenshot.
        terrains_by_coord: Dictionary of terrain predictions already extracted.
        classifier: ModuleClassifier instance. If None, falls back to terrain-only matching.
        templates: Module templates.
        slots: Board slot definitions.
        extract_module_patches_fn: Function to extract patches (optional, for batch processing).
        cnn_weight: Weight for CNN confidence in combined score (0.5 = equal weight).

    Returns:
        LayoutRecognitionResult with hybrid predictions.
    """
    templates = templates or load_module_templates()
    slots = slots or load_slots()

    section_ids = sorted(templates.keys())
    slot_ids = sorted(slots.keys())
    if len(section_ids) != len(slot_ids):
        raise ValueError("Number of sections and slots must match")

    # Get CNN predictions if classifier is available
    cnn_predictions: Dict[int, SectionModuleClassification] | None = None
    if classifier is not None:
        try:
            cnn_predictions = _get_cnn_predictions_for_slots(
                image_path, slots, classifier, extract_module_patches_fn
            )
        except Exception as e:
            print(f"⚠️  CNN prediction failed ({e}), falling back to terrain matching only")
            cnn_predictions = None

    # Compute terrain matching scores for all candidates
    candidate_matches: Dict[int, Dict[Tuple[SectionId, Orientation], int]] = {}
    for slot_id in slot_ids:
        origin_q = slots[slot_id]["origin_q"]
        origin_r = slots[slot_id]["origin_r"]
        per_candidate: Dict[Tuple[SectionId, Orientation], int] = {}
        for section_id in section_ids:
            for orientation in ("normal", "flipped"):
                section_tiles = templates[section_id][orientation]
                matches = 0
                for tile_data in section_tiles.values():
                    q = origin_q + int(tile_data["q"])
                    r = origin_r + int(tile_data["r"])
                    terrain = terrains_by_coord.get((q, r), TerrainType.UNKNOWN)
                    if terrain == tile_data["terrain"]:
                        matches += 1
                per_candidate[(section_id, orientation)] = matches
        candidate_matches[slot_id] = per_candidate

    # Find best assignment combining terrain matching and CNN
    best_total_score = -float("inf")
    best_predictions: List[SlotLayoutPrediction] = []

    for sections_per_slot in _section_assignments(section_ids, len(slot_ids)):
        for orientations in product(("normal", "flipped"), repeat=len(slot_ids)):
            total_score = 0.0
            current_predictions: List[SlotLayoutPrediction] = []

            for index, slot_id in enumerate(slot_ids):
                section_id = sections_per_slot[index]
                orientation = orientations[index]
                matches = candidate_matches[slot_id][(section_id, orientation)]
                total_tiles = len(templates[section_id][orientation])

                # Get CNN confidence for this prediction
                cnn_conf = 0.0
                if cnn_predictions and slot_id in cnn_predictions:
                    cnn_pred = cnn_predictions[slot_id]
                    if cnn_pred.section_id == section_id and cnn_pred.orientation == orientation:
                        cnn_conf = cnn_pred.confidence

                # Compute combined score
                terrain_score = matches / total_tiles if total_tiles > 0 else 0.0
                combined_score = (1 - cnn_weight) * terrain_score + cnn_weight * cnn_conf
                total_score += combined_score

                current_predictions.append(
                    SlotLayoutPrediction(
                        slot_id=slot_id,
                        origin_q=slots[slot_id]["origin_q"],
                        origin_r=slots[slot_id]["origin_r"],
                        section_id=section_id,
                        orientation=orientation,
                        matched_tiles=matches,
                        total_tiles=total_tiles,
                        cnn_confidence=cnn_conf,
                    )
                )

            if total_score > best_total_score:
                best_total_score = total_score
                best_predictions = current_predictions

    return LayoutRecognitionResult(slot_predictions=tuple(best_predictions))


def _get_cnn_predictions_for_slots(
    image_path: str | Path,
    slots: Dict[int, Dict[str, int]],
    classifier: ModuleClassifier,
    extract_module_patches_fn=None,
) -> Dict[int, SectionModuleClassification]:
    """
    Get CNN predictions for each slot by extracting patches and classifying them.

    Args:
        image_path: Path to the board screenshot.
        slots: Board slot definitions.
        classifier: ModuleClassifier instance.
        extract_module_patches_fn: Optional function to extract patches (for testing).

    Returns:
        Dictionary mapping slot_id to SectionModuleClassification.
    """
    image = Image.open(image_path)
    image_array = np.asarray(image)

    predictions: Dict[int, SectionModuleClassification] = {}

    # For each slot, estimate a patch region and classify it
    # This is a simplified version; ideally we'd use precise pixel coordinates
    for slot_id, slot_info in sorted(slots.items()):
        try:
            # Estimate patch region for this slot
            # Using the slot position and a fixed patch size
            patch = _extract_patch_for_slot(image_array, slot_id, slots)

            if patch is not None:
                # Classify the patch
                prediction = classifier.classify_from_array(patch, input_size=224)
                predictions[slot_id] = prediction
        except Exception as e:
            print(f"⚠️  Failed to classify slot {slot_id}: {e}")

    return predictions


def _extract_patch_for_slot(
    image_array: np.ndarray,
    slot_id: int,
    slots: Dict[int, Dict[str, int]],
    patch_size: int = 224,
) -> Optional[np.ndarray]:
    """
    Extract a patch from the image corresponding to a specific slot.

    This is a simplified version that estimates the patch region based on
    slot position. In production, you'd want more precise pixel coordinates.

    Args:
        image_array: The full board image as numpy array.
        slot_id: Which slot to extract.
        slots: Slot definitions.
        patch_size: Size of patch to extract.

    Returns:
        Numpy array of shape (patch_size, patch_size, 3) or None if failed.
    """
    if slot_id not in slots:
        return None

    slot = slots[slot_id]
    origin_q = slot["origin_q"]
    origin_r = slot["origin_r"]

    # This is a very rough estimate; ideally we'd have exact pixel bounds for each slot
    # We estimate based on typical hex grid spacing
    h, w = image_array.shape[:2]

    # Rough estimation of hex tile pixel size
    hex_width_px = w / 12  # Assuming ~12 columns
    hex_height_px = h / 9  # Assuming ~9 rows

    # Compute center of this slot (18 tiles per slot arranged in 6x3)
    center_x = int((origin_q + 3) * hex_width_px)
    center_y = int((origin_r + 1.5) * hex_height_px)

    # Extract square patch
    x0 = max(0, center_x - patch_size // 2)
    y0 = max(0, center_y - patch_size // 2)
    x1 = min(w, x0 + patch_size)
    y1 = min(h, y0 + patch_size)

    # Adjust if cut off
    if x1 - x0 < patch_size:
        x0 = max(0, x1 - patch_size)
    if y1 - y0 < patch_size:
        y0 = max(0, y1 - patch_size)

    x1 = min(w, x0 + patch_size)
    y1 = min(h, y0 + patch_size)

    if x1 <= x0 or y1 <= y0:
        return None

    patch = image_array[y0:y1, x0:x1]

    # Pad if necessary
    if patch.shape[0] < patch_size or patch.shape[1] < patch_size:
        pad_top = (patch_size - patch.shape[0]) // 2
        pad_left = (patch_size - patch.shape[1]) // 2
        patch = np.pad(
            patch,
            ((pad_top, patch_size - patch.shape[0] - pad_top),
             (pad_left, patch_size - patch.shape[1] - pad_left),
             (0, 0)),
            mode="edge"
        )

    return patch


def _section_assignments(section_ids: Iterable[SectionId], count: int) -> Iterable[Tuple[SectionId, ...]]:
    section_list = list(section_ids)
    if count != len(section_list):
        raise ValueError("Section count mismatch")
    if count == 0:
        yield tuple()
        return

    def backtrack(available: List[SectionId], current: List[SectionId]) -> Iterable[Tuple[SectionId, ...]]:
        if not available:
            yield tuple(current)
            return
        for index, section_id in enumerate(available):
            next_available = available[:index] + available[index + 1 :]
            current.append(section_id)
            yield from backtrack(next_available, current)
            current.pop()

    yield from backtrack(section_list, [])

