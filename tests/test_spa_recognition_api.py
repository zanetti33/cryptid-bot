from spa_recognition.backend.api import SpaRecognitionApi


def _warning_codes(result_dict):
    return {warning["code"] for warning in result_dict["warnings"]}


def _default_board_layout():
    return [
        {"slot_id": 1, "section_id": "C", "orientation": "normal"},
        {"slot_id": 2, "section_id": "A", "orientation": "flipped"},
        {"slot_id": 3, "section_id":  "F", "orientation": "normal"},
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


def test_spa_structures_can_be_removed_with_explicit_flag() -> None:
    api = SpaRecognitionApi()
    api.post(
        "/setup",
        {
            "session_id": "s5",
            "player_ids": ["alpha"],
            "turn_order": ["alpha"],
            "bot_player_id": "alpha",
            "bot_clue_id": "terrain_pair_forest_desert",
        },
    )
    api.post("/board-layout", {"session_id": "s5", "placements": _default_board_layout()})
    api.post("/map", {"session_id": "s5"})

    api.post("/structures", {
        "session_id": "s5",
        "structures": [
            {"tile_id": 0, "structure_type": "standing_stone", "structure_color": "white"},
        ],
    })

    removed = api.post("/structures", {
        "session_id": "s5",
        "structures": [
            {"tile_id": 0, "remove": True},
        ],
    }).to_dict()

    assert removed["session"]["structures_state"]["by_tile_id"]["0"] == {
        "structure_type": None,
        "structure_color": None,
    }


def test_board_layout_manual_has_no_auto_structures() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s6",
        "player_ids": ["alpha"],
        "turn_order": ["alpha"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    })

    layout_result = api.post("/board-layout", {
        "session_id": "s6",
        "placements": _default_board_layout(),
        "layout_mode": "manual",
    }).to_dict()

    tiles = layout_result["session"]["board_layout_state"]["board_tiles"]
    assert layout_result["session"]["board_layout_state"]["layout_mode"] == "manual"
    assert all(tile["structure_type"] is None for tile in tiles)


def test_board_layout_bootstrap_auto_places_structures_and_locks_editing() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s7",
        "player_ids": ["alpha"],
        "turn_order": ["alpha"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    })

    layout_result = api.post("/board-layout", {
        "session_id": "s7",
        "placements": _default_board_layout(),
        "layout_mode": "bootstrap",
    }).to_dict()

    tiles = layout_result["session"]["board_layout_state"]["board_tiles"]
    assert layout_result["session"]["board_layout_state"]["layout_mode"] == "bootstrap"
    assert any(tile["structure_type"] is not None for tile in tiles)

    locked_result = api.post("/structures", {
        "session_id": "s7",
        "structures": [
            {"tile_id": 0, "structure_type": "standing_stone", "structure_color": "white"},
        ],
    }).to_dict()
    assert "STRUCTURES_LOCKED" in _warning_codes(locked_result)
    assert locked_result["session"]["structures_state"]["by_tile_id"] == {}


def test_ask_ai_places_a_token_automatically() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s8",
        "player_ids": ["alpha", "beta"],
        "turn_order": ["alpha", "beta"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    })
    api.post("/board-layout", {
        "session_id": "s8",
        "placements": _default_board_layout(),
        "layout_mode": "manual",
    })
    api.post("/map", {"session_id": "s8"})

    ask_result = api.post("/ask-ai", {
        "session_id": "s8",
        "tile_id": 0,
        "player_id": "alpha",
    }).to_dict()

    assert ask_result["data"]["tile_id"] == 0
    assert ask_result["data"]["player_id"] == "alpha"
    assert ask_result["data"]["token_type"] in {"round", "cube"}
    assert len(ask_result["session"]["map_state"]["observed_tokens"]) == 1


def test_map_tokens_overwrite_by_tile_and_player() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s9",
        "player_ids": ["alpha", "beta"],
        "turn_order": ["alpha", "beta"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    })
    api.post("/board-layout", {
        "session_id": "s9",
        "placements": _default_board_layout(),
        "layout_mode": "manual",
    })

    result = api.post("/map", {
        "session_id": "s9",
        "observed_tokens": [
            {"tile_id": 5, "player_id": "alpha", "token_type": "round"},
            {"tile_id": 5, "player_id": "alpha", "token_type": "cube"},
            {"tile_id": 5, "player_id": "beta", "token_type": "round"},
        ],
    }).to_dict()

    tokens = result["session"]["map_state"]["observed_tokens"]
    assert len(tokens) == 2

    by_player = {entry["player_id"]: entry for entry in tokens}
    assert by_player["alpha"]["token_type"] == "cube"
    assert by_player["beta"]["token_type"] == "round"


