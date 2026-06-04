"""
Backward compatibility module. Import from game_model.state instead.
"""

from game_model.state import GameSnapshot, ObservedToken

__all__ = ["GameSnapshot", "ObservedToken"]

