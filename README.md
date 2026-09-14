# Cryptid Bot

Modular Discord bot for the board game Cryptid, with clean separation between game logic, board recognition, AI decision-making, and Discord integration.

## Status

- ✅ Game logic (`game_model/`), board recognition (`recognition/`), and AI engine (`ai/`) — implemented and tested.
- ✅ SPA frontend (`spa_recognition/`) — manual board/game entry + AI orchestration, mostly done (layout presets still WIP, see `spa_recognition/plan-spaRecognition.prompt.md`).
- 🚧 Discord bot integration (`discord_bot/`) — not started yet.
- 🚧 CLI recognition (`cli_recognition/`) — not started yet.

## Architecture

```
game_model/      ← Core game logic (no external dependencies)
    ↓
recognition/     ← Board recognition from screenshots (terrain + optional CNN)
    ↓
ai/              ← Hypothesis-space inference + move recommendation
    ↓
spa_recognition/ ← Manual SPA state entry + AI orchestration (backend + React frontend)
    ↓
discord_bot/     ← Discord UI layer (not started)
```

Each module is independently testable and replaceable. `rules/` and `map_recognition/` are backward-compatibility re-exports of `game_model/` and `recognition/`.

### Board & game rules

- 108 hex tiles across 6 modules (A-F, normal/flipped), 5 terrain types (forest/mountain/water/desert/swamp).
- Each player has a hidden clue restricting valid monster locations. Players ask **"Could it be here?"** (single player, round/cube token) or **"Is it here?"** (all players, wins if everyone agrees).
- Clue definitions: [`clues.md`](clues.md). Board/module data: `data/module_templates.json`, `data/board_slots.json`, `data/clues_catalog.json`.

## Getting Started (Docker-first)

Only requirement: Docker + Docker Compose.

```bash
cp .env.example .env
chmod +x scripts/docker/*.sh
./scripts/docker/doctor.sh
```

| Command | What it does |
|---|---|
| `./scripts/docker/dev.sh` | Backend (`:8000`) + frontend hot-reload (`:5173`) |
| `./scripts/docker/prod.sh` | Backend + static frontend via nginx (`:8080`) |
| `./scripts/docker/test.sh` | Run the Python test suite |
| `./scripts/docker/train.sh` | Train the CNN module classifier (CUDA, falls back to CPU) |

SPA backend endpoints (all `POST`, see `spa_recognition/backend/api.py`): `/catalog`, `/setup`, `/board-layout`, `/map`, `/structures`, `/clues`, `/ask-ai`, `/ai-answer`, `/ai-place-cube`, `/recalculate`, `/simulate-observations`.

### Evaluate AI scenarios

```bash
python scripts/evaluate_ai_scenarios.py data/ai_scenarios/default_layout.json
```

Runs the `ai/` package against a JSON scenario (board, players, clues) and reports the recommended moves. Full format in `docs/AI_SCENARIO_HARNESS.md`.

### Static demo (GitHub Pages)

`spa_recognition/frontend` also builds as a fully static site, published at
**https://zanetti33.github.io/cryptid-bot/** via `.github/workflows/deploy-pages.yml`.
It runs the same `SpaRecognitionApi`/`game_model`/`ai` Python logic entirely
in-browser via [Pyodide](https://pyodide.org/) — no backend at all. Session
state lives only in the browser tab and is lost on reload. This is separate
from the Docker dev/prod flow above, which still talks to a real Python
backend; build it yourself with `VITE_USE_PYODIDE=true npm run build` in
`spa_recognition/frontend`.

## Documentation

- [`AGENTS.md`](AGENTS.md) — coding guidelines and project status
- [`docs/DOCKER_WORKFLOWS.md`](docs/DOCKER_WORKFLOWS.md) — Docker profiles in detail
- [`docs/SPA_RECOGNITION_SPEC.md`](docs/SPA_RECOGNITION_SPEC.md) / [`spa_recognition/plan-spaRecognition.prompt.md`](spa_recognition/plan-spaRecognition.prompt.md) — SPA spec and milestone backlog
- [`docs/AI_STRATEGY.md`](docs/AI_STRATEGY.md) — AI design notes and mapping to actual code
- [`docs/AI_SCENARIO_HARNESS.md`](docs/AI_SCENARIO_HARNESS.md) — AI scenario evaluation format
- [`docs/CNN_MODULE_RECOGNITION.md`](docs/CNN_MODULE_RECOGNITION.md) — optional CNN module recognition (requires training)
- [`clues.md`](clues.md) — game clues reference
