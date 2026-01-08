"""Game implementations."""

from .base import Game
from .registry import GameRegistry, register_game, get_game_class

# Import all games to trigger registration
from .pig.game import PigGame
from .scopa.game import ScopaGame
from .lightturret.game import LightTurretGame
from .threes.game import ThreesGame
from .milebymile.game import MileByMileGame
from .chaosbear.game import ChaosBearGame
from .farkle.game import FarkleGame

__all__ = [
    "Game",
    "GameRegistry",
    "register_game",
    "get_game_class",
    "PigGame",
    "ScopaGame",
    "LightTurretGame",
    "ThreesGame",
    "MileByMileGame",
    "ChaosBearGame",
    "FarkleGame",
]
