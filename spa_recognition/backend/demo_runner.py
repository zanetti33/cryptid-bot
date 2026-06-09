from __future__ import annotations

import json

from spa_recognition.backend.api import SpaRecognitionApi


def main() -> None:
    api = SpaRecognitionApi()

    api.post_setup(
        {
            "session_id": "demo",
            "player_ids": ["bot", "p1", "p2"],
            "turn_order": ["bot", "p1", "p2"],
            "bot_player_id": "bot",
        }
    )
    api.post_map(
        {
            "session_id": "demo",
            "cols": 12,
            "rows": 9,
            "observed_tokens": [
                {"tile_id": 0, "player_id": "bot", "token_type": "cube"},
                {"tile_id": 1, "player_id": "p1", "token_type": "round"},
            ],
        }
    )
    api.post_structures(
        {
            "session_id": "demo",
            "structures": [
                {"tile_id": 1, "structure_type": "standing_stone", "structure_color": "white"}
            ],
        }
    )
    api.post_clues(
        {
            "session_id": "demo",
            "by_player_id": {
                "bot": {"notes": ["demo note"]},
                "p1": {"notes": []},
            },
        }
    )

    result = api.post_recalculate({"session_id": "demo", "top_k": 3})
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()

