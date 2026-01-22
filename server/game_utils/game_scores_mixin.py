"""Mixin providing score checking actions for games."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..games.base import Player
    from ..users.base import User
    from .teams import TeamManager


class GameScoresMixin:
    """Mixin providing score checking and turn announcement actions.

    Expects on the Game class:
        - self.current_player: Player | None
        - self.team_manager: TeamManager
        - self.players: list[Player]
        - self.get_user(player) -> User | None
        - self.status_box(player, lines)
    """

    # Type hints for expected attributes (satisfied by Game class)
    current_player: "Player | None"
    team_manager: "TeamManager"
    players: list["Player"]

    def get_user(self, player: "Player") -> "User | None":
        """Get user for player (implemented in Game)."""
        raise NotImplementedError

    def status_box(self, player: "Player", lines: list[str]) -> None:
        """Show status box to player (implemented in Game)."""
        raise NotImplementedError

    def _action_whose_turn(self, player: "Player", action_id: str) -> None:
        """Announce whose turn it is."""
        user = self.get_user(player)
        if user:
            current = self.current_player
            if current:
                user.speak_l("game-turn-start", player=current.name)
            else:
                user.speak_l("game-no-turn")

    def _action_check_scores(self, player: "Player", action_id: str) -> None:
        """Announce scores briefly."""
        user = self.get_user(player)
        if not user:
            return

        if self.team_manager.teams:
            user.speak(self.team_manager.format_scores_brief(user.locale))
        else:
            user.speak_l("no-scores-available")

    def _action_check_scores_detailed(self, player: "Player", action_id: str) -> None:
        """Show detailed scores in a status box."""
        user = self.get_user(player)
        if not user:
            return

        if self.team_manager.teams:
            lines = self.team_manager.format_scores_detailed(user.locale)
            self.status_box(player, lines)
        else:
            self.status_box(player, ["No scores available."])
