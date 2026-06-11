from collections import Counter
import json
from pathlib import Path

from data.board_loader import load_default_board, load_module_templates
from game_model.tokens import GameState
from game_model.types import StructureType, TokenType


def test_default_board_has_108_tiles() -> None:
    board = load_default_board()
    assert len(board.tiles) == 108


def test_each_section_has_18_tiles() -> None:
    board = load_default_board()
    section_counts = Counter(tile.section_id for tile in board.tiles.values())
    assert section_counts == {"A": 18, "B": 18, "C": 18, "D": 18, "E": 18, "F": 18}


def test_templates_define_two_orientations_with_18_tiles_each() -> None:
    templates = load_module_templates()
    for section_id, orientations in templates.items():
        assert set(orientations.keys()) == {"normal", "flipped"}
        assert len(orientations["normal"]) == 18
        assert len(orientations["flipped"]) == 18
        assert section_id in {"A", "B", "C", "D", "E", "F"}


def test_module_template_file_has_no_structures() -> None:
    path = Path("data/module_templates.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for module in payload["modules"]:
        for orientation in ("normal", "flipped"):
            assert "structures" not in module["orientations"][orientation]


def test_structures_come_from_layout_instance() -> None:
    board = load_default_board()
    structure_tiles = [tile for tile in board.tiles.values() if tile.structure_type is not None]
    assert len(structure_tiles) == 6
    by_type = Counter(tile.structure_type for tile in structure_tiles)
    assert by_type[StructureType.STANDING_STONE] == 3
    assert by_type[StructureType.ABANDONED_SHACK] == 3


def test_center_tile_has_six_neighbors() -> None:
    board = load_default_board()
    neighbors = board.neighbors(8, 3)
    assert len(neighbors) == 6


def test_neighbor_rule_matches_documented_offsets() -> None:
    board = load_default_board()
    origin = (8, 3)
    expected = {
        (7, 3),   # left same row
        (9, 3),   # right same row
        (8, 2),   # above same column
        (8, 4),   # below same column
        (7, 2),   # upper-left
        (9, 2),   # upper-right
    }
    actual = {tile.coord for tile in board.neighbors(*origin)}
    assert actual == expected


def test_token_placement_updates_counts() -> None:
    board = load_default_board()
    state = GameState(board=board)
    state.place_token("p1", 1, 1, TokenType.ROUND)
    state.place_token("p2", 1, 1, TokenType.CUBE)
    assert state.token_counts() == {"round": 1, "cube": 1}
