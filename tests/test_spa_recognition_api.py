from spa_recognition.backend.api import SpaRecognitionApi


def _warning_codes(result_dict):
    return {warning["code"] for warning in result_dict["warnings"]}


def test_spa_setup_and_map_flow_updates_session_phase() -> None:
    api = SpaRecognitionApi()

    setup_result = api.post("/setup", {
        "session_id": "s1",
        "player_ids": ["bot", "p1", "p2"],
        "turn_order": ["bot", "p1", "p2"],
        "bot_player_id": "bot",
    }).to_dict()

    assert setup_result["session"]["phase"] == "map"
    assert setup_result["session"]["setup"]["bot_player_id"] == "bot"

    map_result = api.post("/map", {
        "session_id": "s1",
        "cols": 12,
        "rows": 9,
        "observed_tokens": [
            {"tile_id": 0, "player_id": "bot", "token_type": "cube"},
            {"tile_id": 1, "player_id": "p1", "token_type": "round"},
        ],
    }).to_dict()

    assert map_result["session"]["phase"] == "structures"
    assert len(map_result["session"]["map_state"]["observed_tokens"]) == 2


def test_spa_payload_is_permissive_and_returns_warnings() -> None:
    api = SpaRecognitionApi()

    setup_result = api.post("/setup", {"session_id": "s2", "player_ids": "bad"}).to_dict()
    assert "SETUP_FIELD_INVALID" in _warning_codes(setup_result)

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
    api.post("/setup", {"session_id": "s3", "player_ids": ["bot"], "bot_player_id": "bot"})
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
            "bot": {"notes": ["possible clue A"]},
        },
    }).to_dict()

    assert clues_result["session"]["phase"] == "review"
    assert clues_result["session"]["clues_state"]["by_player_id"]["bot"]["notes"] == ["possible clue A"]


def test_spa_recalculate_returns_hypothesis_space_and_moves() -> None:
    api = SpaRecognitionApi()
    api.post("/setup", {
        "session_id": "s4",
        "player_ids": ["bot", "p1"],
        "turn_order": ["bot", "p1"],
        "bot_player_id": "bot",
    })
    api.post("/map", {
        "session_id": "s4",
        "observed_tokens": [
            {"tile_id": 0, "player_id": "bot", "token_type": "cube"},
            {"tile_id": 3, "player_id": "p1", "token_type": "round"},
        ],
    })

    recalc_result = api.post("/recalculate", {"session_id": "s4", "top_k": 3}).to_dict()

    assert "hypothesis_space" in recalc_result["data"]
    assert "recommended_moves" in recalc_result["data"]
    assert len(recalc_result["data"]["recommended_moves"]) <= 3

