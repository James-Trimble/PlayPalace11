"""
Mile by Mile Game Implementation for PlayPalace v11.

A racing card game based on Mille Bornes. Players race to reach a target distance
while playing hazards on opponents and defending with safeties.
"""

from dataclasses import dataclass, field
import random

from mashumaro.mixins.json import DataClassJSONMixin

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.actions import Action, ActionSet, MenuInput
from ...game_utils.bot_helper import BotHelper
from ...game_utils.options import IntOption, MenuOption, BoolOption, option_field
from ...game_utils.round_timer import RoundTimer
from ...ui.keybinds import KeybindState

from .cards import (
    Card,
    Deck,
    CardType,
    HazardType,
    RemedyType,
    SafetyType,
    HAZARD_TO_SAFETY,
    SAFETY_TO_HAZARD,
)

# Hand size
HAND_SIZE = 6


@dataclass
class MileByMileTeam(DataClassJSONMixin):
    """Team state for Mile by Mile."""

    index: int = 0
    members: list[str] = field(default_factory=list)

    # Race state
    miles: int = 0
    problems: list[str] = field(default_factory=list)  # Active hazard types
    safeties: list[str] = field(default_factory=list)  # Played safety types
    battle_pile: list[Card] = field(default_factory=list)  # Cards played on/by team

    # Scoring tracking
    used_200_mile: bool = False
    dirty_trick_count: int = 0
    round_score: int = 0
    total_score: int = 0

    # Karma rule
    has_karma: bool = True

    def has_problem(self, problem_type: str) -> bool:
        """Check if team has a specific problem."""
        return problem_type in self.problems

    def has_safety(self, safety_type: str) -> bool:
        """Check if team has a specific safety."""
        return safety_type in self.safeties

    def has_any_problem(self) -> bool:
        """Check if team has any problems (excluding speed limit)."""
        return any(p != HazardType.SPEED_LIMIT for p in self.problems)

    def add_problem(self, problem_type: str) -> None:
        """Add a problem to the team."""
        if problem_type not in self.problems:
            self.problems.append(problem_type)

    def remove_problem(self, problem_type: str) -> None:
        """Remove a problem from the team."""
        if problem_type in self.problems:
            self.problems.remove(problem_type)

    def add_safety(self, safety_type: str) -> None:
        """Add a safety to the team."""
        if safety_type not in self.safeties:
            self.safeties.append(safety_type)

    def can_play_distance(self) -> bool:
        """Check if team can play distance cards."""
        # Right of Way allows playing with any problems
        if self.has_safety(SafetyType.RIGHT_OF_WAY):
            return True
        # Otherwise, can't have any problems (except speed limit doesn't block, just restricts)
        return not self.has_any_problem()

    def reset_for_race(self) -> None:
        """Reset team state for a new race."""
        self.miles = 0
        self.problems = [HazardType.STOP]  # Everyone starts stopped
        self.safeties = []
        self.battle_pile = []
        self.used_200_mile = False
        self.dirty_trick_count = 0
        self.round_score = 0
        self.has_karma = True


@dataclass
class MileByMilePlayer(Player):
    """Player state for Mile by Mile."""

    hand: list[Card] = field(default_factory=list)
    team_index: int = 0


@dataclass
class MileByMileOptions(GameOptions):
    """Options for Mile by Mile game."""

    round_distance: int = option_field(
        IntOption(
            default=1000,
            min_val=300,
            max_val=3000,
            value_key="miles",
            label="milebymile-set-distance",
            prompt="milebymile-enter-distance",
            change_msg="milebymile-option-changed-distance",
        )
    )
    winning_score: int = option_field(
        IntOption(
            default=5000,
            min_val=1000,
            max_val=10000,
            value_key="score",
            label="milebymile-set-winning-score",
            prompt="milebymile-enter-winning-score",
            change_msg="milebymile-option-changed-winning",
        )
    )
    team_mode: str = option_field(
        MenuOption(
            default="Individual",
            value_key="mode",
            choices=["Individual", "2 Teams of 2", "2 Teams of 3", "3 Teams of 2"],
            label="game-set-team-mode",
            prompt="game-select-team-mode",
            change_msg="game-option-changed-team",
        )
    )
    only_allow_perfect_crossing: bool = option_field(
        BoolOption(
            default=True,
            value_key="enabled",
            label="milebymile-toggle-perfect-crossing",
            change_msg="milebymile-option-changed-crossing",
        )
    )
    allow_stacking_attacks: bool = option_field(
        BoolOption(
            default=False,
            value_key="enabled",
            label="milebymile-toggle-stacking",
            change_msg="milebymile-option-changed-stacking",
        )
    )
    reshuffle_discard_pile: bool = option_field(
        BoolOption(
            default=True,
            value_key="enabled",
            label="milebymile-toggle-reshuffle",
            change_msg="milebymile-option-changed-reshuffle",
        )
    )
    karma_rule: bool = option_field(
        BoolOption(
            default=False,
            value_key="enabled",
            label="milebymile-toggle-karma",
            change_msg="milebymile-option-changed-karma",
        )
    )
    rig_game: str = option_field(
        MenuOption(
            default="None",
            value_key="rig",
            choices=["None", "No Duplicates", "2x Attacks", "2x Defenses"],
            label="milebymile-set-rig",
            prompt="milebymile-select-rig",
            change_msg="milebymile-option-changed-rig",
        )
    )


