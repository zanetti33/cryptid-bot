"""
Unit test per i building blocks del modulo spa_recognition:
- WarningItem / merge_warnings
- SetupState / MapState / StructuresState / CluesState / AiState / SessionState
- SessionStore
- Adapter SessionState → GameSnapshot (_build_snapshot_from_session)
"""

from __future__ import annotations

import threading

import pytest

from spa_recognition.backend.models import (
    AiState,
    ApiResult,
    CluesState,
    MapState,
    SessionState,
    SetupState,
    StructuresState,
    WarningItem,
    merge_warnings,
)
from spa_recognition.backend.session_store import SessionStore

# ---------------------------------------------------------------------------
# WarningItem
# ---------------------------------------------------------------------------


def test_warning_item_dedupe_key_is_stable() -> None:
    w = WarningItem(code="FOO", message="bar", scope="setup", severity="warn")
    assert w.dedupe_key() == ("FOO", "setup", "bar")


def test_warning_item_to_dict_contains_all_fields() -> None:
    w = WarningItem(code="X", message="y", scope="map", severity="error")
    d = w.to_dict()
    assert d == {"code": "X", "message": "y", "scope": "map", "severity": "error"}


# ---------------------------------------------------------------------------
# merge_warnings
# ---------------------------------------------------------------------------


def test_merge_warnings_deduplicates_by_key() -> None:
    w1 = WarningItem(code="A", message="msg", scope="setup", severity="warn")
    w2 = WarningItem(code="A", message="msg", scope="setup", severity="warn")
    merged = merge_warnings((w1,), (w2,))
    # Stesso dedupe_key → deve apparire una sola volta
    assert len(merged) == 1


def test_merge_warnings_preserves_distinct_entries() -> None:
    w1 = WarningItem(code="A", message="first", scope="setup", severity="warn")
    w2 = WarningItem(code="B", message="second", scope="map", severity="error")
    merged = merge_warnings((w1,), (w2,))
    codes = {w.code for w in merged}
    assert codes == {"A", "B"}


def test_merge_warnings_empty_groups_return_empty() -> None:
    assert merge_warnings((), ()) == ()


# ---------------------------------------------------------------------------
# SessionState.with_updates
# ---------------------------------------------------------------------------


def test_session_with_updates_preserves_unmodified_fields() -> None:
    original = SessionState(session_id="abc")
    updated = original.with_updates(phase="map")
    assert updated.session_id == "abc"
    assert updated.phase == "map"
    # Campo non modificato deve rimanere uguale
    assert updated.setup.player_ids == ()


def test_session_with_updates_returns_new_instance() -> None:
    original = SessionState(session_id="x")
    updated = original.with_updates(phase="structures")
    assert updated is not original


def test_session_to_dict_is_serializable() -> None:
    """to_dict deve produrre solo tipi base Python (no dataclass annidati)."""
    session = SessionState(session_id="s1")
    d = session.to_dict()
    # Non deve sollevare eccezioni con json.dumps
    import json
    json.dumps(d)  # solleva TypeError se ci sono oggetti non serializzabili


# ---------------------------------------------------------------------------
# SetupState / MapState to_dict
# ---------------------------------------------------------------------------


def test_setup_state_to_dict_converts_tuples_to_lists() -> None:
    setup = SetupState(player_ids=("a", "b"), turn_order=("a", "b"), bot_player_id="a")
    d = setup.to_dict()
    assert isinstance(d["player_ids"], list)
    assert isinstance(d["turn_order"], list)


def test_map_state_default_is_108_tiles() -> None:
    ms = MapState()
    assert ms.cols * ms.rows == 108


def test_map_state_observed_tokens_serialized_as_list() -> None:
    ms = MapState(observed_tokens=({"tile_id": 0, "player_id": "bot", "token_type": "cube"},))
    d = ms.to_dict()
    assert isinstance(d["observed_tokens"], list)
    assert d["observed_tokens"][0]["tile_id"] == 0


# ---------------------------------------------------------------------------
# ApiResult.to_dict
# ---------------------------------------------------------------------------


def test_api_result_to_dict_includes_all_keys() -> None:
    session = SessionState(session_id="r1")
    result = ApiResult(session=session, warnings=(), data={"k": 1})
    d = result.to_dict()
    assert set(d.keys()) == {"session", "warnings", "data"}
    assert d["data"]["k"] == 1


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------


def test_session_store_create_or_get_returns_same_object() -> None:
    store = SessionStore()
    s1 = store.create_or_get("sid")
    s2 = store.create_or_get("sid")
    assert s1.session_id == s2.session_id == "sid"


def test_session_store_upsert_overwrites_existing() -> None:
    store = SessionStore()
    original = store.create_or_get("s")
    updated = original.with_updates(phase="map")
    store.upsert(updated)
    fetched = store.get("s")
    assert fetched.phase == "map"


def test_session_store_reset_clears_state() -> None:
    store = SessionStore()
    session = store.create_or_get("r")
    session = session.with_updates(phase="review")
    store.upsert(session)
    reset = store.reset("r")
    assert reset.phase == "setup"


def test_session_store_get_returns_none_for_unknown_id() -> None:
    store = SessionStore()
    assert store.get("nonexistent") is None


def test_session_store_is_thread_safe() -> None:
    """Verifica che accessi concorrenti non producano race condition."""
    store = SessionStore()
    results: list[SessionState] = []
    errors: list[Exception] = []

    def worker(n: int) -> None:
        try:
            session = store.create_or_get(f"t{n}")
            store.upsert(session.with_updates(phase="map"))
            results.append(store.get(f"t{n}"))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(results) == 20


# ---------------------------------------------------------------------------
# Adapter: SessionState → GameSnapshot
# ---------------------------------------------------------------------------


def test_adapter_builds_valid_snapshot_from_minimal_session() -> None:
    """Il snapshot deve avere una board con 108 tile per default (12×9)."""
    from spa_recognition.backend.api import _build_snapshot_from_session

    session = SessionState(session_id="snap")
    snapshot, warnings = _build_snapshot_from_session(session)

    assert len(snapshot.board.tiles) == 108
    assert isinstance(warnings, list)


def test_adapter_places_tokens_correctly() -> None:
    from spa_recognition.backend.api import _build_snapshot_from_session

    session = SessionState(
        session_id="tokens",
        setup=SetupState(player_ids=("bot",), turn_order=("bot",), bot_player_id="bot"),
        map_state=MapState(
            observed_tokens=(
                {"tile_id": 0, "player_id": "bot", "token_type": "cube"},
                {"tile_id": 1, "player_id": "bot", "token_type": "round"},
            )
        ),
    )
    snapshot, warnings = _build_snapshot_from_session(session)

    # tile_id 0 deve avere un cubo, tile_id 1 un tondo
    tiles_by_id = {t.tile_id: t for t in snapshot.board.tiles.values()}
    assert "bot" in tiles_by_id[0].cube_tokens
    assert "bot" in tiles_by_id[1].round_tokens


def test_adapter_warns_on_out_of_bound_structure() -> None:
    from spa_recognition.backend.api import _build_snapshot_from_session

    session = SessionState(
        session_id="oob",
        structures_state=StructuresState(
            by_tile_id={99999: {"structure_type": "standing_stone", "structure_color": "white"}}
        ),
    )
    _, warnings = _build_snapshot_from_session(session)
    codes = {w.code for w in warnings}
    assert "STRUCTURE_TILE_NOT_FOUND" in codes

