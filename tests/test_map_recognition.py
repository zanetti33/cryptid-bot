from pathlib import Path
import json

from PIL import Image, ImageEnhance

from data.board_loader import load_layout_instance, load_module_templates, load_slots
from map_recognition.dataset import dataset_image_path, dataset_label_path
from map_recognition.layout_recognizer import recognize_layout_from_terrains
from map_recognition.pipeline import image_to_board_state
from map_recognition.tile_classifier import classify_terrain
from game_model.types import TerrainType


def _image_path(name: str) -> Path:
    return dataset_image_path(name)


def test_image_pipeline_returns_complete_board() -> None:
    board = image_to_board_state(_image_path("screenshot_example.png"))
    assert len(board.tiles) == 108


def test_image_pipeline_assigns_terrain_values() -> None:
    board = image_to_board_state(_image_path("image_easy.png"))
    terrains = {tile.terrain for tile in board.tiles.values()}
    assert TerrainType.UNKNOWN not in terrains
    assert len(terrains) >= 2


def test_image_pipeline_keeps_section_metadata() -> None:
    board = image_to_board_state(_image_path("image_hard.png"))
    sections = {tile.section_id for tile in board.tiles.values()}
    assert sections == {"A", "B", "C", "D", "E", "F"}


def test_classification_stable_with_brightness_scaling() -> None:
    forest = (65, 120, 70)
    dark_forest = tuple(int(channel * 0.7) for channel in forest)
    bright_forest = tuple(min(255, int(channel * 1.3)) for channel in forest)

    assert classify_terrain(forest, normalize_input=True) == TerrainType.FOREST
    assert classify_terrain(dark_forest, normalize_input=True) == TerrainType.FOREST
    assert classify_terrain(bright_forest, normalize_input=True) == TerrainType.FOREST


def test_pipeline_robust_to_brightness_variants(tmp_path: Path) -> None:
    source = Image.open(_image_path("image_easy.png")).convert("RGB")
    baseline_board = image_to_board_state(_image_path("image_easy.png"))
    baseline_by_coord = {coord: tile.terrain for coord, tile in baseline_board.tiles.items()}

    for factor in (0.7, 1.3):
        variant_path = tmp_path / f"image_easy_brightness_{factor}.png"
        ImageEnhance.Brightness(source).enhance(factor).save(variant_path)

        variant_board = image_to_board_state(variant_path)
        matches = sum(
            1
            for coord, terrain in baseline_by_coord.items()
            if variant_board.tiles[coord].terrain == terrain
        )
        assert matches >= 75


def test_layout_recognition_recovers_known_layout_from_templates() -> None:
    templates = load_module_templates()
    slots = load_slots()
    layout = load_layout_instance()

    terrains_by_coord = {}
    for placement in layout["placements"]:
        slot = slots[placement["slot_id"]]
        section_tiles = templates[placement["section_id"]][placement["orientation"]]
        for tile_data in section_tiles.values():
            q = slot["origin_q"] + int(tile_data["q"])
            r = slot["origin_r"] + int(tile_data["r"])
            terrains_by_coord[(q, r)] = tile_data["terrain"]

    result = recognize_layout_from_terrains(terrains_by_coord, templates=templates, slots=slots)
    by_slot = {prediction.slot_id: prediction for prediction in result.slot_predictions}

    for placement in layout["placements"]:
        prediction = by_slot[placement["slot_id"]]
        assert prediction.section_id == placement["section_id"]
        assert prediction.orientation == placement["orientation"]
        assert prediction.score == 1.0


def test_pipeline_can_write_debug_overlay(tmp_path: Path) -> None:
    debug_path = tmp_path / "debug_overlay.png"
    board = image_to_board_state(_image_path("screenshot_example.png"), debug_output_path=debug_path)
    assert len(board.tiles) == 108
    assert debug_path.exists()
    assert debug_path.stat().st_size > 0


def test_bundled_dataset_images_have_matching_labels() -> None:
    for image_name in ("screenshot_example.png", "image_easy.png", "image_hard.png"):
        label_path = dataset_label_path(image_name)
        assert label_path.exists()

        payload = json.loads(label_path.read_text(encoding="utf-8"))
        assert payload["image_path"].endswith(image_name)
        assert payload["annotation_status"] in {"provisional", "verified"}
        assert len(payload["board_layout"]["placements"]) == 6
        assert len(payload["tiles"]) == 108


