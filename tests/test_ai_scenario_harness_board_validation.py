from ai.scenario_harness import build_board_for_scenario, scenario_definition_from_dict


def test_scenario_definition_rejects_rectangular_board_kind() -> None:
    payload = {
        "scenario_id": "invalid-rectangular",
        "board": {
            "kind": "rectangular",
            "cols": 2,
            "rows": 2,
        },
        "players": [
            {"player_id": "bot", "clue_id": "within_two_bear_territory"},
            {"player_id": "p1", "clue_id": "terrain_pair_forest_desert"},
        ],
        "turn_order": ["bot", "p1"],
        "bot_player_id": "bot",
    }

    try:
        scenario_definition_from_dict(payload)
    except ValueError as exc:
        assert str(exc) == "board.kind must be either 'default_layout' or 'placements'."
    else:
        raise AssertionError("Expected ValueError for rectangular board kind")


def test_board_structures_override_default_layout_structure_positions() -> None:
    scenario = scenario_definition_from_dict(
        {
            "scenario_id": "structures-override",
            "board": {
                "kind": "default_layout",
                "structures": [
                    {
                        "tile_id": 0,
                        "structure_type": "standing_stone",
                        "structure_color": "white",
                    },
                    {
                        "tile_id": 1,
                        "structure_type": "abandoned_shack",
                        "structure_color": "blue",
                    },
                ],
            },
            "players": [
                {"player_id": "bot", "clue_id": "within_two_bear_territory"},
                {"player_id": "p1", "clue_id": "terrain_pair_forest_desert"},
            ],
            "turn_order": ["bot", "p1"],
            "bot_player_id": "bot",
        }
    )

    board = build_board_for_scenario(scenario.board)
    tiles_by_id = {tile.tile_id: tile for tile in board.tiles.values()}

    assert tiles_by_id[0].structure_type == "standing_stone"
    assert tiles_by_id[0].structure_color == "white"
    assert tiles_by_id[1].structure_type == "abandoned_shack"
    assert tiles_by_id[1].structure_color == "blue"

    structure_tiles = [tile.tile_id for tile in board.tiles.values() if tile.structure_type is not None]
    assert structure_tiles == [0, 1]


def test_board_structures_can_target_section_and_local_id() -> None:
    scenario = scenario_definition_from_dict(
        {
            "scenario_id": "structures-section-local",
            "board": {
                "kind": "placements",
                    "include_structure_markers": False,
                "placements": [
                    {"slot_id": 1, "section_id": "D", "orientation": "flipped"},
                    {"slot_id": 2, "section_id": "F", "orientation": "flipped"},
                    {"slot_id": 3, "section_id": "B", "orientation": "normal"},
                    {"slot_id": 4, "section_id": "C", "orientation": "flipped"},
                    {"slot_id": 5, "section_id": "A", "orientation": "normal"},
                    {"slot_id": 6, "section_id": "E", "orientation": "normal"},
                ],
                "structures": [
                    {
                        "section_id": "D",
                        "local_id": 2,
                        "structure_type": "abandoned_shack",
                        "structure_color": "blue",
                    }
                ],
            },
            "players": [
                {"player_id": "bot", "clue_id": "within_two_bear_territory"},
                {"player_id": "p1", "clue_id": "terrain_pair_forest_desert"},
            ],
            "turn_order": ["bot", "p1"],
            "bot_player_id": "bot",
        }
    )

    board = build_board_for_scenario(scenario.board)
    matching_tiles = [
        tile for tile in board.tiles.values() if tile.section_id == "D" and tile.local_id == 2
    ]

    assert len(matching_tiles) == 1
    assert matching_tiles[0].structure_type == "abandoned_shack"
    assert matching_tiles[0].structure_color == "blue"


