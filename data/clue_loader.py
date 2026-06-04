from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(__file__).resolve().parent


def load_clue_payload() -> Dict[str, Any]:
    path = DATA_DIR / "clues_catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_clue_definitions() -> List[Dict[str, Any]]:
    payload = load_clue_payload()
    return payload["clues"]

