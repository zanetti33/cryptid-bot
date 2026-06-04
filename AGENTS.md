Always make code that is easy to understand and maintain, even if it takes more time to implement. 
Make it modular, don't repeat code, use clear variable and function names, and write comments to explain complex logic.
Try to keep every unit of code focused on a single responsibility, and avoid making functions or classes that do too many things at once.
Every time that's possible, write unit tests to verify that your code works as expected and to prevent future bugs when making changes.
Don't hesitate to refactor your code if you see an opportunity to improve its structure or readability.
Don't overcomplicate things, keep it simple and straightforward.

This project has the objective of creating a Discord bot that can play the board game Cryptid with other players.
The bot uses screenshots of the board state to determine its next action.

The project is structured as follows:
- `rules/`: This directory contains the implementation of the game rules and logic for processing the board state.
- `ai/`: This directory contains the implementation of the bot's decision-making agents.
- `discord/`: This directory contains the implementation of the bot's interaction with the Discord API.
- `data/`: This directory contains any necessary data files, such as the list of possible clues and their corresponding board states.
- `tests/`: This directory contains unit tests for the various components of the bot.
- `map_recognition/`: This directory contains the implementation of the map recognition system, which processes screenshots of the board state and extracts relevant information for the bot's decision-making.
- `main.py`: This is the main entry point for the bot, where it connects to Discord and listens for game events.
- `utils/`: This directory contains utility functions.
- `screenshots/`: This directory is used to store screenshots of the board state for analysis.

What needs to be done:
1. Implement the game logic/model for the bot in the `rules/` and `data/` directories. This will involve analyzing the board state and determining the best move based on the current game situation.
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
2. Implement the bot's decision-making agents in the `ai/` directory. 
This will involve creating algorithms that can analyze the board state and make informed decisions based on the clues and the current game situation.
We want to evaluate all the possible hidden information of all others players, if we know for sure the location we can ask "Is the monster in this location?" to win, otherwise we can ask "Could the monster be in this location?" to narrow down the possibilities.
3. Connect the bot to Discord and implement the necessary functionality to listen for game events and respond accordingly. This will involve using the Discord API to interact with the game and other players.
4. Implement the image recognition system in the `map_recognition/` directory to process screenshots of the board state and extract relevant information for the bot's decision-making. This will involve using computer vision techniques to analyze the screenshots and identify the different tiles, clues, and player actions.
5. Write unit tests for the various components of the bot to ensure that they are functioning correctly
6. Document the code and provide clear instructions for how to set up and use the bot on Discord. This will involve writing a README file and providing any necessary documentation for the different components of the bot.