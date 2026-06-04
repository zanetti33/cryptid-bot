from enum import Enum


class TerrainType(str, Enum):
    FOREST = "forest"
    MOUNTAIN = "mountain"
    WATER = "water"
    DESERT = "desert"
    SWAMP = "swamp"
    UNKNOWN = "unknown"


class AnimalTerritory(str, Enum):
    BEAR = "bear"
    COUGAR = "cougar"


class StructureType(str, Enum):
    STANDING_STONE = "standing_stone"
    ABANDONED_SHACK = "abandoned_shack"


class StructureColor(str, Enum):
    WHITE = "white"
    GREEN = "green"
    BLUE = "blue"
    BLACK = "black"


class TokenType(str, Enum):
    ROUND = "round"
    CUBE = "cube"

