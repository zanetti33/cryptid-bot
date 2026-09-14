Always make code that is easy to understand and maintain, even if it takes more time to implement. 
Make it modular, don't repeat code, use clear variable and function names, and write comments to explain complex logic.
Try to keep every unit of code focused on a single responsibility, and avoid making functions or classes that do too many things at once.
Every time that's possible, write unit tests to verify that your code works as expected and to prevent future bugs when making changes.
Don't hesitate to refactor your code if you see an opportunity to improve its structure or readability.
Don't overcomplicate things, keep it simple and straightforward.

This project has the objective of creating a Discord bot that can play the board game Cryptid with other players.
The bot uses screenshots of the board state to determine its next action.

The project is structured as follows:
- `game_model/`: This directory contains the implementation of the game rules and logic for processing the board state.
- `ai/`: This directory contains the implementation of the bot's decision-making agents.
- `discord_bot/`: This directory will contain the implementation of the bot's interaction with the Discord API (still a stub, see item 3 below).
- `data/`: This directory contains any necessary data files, such as the list of possible clues and their corresponding board states.
- `tests/`: This directory contains unit tests for the various components of the bot.
- `recognition/`: This directory contains the implementation of the map recognition system, which processes screenshots of the board state and extracts relevant information for the bot's decision-making (`map_recognition/` is a backward-compatibility re-export of this package).
- `main.py`: This is the main entry point for the bot, where it connects to Discord and listens for game events.
- `spa_recognition/`: This directory contains a Single Page Application (SPA) backend + frontend for manual board/game state entry and AI orchestration, used ahead of/alongside the Discord integration.

Game rules and map reference (still accurate, kept for context):
- The game rules:
   - Each player has a different hidden information on the monster location on the board that they are trying to hide.
   - Players take turns clockwise asking two type of questions:
     - "Could the monster be in this location?" to another player, which will answer based on his/her hidden information.
       - If yes the other player places a round token on that location
       - If no the other player places a cube token on that location, and the player that asked has to place a cube on a location that isn't valid for his/her hidden information.
     - "Is the monster in this location?" to all the players.
       - The current player places a round token on that location (it must be correct for his/her hidden information),
       then clockwise each player answers based on his/her hidden information, until a cube is placed (the location is incorrect for that player) or all players have answered (the location is correct for all players).
       - In the second case, the current player wins the game.
- The map is like this:
   - The board has 108 hex tiles connected.
   - Each tile his of a certain type: forest (green), mountain (gray), water (blue), desert (yellow), or swamp (purple).
   - Some tiles could have bear (black dotted line on the edge) or cougar (red full line on the edge).
   - On some tiles there could be either a octagon (monolith/standing stone) or a piramid (abandoned shack/tent).
     - These could have 3 different colors each: white, green or light blue.
- The clues are [here](clues.md).

Current status (see README.md for the full architecture breakdown):
1. **Done** - Game logic/model (`game_model/`) and clue/data catalog (`data/`) are implemented and tested.
2. **Done** - AI decision-making (`ai/`: `inference.py`, `strategy.py`, `engine.py`, `events.py`, `knowledge_update.py`, `scenario_harness.py`) is implemented; see `docs/AI_SCENARIO_HARNESS.md` for how to evaluate it against real/synthetic scenarios.
3. **Not started** - Discord integration. `discord_bot/` is still an empty stub (`__init__.py` only). This is the main remaining gap in the original roadmap.
4. **Done** - Image recognition (`recognition/`), including terrain classification and an optional CNN module classifier (untrained by default - see `docs/CNN_MODULE_RECOGNITION.md`).
5. **Mostly done** - SPA frontend (`spa_recognition/`): board composition, terrain-colored map, structures/clues editing, and AI orchestration are implemented and covered by tests. Remaining gaps: layout preset save/reset actions (see `spa_recognition/plan-spaRecognition.prompt.md`, milestone M7).
6. **Done** - Unit tests exist under `tests/` for game_model, ai, recognition, and spa_recognition.
7. **Ongoing** - Documentation exists (`README.md`, `docs/`) but needs to be kept in sync with the code as features land; treat stale docs/TODOs as bugs.