def test_map_tokens_allow_one_token_per_player_on_same_tile() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s10",
        "player_ids": ["alpha", "beta", "gamma"],
        "turn_order": ["alpha", "beta", "gamma"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    })
    api.post("/board-layout", {
        "session_id": "s10",
        "placements": _default_board_layout(),
        "layout_mode": "manual",
    })

    result = api.post("/map", {
        "session_id": "s10",
        "observed_tokens": [
            {"tile_id": 12, "player_id": "alpha", "token_type": "round"},
            {"tile_id": 12, "player_id": "beta", "token_type": "cube"},
            {"tile_id": 12, "player_id": "gamma", "token_type": "round"},
        ],
    }).to_dict()

    tokens = result["session"]["map_state"]["observed_tokens"]
    assert len(tokens) == 3
    assert {entry["player_id"] for entry in tokens} == {"alpha", "beta", "gamma"}


def test_map_tokens_overwrite_uses_trimmed_player_id_key() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s11",
        "player_ids": ["alpha"],
        "turn_order": ["alpha"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    })
    api.post("/board-layout", {
        "session_id": "s11",
        "placements": _default_board_layout(),
        "layout_mode": "manual",
    })

    result = api.post("/map", {
        "session_id": "s11",
        "observed_tokens": [
            {"tile_id": 3, "player_id": " alpha ", "token_type": "round"},
            {"tile_id": 3, "player_id": "alpha", "token_type": "cube"},
        ],
    }).to_dict()

    tokens = result["session"]["map_state"]["observed_tokens"]
    assert len(tokens) == 1
    assert tokens[0]["player_id"] == "alpha"
    assert tokens[0]["token_type"] == "cube"


def test_ask_ai_overwrites_existing_token_for_same_tile_and_player() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s12",
        "player_ids": ["alpha", "beta"],
        "turn_order": ["alpha", "beta"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    })
    api.post("/board-layout", {
        "session_id": "s12",
        "placements": _default_board_layout(),
        "layout_mode": "manual",
    })
    api.post("/map", {
        "session_id": "s12",
        "observed_tokens": [
            {"tile_id": 0, "player_id": "alpha", "token_type": "round"},
            {"tile_id": 0, "player_id": "beta", "token_type": "cube"},
        ],
    })

    ask_result = api.post("/ask-ai", {
        "session_id": "s12",
        "tile_id": 0,
        "player_id": "alpha",
    }).to_dict()

    tokens = ask_result["session"]["map_state"]["observed_tokens"]
    alpha_tokens = [entry for entry in tokens if entry["player_id"] == "alpha" and entry["tile_id"] == 0]
    beta_tokens = [entry for entry in tokens if entry["player_id"] == "beta" and entry["tile_id"] == 0]

    assert len(alpha_tokens) == 1
    assert len(beta_tokens) == 1
    assert alpha_tokens[0]["token_type"] == ask_result["data"]["token_type"]


def test_ai_answer_endpoint_updates_bot_model_on_map() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s13",
        "player_ids": ["alpha", "beta"],
        "turn_order": ["alpha", "beta"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    })
    api.post("/board-layout", {
        "session_id": "s13",
        "placements": _default_board_layout(),
        "layout_mode": "manual",
    })
    api.post("/map", {"session_id": "s13"})

    result = api.post("/ai-answer", {
        "session_id": "s13",
        "tile_id": 0,
    }).to_dict()

    assert result["data"]["player_id"] == "alpha"
    assert result["data"]["token_type"] in {"round", "cube"}
    tokens = result["session"]["map_state"]["observed_tokens"]
    assert len(tokens) == 1
    assert tokens[0]["player_id"] == "alpha"
    assert tokens[0]["tile_id"] == 0
    assert tokens[0]["token_type"] == result["data"]["token_type"]


