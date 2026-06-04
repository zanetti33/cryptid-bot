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

The project is now organized into **4 independent modules**:

```
game_model/     ← Core game logic (no external dependencies)
    ↓
recognition/    ← Board recognition (intercambiabile)
    ↓
ai/             ← AI strategy engine
    ↓
discord_bot/    ← Discord UI layer (coming soon)
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

### `discord_bot/` - Discord Integration (Future)
Frontend module for Discord API integration.

### Support Modules

- `rules/` - Backward compatibility wrappers (re-export from `game_model/`)
- `map_recognition/` - Backward compatibility wrappers (re-export from `recognition/`)
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

### Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run Tests

```bash
# Using test runner (recommended)
python scripts/run_tests.py

# Or with pytest
pytest -q tests/
```

### Load Board from Image

```bash
python -c "
from recognition import image_to_board_state
board = image_to_board_state('screenshot.png')
print(f'Board loaded with {len(board.tiles)} tiles')
"
```

### Use AI to Recommend Moves

```bash
python -c "
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

## 🤖 Optional: CNN Training

Train a CNN model for better module recognition:

```bash
python scripts/train_module_classifier.py \
    --data-path datasets/map_recognition \
    --epochs 50 \
    --batch-size 32 \
    --output models/module_classifier.pt
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

- `REFACTORING_COMPLETE.md` - Full architecture documentation
- `clues.md` - Game clues and their descriptions
- `AGENTS.md` - Coding guidelines and practices

## 🔄 Backward Compatibility

Old code continues to work without changes:

```python
# Old style (still works)
from rules import Board, Game
from rules.clues import build_clue_catalog

# New style (recommended)
from game_model import Board, Game
from game_model.clues import build_clue_catalog
```

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

## 🚧 Roadmap

- [ ] Implement CLI recognition module
- [ ] Implement Discord bot integration
- [ ] Add move execution via Discord reactions
- [ ] Add game persistence (save/load)
- [ ] Add multi-table support
- [ ] Add player rating system
- [ ] Create web UI alternative frontend

## 📝 Development Principles

- **Separation of Concerns**: Each module does one thing
- **Testability**: All modules are independently testable
- **Modularity**: Easy to replace or extend any component
- **Code Clarity**: Prefer readability over cleverness
- **Documentation**: Clear code with meaningful comments

See `AGENTS.md` for detailed coding guidelines.

---

**Project**: Cryptid Bot  
**Status**: Core architecture complete, features in development  
**Last Updated**: June 4, 2026  
**Python**: 3.10+

