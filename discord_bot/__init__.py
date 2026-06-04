"""
Discord bot integration module for Cryptid.

This module handles all interactions with the Discord API, including:
- Listening for game events through messages/reactions
- Sending messages and reactions to update game state
- Managing game sessions on Discord channels
- Handling user commands

## Architecture

The Discord bot is designed to work with the modular components:
- **game_model**: Core game logic
- **recognition**: Board state recognition (automatic or CLI)
- **ai**: Decision-making for bot's moves
- **discord_bot**: Discord API integration

## Usage Example

    from discord_bot import CryptidBot, create_bot

    bot = create_bot(token="YOUR_DISCORD_TOKEN")
    bot.run()

## Features (TODO)

- [ ] Game session management
- [ ] Board state synchronization
- [ ] Player turn management
- [ ] Move execution and validation
- [ ] Multi-channel game support
- [ ] Persistence across restarts

## API Components

TODO: Implement these classes and functions
- CryptidBot: Main Discord bot class
- GameSession: Manages a single game session
- create_bot(token: str) -> CryptidBot
"""

__all__ = []


