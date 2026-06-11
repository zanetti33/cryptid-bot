from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from PIL import Image

from game_model.map import Board

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAP_RECOGNITION_DATASET_DIR = PROJECT_ROOT / "datasets" / "map_recognition"
MAP_RECOGNITION_IMAGES_DIR = MAP_RECOGNITION_DATASET_DIR / "images"
MAP_RECOGNITION_LABELS_DIR = MAP_RECOGNITION_DATASET_DIR / "labels"
MAP_RECOGNITION_MANIFEST_PATH = MAP_RECOGNITION_DATASET_DIR / "manifest.json"


def sample_id_from_image_name(image_name: str | Path) -> str:
    return Path(image_name).stem


def dataset_image_path(image_name: str | Path) -> Path:
    return MAP_RECOGNITION_IMAGES_DIR / Path(image_name).name


def dataset_label_path(image_name: str | Path) -> Path:
    sample_id = sample_id_from_image_name(image_name)
    return MAP_RECOGNITION_LABELS_DIR / f"{sample_id}.json"


def resolve_image_reference(image_reference: str | Path) -> Path:
    candidate = Path(image_reference)
    if candidate.exists():
        return candidate.resolve()

    dataset_candidate = dataset_image_path(candidate.name)
    if dataset_candidate.exists():
        return dataset_candidate

    raise FileNotFoundError(
        f"Image not found: {image_reference}. Checked both the provided path and {dataset_candidate}."
    )


def iter_dataset_images() -> List[Path]:
    if not MAP_RECOGNITION_IMAGES_DIR.exists():
        return []
    return sorted(path for path in MAP_RECOGNITION_IMAGES_DIR.iterdir() if path.is_file())


def board_to_tile_labels(board: Board) -> List[Dict[str, Any]]:
    tiles: List[Dict[str, Any]] = []
    for tile in sorted(board.tiles.values(), key=lambda item: (item.r, item.q)):
        tiles.append(
            {
                "q": tile.q,
                "r": tile.r,
                "terrain": tile.terrain.value,
                "section_id": tile.section_id,
                "local_id": tile.local_id,
                "animal": tile.animal.value if tile.animal is not None else None,
                "structure_type": tile.structure_type.value if tile.structure_type is not None else None,
                "structure_color": tile.structure_color.value if tile.structure_color is not None else None,
                "tokens": [],
            }
        )
    return tiles


def build_label_payload(
    image_path: str | Path,
    board: Board,
    annotation_status: str = "provisional",
    notes: str = "",
    placements: Iterable[Dict[str, Any]] | None = None,
    structure_markers: Iterable[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    resolved_image_path = resolve_image_reference(image_path)
    relative_image_path = resolved_image_path.relative_to(PROJECT_ROOT).as_posix()
    with Image.open(resolved_image_path) as image:
        image_width, image_height = image.size

    normalized_placements = sorted(list(placements or []), key=lambda item: int(item["slot_id"]))

    normalized_structure_markers = list(structure_markers or [])
    if not normalized_structure_markers:
        for tile in sorted(board.tiles.values(), key=lambda item: (item.section_id or "", item.local_id or 0)):
            if tile.section_id is None or tile.local_id is None or tile.structure_type is None:
                continue
            normalized_structure_markers.append(
                {
                    "section_id": tile.section_id,
                    "local_id": tile.local_id,
                    "structure_type": tile.structure_type.value,
                    "structure_color": tile.structure_color.value if tile.structure_color is not None else None,
                }
            )

    payload: Dict[str, Any] = {
        "schema_version": 1,
        "sample_id": sample_id_from_image_name(resolved_image_path),
        "image_path": relative_image_path,
        "image_size": {
            "width": image_width,
            "height": image_height,
        },
        "annotation_status": annotation_status,
        "board_layout": {
            "placements": normalized_placements,
            "structure_markers": normalized_structure_markers,
        },
        "tiles": board_to_tile_labels(board),
        "notes": notes,
    }
    return payload


def write_label_file(label_path: str | Path, payload: Dict[str, Any]) -> Path:
    destination = Path(label_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination


def build_manifest_payload() -> Dict[str, Any]:
    samples = []
    for image_path in iter_dataset_images():
        label_path = dataset_label_path(image_path)
        sample_id = sample_id_from_image_name(image_path)
        annotation_status = None
        if label_path.exists():
            label_data = json.loads(label_path.read_text(encoding="utf-8"))
            annotation_status = label_data.get("annotation_status")
        samples.append(
            {
                "sample_id": sample_id,
                "image_path": image_path.relative_to(PROJECT_ROOT).as_posix(),
                "label_path": label_path.relative_to(PROJECT_ROOT).as_posix(),
                "annotation_status": annotation_status,
            }
        )
    return {
        "schema_version": 1,
        "dataset": "map_recognition",
        "samples": samples,
    }


def write_manifest(payload: Dict[str, Any] | None = None) -> Path:
    manifest_payload = payload or build_manifest_payload()
    MAP_RECOGNITION_DATASET_DIR.mkdir(parents=True, exist_ok=True)
    MAP_RECOGNITION_MANIFEST_PATH.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    return MAP_RECOGNITION_MANIFEST_PATH


