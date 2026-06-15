# Cryptid Bot

Modular Discord bot for the board game Cryptid, with clean separation between game logic, board recognition, AI decision-making, and Discord integration.

## 🎯 Current Status

**Architecture Version**: 2.0 (Modularized) - Fully refactored

- ✅ Game model module (core logic, independent)
- ✅ Board recognition (automatic via image recognition)
- ✅ CLI recognition module (manual board input - coming soon)
- ✅ AI decision-making engine
- 🚧 Discord bot integration (coming soon)

## 🏗️ Architecture Overview

The project is now organized into **5 independent modules**:

```
game_model/      ← Core game logic (no external dependencies)
    ↓
recognition/     ← Board recognition (interchangeable)
    ↓
ai/              ← AI strategy engine
    ↓
spa_recognition/ ← Manual SPA state entry + AI orchestration (MVP V1)
    ↓
discord_bot/     ← Discord UI layer (coming soon)
```

Each module can be tested, replaced, or extended independently.

## 📁 Detailed Project Structure

### `game_model/` - Core Game Logic
**Independent module** - contains pure game logic with zero external dependencies.

```
game_model/
├── types.py          # TerrainType, TokenType, AnimalTerritory, StructureType, StructureColor
├── map.py            # Board model, HexTile, 6-neighbor hexagon adjacency
├── tokens.py         # TokenPlacement, GameState (turn management)
├── state.py          # GameSnapshot (observation snapshot for AI)
├── clues.py          # Clue system with predicates (And/Or/Not)
├── game.py           # Game engine (ask_could, ask_is, turn resolution)
└── __init__.py       # Public API
```

**Usage:**
```python
from game_model import Board, Game, PlayerState, GameSnapshot
from game_model.clues import build_clue_catalog

# Create a board
board = Board.rectangular(cols=12, rows=9)  # 108 hexes

# Create snapshot for AI
snapshot = GameSnapshot(board=board, bot_player_id="bot")

# Create and play game
game = Game(board=board, players=[...])
```

### `recognition/` - Board Recognition
**Interchangeable module** - automatically recognizes board state from screenshots using terrain classification and CNN.

```
recognition/
├── pipeline.py            # Main orchestration (image_to_board_state)
├── tile_classifier.py     # RGB pixel → TerrainType
├── board_extractor.py     # Extract hex tiles from image
├── layout_recognizer.py   # Terrain pattern matching + CNN
├── module_classifier.py   # CNN model (12 classes: A-F × normal/flipped)
├── debug_overlay.py       # Debug visualization
├── dataset.py             # Dataset utilities, label generation
└── __init__.py            # Public API
```

**Usage:**
```python
from recognition import image_to_board_state

# Terrain-only recognition (fast, no model needed)
board = image_to_board_state("screenshot.png")

# With CNN model (more accurate if available)
board = image_to_board_state(
    "screenshot.png",
    use_cnn=True,
    cnn_model_path="models/module_classifier.pt"
)
```

### `ai/` - AI Decision-Making
**Independent module** - bot's tactical reasoning engine.

```
ai/
├── inference.py    # Hypothesis space inference
├── strategy.py     # Move recommendation (scoring, ranking)
└── __init__.py     # Public API
```

**Usage:**
```python
from ai import infer_hypothesis_space, recommend_moves

hyp_space = infer_hypothesis_space(snapshot)
moves = recommend_moves(snapshot, hypothesis_space=hyp_space, top_k=5)

for move in moves:
    print(f"{move.action_type} tile {move.tile_id}: {move.confidence:.2%}")
```

### `cli_recognition/` - Manual Board Input (Future)
Alternative recognition module for interactive terminal input.

### `spa_recognition/` - SPA Integration (MVP V1)
Frontend/backend module for manual board and game state entry, plus AI orchestration through permissive API endpoints.

### `discord_bot/` - Discord Integration (Future)
Frontend module for Discord API integration.

### Support Modules

- `rules/` - Backward compatibility wrappers (re-export from `game_model/`)
- `map_recognition/` - Backward compatibility wrappers (re-export from `recognition/`)
- `spa_recognition/` - SPA backend + minimal React frontend for manual board/game input
- `data/` - Module templates, board configuration, clue definitions
- `datasets/map_recognition/` - Labeled training images
- `tests/` - Unit tests for all modules
- `scripts/` - Utility scripts (testing, training)
- `models/` - Trained model weights (CNN classifier)
- `docs/` - Technical documentation

## 🎮 Game Model

### Board Geometry

- **Total tiles**: 108 (hexagons arranged in 6 sections)
- **Module layout**: 6 sections (A-F) × 2 orientations (normal/flipped)
- **Hexagons per module**: 18 (3 rows × 6 columns)
- **Hexagon adjacency**: 6-neighbor model

### Game Rules

Each player has a hidden clue that defines valid monster locations. Players take turns:

1. **"Could the monster be here?"** - Ask a specific player about a tile
   - Yes → other player places round token
   - No → both players place cube tokens

