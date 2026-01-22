"""Online player tracking and presence management."""

import time
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class PlayerPresence:
    """Represents a player's online presence."""
    
    username: str
    login_time: int  # Unix timestamp when player logged in
    idle_time: int = field(default_factory=lambda: int(time.time()))  # Last activity
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "username": self.username,
            "login_time": self.login_time,
            "idle_time": self.idle_time,
            "online_duration": int(time.time()) - self.login_time,
        }


class PresenceTracker:
    """Tracks which players are currently online."""
    
    def __init__(self):
        """Initialize the presence tracker."""
        self._players: dict[str, PlayerPresence] = {}  # username -> PlayerPresence
    
    def login(self, username: str) -> None:
        """Record a player logging in."""
        self._players[username] = PlayerPresence(
            username=username,
            login_time=int(time.time()),
        )
    
    def logout(self, username: str) -> None:
        """Record a player logging out."""
        self._players.pop(username, None)
    
    def update_activity(self, username: str) -> None:
        """Update last activity time for a player."""
        if username in self._players:
            self._players[username].idle_time = int(time.time())
    
    def get_online_players(self) -> list[str]:
        """Get list of online player usernames."""
        return sorted(list(self._players.keys()))
    
    def get_online_players_detailed(self) -> list[dict]:
        """Get detailed info about all online players."""
        return [p.to_dict() for p in sorted(
            self._players.values(),
            key=lambda p: p.login_time,
            reverse=True
        )]
    
    def get_player_count(self) -> int:
        """Get number of online players."""
        return len(self._players)
    
    def is_online(self, username: str) -> bool:
        """Check if a player is online."""
        return username in self._players
    
    def to_dict(self) -> dict:
        """Convert to dictionary for status file."""
        return {
            "count": self.get_player_count(),
            "players": self.get_online_players(),
            "updated": int(time.time()),
        }
