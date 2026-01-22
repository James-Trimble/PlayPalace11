"""
UNO Game Implementation for PlayPalace v11.

Fixed version with:
- Proper bot color selection after wilds
- No duplicate draw/show-top actions
- Correct sound scheduling
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random

from mashumaro.mixins.json import DataClassJSONMixin

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.actions import Action, ActionSet, Visibility
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.options import IntOption, option_field
from ...messages.localization import Localization
from ...ui.keybinds import KeybindState

# Color and value constants
UNO_COLORS = ["red", "yellow", "green", "blue"]
UNO_VALUES = [
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "skip",
    "reverse",
    "draw2",
]

WILD = "wild"
WILD_DRAW_FOUR = "wild_draw4"


@dataclass
class UnoCard(DataClassJSONMixin):
    """UNO card model."""

    color: str  # red/yellow/green/blue or "wild"
    value: str  # 0-9, skip, reverse, draw2, wild, wild_draw4

    def is_wild(self) -> bool:
        return self.value in {WILD, WILD_DRAW_FOUR}


@dataclass
class UnoPlayer(Player):
    """Player state for UNO."""

    hand: list[UnoCard] = field(default_factory=list)


@dataclass
class UnoOptions(GameOptions):
    """Options for UNO game."""

    starting_cards: int = option_field(
        IntOption(
            default=7,
            min_val=1,
            max_val=20,
            value_key="cards",
            label="uno-set-starting-cards",
            prompt="uno-enter-starting-cards",
            change_msg="uno-option-changed-starting-cards",
        )
    )


@dataclass
@register_game
class UnoGame(Game):
    """UNO game implementation."""

    players: list[UnoPlayer] = field(default_factory=list)
    options: UnoOptions = field(default_factory=UnoOptions)

    deck: list[UnoCard] = field(default_factory=list)
    discard_pile: list[UnoCard] = field(default_factory=list)

    current_color: str = ""  # Current active color
    current_value: str = ""  # Current top value (skip/reverse/number/etc.)

    pending_draw_amount: int = 0
    pending_draw_target_id: str | None = None

    pending_color_player_id: str | None = None
    pending_color_value: str = ""  # value associated with the pending wild

    def create_player(
        self, player_id: str, name: str, is_bot: bool = False
    ) -> UnoPlayer:
        return UnoPlayer(id=player_id, name=name, is_bot=is_bot, hand=[])

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    @classmethod
    def get_name(cls) -> str:
        return "UNO"

    @classmethod
    def get_type(cls) -> str:
        return "uno"

    @classmethod
    def get_category(cls) -> str:
        return "category-card-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 6

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_start(self) -> None:
        self.status = "playing"
        self.game_active = True
        self.round = 1

        active_players = self.get_active_players()
        self.set_turn_players(active_players)

        self.deck = self._build_deck()
        random.shuffle(self.deck)

        for player in active_players:
            self._draw_cards(player, self.options.starting_cards)

        self._flip_start_card()

        # Create action sets
        for player in self.players:
            self.add_action_set(player, self.create_turn_action_set(player))

        self._update_all_card_actions()

        self.play_music("game_uno/music.ogg")
        self._start_turn()

    # ------------------------------------------------------------------
    # Action sets / keybinds
    # ------------------------------------------------------------------
    def create_turn_action_set(self, player: UnoPlayer) -> ActionSet:
        action_set = ActionSet(name="turn")

        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set.add(
            Action(
                id="draw_card",
                label=Localization.get(locale, "uno-draw"),
                handler="_action_draw_card",
                is_enabled="_is_draw_enabled",
                is_hidden="_is_draw_hidden",
            )
        )

        action_set.add(
            Action(
                id="show_top",
                label=Localization.get(locale, "uno-show-top"),
                handler="_action_show_top",
                is_enabled="_is_show_top_enabled",
                is_hidden="_is_show_top_hidden",
            )
        )

        # Color choice actions (shown only when pending_color_player_id matches)
        for color in UNO_COLORS:
            action_set.add(
                Action(
                    id=f"choose_color_{color}",
                    label=Localization.get(locale, f"uno-choose-color-{color}"),
                    handler="_action_choose_color",
                    is_enabled="_is_color_choice_enabled",
                    is_hidden="_is_color_choice_hidden",
                )
            )

        return action_set

    def setup_keybinds(self) -> None:
        super().setup_keybinds()

        # Number keys for card slots 1-9, 0 for 10
        for i in range(1, 10):
            self.define_keybind(str(i), f"Play card {i}", [f"play_{i}"], state=KeybindState.ACTIVE)
        self.define_keybind("0", "Play card 10", ["play_10"], state=KeybindState.ACTIVE)

        # Draw card
        self.define_keybind("d", "Draw card", ["draw_card"], state=KeybindState.ACTIVE)
        self.define_keybind("space", "Draw card", ["draw_card"], state=KeybindState.ACTIVE)

        # Show top card
        self.define_keybind("c", "Show top card", ["show_top"], state=KeybindState.ACTIVE, include_spectators=True)

        # Color choices for wild
        for key, color in zip(["r", "y", "g", "b"], UNO_COLORS):
            self.define_keybind(key, f"Choose {color}", [f"choose_color_{color}"], state=KeybindState.ACTIVE)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _action_play_card(self, player: Player, action_id: str) -> None:
        if self.status != "playing" or player != self.current_player:
            return

        if self.pending_color_player_id:
            return  # Must resolve color first

        try:
            index = int(action_id.replace("play_", "")) - 1
        except ValueError:
            return

        if index < 0:
            return

        uno_player: UnoPlayer = player  # type: ignore
        if index >= len(uno_player.hand):
            return

        card = uno_player.hand[index]
        if not self._can_play_card(card):
            user = self.get_user(player)
            if user:
                user.speak_l("uno-invalid-play")
            return

        # Remove before effects to avoid double-play
        uno_player.hand.pop(index)
        self._play_card(player, card)

    def _action_draw_card(self, player: Player, action_id: str) -> None:
        if self.status != "playing" or player != self.current_player:
            return
        if self.pending_color_player_id:
            return

        uno_player: UnoPlayer = player  # type: ignore
        drawn = self._draw_cards(uno_player, 1)
        if drawn:
            card = drawn[0]
            self.broadcast_l("uno-drew-card", player=player.name)
            # Auto-play if immediately playable
            if self._can_play_card(card):
                uno_player.hand.pop()  # remove the drawn card from hand
                self._play_card(player, card, from_draw=True)
                return
        self._end_turn()

    def _action_choose_color(self, player: Player, action_id: str) -> None:
        if player.id != self.pending_color_player_id:
            return

        color = action_id.replace("choose_color_", "")
        if color not in UNO_COLORS:
            return

        self.current_color = color
        value = self.pending_color_value or WILD
        self.current_value = value
        self.pending_color_player_id = None
        self.pending_color_value = ""

        user = self.get_user(player)
        locale = user.locale if user else "en"
        self.broadcast_l("uno-color-chosen", color=self._color_name(color, locale))

        # Schedule wild sound
        self.schedule_sound("game_uno/wild.ogg", delay_ticks=10)

        if value == WILD_DRAW_FOUR:
            target_id = self._get_next_player_id()
            if target_id:
                self.pending_draw_target_id = target_id
                self.pending_draw_amount = 4

        self._update_all_card_actions()
        self._end_turn()

    def _action_show_top(self, player: Player, action_id: str) -> None:
        if not self.discard_pile:
            return
        user = self.get_user(player)
        if not user:
            return
        top = self.discard_pile[-1]
        user.speak_l("uno-top-card", card=self._card_name(top, user.locale))

    # ------------------------------------------------------------------
    # Action availability
    # ------------------------------------------------------------------
    def _is_draw_enabled(self, player: Player) -> str | None:
        if self.status != "playing":
            return "action-not-playing"
        if player.is_spectator:
            return "action-spectator"
        if player != self.current_player:
            return "action-not-your-turn"
        if self.pending_color_player_id:
            return "uno-need-color"
        return None

    def _is_draw_hidden(self, player: Player) -> Visibility:
        if self.status != "playing" or player.is_spectator:
            return Visibility.HIDDEN
        if player != self.current_player:
            return Visibility.HIDDEN
        if player.id == self.pending_color_player_id:
            return Visibility.HIDDEN
        return Visibility.VISIBLE

    def _is_show_top_enabled(self, player: Player) -> str | None:
        if self.status != "playing":
            return "action-not-playing"
        if self.pending_color_player_id:
            return "uno-need-color"
        return None

    def _is_show_top_hidden(self, player: Player) -> Visibility:
        if self.status != "playing":
            return Visibility.HIDDEN
        if self.pending_color_player_id:
            return Visibility.HIDDEN
        return Visibility.VISIBLE

    def _is_color_choice_enabled(self, player: Player, action_id: str | None = None) -> str | None:
        if player.id != self.pending_color_player_id:
            return "uno-need-color"
        return None

    def _is_color_choice_hidden(self, player: Player) -> Visibility:
        if player.id != self.pending_color_player_id:
            return Visibility.HIDDEN
        return Visibility.VISIBLE

    # ------------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------------
    def _start_turn(self) -> None:
        player = self.current_player
        if not player or self.status != "playing":
            return

        # Apply pending draw penalties
        if self.pending_draw_target_id == player.id and self.pending_draw_amount > 0:
            amount = self.pending_draw_amount
            self.pending_draw_amount = 0
            self.pending_draw_target_id = None
            uno_player: UnoPlayer = player  # type: ignore
            self._draw_cards(uno_player, amount)
            self.schedule_sound("game_uno/buzzerplay.ogg", delay_ticks=5)
            self.broadcast_l("uno-draw-penalty", player=player.name, count=amount)
            self._update_all_card_actions()
            if player.is_bot:
                self._bot_take_turn(player)
            else:
                self.rebuild_all_menus()
            return

        # If we're waiting for color choice from a bot, bot chooses now
        if self.pending_color_player_id == player.id and player.is_bot:
            self._bot_choose_color(player)
            return

        # Announce turn
        self.announce_turn("game_uno/playable.ogg")
        self._update_all_card_actions()

        # Simple bot: play first playable card, else draw
        if player.is_bot:
            self._bot_take_turn(player)
        else:
            self.rebuild_all_menus()

    def _end_turn(self) -> None:
        self.advance_turn(announce=False)
        self._start_turn()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _bot_choose_color(self, player: Player) -> None:
        """Bot automatically chooses the most common color in hand."""
        uno_player: UnoPlayer = player  # type: ignore
        color_counts = {color: 0 for color in UNO_COLORS}
        for card in uno_player.hand:
            if card.color in UNO_COLORS:
                color_counts[card.color] += 1
        chosen_color = max(color_counts, key=color_counts.get) if any(color_counts.values()) else "red"
        self._action_choose_color(player, f"choose_color_{chosen_color}")

    def _bot_take_turn(self, player: Player) -> None:
        uno_player: UnoPlayer = player  # type: ignore
        
        playable_indices = [i for i, c in enumerate(uno_player.hand) if self._can_play_card(c)]
        if playable_indices:
            idx = playable_indices[0]
            card = uno_player.hand.pop(idx)
            self._play_card(player, card)
            return
        drawn = self._draw_cards(uno_player, 1)
        if drawn and self._can_play_card(drawn[0]):
            uno_player.hand.pop()
            self._play_card(player, drawn[0], from_draw=True)
        else:
            self._end_turn()

    def _play_card(self, player: Player, card: UnoCard, from_draw: bool = False) -> None:
        # Place on discard
        self.discard_pile.append(card)
        self.current_value = card.value
        if not card.is_wild():
            self.current_color = card.color

        locale = "en"
        user = self.get_user(player)
        if user:
            locale = user.locale
        self.broadcast_l("uno-played-card", player=player.name, card=self._card_name(card, locale))

        # Sounds for special cards
        sound_map = {
            "skip": "game_uno/skip.ogg",
            "reverse": "game_uno/reverse.ogg",
            "draw2": "game_uno/buzzerpress.ogg",
            WILD: "game_uno/wild.ogg",
            WILD_DRAW_FOUR: "game_uno/wild4.ogg",
        }
        sound = sound_map.get(card.value)
        if sound:
            self.schedule_sound(sound, delay_ticks=5)

        # Wild cards require color choice
        if card.is_wild():
            self.pending_color_player_id = player.id
            self.pending_color_value = card.value
            self.rebuild_all_menus()
            # If bot played the wild, it should choose color immediately
            if player.is_bot:
                self._bot_choose_color(player)
            return

        # Apply special effects
        self._apply_card_effect(card)

        self._after_card_play(player)

    def _apply_card_effect(self, card: UnoCard) -> None:
        if card.value == "skip":
            self.skip_next_players(1)
        elif card.value == "reverse":
            self.reverse_turn_direction()
            if len(self.turn_players) == 2:
                self.skip_next_players(1)
        elif card.value == "draw2":
            target = self._get_next_player_id()
            if target:
                self.pending_draw_target_id = target
                self.pending_draw_amount = 2

    def _after_card_play(self, player: Player) -> None:
        uno_player: UnoPlayer = player  # type: ignore
        if len(uno_player.hand) == 1:
            self.schedule_sound("game_uno/uno.ogg", delay_ticks=10)
            self.broadcast_l("uno-uno-call", player=player.name)
        if len(uno_player.hand) == 0:
            self.schedule_sound("game_uno/wingame.ogg", delay_ticks=15)
            self.broadcast_l("uno-winner", player=player.name)
            self.finish_game()
            return
        self._update_all_card_actions()
        self._end_turn()

    def _build_deck(self) -> list[UnoCard]:
        deck: list[UnoCard] = []
        for color in UNO_COLORS:
            deck.append(UnoCard(color=color, value="0"))
            for value in UNO_VALUES:
                if value == "0":
                    continue
                deck.append(UnoCard(color=color, value=value))
                deck.append(UnoCard(color=color, value=value))
        for _ in range(4):
            deck.append(UnoCard(color="wild", value=WILD))
            deck.append(UnoCard(color="wild", value=WILD_DRAW_FOUR))
        return deck

    def _draw_cards(self, player: UnoPlayer, count: int) -> list[UnoCard]:
        drawn: list[UnoCard] = []
        for _ in range(count):
            if not self.deck:
                self._refill_deck()
            if not self.deck:
                break
            card = self.deck.pop()
            player.hand.append(card)
            drawn.append(card)
        return drawn

    def _refill_deck(self) -> None:
        if len(self.discard_pile) <= 1:
            return
        top = self.discard_pile[-1]
        remaining = self.discard_pile[:-1]
        random.shuffle(remaining)
        self.deck = remaining
        self.discard_pile = [top]

    def _flip_start_card(self) -> None:
        while self.deck:
            card = self.deck.pop()
            if card.value == WILD_DRAW_FOUR:
                # Avoid starting with draw four
                self.deck.insert(0, card)
                continue
            self.discard_pile.append(card)
            self.current_value = card.value
            if card.is_wild():
                self.current_color = random.choice(UNO_COLORS)
            else:
                self.current_color = card.color
            # Apply starting effect if needed
            if card.value == "skip":
                self.skip_next_players(1)
            elif card.value == "reverse":
                self.reverse_turn_direction()
            elif card.value == "draw2":
                target = self._get_next_player_id()
                if target:
                    self.pending_draw_target_id = target
                    self.pending_draw_amount = 2
            break

    def _get_next_player_id(self) -> str | None:
        if not self.turn_player_ids:
            return None
        next_index = (self.turn_index + self.turn_direction) % len(self.turn_player_ids)
        return self.turn_player_ids[next_index]

    def _can_play_card(self, card: UnoCard) -> bool:
        if self.pending_color_player_id:
            return False
        if not self.discard_pile:
            return True
        if card.is_wild():
            return True
        if card.color == self.current_color:
            return True
        if self.current_value not in {WILD, WILD_DRAW_FOUR} and card.value == self.current_value:
            return True
        return False

    def _update_card_actions(self, player: UnoPlayer) -> None:
        turn_set = self.get_action_set(player, "turn")
        if not turn_set:
            return

        turn_set.remove_by_prefix("play_")

        user = self.get_user(player)
        locale = user.locale if user else "en"

        for idx, card in enumerate(player.hand, start=1):
            label = Localization.get(locale, "uno-play", card=self._card_name(card, locale))
            action_id = f"play_{idx}"
            turn_set.add(
                Action(
                    id=action_id,
                    label=label,
                    handler="_action_play_card",
                    is_enabled="_is_play_enabled",
                    is_hidden="_is_play_hidden",
                )
            )

    def _update_all_card_actions(self) -> None:
        for p in self.players:
            if isinstance(p, UnoPlayer):
                self._update_card_actions(p)
        self.rebuild_all_menus()

    def _is_play_enabled(self, player: Player) -> str | None:
        if self.status != "playing":
            return "action-not-playing"
        if player.is_spectator:
            return "action-spectator"
        if player != self.current_player:
            return "action-not-your-turn"
        if self.pending_color_player_id:
            return "uno-need-color"
        # Enabled check handled per-card in handler
        return None

    def _is_play_hidden(self, player: Player) -> Visibility:
        if self.status != "playing" or player.is_spectator:
            return Visibility.HIDDEN
        if player != self.current_player:
            return Visibility.HIDDEN
        if player.id == self.pending_color_player_id:
            return Visibility.HIDDEN
        return Visibility.VISIBLE

    # ------------------------------------------------------------------
    # Localization helpers
    # ------------------------------------------------------------------
    def _card_name(self, card: UnoCard, locale: str) -> str:
        color = self._color_name(card.color, locale)
        value = self._value_name(card.value, locale)
        if card.is_wild():
            return value
        return f"{color} {value}"

    def _color_name(self, color: str, locale: str) -> str:
        return Localization.get(locale, f"uno-color-{color}")

    def _value_name(self, value: str, locale: str) -> str:
        return Localization.get(locale, f"uno-value-{value}")

    # ------------------------------------------------------------------
    # Game result
    # ------------------------------------------------------------------
    def build_game_result(self) -> GameResult:  # type: ignore[override]
        from datetime import datetime

        winner_name = None
        for p in self.players:
            if isinstance(p, UnoPlayer) and len(p.hand) == 0:
                winner_name = p.name
                break

        return GameResult(
            game_type=self.get_type(),
            timestamp=datetime.now().isoformat(),
            duration_ticks=self.sound_scheduler_tick,
            player_results=[
                PlayerResult(
                    player_id=pl.id,
                    player_name=pl.name,
                    is_bot=pl.is_bot,
                )
                for pl in self.get_active_players()
            ],
            custom_data={"winner_name": winner_name},
        )
