"""
Scopa Card Game Implementation for PlayPalace v11.

Classic Italian card game: capture cards from the table by matching ranks or sums.
"""

from dataclasses import dataclass, field
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.actions import Action, ActionSet
from ...game_utils.bot_helper import BotHelper
from ...game_utils.cards import (
    Card,
    Deck,
    DeckFactory,
    card_name,
    read_cards,
    sort_cards,
)
from ...game_utils.options import IntOption, MenuOption, BoolOption, option_field
from ...game_utils.teams import TeamManager
from ...game_utils.round_timer import RoundTimer
from ...messages.localization import Localization
from ...ui.keybinds import KeybindState

# Modular components
from .capture import find_captures, select_best_capture, get_capture_hint
from .scoring import score_round, check_winner, declare_winner
from .bot import bot_think


@dataclass
class ScopaPlayer(Player):
    """Player state for Scopa game."""

    hand: list[Card] = field(default_factory=list)
    captured: list[Card] = field(default_factory=list)
    scopas: int = 0
    round_score: int = 0
    total_score: int = 0
    team_index: int = 0


@dataclass
class ScopaOptions(GameOptions):
    """Options for Scopa game using declarative option system."""

    target_score: int = option_field(
        IntOption(
            default=11,
            min_val=1,
            max_val=121,
            value_key="score",
            label="game-set-target-score",
            prompt="scopa-enter-target-score",
            change_msg="game-option-changed-target",
        )
    )
    cards_per_deal: int = option_field(
        IntOption(
            default=3,
            min_val=1,
            max_val=10,
            value_key="cards",
            label="scopa-set-cards-per-deal",
            prompt="scopa-enter-cards-per-deal",
            change_msg="scopa-option-changed-cards",
        )
    )
    number_of_decks: int = option_field(
        IntOption(
            default=1,
            min_val=1,
            max_val=6,
            value_key="decks",
            label="scopa-set-decks",
            prompt="scopa-enter-decks",
            change_msg="scopa-option-changed-decks",
        )
    )
    escoba_rules: bool = option_field(
        BoolOption(
            default=False,
            value_key="enabled",
            label="scopa-toggle-escoba",
            change_msg="scopa-option-changed-escoba",
        )
    )
    show_capture_hints: bool = option_field(
        BoolOption(
            default=False,
            value_key="enabled",
            label="scopa-toggle-hints",
            change_msg="scopa-option-changed-hints",
        )
    )
    scopa_mechanic: str = option_field(
        MenuOption(
            default="normal",
            value_key="mechanic",
            choices=["normal", "no_scopas", "only_scopas"],
            label="scopa-set-mechanic",
            prompt="scopa-select-mechanic",
            change_msg="scopa-option-changed-mechanic",
        )
    )
    instant_win_scopas: bool = option_field(
        BoolOption(
            default=False,
            value_key="enabled",
            label="scopa-toggle-instant-win",
            change_msg="scopa-option-changed-instant",
        )
    )
    team_mode: str = option_field(
        MenuOption(
            default="individual",
            value_key="mode",
            choices=lambda g, p: TeamManager.get_all_team_modes(2, 6),
            label="game-set-team-mode",
            prompt="game-select-team-mode",
            change_msg="game-option-changed-team",
        )
    )
    team_card_scoring: bool = option_field(
        BoolOption(
            default=True,
            value_key="enabled",
            label="scopa-toggle-team-scoring",
            change_msg="scopa-option-changed-team-scoring",
        )
    )
    inverse_scopa: bool = option_field(
        BoolOption(
            default=False,
            value_key="enabled",
            label="scopa-toggle-inverse",
            change_msg="scopa-option-changed-inverse",
        )
    )