def test_ai_place_cube_endpoint_places_bot_cube_on_map() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s14",
        "player_ids": ["alpha", "beta"],
        "turn_order": ["alpha", "beta"],
        "bot_player_id": "alpha",
        "bot_clue_id": "terrain_pair_forest_desert",
    })
    api.post("/board-layout", {
        "session_id": "s14",
        "placements": _default_board_layout(),
        "layout_mode": "manual",
    })
    api.post("/map", {"session_id": "s14"})

    result = api.post("/ai-place-cube", {
        "session_id": "s14",
    }).to_dict()

    assert result["data"]["player_id"] == "alpha"
    assert result["data"]["token_type"] == "cube"
    assert result["data"]["tile_id"] is not None
    tokens = result["session"]["map_state"]["observed_tokens"]
    assert len(tokens) == 1
    assert tokens[0]["player_id"] == "alpha"
    assert tokens[0]["token_type"] == "cube"


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


def test_simulate_observations_distributes_equally_per_player_without_fixed_seed() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s15",
        "player_ids": ["bot", "p1", "p2", "p3"],
        "turn_order": ["p1", "p2", "p3", "bot"],
        "bot_player_id": "bot",
        "bot_clue_id": "within_one_swamp",
    })
    api.post("/board-layout", {
        "session_id": "s15",
        "placements": [
            {"slot_id": 1, "section_id": "D", "orientation": "flipped"},
            {"slot_id": 2, "section_id": "F", "orientation": "flipped"},
            {"slot_id": 3, "section_id": "B", "orientation": "normal"},
            {"slot_id": 4, "section_id": "C", "orientation": "flipped"},
            {"slot_id": 5, "section_id": "A", "orientation": "normal"},
            {"slot_id": 6, "section_id": "E", "orientation": "normal"},
        ],
        "layout_mode": "manual",
    })
    api.post("/map", {"session_id": "s15"})

    result = api.post("/simulate-observations", {
        "session_id": "s15",
        "player_clues": [
            {"player_id": "bot", "clue_id": "within_one_swamp"},
            {"player_id": "p1", "clue_id": "within_one_either_animal_territory"},
            {"player_id": "p2", "clue_id": "terrain_pair_desert_water"},
            {"player_id": "p3", "clue_id": "within_three_blue_structure"},
        ],
        "observation_count": 12,
        "include_bot_observations": True,
        "ensure_player_polarity_coverage": True,
        "distribution_mode": "equal_per_player",
    }).to_dict()

    assert isinstance(result["data"]["used_seed"], int)
    assert result["data"]["generated_count"] == 12

    tokens = result["session"]["map_state"]["observed_tokens"]
    by_player = {}
    for token in tokens:
        by_player.setdefault(token["player_id"], 0)
        by_player[token["player_id"]] += 1

    assert by_player == {"bot": 3, "p1": 3, "p2": 3, "p3": 3}


def test_spa_catalog_includes_tagged_inverse_clues() -> None:
    api = SpaRecognitionApi()
    result = api.post("/catalog", {"session_id": "catalog-inverse"}).to_dict()

    clues = result["data"]["clues_catalog"]
    assert len(clues) == 48
    inverse_clues = [clue for clue in clues if clue["is_inverse"]]
    assert len(inverse_clues) == 24
    assert any(clue["clue_id"] == "not_terrain_pair_forest_desert" for clue in inverse_clues)


def test_spa_setup_rejects_inverse_clue_when_mode_disabled() -> None:
    api = SpaRecognitionApi()
    result = api.post("/setup", {
        "session_id": "advanced-off",
        "player_ids": ["alpha", "beta"],
        "turn_order": ["alpha", "beta"],
        "bot_player_id": "alpha",
        "bot_clue_id": "not_terrain_pair_forest_desert",
    }).to_dict()

    assert result["session"]["setup"]["include_inverse_clues"] is False
    assert "SETUP_CLUE_UNKNOWN" in _warning_codes(result)


def test_spa_setup_accepts_inverse_clue_when_mode_enabled() -> None:
    api = SpaRecognitionApi()
    result = api.post("/setup", {
        "session_id": "advanced-on",
        "player_ids": ["alpha", "beta"],
        "turn_order": ["alpha", "beta"],
        "bot_player_id": "alpha",
        "bot_clue_id": "not_terrain_pair_forest_desert",
        "include_inverse_clues": True,
    }).to_dict()

    assert result["session"]["setup"]["include_inverse_clues"] is True
    assert result["session"]["setup"]["bot_clue_id"] == "not_terrain_pair_forest_desert"
    assert "SETUP_CLUE_UNKNOWN" not in _warning_codes(result)