2. **"Is the monster here?"** - Ask all players about a tile
   - All agree → current player wins
   - Any disagree → place cube token on rejecting player, continue

### Data Files

- `data/module_templates.json` - 6 canonical modules with terrain and animal territories
- `data/board_slots.json` - 6 positions where modules are placed
- `data/clues_catalog.json` - All 20 base clues + inversions
- `data/board_layout.json` - Current game composition

## 🚀 Getting Started

### Setup (Docker-first)

Only requirement: Docker + Docker Compose.

```bash
cp .env.example .env
chmod +x scripts/docker/*.sh
./scripts/docker/doctor.sh
```

Profiles available in `docker-compose.yml`:
- `dev` - backend + frontend with hot reload
- `prod` - backend + static frontend via nginx
- `test` - Python tests
- `train` - CNN training (CUDA first, CPU fallback)

### Run Tests

```bash
./scripts/docker/test.sh
```

### Run Development Stack (Backend + Frontend)

```bash
./scripts/docker/dev.sh
```

Backend: `http://127.0.0.1:8000`  
Frontend (Vite): `http://127.0.0.1:5173`

Available endpoints (POST):
- `/setup`
- `/map`
- `/structures`
- `/clues`
- `/recalculate`

### Run Production-like Stack

```bash
./scripts/docker/prod.sh
```

Frontend is served by nginx on `http://127.0.0.1:8080`.

### Run SPA Recognition Demo Flow (CLI)

```bash
docker compose --profile dev run --rm backend-dev python -m spa_recognition.backend.demo_runner
```

### Load Board from Image

```bash
docker compose --profile dev run --rm backend-dev python -c "
from recognition import image_to_board_state
board = image_to_board_state('screenshot.png')
print(f'Board loaded with {len(board.tiles)} tiles')
"
```

### Use AI to Recommend Moves

```bash
docker compose --profile dev run --rm backend-dev python -c "
from game_model import GameSnapshot
from ai import recommend_moves
from recognition import image_to_board_state

board = image_to_board_state('screenshot.png')
snapshot = GameSnapshot(board=board, bot_player_id='bot')
moves = recommend_moves(snapshot, top_k=5)

for move in moves:
    print(f'{move.action_type} tile {move.tile_id}: confidence {move.confidence:.1%}')
"
```

### Evaluate Full AI Scenarios

You can evaluate the whole `ai/` package from scenario JSON files that describe:

- board configuration
- players and turn order
- the real clue for each player
- generation settings for synthetic observations

Run the sample scenario:

```bash
python scripts/evaluate_ai_scenarios.py data/ai_scenarios/default_layout.json
```

Put your scenario JSON files under `data/ai_scenarios/`.
If you are starting from a real game played on the standard board, copy and adapt:

- `data/ai_scenarios/default_layout.template.json`

See `docs/AI_SCENARIO_HARNESS.md` for the full field-by-field format.

Run multiple scenarios with overrides:

```bash
python scripts/evaluate_ai_scenarios.py data/ai_scenarios/*.json --seed 99 --observations 14 --top-k 7
```

See `docs/AI_SCENARIO_HARNESS.md` for the scenario format and workflow.

## 🤖 Optional: CNN Training

Train a CNN model for better module recognition:

```bash
./scripts/docker/train.sh --epochs 50 --batch-size 32 --output models/module_classifier.pt
```

Then use it:

```bash
board = image_to_board_state(
    "screenshot.png",
    use_cnn=True,
    cnn_model_path="models/module_classifier.pt",
    cnn_weight=0.5  # Balance CNN vs terrain matching
)
```

## 📚 Documentation

- `docs/DOCKER_WORKFLOWS.md` - Docker-first workflows (dev/prod/test/train)
- `docs/SPA_RECOGNITION_SPEC.md` - SPA Recognition MVP specification and milestones
- `REFACTORING_COMPLETE.md` - Full architecture documentation
- `clues.md` - Game clues and their descriptions
- `AGENTS.md` - Coding guidelines and practices

## 🧪 Testing Examples

```python
# Test game logic
from game_model import Board, Game, PlayerState

board = Board.rectangular(12, 9)
players = [
    PlayerState(player_id="p1", clue_id="clue_1"),
    PlayerState(player_id="p2", clue_id="clue_2"),
]
game = Game(board=board, players=players)

# Test AI
from ai import infer_hypothesis_space, recommend_moves
from game_model import GameSnapshot

snapshot = GameSnapshot(board=board, bot_player_id="p1")
hyp = infer_hypothesis_space(snapshot)
moves = recommend_moves(snapshot, hypothesis_space=hyp)
assert len(moves) > 0

# Test recognition
from recognition import image_to_board_state

board = image_to_board_state("test_image.png")
assert len(board.tiles) == 108
```

## 📝 Development Principles

- **Separation of Concerns**: Each module does one thing
- **Testability**: All modules are independently testable
- **Modularity**: Easy to replace or extend any component
- **Code Clarity**: Prefer readability over cleverness
- **Documentation**: Clear code with meaningful comments

See `AGENTS.md` for detailed coding guidelines.