@dataclass
@register_game
class ScopaGame(Game):
    """
    Scopa card game.

    Players take turns playing cards from their hand. If the played card matches
    a table card by rank, or if table cards sum to the played card's value,
    those cards are captured. Clearing all table cards scores a "scopa" point.
    Points are also awarded for most cards, most diamonds, the 7 of diamonds,
    and most 7s.
    """

    players: list[ScopaPlayer] = field(default_factory=list)
    options: ScopaOptions = field(default_factory=ScopaOptions)

    # Game state
    deck: Deck = field(default_factory=Deck)
    table_cards: list[Card] = field(default_factory=list)
    last_capture_player: str | None = None
    dealer_index: int = 0
    current_round: int = 0
    _current_deal: int = 0  # Current deal number in round
    _total_deals: int = 0  # Total deals in round

    # Team management (serialized)
    _team_manager: TeamManager = field(default_factory=TeamManager)

    @property
    def team_manager(self) -> TeamManager:
        """Get the team manager."""
        return self._team_manager

    # Card lookup (rebuilt on load)
    _card_lookup: dict[int, Card] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize runtime state."""
        super().__post_init__()
        # Round timer for delays between rounds (state is in game fields)
        self._round_timer = RoundTimer(self)

    def rebuild_runtime_state(self) -> None:
        """Rebuild non-serialized state after deserialization."""
        super().rebuild_runtime_state()
        # Rebuild round timer
        self._round_timer = RoundTimer(self)

    def on_round_timer_ready(self) -> None:
        """Called when round timer expires. Start the next round."""
        self._start_round()

    @classmethod
    def get_name(cls) -> str:
        return "Scopa"

    @classmethod
    def get_type(cls) -> str:
        return "scopa"

    @classmethod
    def get_category(cls) -> str:
        return "category-card-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 16

    def create_player(
        self, player_id: str, name: str, is_bot: bool = False
    ) -> ScopaPlayer:
        """Create a new player with Scopa-specific state."""
        return ScopaPlayer(id=player_id, name=name, is_bot=is_bot)

    # ==========================================================================
    # Action Sets
    # ==========================================================================

    def create_turn_action_set(self, player: ScopaPlayer) -> ActionSet:
        """Create the turn action set for a player."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")

        # Dynamic card actions will be created per-turn
        # Add info actions (hidden from menu)
        action_set.add(
            Action(
                id="view_table",
                label=Localization.get(locale, "scopa-view-table"),
                handler="_action_view_table",
                hidden=True,
            )
        )
        action_set.add(
            Action(
                id="view_captured",
                label=Localization.get(locale, "scopa-view-captured"),
                handler="_action_view_captured",
                hidden=True,
            )
        )
        # Note: whose_turn, check_scores, check_scores_detailed are in base class standard set

        # View individual table cards (0-9 keys)
        for i in range(10):
            action_set.add(
                Action(
                    id=f"view_table_card_{i}",
                    label=f"View table card {i if i > 0 else 10}",
                    handler="_action_view_table_card",
                    hidden=True,
                )
            )

        # Host-only pause timer action (hidden from menu)
        action_set.add(
            Action(
                id="pause_timer",
                label="Pause timer",
                handler="_action_pause_timer",
            )
        )
        action_set.hide("pause_timer")

        return action_set

    # Options are now defined declaratively in ScopaOptions - no need to override
    # create_options_action_set as the base class handles it automatically

    def setup_keybinds(self) -> None:
        """Define all keybinds for the game."""
        # Base class has t/s/shift+s for whose_turn/check_scores/check_scores_detailed
        super().setup_keybinds()

        # Scopa-specific info keybinds
        self.define_keybind(
            "c",
            "View table cards",
            ["view_table"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )
        self.define_keybind(
            "d",
            "View captured cards",
            ["view_captured"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )

        # Number keys to view specific table cards
        for i in range(1, 10):
            self.define_keybind(
                str(i),
                f"View table card {i}",
                [f"view_table_card_{i}"],
                state=KeybindState.ACTIVE,
                include_spectators=True,
            )
        self.define_keybind(
            "0",
            "View table card 10",
            ["view_table_card_0"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )

        # Host-only pause keybind (hidden from menu)
        self.define_keybind(
            "p", "Pause/skip round timer", ["pause_timer"], state=KeybindState.ACTIVE
        )

    # ==========================================================================
    # Update Actions
    # ==========================================================================

    def update_turn_actions(self, player: ScopaPlayer) -> None:
        """Update turn action availability for a player."""
        turn_set = self.get_action_set(player, "turn")
        if not turn_set:
            return

        user = self.get_user(player)
        locale = user.locale if user else "en"
        is_playing = self.status == "playing"
        is_spectator = player.is_spectator
        is_current = self.current_player == player
        is_host = player.name == self.host

        # Scopa-specific info actions available during play
        if is_playing:
            turn_set.enable("view_table", "view_captured")
            for i in range(10):
                turn_set.enable(f"view_table_card_{i}")
        else:
            turn_set.disable("view_table", "view_captured")
            for i in range(10):
                turn_set.disable(f"view_table_card_{i}")

        # Pause timer action: host-only, when timer is active
        if is_host and self._round_timer.is_active:
            turn_set.enable("pause_timer")
        else:
            turn_set.disable("pause_timer")

        # Update standard actions (whose_turn, check_scores, check_scores_detailed)
        self.update_standard_actions(player)

        # Remove old card actions
        for action_id in list(turn_set._actions.keys()):
            if action_id.startswith("play_card_"):
                turn_set.remove(action_id)

        # Add card actions for current player
        if is_playing and is_current and not is_spectator:
            for card in sort_cards(player.hand, by_suit=False):
                name = card_name(card, locale)
                if self.options.show_capture_hints:
                    hint = get_capture_hint(
                        self.table_cards, card, self.options.escoba_rules, locale
                    )
                    name += hint
                turn_set.add(
                    Action(
                        id=f"play_card_{card.id}",
                        label=name,
                        handler="_action_play_card",  # Extracts card ID from action_id
                        enabled=True,
                    )
                )

    def update_all_turn_actions(self) -> None:
        """Update turn actions for all players."""
        for player in self.players:
            self.update_turn_actions(player)

    # ==========================================================================
    # Game Flow
    # ==========================================================================

    def on_start(self) -> None:
        """Called when the game starts."""
        self.status = "playing"
        self.game_active = True
        self.current_round = 0

        # Setup teams
        self._team_manager = TeamManager(team_mode=self.options.team_mode)
        active_players = self.get_active_players()
        player_names = [p.name for p in active_players]
        self.team_manager.setup_teams(player_names)

        # Initialize turn order
        self.set_turn_players(active_players)

        # Assign team indices to players
        for player in self.players:
            player.team_index = self.team_manager.get_team_index(player.name)

        # Reset scores
        for player in active_players:
            player.captured = []
            player.scopas = 0
            player.round_score = 0
            player.total_score = 0
            player.hand = []

        self.team_manager.reset_all_scores()

        # Update actions
        self.update_all_lobby_actions()
        self.update_all_options_actions()

        # Play music
        self.play_music("game_pig/mus.ogg")

        # Start first round
        self._start_round()

    def _broadcast_cards_l(
        self,
        message_id: str,
        cards: list[Card] | None = None,
        card: Card | None = None,
        exclude: ScopaPlayer | None = None,
        **kwargs,
    ) -> None:
        """Broadcast a message with per-user localized card names."""
        for player in self.players:
            if player is exclude:
                continue
            user = self.get_user(player)
            if user:
                msg_kwargs = dict(kwargs)
                if cards is not None:
                    msg_kwargs["cards"] = read_cards(cards, user.locale)
                if card is not None:
                    msg_kwargs["card"] = card_name(card, user.locale)
                user.speak_l(message_id, **msg_kwargs)

    def _create_deck(self) -> None:
        """Create and shuffle the deck."""
        self.deck, self._card_lookup = DeckFactory.italian_deck(
            self.options.number_of_decks
        )
        # Play shuffle sound
        shuffle_sound = random.choice(["shuffle1.ogg", "shuffle2.ogg", "shuffle3.ogg"])
        self.play_sound(f"game_cards/{shuffle_sound}")

    def _start_round(self) -> None:
        """Start a new round."""
        self.current_round += 1
        self.last_capture_player = None

        # Reset player state for round
        for player in self.get_active_players():
            player.captured = []
            player.scopas = 0
            player.hand = []

        self.team_manager.reset_round_scores()
        self.table_cards = []

        # Announce round
        self.broadcast_l("game-round-start", round=self.current_round)

        # Rotate dealer (rightmost/last player, moves left/decreases)
        active_players = self.get_active_players()
        self.dealer_index = (
            (self.dealer_index - 1) % len(active_players) if active_players else 0
        )
        dealer = active_players[self.dealer_index] if active_players else None

        # Announce dealer
        if dealer:
            dealer_user = self.get_user(dealer)
            if dealer_user:
                dealer_user.speak_l("game-you-deal")
            self.broadcast_l("game-player-deals", player=dealer.name, exclude=dealer)

        # Create and shuffle deck
        self._create_deck()

        # Calculate deal tracking
        total_cards = self.deck.size()
        cards_for_players = (
            self.options.cards_per_deal * len(active_players) if active_players else 1
        )
        initial_table = total_cards % cards_for_players if cards_for_players > 0 else 0
        cards_after_table = total_cards - initial_table
        self._total_deals = (
            cards_after_table // cards_for_players if cards_for_players > 0 else 0
        )
        self._current_deal = 0

        # For standard scopa, avoid too many 10s on table (re-shuffle if needed)
        if not self.options.escoba_rules:
            max_attempts = 10
            for _ in range(max_attempts):
                self.table_cards = self.deck.draw(initial_table)
                tens_count = sum(1 for c in self.table_cards if c.rank == 10)
                total_tens = 4 * self.options.number_of_decks
                max_tens = total_tens // 2 + 1
                if tens_count <= max_tens:
                    break
                # Re-shuffle and try again
                self.deck.add(self.table_cards)
                self.deck.shuffle()
        else:
            self.table_cards = self.deck.draw(initial_table)

        if self.table_cards:
            self._broadcast_cards_l("scopa-initial-table", cards=self.table_cards)
        else:
            self.broadcast_l("scopa-no-initial-table")

        # Set starting player (player after dealer)
        if active_players:
            self.turn_index = (self.dealer_index + 1) % len(active_players)

        # Deal cards to players
        self._deal_cards()

    def _deal_cards(self) -> None:
        """Deal cards to all active players."""
        active_players = self.get_active_players()
        if not active_players or self.deck.is_empty():
            return

        # Increment deal counter
        self._current_deal += 1

        # Play small shuffle sound for deals after the first
        if self._current_deal > 1:
            self.play_sound("game_cards/small_shuffle.ogg")

        # Announce deal counter
        self.broadcast_l(
            "game-deal-counter", current=self._current_deal, total=self._total_deals
        )

        cards_to_deal = self.options.cards_per_deal

        for player in active_players:
            cards = self.deck.draw(cards_to_deal)
            player.hand.extend(cards)

        # Reset to the player after the dealer for each deal within the round
        # (Traditional scopa: play order only rotates once per round, not per deal)
        self.turn_index = (self.dealer_index + 1) % len(active_players)

        self._start_turn()

    def _start_turn(self) -> None:
        """Start a player's turn."""
        player = self.current_player
        if not player:
            return

        # Announce turn (plays sound and broadcasts message)
        self.announce_turn()

        if player.is_bot:
            BotHelper.jolt_bot(player, ticks=random.randint(15, 25))

        self.update_all_turn_actions()
        self.rebuild_all_menus()

    def _play_card(self, player: ScopaPlayer, card: Card) -> None:
        """Handle playing a card."""
        # Remove card from hand
        player.hand = [c for c in player.hand if c.id != card.id]

        # Play sound
        play_sound = random.choice(["play1.ogg", "play2.ogg", "play3.ogg", "play4.ogg"])
        self.play_sound(f"game_cards/{play_sound}")

        # Find and execute capture
        captures = find_captures(self.table_cards, card.rank, self.options.escoba_rules)

        if captures:
            best_capture = select_best_capture(captures)
            self._execute_capture(player, card, best_capture)
        else:
            # No capture, card goes to table
            self.table_cards.append(card)

            # Personal message for player
            user = self.get_user(player)
            if user:
                user.speak_l("scopa-you-put-down", card=card_name(card, user.locale))

            # Broadcast to others
            self._broadcast_cards_l(
                "scopa-player-puts-down", card=card, player=player.name, exclude=player
            )

        BotHelper.jolt_bots(self, ticks=random.randint(8, 15))
        self._end_turn()

    def _execute_capture(
        self, player: ScopaPlayer, played_card: Card, captured: list[Card]
    ) -> None:
        """Execute a capture."""
        # Remove captured cards from table
        for card in captured:
            self.table_cards = [c for c in self.table_cards if c.id != card.id]

        # Add to player's captured pile
        player.captured.append(played_card)
        player.captured.extend(captured)
        self.last_capture_player = player.name

        # Play capture sound with pitch based on cards captured
        num_captured = len(captured)
        is_scopa = len(self.table_cards) == 0

        if is_scopa:
            pitch = 200  # 2x for scopa
        else:
            # Calculate pitch: 100 for 1 card, 110 for 2, 120 for 3, etc.
            pitch = min(100 + (num_captured - 1) * 10, 190)

        self.play_sound("mention.ogg", pitch=pitch, volume=50)

        # Determine suffix key based on scopa status
        suffix_key = None
        if is_scopa:
            if self.options.scopa_mechanic != "no_scopas":
                player.scopas += 1
                suffix_key = "scopa-scopa-suffix"
                # Award point to team
                self.team_manager.add_to_team_score(player.name, 1)
            else:
                suffix_key = "scopa-clear-table-suffix"

        # Send per-user localized capture messages
        for p in self.players:
            usr = self.get_user(p)
            if not usr:
                continue

            captured_str = read_cards(captured, usr.locale)
            card_str = card_name(played_card, usr.locale)
            suffix = Localization.get(usr.locale, suffix_key) if suffix_key else ""

            if p is player:
                msg = (
                    Localization.get(
                        usr.locale,
                        "scopa-you-collect",
                        cards=captured_str,
                        card=card_str,
                    )
                    + suffix
                )
            else:
                msg = (
                    Localization.get(
                        usr.locale,
                        "scopa-player-collects",
                        player=player.name,
                        cards=captured_str,
                        card=card_str,
                    )
                    + suffix
                )
            usr.speak(msg)

        # Check for instant win
        if (
            is_scopa
            and self.options.scopa_mechanic != "no_scopas"
            and self.options.instant_win_scopas
        ):
            team = self.team_manager.get_team(player.name)
            if team and team.total_score >= self.options.target_score:
                declare_winner(self, team)
                return

    def _end_turn(self) -> None:
        """Handle end of a player's turn."""
        active_players = self.get_active_players()

        # Check if all players are out of cards
        all_empty_hands = all(len(p.hand) == 0 for p in active_players)

        if all_empty_hands:
            if self.deck.is_empty():
                # Round is over
                self._end_round()
            else:
                # Deal more cards
                self._deal_cards()
        else:
            # Next player (don't announce yet, _start_turn will do it)
            self.advance_turn(announce=False)
            self._start_turn()

    def _end_round(self) -> None:
        """Handle end of a round."""
        # Give remaining table cards to last capturer
        if self.table_cards and self.last_capture_player:
            self.broadcast_l("scopa-remaining-cards", player=self.last_capture_player)
            for player in self.players:
                if player.name == self.last_capture_player:
                    player.captured.extend(self.table_cards)
                    self.table_cards = []
                    break

        self.broadcast_l("game-round-end", round=self.current_round)

        # Score the round
        if self.options.scopa_mechanic != "only_scopas":
            score_round(self)

        # Commit round scores to total
        self.team_manager.commit_round_scores()

        # Check for winner
        winner = check_winner(self)
        if winner:
            declare_winner(self, winner)
        else:
            # Start timer for next round
            self._round_timer.start()
            self.update_all_turn_actions()

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def on_tick(self) -> None:
        """Called every tick. Handle bot AI and round timer."""
        if not self.game_active:
            return
        # Tick round timer
        self._round_timer.on_tick()
        BotHelper.on_tick(self)

    def bot_think(self, player: Player) -> str | None:
        """Bot AI decision making - delegated to bot module."""
        if not isinstance(player, ScopaPlayer):
            return None
        return bot_think(self, player)

    # ==========================================================================
    # Action Handlers
    # ==========================================================================

    def _action_play_card(self, player: Player, action_id: str) -> None:
        """Handle playing a card - extracts card ID from action_id."""
        if not isinstance(player, ScopaPlayer):
            return

        # Extract card ID from action_id (e.g., "play_card_42" -> 42)
        try:
            card_id = int(action_id.removeprefix("play_card_"))
        except ValueError:
            return

        # Find the card in player's hand
        card = next((c for c in player.hand if c.id == card_id), None)
        if card:
            self._play_card(player, card)

    def _action_view_table(self, player: Player, action_id: str) -> None:
        """View all table cards."""
        user = self.get_user(player)
        if user:
            if self.table_cards:
                cards_str = read_cards(self.table_cards, user.locale)
                user.speak(cards_str)
            else:
                user.speak_l("scopa-table-empty")

    def _action_view_table_card(self, player: Player, action_id: str) -> None:
        """View a specific table card."""
        user = self.get_user(player)
        if not user:
            return

        # Extract card number from action ID
        try:
            num = int(action_id.replace("view_table_card_", ""))
            if num == 0:
                num = 10
        except ValueError:
            return

        if num <= len(self.table_cards):
            card = self.table_cards[num - 1]
            user.speak(card_name(card, user.locale))
        else:
            user.speak_l("scopa-no-such-card")

    def _action_view_captured(self, player: Player, action_id: str) -> None:
        """View captured card count."""
        user = self.get_user(player)
        if user and isinstance(player, ScopaPlayer):
            count = len(player.captured)
            user.speak_l("scopa-captured-count", count=count)

    def _action_pause_timer(self, player: Player, action_id: str) -> None:
        """Handle pause timer action (host only)."""
        if player.name == self.host:
            self._round_timer.toggle_pause(player.name)

    # Note: _action_check_scores, _action_check_scores_detailed, _action_whose_turn
    # are now provided by the base Game class using TeamManager

    # Options are now handled by the declarative system in GameOptions
