"""
Board recognition module for Cryptid.

This module provides automated board state recognition from screenshots using
terrain classification and optional CNN-based module identification.

Can be replaced with a CLI-based alternative for manual board state input.
"""

from recognition.board_extractor import ExtractedBoard, ExtractedTile, extract_tiles
from recognition.pipeline import MapRecognitionArtifacts, image_to_board_state, recognize_image
from recognition.tile_classifier import TerrainPrediction, classify_terrain, classify_terrain_with_confidence
from recognition.layout_recognizer import (
    LayoutRecognitionResult,
    SlotLayoutPrediction,
    apply_recognized_layout_to_board,
    recognize_layout_from_terrains,
    recognize_layout_with_cnn,
)
from recognition.module_classifier import ModuleClassifier, ModuleCNN, SectionModuleClassification

__all__ = [
    # Board state recognition
    "image_to_board_state",
    "recognize_image",
    "MapRecognitionArtifacts",
    # Terrain classification
    "classify_terrain",
    "classify_terrain_with_confidence",
    "TerrainPrediction",
    # Layout recognition
    "recognize_layout_from_terrains",
    "recognize_layout_with_cnn",
    "apply_recognized_layout_to_board",
    "LayoutRecognitionResult",
    "SlotLayoutPrediction",
    # Module classification
    "ModuleClassifier",
    "ModuleCNN",
    "SectionModuleClassification",
    # Tile extraction
    "extract_tiles",
    "ExtractedBoard",
    "ExtractedTile",
]


