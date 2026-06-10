from spa_recognition.backend.api import SpaRecognitionApi


def _warning_codes(result_dict):
    return {warning["code"] for warning in result_dict["warnings"]}


def _default_board_layout():
    return [
        {"slot_id": 1, "section_id": "C", "orientation": "normal"},
        {"slot_id": 2, "section_id": "A", "orientation": "flipped"},
        {"slot_id": 3, "section_id": "F", "orientation": "normal"},
        {"slot_id": 4, "section_id": "B", "orientation": "normal"},
        {"slot_id": 5, "section_id": "E", "orientation": "flipped"},
        {"slot_id": 6, "section_id": "D", "orientation": "normal"},
    ]


def test_spa_catalog_returns_board_and_clues_catalogs() -> None:
    api = SpaRecognitionApi()
    result = api.post("/catalog", {"session_id": "catalog"}).to_dict()

    assert "board_layout_catalog" in result["data"]
    assert "clues_catalog" in result["data"]
    assert len(result["data"]["clues_catalog"]) > 0


def test_spa_setup_and_map_flow_updates_session_phase() -> None:
    api = SpaRecognitionApi()

    setup_result = api.post("/setup", {
        "session_id": "s1",
        "player_ids": ["alpha", "beta", "gamma"],
        "turn_order": ["alpha", "beta", "gamma"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    }).to_dict()

    assert setup_result["session"]["phase"] == "board_layout"
    assert setup_result["session"]["setup"]["bot_player_id"] == "alpha"
    assert setup_result["session"]["setup"]["bot_clue_id"] == "terrain_pair_forest_desert"
    assert setup_result["data"]["board_layout_catalog"]["sections"] == ["A", "B", "C", "D", "E", "F"]
    assert len(setup_result["data"]["clues_catalog"]) > 0

    board_layout_result = api.post("/board-layout", {
        "session_id": "s1",
        "placements": _default_board_layout(),
    }).to_dict()

    assert board_layout_result["session"]["phase"] == "map"
    assert board_layout_result["session"]["board_layout_state"]["is_complete"] is True
    assert len(board_layout_result["session"]["board_layout_state"]["board_tiles"]) == 108
    assert board_layout_result["session"]["board_layout_state"]["board_tiles"][0]["terrain"] in {
        "forest", "mountain", "water", "desert", "swamp"
    }

    map_result = api.post("/map", {
        "session_id": "s1",
        "observed_tokens": [
            {"tile_id": 0, "player_id": "alpha", "token_type": "cube"},
            {"tile_id": 1, "player_id": "beta", "token_type": "round"},
        ],
    }).to_dict()

    assert map_result["session"]["phase"] == "structures"
    assert len(map_result["session"]["map_state"]["observed_tokens"]) == 2


def test_spa_payload_is_permissive_and_returns_warnings() -> None:
    api = SpaRecognitionApi()

    setup_result = api.post("/setup", {"session_id": "s2", "player_ids": "bad"}).to_dict()
    assert "SETUP_FIELD_INVALID" in _warning_codes(setup_result)

    board_layout_result = api.post("/board-layout", {
        "session_id": "s2",
        "placements": [
            {"slot_id": 1, "section_id": "A", "orientation": "normal"},
            {"slot_id": 2, "section_id": "A", "orientation": "flipped"},
        ],
    }).to_dict()
    layout_codes = _warning_codes(board_layout_result)
    assert "BOARD_LAYOUT_DUPLICATE_SECTION" in layout_codes
    assert "BOARD_LAYOUT_INCOMPLETE" in layout_codes

    map_result = api.post("/map", {
        "session_id": "s2",
        "observed_tokens": [
            {"tile_id": -1, "player_id": "p1", "token_type": "round"},
            {"tile_id": 0, "player_id": "", "token_type": "round"},
            {"tile_id": 1, "player_id": "p2", "token_type": "triangle"},
        ],
    }).to_dict()

    codes = _warning_codes(map_result)
    assert "TOKEN_TILE_OUT_OF_RANGE" in codes
    assert "TOKEN_PLAYER_MISSING" in codes
    assert "TOKEN_TYPE_UNKNOWN" in codes


def test_spa_structures_and_clues_are_stored() -> None:
    api = SpaRecognitionApi()
    api.post(
        "/setup",
        {
            "session_id": "s3",
            "player_ids": ["alpha"],
            "turn_order": ["alpha"],
            "bot_player_id": "alpha",
            "bot_clue_id": "terrain_pair_forest_desert",
        },
    )
    api.post("/board-layout", {"session_id": "s3", "placements": _default_board_layout()})
    api.post("/map", {"session_id": "s3"})

    structures_result = api.post("/structures", {
        "session_id": "s3",
        "structures": [
            {"tile_id": 0, "structure_type": "standing_stone", "structure_color": "white"},
            {"tile_id": 1, "structure_type": "abandoned_shack", "structure_color": "green"},
        ],
    }).to_dict()

    structure_map = structures_result["session"]["structures_state"]["by_tile_id"]
    assert structure_map["0"]["structure_type"] == "standing_stone"
    assert structure_map["1"]["structure_color"] == "green"

    clues_result = api.post("/clues", {
        "session_id": "s3",
        "by_player_id": {
            "alpha": {"notes": ["possible clue A"]},
        },
    }).to_dict()

    assert clues_result["session"]["phase"] == "review"
    assert clues_result["session"]["clues_state"]["by_player_id"]["alpha"]["notes"] == ["possible clue A"]


def test_spa_recalculate_returns_hypothesis_space_and_moves() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s4",
        "player_ids": ["alpha", "beta"],
        "turn_order": ["alpha", "beta"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    })
    api.post("/board-layout", {
        "session_id": "s4",
        "placements": _default_board_layout(),
    })
    api.post("/map", {
        "session_id": "s4",
        "observed_tokens": [
            {"tile_id": 0, "player_id": "alpha", "token_type": "cube"},
            {"tile_id": 3, "player_id": "beta", "token_type": "round"},
        ],
    })

    recalc_result = api.post("/recalculate", {"session_id": "s4", "top_k": 3}).to_dict()

    assert "hypothesis_space" in recalc_result["data"]
    assert "recommended_moves" in recalc_result["data"]
    assert len(recalc_result["data"]["recommended_moves"]) <= 3