@dataclass
@register_game
class MileByMileGame(Game):
    """
    Mile by Mile - A racing card game based on Mille Bornes.

    Players race to reach a target distance by playing distance cards.
    Hazards slow opponents, remedies fix problems, and safeties provide
    permanent protection. First team to reach the winning score wins.
    """

    players: list[MileByMilePlayer] = field(default_factory=list)
    options: MileByMileOptions = field(default_factory=MileByMileOptions)

    # Game state
    deck: Deck = field(default_factory=Deck)
    discard_pile: list[Card] = field(default_factory=list)
    protections_pile: list[Card] = field(
        default_factory=list
    )  # Safeties, never reshuffled
    teams: list[MileByMileTeam] = field(default_factory=list)
    current_race: int = 0
    race_winner_team_index: int | None = None

    # Dirty trick window
    dirty_trick_window_team: int | None = None
    dirty_trick_window_hazard: str | None = None
    dirty_trick_window_ticks: int = 0

    # Round timer state (serialized)
    round_timer_state: str = "idle"
    round_timer_ticks: int = 0

    def __post_init__(self):
        """Initialize runtime state."""
        super().__post_init__()
        self._round_timer = RoundTimer(self, delay_seconds=10.0)

    def rebuild_runtime_state(self) -> None:
        """Rebuild non-serialized state after deserialization."""
        super().rebuild_runtime_state()
        self._round_timer = RoundTimer(self, delay_seconds=10.0)

    @classmethod
    def get_name(cls) -> str:
        return "Mile by Mile"

    @classmethod
    def get_type(cls) -> str:
        return "milebymile"

    @classmethod
    def get_category(cls) -> str:
        return "category-card-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 9

    def create_player(
        self, player_id: str, name: str, is_bot: bool = False
    ) -> MileByMilePlayer:
        """Create a new player."""
        return MileByMilePlayer(id=player_id, name=name, is_bot=is_bot)

    # ==========================================================================
    # Team Management
    # ==========================================================================

    def _setup_teams(self) -> None:
        """Set up teams based on options."""
        active_players = self.get_active_players()
        self.teams = []

        if self.options.team_mode == "Individual":
            # Each player is their own team
            for i, player in enumerate(active_players):
                team = MileByMileTeam(index=i, members=[player.name])
                self.teams.append(team)
                player.team_index = i
        else:
            # Parse team mode (e.g., "2 Teams of 2")
            parts = self.options.team_mode.split()
            num_teams = int(parts[0])

            for i in range(num_teams):
                team = MileByMileTeam(index=i, members=[])
                self.teams.append(team)

            # Distribute players to teams
            for i, player in enumerate(active_players):
                team_idx = i % num_teams
                self.teams[team_idx].members.append(player.name)
                player.team_index = team_idx

    def get_player_team(self, player: MileByMilePlayer) -> MileByMileTeam | None:
        """Get the team for a player."""
        if 0 <= player.team_index < len(self.teams):
            return self.teams[player.team_index]
        return None

    def get_team_display_name(self, team: MileByMileTeam) -> str:
        """Get display name for a team."""
        if self.options.team_mode == "Individual":
            return team.members[0] if team.members else f"Team {team.index + 1}"
        return f"Team {team.index + 1}"

    def is_individual_mode(self) -> bool:
        """Check if game is in individual mode."""
        return self.options.team_mode == "Individual"

    # ==========================================================================
    # Action Sets
    # ==========================================================================

    def create_turn_action_set(self, player: MileByMilePlayer) -> ActionSet:
        """Create the turn action set for a player."""
        action_set = ActionSet(name="turn")

        # Card slot actions will be dynamically added/removed
        # Status action (will be repositioned after cards in _update_card_actions)
        action_set.add(
            Action(
                id="check_status",
                label="Check status",
                handler="_action_check_status",
                hidden=False,
            )
        )

        # Dirty trick action (hidden, triggered by keybind)
        action_set.add(
            Action(
                id="dirty_trick",
                label="Play dirty trick",
                handler="_action_dirty_trick",
                hidden=True,
            )
        )

        # Junk card action (hidden, triggered by shift+enter keybind)
        action_set.add(
            Action(
                id="junk_card",
                label="Discard card",
                handler="_action_junk_card",
                hidden=True,
            )
        )

        return action_set

    def setup_keybinds(self) -> None:
        """Define all keybinds for the game."""
        super().setup_keybinds()

        # Status keybind
        self.define_keybind(
            "s",
            "Check status",
            ["check_status"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )

        # Dirty trick keybind
        self.define_keybind(
            "d", "Play dirty trick", ["dirty_trick"], state=KeybindState.ACTIVE
        )

        # Number keys for card slots (1-6)
        for i in range(1, HAND_SIZE + 1):
            self.define_keybind(
                str(i), f"Play card {i}", [f"card_slot_{i}"], state=KeybindState.ACTIVE
            )

        # Shift+Enter to discard the selected card
        self.define_keybind(
            "shift+enter", "Discard card", ["junk_card"], state=KeybindState.ACTIVE
        )

    def _update_card_actions(self, player: MileByMilePlayer) -> None:
        """Update card slot actions based on player's hand."""
        turn_set = self.get_action_set(player, "turn")
        if not turn_set:
            return

        # Remove old card actions and ensure they're removed from _order
        # Note: HAND_SIZE + 2 to account for the card drawn at start of turn
        for i in range(1, HAND_SIZE + 2):
            action_id = f"card_slot_{i}"
            if turn_set.get_action(action_id):
                turn_set.remove(action_id)
            # Also ensure it's not lingering in _order
            if action_id in turn_set._order:
                turn_set._order.remove(action_id)

        # Add actions for cards in hand
        is_playing = self.status == "playing"
        is_between_races = self._round_timer.is_active

        # Get locale for this player
        user = self.get_user(player)
        locale = user.locale if user else "en"

        for i, card in enumerate(player.hand, 1):
            action_id = f"card_slot_{i}"
            playable = self._can_play_card(player, card)
            label = self._get_localized_card_name(card, locale)

            # Check if hazard with multiple targets needs menu
            input_request = None
            if card.card_type == CardType.HAZARD and playable:
                targets = self._get_valid_hazard_targets(player, card.value)
                if len(targets) > 1:
                    input_request = MenuInput(
                        prompt="milebymile-select-target",
                        options="_hazard_target_options",
                        bot_select="_bot_select_hazard_target",
                    )

            # Always show cards in menu (enabled=True), but handler checks if it's player's turn
            turn_set.add(
                Action(
                    id=action_id,
                    label=label,
                    handler="_action_play_card",
                    enabled=is_playing and not is_between_races,
                    input_request=input_request,
                )
            )

        # Move check_status to the end (after card actions)
        if "check_status" in turn_set._order:
            turn_set._order.remove("check_status")
            turn_set._order.append("check_status")

    def update_turn_actions(self, player: MileByMilePlayer) -> None:
        """Update turn action availability for a player."""
        turn_set = self.get_action_set(player, "turn")
        if not turn_set:
            return

        is_playing = self.status == "playing"
        is_current = self.current_player == player

        # Update card actions
        self._update_card_actions(player)

        # Status always available during play
        if is_playing:
            turn_set.enable("check_status")
        else:
            turn_set.disable("check_status")

        # Dirty trick only during window
        if self.dirty_trick_window_team is not None:
            team = self.get_player_team(player)
            if team and team.index == self.dirty_trick_window_team:
                turn_set.enable("dirty_trick")
            else:
                turn_set.disable("dirty_trick")
        else:
            turn_set.disable("dirty_trick")

        # Junk card available during your turn (shift+enter to discard selected card)
        is_between_races = self._round_timer.is_active
        if is_playing and is_current and not is_between_races:
            turn_set.enable("junk_card")
        else:
            turn_set.disable("junk_card")

        self.update_standard_actions(player)

    def update_all_turn_actions(self) -> None:
        """Update turn actions for all players."""
        for player in self.players:
            self.update_turn_actions(player)

    # ==========================================================================
    # Card Logic
    # ==========================================================================

    def _can_play_card(self, player: MileByMilePlayer, card: Card) -> bool:
        """Check if a card can be played."""
        team = self.get_player_team(player)
        if not team:
            return False

        if card.card_type == CardType.DISTANCE:
            return self._can_play_distance(team, card)
        elif card.card_type == CardType.HAZARD:
            return self._can_play_hazard(player, card)
        elif card.card_type == CardType.REMEDY:
            return self._can_play_remedy(team, card)
        elif card.card_type == CardType.SAFETY:
            return not team.has_safety(card.value)
        elif card.card_type == CardType.SPECIAL:
            if card.value == "false_virtue":
                return not team.has_karma
        return False

    def _get_unplayable_reason(
        self, player: MileByMilePlayer, card: Card, locale: str = "en"
    ) -> str:
        """Get a human-readable reason why a card can't be played."""
        from ...messages.localization import Localization

        team = self.get_player_team(player)
        if not team:
            return Localization.get(locale, "milebymile-reason-not-on-team")

        if card.card_type == CardType.DISTANCE:
            distance = card.distance
            if not team.can_play_distance():
                if team.has_problem(HazardType.STOP):
                    return Localization.get(locale, "milebymile-reason-stopped")
                return Localization.get(locale, "milebymile-reason-has-problem")
            if team.has_problem(HazardType.SPEED_LIMIT) and distance > 50:
                return Localization.get(locale, "milebymile-reason-speed-limit")
            if self.options.only_allow_perfect_crossing:
                if team.miles + distance > self.options.round_distance:
                    return Localization.get(
                        locale,
                        "milebymile-reason-exceeds-distance",
                        miles=self.options.round_distance,
                    )

        elif card.card_type == CardType.HAZARD:
            return Localization.get(locale, "milebymile-reason-no-targets")

        elif card.card_type == CardType.REMEDY:
            remedy = card.value
            if remedy == RemedyType.END_OF_LIMIT:
                return Localization.get(locale, "milebymile-reason-no-speed-limit")
            if remedy == RemedyType.ROLL:
                if team.has_safety(SafetyType.RIGHT_OF_WAY):
                    return Localization.get(
                        locale, "milebymile-reason-has-right-of-way"
                    )
                if not team.has_problem(HazardType.STOP):
                    return Localization.get(locale, "milebymile-reason-already-moving")
                # Check for other problems
                for problem in team.problems:
                    if problem not in (HazardType.STOP, HazardType.SPEED_LIMIT):
                        problem_name = self._get_localized_problem_name(problem, locale)
                        return Localization.get(
                            locale,
                            "milebymile-reason-must-fix-first",
                            problem=problem_name,
                        )
            if remedy == RemedyType.GASOLINE:
                return Localization.get(locale, "milebymile-reason-has-gas")
            if remedy == RemedyType.SPARE_TIRE:
                return Localization.get(locale, "milebymile-reason-tires-fine")
            if remedy == RemedyType.REPAIRS:
                return Localization.get(locale, "milebymile-reason-no-accident")

        elif card.card_type == CardType.SAFETY:
            return Localization.get(locale, "milebymile-reason-has-safety")

        elif card.card_type == CardType.SPECIAL:
            if card.value == "false_virtue":
                return Localization.get(locale, "milebymile-reason-has-karma")

        return Localization.get(locale, "milebymile-reason-generic")

    def _get_localized_problem_name(self, problem: str, locale: str) -> str:
        """Get localized name for a problem/hazard type."""
        from ...messages.localization import Localization

        key_map = {
            HazardType.OUT_OF_GAS: "milebymile-card-out-of-gas",
            HazardType.FLAT_TIRE: "milebymile-card-flat-tire",
            HazardType.ACCIDENT: "milebymile-card-accident",
            HazardType.SPEED_LIMIT: "milebymile-card-speed-limit",
            HazardType.STOP: "milebymile-card-stop",
        }
        key = key_map.get(problem, "")
        return Localization.get(locale, key) if key else problem

    def _get_localized_safety_name(self, safety: str, locale: str) -> str:
        """Get localized name for a safety type."""
        from ...messages.localization import Localization

        key_map = {
            SafetyType.EXTRA_TANK: "milebymile-card-extra-tank",
            SafetyType.PUNCTURE_PROOF: "milebymile-card-puncture-proof",
            SafetyType.DRIVING_ACE: "milebymile-card-driving-ace",
            SafetyType.RIGHT_OF_WAY: "milebymile-card-right-of-way",
        }
        key = key_map.get(safety, "")
        return Localization.get(locale, key) if key else safety

    def _get_localized_card_name(self, card: Card, locale: str) -> str:
        """Get localized name for a card."""
        from ...messages.localization import Localization

        if card.card_type == CardType.DISTANCE:
            return Localization.get(locale, "milebymile-card-miles", miles=card.value)

        key_map = {
            # Hazards
            HazardType.OUT_OF_GAS: "milebymile-card-out-of-gas",
            HazardType.FLAT_TIRE: "milebymile-card-flat-tire",
            HazardType.ACCIDENT: "milebymile-card-accident",
            HazardType.SPEED_LIMIT: "milebymile-card-speed-limit",
            HazardType.STOP: "milebymile-card-stop",
            # Remedies
            RemedyType.GASOLINE: "milebymile-card-gasoline",
            RemedyType.SPARE_TIRE: "milebymile-card-spare-tire",
            RemedyType.REPAIRS: "milebymile-card-repairs",
            RemedyType.END_OF_LIMIT: "milebymile-card-end-of-limit",
            RemedyType.ROLL: "milebymile-card-green-light",
            # Safeties
            SafetyType.EXTRA_TANK: "milebymile-card-extra-tank",
            SafetyType.PUNCTURE_PROOF: "milebymile-card-puncture-proof",
            SafetyType.DRIVING_ACE: "milebymile-card-driving-ace",
            SafetyType.RIGHT_OF_WAY: "milebymile-card-right-of-way",
            # Special
            "false_virtue": "milebymile-card-false-virtue",
        }
        key = key_map.get(card.value, "")
        return Localization.get(locale, key) if key else card.name

    def _can_play_distance(self, team: MileByMileTeam, card: Card) -> bool:
        """Check if team can play a distance card."""
        if not team.can_play_distance():
            return False

        distance = card.distance

        # Check speed limit
        if team.has_problem(HazardType.SPEED_LIMIT) and distance > 50:
            return False

        # Check perfect crossing
        if self.options.only_allow_perfect_crossing:
            if team.miles + distance > self.options.round_distance:
                return False

        return True

    def _can_play_hazard(self, player: MileByMilePlayer, card: Card) -> bool:
        """Check if hazard can be played on any opponent."""
        attacker_team = self.get_player_team(player)
        if not attacker_team:
            return False

        for team in self.teams:
            if team.index == attacker_team.index:
                continue
            if self._can_play_hazard_on_team(card.value, team, attacker_team):
                return True
        return False

    def _can_play_hazard_on_team(
        self, hazard: str, target: MileByMileTeam, attacker: MileByMileTeam
    ) -> bool:
        """Check if hazard can be played on a specific team."""
        # Check if target has blocking safety
        blocking_safety = HAZARD_TO_SAFETY.get(hazard)
        if blocking_safety and target.has_safety(blocking_safety):
            return False

        # Karma rule check
        if self.options.karma_rule:
            if not attacker.has_karma and target.has_karma:
                return False

        # Check for existing problems
        if hazard == HazardType.SPEED_LIMIT:
            # Speed limit just checks for duplicate
            return not target.has_problem(hazard)
        else:
            # Critical hazards: can't stack unless option enabled
            if self.options.allow_stacking_attacks:
                return not target.has_problem(hazard)
            else:
                return not target.has_any_problem()

    def _can_play_remedy(self, team: MileByMileTeam, card: Card) -> bool:
        """Check if remedy can be played."""
        remedy = card.value

        if remedy == RemedyType.END_OF_LIMIT:
            return team.has_problem(HazardType.SPEED_LIMIT)

        if remedy == RemedyType.ROLL:
            # Can't play if have Right of Way
            if team.has_safety(SafetyType.RIGHT_OF_WAY):
                return False
            # Must have stop problem
            if not team.has_problem(HazardType.STOP):
                return False
            # Can't have other problems (except speed limit)
            for problem in team.problems:
                if problem not in (HazardType.STOP, HazardType.SPEED_LIMIT):
                    return False
            return True

        # Specific remedies
        remedy_to_hazard = {
            RemedyType.GASOLINE: HazardType.OUT_OF_GAS,
            RemedyType.SPARE_TIRE: HazardType.FLAT_TIRE,
            RemedyType.REPAIRS: HazardType.ACCIDENT,
        }
        hazard = remedy_to_hazard.get(remedy)
        return hazard and team.has_problem(hazard)

    def _get_valid_hazard_targets(
        self, player: MileByMilePlayer, hazard: str
    ) -> list[MileByMileTeam]:
        """Get list of teams that can be targeted by a hazard."""
        attacker_team = self.get_player_team(player)
        if not attacker_team:
            return []

        targets = []
        for team in self.teams:
            if team.index == attacker_team.index:
                continue
            if self._can_play_hazard_on_team(hazard, team, attacker_team):
                targets.append(team)
        return targets

    # ==========================================================================
    # Action Handlers
    # ==========================================================================

    def _action_check_status(self, player: Player, action_id: str) -> None:
        """Show game status to player."""
        user = self.get_user(player)
        if not user:
            return

        from ...messages.localization import Localization

        locale = user.locale
        none_str = Localization.get(locale, "milebymile-none")

        for team in self.teams:
            name = self.get_team_display_name(team)
            if team.problems:
                problems_str = ", ".join(
                    self._get_localized_problem_name(p, locale) for p in team.problems
                )
            else:
                problems_str = none_str
            if team.safeties:
                safeties_str = ", ".join(
                    self._get_localized_safety_name(s, locale) for s in team.safeties
                )
            else:
                safeties_str = none_str

            user.speak_l(
                "milebymile-status",
                name=name,
                miles=team.miles,
                problems=problems_str,
                safeties=safeties_str,
            )

    def _action_dirty_trick(self, player: Player, action_id: str) -> None:
        """Handle dirty trick (Coup Fourré) attempt."""
        if not isinstance(player, MileByMilePlayer):
            return

        team = self.get_player_team(player)
        if not team or self.dirty_trick_window_team != team.index:
            return

        hazard = self.dirty_trick_window_hazard
        if not hazard:
            return

        # Find matching safety in hand
        blocking_safety = HAZARD_TO_SAFETY.get(hazard)
        if not blocking_safety:
            return

        safety_card = None
        card_index = -1
        for i, card in enumerate(player.hand):
            if card.card_type == CardType.SAFETY and card.value == blocking_safety:
                safety_card = card
                card_index = i
                break

        if not safety_card:
            user = self.get_user(player)
            if user:
                user.speak_l("milebymile-no-matching-safety")
            return

        # Play the dirty trick!
        self._play_safety(player, card_index, safety_card, is_dirty_trick=True)

        # Close the window
        self.dirty_trick_window_team = None
        self.dirty_trick_window_hazard = None
        self.dirty_trick_window_ticks = 0

    def _hazard_target_options(self, player: Player) -> list[str]:
        """Get list of valid hazard target names for menu input."""
        if not isinstance(player, MileByMilePlayer):
            return []

        # Get the pending action to find which card slot
        action_id = self._pending_actions.get(player.name)
        if not action_id:
            return []

        try:
            slot = int(action_id.split("_")[-1]) - 1
        except ValueError:
            return []

        if slot < 0 or slot >= len(player.hand):
            return []

        card = player.hand[slot]
        if card.card_type != CardType.HAZARD:
            return []

        targets = self._get_valid_hazard_targets(player, card.value)
        # Format like v10: "Name (X miles)" for individual, "Team N: members (X miles)" for teams
        options = []
        for team in targets:
            if self.is_individual_mode():
                options.append(f"{team.members[0]} ({team.miles} miles)")
            else:
                members = ", ".join(team.members)
                options.append(f"Team {team.index + 1}: {members} ({team.miles} miles)")
        return options

    def _bot_select_hazard_target(
        self, player: Player, options: list[str]
    ) -> str | None:
        """Bot selects hazard target - picks team with most miles."""
        if not isinstance(player, MileByMilePlayer):
            return None

        action_id = self._pending_actions.get(player.name)
        if not action_id:
            return None

        try:
            slot = int(action_id.split("_")[-1]) - 1
        except ValueError:
            return None

        if slot < 0 or slot >= len(player.hand):
            return None

        card = player.hand[slot]
        if card.card_type != CardType.HAZARD:
            return None

        targets = self._get_valid_hazard_targets(player, card.value)
        if not targets:
            return None

        # Pick target with most miles
        best_target = max(targets, key=lambda t: t.miles)
        # Return in same format as _hazard_target_options
        if self.is_individual_mode():
            return f"{best_target.members[0]} ({best_target.miles} miles)"
        else:
            members = ", ".join(best_target.members)
            return (
                f"Team {best_target.index + 1}: {members} ({best_target.miles} miles)"
            )

    def _action_play_card(self, player: Player, *args) -> None:
        """Handle playing a card from hand.

        Can be called as:
        - _action_play_card(player, action_id) - no input
        - _action_play_card(player, input_value, action_id) - with menu input
        """
        if not isinstance(player, MileByMilePlayer):
            return

        # Check if it's this player's turn
        if self.current_player != player:
            return

        # Parse arguments - handler can receive (player, action_id) or (player, input_value, action_id)
        if len(args) == 1:
            action_id = args[0]
            input_value = None
        elif len(args) == 2:
            input_value, action_id = args
        else:
            return

        # Extract slot number from action_id (e.g., "card_slot_1" -> 0)
        try:
            slot = int(action_id.split("_")[-1]) - 1
        except ValueError:
            return

        if slot < 0 or slot >= len(player.hand):
            return

        card = player.hand[slot]

        if self._can_play_card(player, card):
            self._play_card(player, slot, card, input_value)
        else:
            # Can't play - tell human players why, bots auto-discard
            if player.is_bot:
                self._discard_card(player, slot, card)
            else:
                user = self.get_user(player)
                if user:
                    reason = self._get_unplayable_reason(player, card, user.locale)
                    card_name = self._get_localized_card_name(card, user.locale)
                    user.speak_l("milebymile-cant-play", card=card_name, reason=reason)

    def _action_junk_card(self, player: Player, action_id: str) -> None:
        """Handle discarding the currently selected card (shift+enter keybind)."""
        if not isinstance(player, MileByMilePlayer):
            return

        # Check if it's this player's turn
        if self.current_player != player:
            return

        # Get the selected menu item from context
        context = self.get_action_context(player)
        menu_item_id = context.menu_item_id

        if not menu_item_id or not menu_item_id.startswith("card_slot_"):
            user = self.get_user(player)
            if user:
                user.speak_l("milebymile-no-card-selected")
            return

        # Extract slot number from menu_item_id
        try:
            slot = int(menu_item_id.split("_")[-1]) - 1
        except ValueError:
            return

        if slot < 0 or slot >= len(player.hand):
            return

        card = player.hand[slot]
        self._discard_card(player, slot, card)

    def _play_card(
        self,
        player: MileByMilePlayer,
        slot: int,
        card: Card,
        target_name: str | None = None,
    ) -> None:
        """Play a card from hand."""
        if card.card_type == CardType.DISTANCE:
            self._play_distance(player, slot, card)
        elif card.card_type == CardType.HAZARD:
            self._play_hazard(player, slot, card, target_name)
        elif card.card_type == CardType.REMEDY:
            self._play_remedy(player, slot, card)
        elif card.card_type == CardType.SAFETY:
            self._play_safety(player, slot, card, is_dirty_trick=False)
        elif card.card_type == CardType.SPECIAL:
            self._play_special(player, slot, card)

    def _play_distance(self, player: MileByMilePlayer, slot: int, card: Card) -> None:
        """Play a distance card."""
        team = self.get_player_team(player)
        if not team:
            return

        distance = card.distance
        player.hand.pop(slot)
        team.miles += distance

        if distance == 200:
            team.used_200_mile = True

        # Play sounds
        self.play_sound(f"game_cards/play{random.randint(1, 4)}.ogg")

        # Distance-specific sounds
        sound_variants = {25: 2, 50: 3, 75: 3, 100: 3, 200: 3}
        if distance in sound_variants:
            variant = random.randint(1, sound_variants[distance])
            self.play_sound(f"game_milebymile/{distance}miles{variant}.ogg")

        # Announce
        if self.is_individual_mode():
            self.broadcast_l(
                "milebymile-plays-distance-individual",
                player=player.name,
                distance=distance,
                total=team.miles,
            )
        else:
            self.broadcast_l(
                "milebymile-plays-distance-team",
                player=player.name,
                distance=distance,
                total=team.miles,
            )

        self.discard_pile.append(card)

        # Check for race win
        if team.miles >= self.options.round_distance:
            if (
                team.miles == self.options.round_distance
                and not self.options.only_allow_perfect_crossing
            ):
                if self.is_individual_mode():
                    self.broadcast_l(
                        "milebymile-journey-complete-perfect-individual",
                        player=player.name,
                    )
                else:
                    self.broadcast_l(
                        "milebymile-journey-complete-perfect-team", team=team.index + 1
                    )
            else:
                if self.is_individual_mode():
                    self.broadcast_l(
                        "milebymile-journey-complete-individual", player=player.name
                    )
                else:
                    self.broadcast_l(
                        "milebymile-journey-complete-team", team=team.index + 1
                    )

            self.play_sound("game_milebymile/winround.ogg")
            self.race_winner_team_index = team.index

        self._end_turn()

    def _play_hazard(
        self,
        player: MileByMilePlayer,
        slot: int,
        card: Card,
        target_selection: str | None = None,
    ) -> None:
        """Play a hazard card on an opponent."""
        attacker_team = self.get_player_team(player)
        if not attacker_team:
            return

        targets = self._get_valid_hazard_targets(player, card.value)
        if not targets:
            user = self.get_user(player)
            if user:
                user.speak_l("milebymile-no-valid-targets")
            return

        # Find target team
        if target_selection:
            # Target was selected from menu - parse the selection string
            # Format: "Name (X miles)" or "Team N: members (X miles)"
            target_team = None
            if self.is_individual_mode():
                # Extract name from "Name (X miles)"
                name = (
                    target_selection.split(" (")[0]
                    if " (" in target_selection
                    else target_selection
                )
                for team in targets:
                    if team.members and team.members[0] == name:
                        target_team = team
                        break
            else:
                # Extract team number from "Team N: members (X miles)"
                if target_selection.startswith("Team "):
                    try:
                        team_num = int(
                            target_selection.split(":")[0].replace("Team ", "")
                        )
                        for team in targets:
                            if team.index + 1 == team_num:
                                target_team = team
                                break
                    except (ValueError, IndexError):
                        pass
            if not target_team:
                return
        elif len(targets) == 1:
            target_team = targets[0]
        else:
            # Multiple targets but no selection - shouldn't happen with MenuInput
            target_team = targets[0]

        player.hand.pop(slot)

        # Karma rule: handle karma interactions
        attacker_shunned = False
        if self.options.karma_rule:
            if attacker_team.has_karma and target_team.has_karma:
                # Both have karma - attack neutralized
                attacker_team.has_karma = False
                target_team.has_karma = False

                self.play_sound(f"game_cards/play{random.randint(1, 4)}.ogg")

                # First announce the attack
                if self.is_individual_mode():
                    target_name = target_team.members[0]
                    self._broadcast_card_message(
                        "milebymile-plays-hazard-individual",
                        card,
                        player=player.name,
                        target=target_name,
                    )
                else:
                    self._broadcast_card_message(
                        "milebymile-plays-hazard-team",
                        card,
                        player=player.name,
                        team=target_team.index + 1,
                    )

                # Then announce neutralization with personalized messages
                self._announce_karma_clash(player, attacker_team, target_team)

                self.discard_pile.append(card)
                self._end_turn()
                return

            elif attacker_team.has_karma and not target_team.has_karma:
                # Attacker loses karma
                attacker_team.has_karma = False
                attacker_shunned = True

        # Apply hazard
        target_team.battle_pile.append(card)
        target_team.add_problem(card.value)

        # All hazards except speed limit also add stop
        if card.value != HazardType.SPEED_LIMIT:
            if not target_team.has_safety(SafetyType.RIGHT_OF_WAY):
                target_team.add_problem(HazardType.STOP)

        # Announce
        self.play_sound(f"game_cards/play{random.randint(1, 4)}.ogg")

        # Hazard-specific sounds
        hazard_sounds = {
            HazardType.ACCIDENT: f"game_milebymile/crash{random.randint(1, 2)}.ogg",
            HazardType.OUT_OF_GAS: "game_milebymile/outofgas.ogg",
            HazardType.FLAT_TIRE: "game_milebymile/flat.ogg",
            HazardType.STOP: "game_milebymile/stop.ogg",
            HazardType.SPEED_LIMIT: "game_milebymile/speedlimit.ogg",
        }
        if card.value in hazard_sounds:
            self.play_sound(hazard_sounds[card.value])

        if self.is_individual_mode():
            target_name = target_team.members[0]
            self._broadcast_card_message(
                "milebymile-plays-hazard-individual",
                card,
                player=player.name,
                target=target_name,
            )
        else:
            self._broadcast_card_message(
                "milebymile-plays-hazard-team",
                card,
                player=player.name,
                team=target_team.index + 1,
            )

        # Announce karma loss (personalized)
        if attacker_shunned:
            self._announce_attacker_shunned(player, attacker_team)

        # Open dirty trick window
        self.dirty_trick_window_team = target_team.index
        self.dirty_trick_window_hazard = card.value
        self.dirty_trick_window_ticks = 60  # 3 seconds at 20 ticks/sec

        # Schedule bot dirty trick check
        for member_name in target_team.members:
            member = self._get_player_by_name(member_name)
            if member and member.is_bot:
                BotHelper.jolt_bot(member, ticks=random.randint(12, 18))

        self._end_turn()

    def _play_remedy(self, player: MileByMilePlayer, slot: int, card: Card) -> None:
        """Play a remedy card."""
        team = self.get_player_team(player)
        if not team:
            return

        player.hand.pop(slot)
        team.battle_pile.append(card)

        remedy = card.value
        self.play_sound(f"game_cards/play{random.randint(1, 4)}.ogg")

        if remedy == RemedyType.END_OF_LIMIT:
            team.remove_problem(HazardType.SPEED_LIMIT)
            self.play_sound("game_milebymile/speedlimitend.ogg")
        elif remedy == RemedyType.ROLL:
            team.remove_problem(HazardType.STOP)
            self.play_sound(f"game_milebymile/greenlight{random.randint(1, 3)}.ogg")
        elif remedy == RemedyType.GASOLINE:
            team.remove_problem(HazardType.OUT_OF_GAS)
            self.play_sound("game_milebymile/gas.ogg")
        elif remedy == RemedyType.SPARE_TIRE:
            team.remove_problem(HazardType.FLAT_TIRE)
            self.play_sound("game_milebymile/sparetyre.ogg")
        elif remedy == RemedyType.REPAIRS:
            team.remove_problem(HazardType.ACCIDENT)
            self.play_sound(f"game_milebymile/repair{random.randint(1, 2)}.ogg")

        self._broadcast_card_message("milebymile-plays-card", card, player=player.name)
        self.discard_pile.append(card)
        self._end_turn()

    def _play_safety(
        self,
        player: MileByMilePlayer,
        slot: int,
        card: Card,
        is_dirty_trick: bool = False,
    ) -> None:
        """Play a safety card."""
        team = self.get_player_team(player)
        if not team:
            return

        player.hand.pop(slot)
        team.add_safety(card.value)

        if is_dirty_trick:
            team.dirty_trick_count += 1
            self._broadcast_card_message(
                "milebymile-plays-dirty-trick", card, player=player.name
            )
            self.play_sound("mention.ogg")

            # Remove the hazard that triggered this
            hazard = SAFETY_TO_HAZARD.get(card.value)
            if hazard:
                team.remove_problem(hazard)
            if card.value == SafetyType.RIGHT_OF_WAY:
                team.remove_problem(HazardType.SPEED_LIMIT)
                team.remove_problem(HazardType.STOP)

            # Clean up remaining stop if no other problems
            if len(team.problems) == 1 and HazardType.STOP in team.problems:
                team.remove_problem(HazardType.STOP)
        else:
            self._broadcast_card_message(
                "milebymile-plays-card", card, player=player.name
            )
            self.play_sound(f"game_cards/play{random.randint(1, 4)}.ogg")

            # Safety-specific sounds
            safety_sounds = {
                SafetyType.DRIVING_ACE: "game_milebymile/drivingace.ogg",
                SafetyType.EXTRA_TANK: f"game_milebymile/extratank{random.randint(1, 2)}.ogg",
                SafetyType.PUNCTURE_PROOF: "game_milebymile/punctureproof.ogg",
                SafetyType.RIGHT_OF_WAY: "game_milebymile/rightofway.ogg",
            }
            if card.value in safety_sounds:
                self.play_sound(safety_sounds[card.value])

            # Remove matching problem
            hazard = SAFETY_TO_HAZARD.get(card.value)
            if hazard:
                team.remove_problem(hazard)
            if card.value == SafetyType.RIGHT_OF_WAY:
                team.remove_problem(HazardType.SPEED_LIMIT)
                team.remove_problem(HazardType.STOP)

        # Safety cards go to protections pile (never reshuffled)
        self.protections_pile.append(card)

        # Safety grants extra turn - draw replacement and continue
        new_card = self._draw_card(player)
        if new_card:
            player.hand.append(new_card)
            user = self.get_user(player)
            if user:
                card_name = self._get_localized_card_name(new_card, user.locale)
                user.speak_l("milebymile-you-drew", card=card_name)

        self.update_turn_actions(player)
        self.rebuild_player_menu(player)
        # Don't end turn - safety grants extra turn

        # Jolt bot to think about next play
        if player.is_bot:
            BotHelper.jolt_bot(player, ticks=random.randint(30, 40))

    def _play_special(self, player: MileByMilePlayer, slot: int, card: Card) -> None:
        """Play a special card (False Virtue)."""
        team = self.get_player_team(player)
        if not team:
            return

        player.hand.pop(slot)

        if card.value == "false_virtue":
            team.has_karma = True
            self.play_sound(f"game_cards/play{random.randint(1, 4)}.ogg")

            # Personalized messages like v10
            self._announce_false_virtue(player, team)

        self.protections_pile.append(card)
        self._end_turn()

    def _discard_card(self, player: MileByMilePlayer, slot: int, card: Card) -> None:
        """Discard a card."""
        player.hand.pop(slot)

        # Safety cards go to protections to prevent reshuffling
        if card.card_type == CardType.SAFETY:
            self.protections_pile.append(card)
        else:
            self.discard_pile.append(card)

        self.broadcast_l("milebymile-discards", player=player.name)
        self.play_sound(f"game_cards/discard{random.randint(1, 3)}.ogg")
        self._end_turn()

    # ==========================================================================
    # Deck Management
    # ==========================================================================

    def _draw_card(self, player: MileByMilePlayer) -> Card | None:
        """Draw a card for a player."""
        if self.deck.is_empty():
            if not self.discard_pile or not self.options.reshuffle_discard_pile:
                return None
            # Reshuffle discard pile
            self.deck.add_all(self.discard_pile)
            self.discard_pile = []
            self.deck.shuffle()
            self.broadcast_l("milebymile-deck-reshuffled")
            self.play_sound(f"game_cards/shuffle{random.randint(1, 3)}.ogg")

        if self.options.rig_game == "No Duplicates":
            return self.deck.draw_non_duplicate(player.hand)
        return self.deck.draw()

    def _deal_initial_hands(self) -> None:
        """Deal initial hands to all players."""
        active_players = self.get_active_players()
        for player in active_players:
            player.hand = []
            for _ in range(HAND_SIZE):
                card = self._draw_card(player)
                if card:
                    player.hand.append(card)

    # ==========================================================================
    # Game Flow
    # ==========================================================================

    def on_start(self) -> None:
        """Called when the game starts."""
        self.status = "playing"
        self.game_active = True
        self.current_race = 0

        # Set up teams
        self._setup_teams()

        # Initialize turn order
        active_players = self.get_active_players()
        self.set_turn_players(active_players)

        # Update actions
        self.update_all_lobby_actions()
        self.update_all_options_actions()

        # Play music and ambience
        self.play_music("game_milebymile/music.ogg")
        self.play_ambience("game_milebymile/amloop.ogg")

        # Start first race
        self._start_race()

    def _start_race(self) -> None:
        """Start a new race."""
        self.current_race += 1
        self.race_winner_team_index = None

        # Reset teams for new race
        for team in self.teams:
            team.reset_for_race()

        # Build and shuffle deck
        attack_mult = 2 if self.options.rig_game == "2x Attacks" else 1
        defense_mult = 2 if self.options.rig_game == "2x Defenses" else 1
        self.deck = Deck()
        self.deck.build_standard_deck(
            attack_multiplier=attack_mult,
            defense_multiplier=defense_mult,
            include_karma_cards=self.options.karma_rule,
        )
        self.deck.shuffle()

        self.discard_pile = []
        self.protections_pile = []

        # Deal hands
        self._deal_initial_hands()

        self.play_sound("game_pig/roundstart.ogg")
        self.broadcast_l("milebymile-new-race")

        # Start first turn
        self.reset_turn_order()
        self._start_turn()

    def _start_turn(self) -> None:
        """Start a player's turn."""
        player = self.current_player
        if not player or not isinstance(player, MileByMilePlayer):
            return

        # Draw a card at start of turn
        card = self._draw_card(player)
        if card:
            player.hand.append(card)
            self.play_sound(f"game_cards/draw{random.randint(1, 4)}.ogg")
            user = self.get_user(player)
            if user:
                card_name = self._get_localized_card_name(card, user.locale)
                user.speak_l("milebymile-you-drew", card=card_name)

        # Announce turn
        self.announce_turn()

        if player.is_bot:
            BotHelper.jolt_bot(player, ticks=random.randint(30, 50))

        self.update_all_turn_actions()
        self.rebuild_all_menus()

    def _end_turn(self) -> None:
        """End current player's turn."""
        # Don't process turns during countdown
        if self._round_timer.is_active:
            return

        # Check for race end
        if self.race_winner_team_index is not None:
            self._end_race()
            return

        # Check for deck exhaustion
        if self.deck.is_empty() and not self.discard_pile:
            if not self.options.reshuffle_discard_pile:
                # Check if all hands empty
                all_empty = all(len(p.hand) == 0 for p in self.get_active_players())
                if all_empty:
                    self._end_race()
                    return

        # Advance to next player
        BotHelper.jolt_bots(self, ticks=random.randint(15, 25))
        self.advance_turn(announce=False)
        self._start_turn()

    def _end_race(self) -> None:
        """End the current race and calculate scores."""
        # Find winner (team with most miles if no one reached target)
        winning_team = None
        if self.race_winner_team_index is not None:
            winning_team = self.teams[self.race_winner_team_index]
        else:
            # Find team with most miles
            max_miles = -1
            for team in self.teams:
                if team.miles > max_miles:
                    max_miles = team.miles
                    winning_team = team

        self.broadcast_l("milebymile-race-complete")

        # Calculate and announce scores
        self._calculate_race_scores(winning_team)

        # Check for game winner
        game_winner = self._check_game_winner()
        if game_winner:
            self._end_game(game_winner)
        else:
            # Start next race after delay (silent countdown)
            self._round_timer.start()
            # Disable all actions during countdown
            self.update_all_turn_actions()
            self.rebuild_all_menus()

    def on_round_timer_ready(self) -> None:
        """Called when round timer expires - start the next race."""
        self._start_race()

    def _calculate_race_scores(self, winning_team: MileByMileTeam | None) -> None:
        """Calculate and announce race scores."""
        from ...messages.localization import Localization

        for team in self.teams:
            base_miles = min(team.miles, self.options.round_distance)
            score = base_miles
            # Store bonus keys and their parameters for localization
            bonus_parts: list[tuple[str, dict]] = []  # (message_key, params)

            if team == winning_team and team.miles >= self.options.round_distance:
                # Trip complete bonus
                score += 400
                bonus_parts.append(("milebymile-from-trip", {"points": 400}))

                # Perfect crossing (only if not forced)
                if not self.options.only_allow_perfect_crossing:
                    if team.miles == self.options.round_distance:
                        score += 200
                        bonus_parts.append(("milebymile-from-perfect", {"points": 200}))

                # Safe trip (no 200s)
                if not team.used_200_mile:
                    score += 300
                    bonus_parts.append(("milebymile-from-safe", {"points": 300}))

                # Shut out
                if all(t.miles == 0 for t in self.teams if t != team):
                    score += 500
                    bonus_parts.append(("milebymile-from-shutout", {"points": 500}))

            # Safety bonuses (all teams)
            safety_count = len(team.safeties)
            if safety_count > 0:
                safety_bonus = safety_count * 100
                score += safety_bonus
                bonus_parts.append(
                    (
                        "milebymile-from-safeties",
                        {"points": safety_bonus, "count": safety_count},
                    )
                )

            # All 4 safeties bonus
            if safety_count == 4:
                score += 300
                bonus_parts.append(("milebymile-from-all-safeties", {"points": 300}))

            # Dirty trick bonuses
            if team.dirty_trick_count > 0:
                dt_bonus = team.dirty_trick_count * 300
                score += dt_bonus
                bonus_parts.append(
                    (
                        "milebymile-from-dirty-tricks",
                        {"points": dt_bonus, "count": team.dirty_trick_count},
                    )
                )

            team.round_score = score
            team.total_score += score

            # Announce to each player in their locale
            name = self.get_team_display_name(team)
            for p in self.players:
                user = self.get_user(p)
                if not user:
                    continue
                locale = user.locale

                # Build localized bonus descriptions
                bonus_descriptions = [
                    Localization.get(
                        locale, "milebymile-from-distance", miles=base_miles
                    )
                ]
                for key, params in bonus_parts:
                    bonus_descriptions.append(Localization.get(locale, key, **params))

                # Format list with babel via Localization wrapper
                breakdown = Localization.format_list_and(locale, bonus_descriptions)
                user.speak_l(
                    "milebymile-earned-points",
                    name=name,
                    score=score,
                    breakdown=breakdown,
                )

        # Announce total scores
        self.broadcast_l("milebymile-total-scores")
        for team in self.teams:
            name = self.get_team_display_name(team)
            self.broadcast_l("milebymile-team-score", name=name, score=team.total_score)

    def _check_game_winner(self) -> MileByMileTeam | None:
        """Check if any team has won the game."""
        for team in self.teams:
            if team.total_score >= self.options.winning_score:
                # Find team with highest score
                best = team
                for other in self.teams:
                    if other.total_score > best.total_score:
                        best = other
                return best
        return None

    def _end_game(self, winner: MileByMileTeam) -> None:
        """End the game with a winner."""
        self.play_sound("game_pig/win.ogg")

        if self.is_individual_mode():
            self.broadcast_l("milebymile-wins-individual", player=winner.members[0])
        else:
            members_str = ", ".join(winner.members)
            self.broadcast_l(
                "milebymile-wins-team", team=winner.index + 1, members=members_str
            )
        self.broadcast_l("milebymile-final-score", score=winner.total_score)

        self.finish_game()
        self._show_final_scores()

    def _show_final_scores(self) -> None:
        """Show final scores to all players."""
        sorted_teams = sorted(self.teams, key=lambda t: t.total_score, reverse=True)
        lines = ["Final Scores:"]
        for i, team in enumerate(sorted_teams, 1):
            name = self.get_team_display_name(team)
            lines.append(f"{i}. {name}: {team.total_score} points")
        self.show_game_end_menu(lines)

    def _get_player_by_name(self, name: str) -> MileByMilePlayer | None:
        """Get a player by name."""
        for player in self.players:
            if player.name == name:
                return player
        return None

    # ==========================================================================
    # Karma Announcements (personalized per player like v10)
    # ==========================================================================

    def _announce_karma_clash(
        self,
        attacker: MileByMilePlayer,
        attacker_team: MileByMileTeam,
        target_team: MileByMileTeam,
    ) -> None:
        """Announce when both attacker and target lose karma (attack neutralized)."""
        if self.is_individual_mode():
            target_name = target_team.members[0]
            for p in self.players:
                user = self.get_user(p)
                if not user:
                    continue
                if p == attacker:
                    user.speak_l("milebymile-karma-clash-you-target")
                elif p.name == target_name:
                    user.speak_l(
                        "milebymile-karma-clash-you-attacker", attacker=attacker.name
                    )
                else:
                    user.speak_l(
                        "milebymile-karma-clash-others",
                        attacker=attacker.name,
                        target=target_name,
                    )
        else:
            for p in self.players:
                user = self.get_user(p)
                if not user:
                    continue
                player_team = self.get_player_team(p)
                if player_team == attacker_team:
                    user.speak_l("milebymile-karma-clash-your-team")
                elif player_team == target_team:
                    user.speak_l(
                        "milebymile-karma-clash-target-team",
                        team=attacker_team.index + 1,
                    )
                else:
                    user.speak_l(
                        "milebymile-karma-clash-other-teams",
                        attacker=attacker_team.index + 1,
                        target=target_team.index + 1,
                    )

    def _announce_attacker_shunned(
        self, attacker: MileByMilePlayer, attacker_team: MileByMileTeam
    ) -> None:
        """Announce when attacker loses karma for attacking."""
        if self.is_individual_mode():
            for p in self.players:
                user = self.get_user(p)
                if not user:
                    continue
                if p == attacker:
                    user.speak_l("milebymile-karma-shunned-you")
                else:
                    user.speak_l("milebymile-karma-shunned-other", player=attacker.name)
        else:
            for p in self.players:
                user = self.get_user(p)
                if not user:
                    continue
                player_team = self.get_player_team(p)
                if player_team == attacker_team:
                    user.speak_l("milebymile-karma-shunned-your-team")
                else:
                    user.speak_l(
                        "milebymile-karma-shunned-other-team",
                        team=attacker_team.index + 1,
                    )

    def _announce_false_virtue(
        self, player: MileByMilePlayer, team: MileByMileTeam
    ) -> None:
        """Announce when a player plays False Virtue to regain karma."""
        if self.is_individual_mode():
            for p in self.players:
                user = self.get_user(p)
                if not user:
                    continue
                if p == player:
                    user.speak_l("milebymile-false-virtue-you")
                else:
                    user.speak_l("milebymile-false-virtue-other", player=player.name)
        else:
            for p in self.players:
                user = self.get_user(p)
                if not user:
                    continue
                player_team = self.get_player_team(p)
                if player_team == team:
                    user.speak_l("milebymile-false-virtue-your-team")
                else:
                    user.speak_l(
                        "milebymile-false-virtue-other-team", team=team.index + 1
                    )

    def _broadcast_card_message(self, message_key: str, card: Card, **kwargs) -> None:
        """Broadcast a message with a localized card name to all players."""
        for p in self.players:
            user = self.get_user(p)
            if not user:
                continue
            card_name = self._get_localized_card_name(card, user.locale)
            user.speak_l(message_key, card=card_name, **kwargs)

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def on_tick(self) -> None:
        """Called every tick."""
        if not self.game_active:
            return

        # Handle round timer
        self._round_timer.on_tick()

        # Handle dirty trick window
        if self.dirty_trick_window_ticks > 0:
            self.dirty_trick_window_ticks -= 1
            if self.dirty_trick_window_ticks <= 0:
                self.dirty_trick_window_team = None
                self.dirty_trick_window_hazard = None

        BotHelper.on_tick(self)

    def bot_think(self, player: MileByMilePlayer) -> str | None:
        """Bot AI decision making."""
        # Check for dirty trick opportunity first
        if self.dirty_trick_window_team is not None:
            team = self.get_player_team(player)
            if team and team.index == self.dirty_trick_window_team:
                hazard = self.dirty_trick_window_hazard
                blocking_safety = HAZARD_TO_SAFETY.get(hazard) if hazard else None
                if blocking_safety:
                    for card in player.hand:
                        if (
                            card.card_type == CardType.SAFETY
                            and card.value == blocking_safety
                        ):
                            return "dirty_trick"

        # Not our turn? Skip
        if self.current_player != player:
            return None

        # Choose best card to play
        return self._bot_choose_card(player)

    def _bot_choose_card(self, player: MileByMilePlayer) -> str | None:
        """Bot card selection logic."""
        if not player.hand:
            return None

        team = self.get_player_team(player)
        if not team:
            return None

        target_distance = self.options.round_distance
        distance_needed = target_distance - team.miles
        is_endgame = distance_needed <= 200

        # Score each card
        best_slot = 0
        best_priority = -1

        for i, card in enumerate(player.hand):
            priority = self._bot_score_card(
                player, card, team, distance_needed, is_endgame
            )
            if priority > best_priority:
                best_priority = priority
                best_slot = i

        return f"card_slot_{best_slot + 1}"

    def _bot_score_card(
        self,
        player: MileByMilePlayer,
        card: Card,
        team: MileByMileTeam,
        distance_needed: int,
        is_endgame: bool,
    ) -> int:
        """Score a card for bot decision making."""
        if card.card_type == CardType.DISTANCE:
            if not self._can_play_card(player, card):
                return 100

            distance = card.distance
            if is_endgame:
                if distance == distance_needed:
                    return 5000  # Perfect finish
                elif distance > distance_needed:
                    if self.options.only_allow_perfect_crossing:
                        return 50
                    return 4000  # Finish anyway
                else:
                    return 1000 + distance
            return 1000 + distance

        elif card.card_type == CardType.REMEDY:
            if card.value == RemedyType.ROLL and team.has_problem(HazardType.STOP):
                if not team.has_safety(SafetyType.RIGHT_OF_WAY):
                    return 3000
            if card.value == RemedyType.END_OF_LIMIT and team.has_problem(
                HazardType.SPEED_LIMIT
            ):
                return 2800
            if self._can_play_card(player, card):
                return 2500
            return 150

        elif card.card_type == CardType.SAFETY:
            if team.has_safety(card.value):
                return 50
            if is_endgame and distance_needed <= 100:
                return 1500
            return 2000

        elif card.card_type == CardType.HAZARD:
            if not self._can_play_card(player, card):
                return 200
            if self.options.karma_rule and team.has_karma:
                # Prefer not attacking if we have karma and can play distance
                has_playable_distance = any(
                    c.card_type == CardType.DISTANCE and self._can_play_card(player, c)
                    for c in player.hand
                )
                if has_playable_distance:
                    return 50
            return 800

        elif card.card_type == CardType.SPECIAL:
            if card.value == "false_virtue" and not team.has_karma:
                return 1800
            return 50

        return 100
