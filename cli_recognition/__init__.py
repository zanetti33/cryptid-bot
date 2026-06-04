"""
CLI-based board recognition module for Cryptid.

This module provides an interactive CLI interface for users to manually describe
the board state instead of using automated image recognition.

This can be used as an alternative to the automatic recognition module when:
- Screenshots are unavailable
- Automatic recognition fails
- A user wants to manually play through a scenario

## Usage Example

    from cli_recognition import create_board_from_cli

    board = create_board_from_cli()
    # User is prompted to describe terrain and modules interactively

## API Functions

TODO: Implement these functions
- create_board_from_cli() -> Board
- describe_module_interactively() -> ModuleDescription
- parse_terrain_description(description: str) -> TerrainType
"""

__all__ = []


