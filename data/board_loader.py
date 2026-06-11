from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from game_model.map import Board, HexTile
from game_model.types import AnimalTerritory, StructureColor, StructureType, TerrainType

DATA_DIR = Path(__file__).resolve().parent


def _load_json(file_name: str) -> Dict[str, Any]:
    path = DATA_DIR / file_name
    return json.loads(path.read_text(encoding="utf-8"))


def _terrain_from_code(code: str, legend: Dict[str, str]) -> TerrainType:
    terrain_name = legend[code]
    return TerrainType(terrain_name)


def _parse_orientation_tiles(
    section_id: str,
    orientation_data: Dict[str, Any],
    terrain_legend: Dict[str, str],
) -> Dict[int, Dict[str, Any]]:
    rows: List[str] = orientation_data["rows"]
    if len(rows) != 3:
        raise ValueError(f"Section {section_id}: expected 3 rows per orientation")

    tiles: Dict[int, Dict[str, Any]] = {}
    local_id = 1
    for r, row in enumerate(rows):
        if len(row) != 6:
            raise ValueError(f"Section {section_id}: expected 6 cells per row")
        for q, code in enumerate(row):
            tiles[local_id] = {
                "q": q,
                "r": r,
                "terrain": _terrain_from_code(code, terrain_legend),
                "animal": None,
                "structure_type": None,
                "structure_color": None,
            }
            local_id += 1

    for animal_marker in orientation_data.get("animals", []):
        marker_local_id = int(animal_marker["local_id"])
        tiles[marker_local_id]["animal"] = AnimalTerritory(animal_marker["animal"])

    return tiles


def load_module_templates() -> Dict[str, Dict[str, Dict[int, Dict[str, Any]]]]:
    payload = _load_json("module_templates.json")
    legend: Dict[str, str] = payload["terrain_legend"]

    templates: Dict[str, Dict[str, Dict[int, Dict[str, Any]]]] = {}
    for module in payload["modules"]:
        section_id = module["section_id"]
        templates[section_id] = {
            "normal": _parse_orientation_tiles(section_id, module["orientations"]["normal"], legend),
            "flipped": _parse_orientation_tiles(section_id, module["orientations"]["flipped"], legend),
        }
    return templates


def load_slots() -> Dict[int, Dict[str, int]]:
    payload = _load_json("board_slots.json")
    slots: Dict[int, Dict[str, int]] = {}
    for slot in payload["slots"]:
        slots[int(slot["slot_id"])] = {
            "origin_q": int(slot["origin_q"]),
            "origin_r": int(slot["origin_r"]),
        }
    return slots


def load_layout_instance() -> Dict[str, Any]:
    payload = _load_json("game_layout_instance.json")

    placements: List[Dict[str, Any]] = []
    for placement in payload["placements"]:
        orientation = placement["orientation"]
        if orientation not in {"normal", "flipped"}:
            raise ValueError(f"Unsupported orientation: {orientation}")
        placements.append(
            {
                "slot_id": int(placement["slot_id"]),
                "section_id": placement["section_id"],
                "orientation": orientation,
            }
        )

    structure_markers: List[Dict[str, Any]] = []
    for marker in payload.get("structure_markers", []):
        structure_markers.append(
            {
                "section_id": marker["section_id"],
                "local_id": int(marker["local_id"]),
                "structure_type": StructureType(marker["structure_type"]),
                "structure_color": StructureColor(marker["structure_color"]),
            }
        )

    return {"placements": placements, "structure_markers": structure_markers}


def build_board_from_templates() -> Board:
    templates = load_module_templates()
    slots = load_slots()
    layout = load_layout_instance()
    placements = layout["placements"]
    structure_markers = layout["structure_markers"]

    tiles = {}
    tile_id = 0
    seen_sections = set()
    seen_slots = set()
    section_local_index: Dict[tuple[str, int], HexTile] = {}

    for placement in placements:
        slot_id = placement["slot_id"]
        section_id = placement["section_id"]
        orientation = placement["orientation"]

        if section_id in seen_sections:
            raise ValueError(f"Duplicated section placement: {section_id}")
        if slot_id in seen_slots:
            raise ValueError(f"Duplicated slot placement: {slot_id}")

        seen_sections.add(section_id)
        seen_slots.add(slot_id)

        slot_origin = slots[slot_id]
        section_tiles = templates[section_id][orientation]

        if len(section_tiles) != 18:
            raise ValueError(f"Section {section_id} orientation {orientation} must have 18 tiles")

        for local_id, tile_data in section_tiles.items():
            q = slot_origin["origin_q"] + tile_data["q"]
            r = slot_origin["origin_r"] + tile_data["r"]
            coord = (q, r)
            if coord in tiles:
                raise ValueError(f"Overlapping coordinate in composed board: {coord}")

            tile = HexTile(
                tile_id=tile_id,
                q=q,
                r=r,
                terrain=tile_data["terrain"],
                animal=tile_data["animal"],
                structure_type=None,
                structure_color=None,
                section_id=section_id,
                local_id=local_id,
            )
            tiles[coord] = tile
            section_local_index[(section_id, local_id)] = tile
            tile_id += 1

    for marker in structure_markers:
        key = (marker["section_id"], marker["local_id"])
        tile = section_local_index.get(key)
        if tile is None:
            raise ValueError(f"Structure marker points to unknown tile: {key}")
        if tile.structure_type is not None:
            raise ValueError(f"Duplicate structure marker on tile: {key}")
        tile.structure_type = marker["structure_type"]
        tile.structure_color = marker["structure_color"]

    if len(tiles) != 108:
        raise ValueError(f"Expected 108 tiles, found {len(tiles)}")

    return Board(tiles=tiles)


def load_default_board() -> Board:
    return build_board_from_templates()
