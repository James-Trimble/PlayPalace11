"""
Reusable team management utility for team-based games.

Provides Team dataclass and TeamManager for handling team assignments,
scoring, and elimination (for inverse game modes).
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mashumaro.mixins.json import DataClassJSONMixin

if TYPE_CHECKING:
    pass


@dataclass
class Team(DataClassJSONMixin):
    """A team of players."""

    index: int  # Team number (0-based)
    members: list[str] = field(default_factory=list)  # Player names
    round_score: int = 0  # Points earned this round
    total_score: int = 0  # Total points across rounds
    eliminated: bool = False  # For inverse mode


@dataclass
class TeamManager(DataClassJSONMixin):
    """
    Manages team assignments and scoring for games.

    Supports individual mode (teams of 1) and various team configurations
    like 2v2, 3v3, 2v2v2, etc.
    """

    teams: list[Team] = field(default_factory=list)
    team_mode: str = "individual"  # "individual", "2v2", "3v3", "2v2v2", etc.
    _player_to_team: dict[str, int] = field(default_factory=dict)

    def setup_teams(self, player_names: list[str]) -> None:
        """
        Create teams based on team_mode and assign players.

        Args:
            player_names: List of player names to assign to teams.
        """
        self.teams = []
        self._player_to_team = {}

        if self.team_mode == "individual":
            # Each player is their own team
            for i, name in enumerate(player_names):
                team = Team(index=i, members=[name])
                self.teams.append(team)
                self._player_to_team[name] = i
        else:
            # Parse team mode like "2v2", "3v3", "2v2v2"
            team_sizes = self._parse_team_mode(self.team_mode)
            player_idx = 0

            for team_idx, size in enumerate(team_sizes):
                members = []
                for _ in range(size):
                    if player_idx < len(player_names):
                        name = player_names[player_idx]
                        members.append(name)
                        self._player_to_team[name] = team_idx
                        player_idx += 1

                team = Team(index=team_idx, members=members)
                self.teams.append(team)

    def _parse_team_mode(self, mode: str) -> list[int]:
        """
        Parse a team mode string into list of team sizes.

        Examples:
            "2v2" -> [2, 2]
            "3v3" -> [3, 3]
            "2v2v2" -> [2, 2, 2]
            "2v3" -> [2, 3]
        """
        if mode == "individual":
            return []
        parts = mode.lower().split("v")
        return [int(p) for p in parts if p.isdigit()]

    def get_team(self, player_name: str) -> Team | None:
        """Get the team a player belongs to."""
        team_idx = self._player_to_team.get(player_name)
        if team_idx is not None and team_idx < len(self.teams):
            return self.teams[team_idx]
        return None

    def get_team_index(self, player_name: str) -> int:
        """Get the team index for a player (0 if not found)."""
        return self._player_to_team.get(player_name, 0)

    def get_teammates(self, player_name: str) -> list[str]:
        """Get names of player's teammates (excluding self)."""
        team = self.get_team(player_name)
        if team:
            return [m for m in team.members if m != player_name]
        return []

    def get_team_members(self, player_name: str) -> list[str]:
        """Get names of all players on the same team (including self)."""
        team = self.get_team(player_name)
        if team:
            return list(team.members)
        return [player_name]

    def add_to_team_score(self, player_name: str, points: int) -> None:
        """Add points to a player's team total score."""
        team = self.get_team(player_name)
        if team:
            team.total_score += points

    def add_to_team_round_score(self, player_name: str, points: int) -> None:
        """Add points to a player's team round score."""
        team = self.get_team(player_name)
        if team:
            team.round_score += points

    def commit_round_scores(self) -> None:
        """Add all round scores to total scores and reset round scores."""
        for team in self.teams:
            team.total_score += team.round_score
            team.round_score = 0

    def reset_round_scores(self) -> None:
        """Reset all team round scores to 0."""
        for team in self.teams:
            team.round_score = 0

    def reset_all_scores(self) -> None:
        """Reset all team scores to 0."""
        for team in self.teams:
            team.round_score = 0
            team.total_score = 0
            team.eliminated = False

    def get_alive_teams(self) -> list[Team]:
        """Get non-eliminated teams (for inverse mode)."""
        return [t for t in self.teams if not t.eliminated]

    def eliminate_team(self, team: Team) -> None:
        """Mark a team as eliminated."""
        team.eliminated = True

    def eliminate_by_player(self, player_name: str) -> None:
        """Eliminate the team that contains the given player."""
        team = self.get_team(player_name)
        if team:
            team.eliminated = True

    def is_team_eliminated(self, player_name: str) -> bool:
        """Check if a player's team is eliminated."""
        team = self.get_team(player_name)
        return team.eliminated if team else False

    def get_teams_at_or_above_score(self, target: int) -> list[Team]:
        """Get all teams that have reached or exceeded the target score."""
        return [t for t in self.teams if t.total_score >= target]

    def get_leading_team(self) -> Team | None:
        """Get the team with the highest total score."""
        if not self.teams:
            return None
        return max(self.teams, key=lambda t: t.total_score)

    def get_team_name(self, team: Team, locale: str = "en") -> str:
        """
        Get a display name for a team.

        For individual mode, returns the player name.
        For team mode, returns "Team N" or lists members.
        """
        if self.team_mode == "individual" and team.members:
            return team.members[0]
        if len(team.members) == 1:
            return team.members[0]
        # For actual teams, could use localization
        return f"Team {team.index + 1}"

    def get_sorted_teams(
        self, by_score: bool = True, descending: bool = True
    ) -> list[Team]:
        """
        Get teams sorted by score or index.

        Args:
            by_score: If True, sort by total_score. Otherwise by index.
            descending: If True, highest first.
        """
        key = (lambda t: t.total_score) if by_score else (lambda t: t.index)
        return sorted(self.teams, key=key, reverse=descending)

    @staticmethod
    def get_team_modes_for_player_count(num_players: int) -> list[str]:
        """
        Get valid team mode options for a given number of players.

        Args:
            num_players: Number of players in the game.

        Returns:
            List of valid team mode strings.
        """
        modes = ["individual"]

        if num_players < 2:
            return modes

        # Generate symmetric team modes (2v2, 3v3, etc.)
        for team_size in range(2, num_players // 2 + 1):
            num_teams = num_players // team_size
            if num_teams >= 2 and num_teams * team_size == num_players:
                mode = "v".join([str(team_size)] * num_teams)
                modes.append(mode)

        # Could add asymmetric modes like "2v3" for 5 players
        # but keeping it simple for now

        return modes

    @staticmethod
    def get_all_team_modes(min_players: int, max_players: int) -> list[str]:
        """
        Get all possible team mode options for a range of player counts.

        Args:
            min_players: Minimum number of players.
            max_players: Maximum number of players.

        Returns:
            Sorted list of unique team mode strings.
        """
        all_modes = set()
        for count in range(min_players, max_players + 1):
            modes = TeamManager.get_team_modes_for_player_count(count)
            all_modes.update(modes)

        # Sort: individual first, then by total players, then alphabetically
        def sort_key(mode: str) -> tuple:
            if mode == "individual":
                return (0, 0, "")
            parts = mode.split("v")
            total = sum(int(p) for p in parts)
            return (1, total, mode)

        return sorted(all_modes, key=sort_key)

    # ==========================================================================
    # Score Formatting
    # ==========================================================================

    def format_scores_brief(self, locale: str = "en") -> str:
        """
        Format scores as a brief single-line string for speaking.

        Returns something like: "Alice: 5. Bob: 3. Charlie: 1."
        """
        sorted_teams = self.get_sorted_teams(by_score=True, descending=True)
        parts = []
        for team in sorted_teams:
            name = self.get_team_name(team, locale)
            parts.append(f"{name}: {team.total_score}")
        return ". ".join(parts) + "."

    def format_scores_detailed(self, locale: str = "en") -> list[str]:
        """
        Format scores as a list of lines for a status box.

        Returns something like:
        ["Alice: 5 points", "Bob: 3 points", ...]

        No header needed - screen readers speak list items directly.
        """
        sorted_teams = self.get_sorted_teams(by_score=True, descending=True)
        lines = []
        for team in sorted_teams:
            name = self.get_team_name(team, locale)
            lines.append(f"{name}: {team.total_score} points")
        return lines
