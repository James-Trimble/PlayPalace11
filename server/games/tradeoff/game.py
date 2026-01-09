"""
Tradeoff Game Implementation for PlayPalace v11.

A dice trading game where players roll dice, trade unwanted ones to a shared pool,
and take dice back in turn order (lowest scorer first). After 3 iterations,
players score based on set combinations formed from their 15 dice.
"""

from dataclasses import dataclass, field
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.actions import Action, ActionSet
from ...game_utils.bot_helper import BotHelper
from ...game_utils.dice import roll_dice
from ...game_utils.options import IntOption, option_field
from ...messages.localization import Localization
from ...users.preferences import DiceKeepingStyle

from .scoring import SET_DEFINITIONS, find_best_scoring
from .bot import bot_think_trading, bot_think_taking


@dataclass
class TradeoffPlayer(Player):
    """Player state for Tradeoff game."""

    # Current hand of dice (accumulates over 3 iterations)
    hand: list[int] = field(default_factory=list)

    # Current iteration's rolled dice (before trading)
    rolled_dice: list[int] = field(default_factory=list)

    # Dice selected for trading (indices into rolled_dice)
    trading_indices: list[int] = field(default_factory=list)

    # Whether this player has confirmed their trades
    trades_confirmed: bool = False

    # Dice that were traded (stored for reveal after all confirm)
    traded_dice: list[int] = field(default_factory=list)

    # How many dice this player traded (to know how many to take back)
    dice_traded_count: int = 0

    # How many dice taken from pool so far this taking phase
    dice_taken_count: int = 0

    # Round score (accumulated during scoring phase)
    round_score: int = 0


@dataclass
class TradeoffOptions(GameOptions):
    """Options for Tradeoff game."""

    target_score: int = option_field(
        IntOption(
            default=60,
            min_val=30,
            max_val=500,
            value_key="score",
            label="tradeoff-set-target",
            prompt="tradeoff-enter-target",
            change_msg="tradeoff-option-changed-target",
        )
    )


@dataclass
@register_game
class TradeoffGame(Game):
    """
    Tradeoff dice trading game.

    Players roll 5 dice each, select dice to trade to a shared pool, then
    take dice back from the pool in turn order (lowest scorer first).
    After 3 iterations of this, players score based on the sets they form
    from their 15 accumulated dice.

    First to reach the target score wins.
    """

    players: list[TradeoffPlayer] = field(default_factory=list)
    options: TradeoffOptions = field(default_factory=TradeoffOptions)

    # Game state
    phase: str = "waiting"  # waiting, trading, taking, scoring
    iteration: int = 0  # 1-3 within a round

    # Pool of traded dice
    pool: list[int] = field(default_factory=list)

    # Taking order (player ids, sorted by score)
    taking_order: list[str] = field(default_factory=list)
    taking_index: int = 0

    @classmethod
    def get_name(cls) -> str:
        return "Tradeoff"

    @classmethod
    def get_type(cls) -> str:
        return "tradeoff"

    @classmethod
    def get_category(cls) -> str:
        return "category-dice-games"

    def _get_player_score(self, player_name: str) -> int:
        """Get a player's total score from the team manager."""
        team = self._team_manager.get_team(player_name)
        return team.total_score if team else 0

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 8

    def create_player(
        self, player_id: str, name: str, is_bot: bool = False
    ) -> TradeoffPlayer:
        """Create a new player with Tradeoff-specific state."""
        return TradeoffPlayer(id=player_id, name=name, is_bot=is_bot)

    def create_turn_action_set(self, player: TradeoffPlayer) -> ActionSet:
        """Create the turn action set for a player."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")

        # Trading phase actions - toggle dice to trade (for menu items)
        for i in range(5):
            action_set.add(
                Action(
                    id=f"toggle_trade_{i}",
                    label=f"Die {i + 1}",
                    handler=f"_action_toggle_trade_{i}",
                )
            )

        # Keybind actions for dice keys 1-6 (respects user preference)
        for v in range(1, 7):
            action_set.add(
                Action(
                    id=f"dice_key_{v}",
                    label=f"Dice key {v}",
                    handler=f"_action_dice_key_{v}",
                    hidden=True,
                    enabled=True,
                )
            )
            # Shift+key actions for Quentin C style
            action_set.add(
                Action(
                    id=f"dice_trade_{v}",
                    label=f"Trade {v}",
                    handler=f"_action_dice_trade_{v}",
                    hidden=True,
                    enabled=True,
                )
            )

        # Confirm trades action
        action_set.add(
            Action(
                id="confirm_trades",
                label=Localization.get(locale, "tradeoff-confirm-trades", count=0),
                handler="_action_confirm_trades",
            )
        )

        # Taking phase actions - take dice from pool (one for each value 1-6)
        for v in range(1, 7):
            action_set.add(
                Action(
                    id=f"take_{v}",
                    label=f"Take a {v}",
                    handler=f"_action_take_{v}",
                )
            )

        # View actions
        action_set.add(
            Action(
                id="view_hand",
                label=Localization.get(locale, "tradeoff-view-hand"),
                handler="_action_view_hand",
                hidden=True,
            )
        )
        action_set.add(
            Action(
                id="view_pool",
                label=Localization.get(locale, "tradeoff-view-pool"),
                handler="_action_view_pool",
                hidden=True,
            )
        )
        action_set.add(
            Action(
                id="view_players",
                label=Localization.get(locale, "tradeoff-view-players"),
                handler="_action_view_players",
                hidden=True,
            )
        )

        return action_set

    def setup_keybinds(self) -> None:
        """Define all keybinds for the game."""
        super().setup_keybinds()

        # Number keys 1-6 for dice actions (respects user preference)
        from ...ui.keybinds import KeybindState
        for v in range(1, 7):
            self.define_keybind(
                str(v),
                f"Dice key {v}",
                [f"dice_key_{v}"],
                state=KeybindState.ACTIVE,
            )
            # Shift+1-6 for trading by value (Quentin C style)
            self.define_keybind(
                f"shift+{v}",
                f"Trade dice {v}",
                [f"dice_trade_{v}"],
                state=KeybindState.ACTIVE,
            )

        # B to confirm trades
        self.define_keybind(
            "b",
            "Confirm trades",
            ["confirm_trades"],
            state=KeybindState.ACTIVE,
        )

        # View keybinds
        self.define_keybind(
            "h",
            "View hand",
            ["view_hand"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )
        self.define_keybind(
            "p",
            "View pool",
            ["view_pool"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )
        self.define_keybind(
            "v",
            "View players",
            ["view_players"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )

    def update_turn_actions(self, player: TradeoffPlayer) -> None:
        """Update turn action availability for a player."""
        turn_set = self.get_action_set(player, "turn")
        if not turn_set:
            return

        user = self.get_user(player)
        locale = user.locale if user else "en"
        is_playing = self.status == "playing"
        is_spectator = player.is_spectator

        # Hide all by default
        for i in range(5):
            turn_set.disable(f"toggle_trade_{i}")
            turn_set.hide(f"toggle_trade_{i}")
        turn_set.disable("confirm_trades")
        turn_set.hide("confirm_trades")
        for v in range(1, 7):
            turn_set.disable(f"take_{v}")
            turn_set.hide(f"take_{v}")

        if not is_playing or is_spectator:
            self.update_standard_actions(player)
            return

        if self.phase == "trading":
            # Show trade toggle actions for this player's rolled dice
            if not player.trades_confirmed and player.rolled_dice:
                for i, die_val in enumerate(player.rolled_dice):
                    is_trading = i in player.trading_indices
                    status = Localization.get(
                        locale,
                        "tradeoff-trade-status-trading" if is_trading else "tradeoff-trade-status-keeping"
                    )
                    turn_set.set_label(
                        f"toggle_trade_{i}",
                        Localization.get(locale, "tradeoff-toggle-trade", value=die_val, status=status)
                    )
                    turn_set.enable(f"toggle_trade_{i}")
                    turn_set.show(f"toggle_trade_{i}")

                # Show confirm button
                trade_count = len(player.trading_indices)
                turn_set.set_label(
                    "confirm_trades",
                    Localization.get(locale, "tradeoff-confirm-trades", count=trade_count)
                )
                turn_set.enable("confirm_trades")
                turn_set.show("confirm_trades")

        elif self.phase == "taking":
            # Is it this player's turn to take?
            if self.taking_index < len(self.taking_order):
                current_taker_id = self.taking_order[self.taking_index]
                if player.id == current_taker_id and player.dice_taken_count < player.dice_traded_count:
                    # Show available dice in pool
                    pool_counts = {}
                    for d in self.pool:
                        pool_counts[d] = pool_counts.get(d, 0) + 1

                    for v in range(1, 7):
                        count = pool_counts.get(v, 0)
                        if count > 0:
                            turn_set.set_label(
                                f"take_{v}",
                                Localization.get(locale, "tradeoff-take-die", value=v, remaining=count)
                            )
                            turn_set.enable(f"take_{v}")
                            turn_set.show(f"take_{v}")

        # View actions available during play
        if is_playing:
            turn_set.enable("view_hand", "view_pool")
            # View players only available during taking phase (after trades revealed)
            if self.phase == "taking":
                turn_set.enable("view_players")

        self.update_standard_actions(player)

    def update_all_turn_actions(self) -> None:
        """Update turn actions for all players."""
        for player in self.players:
            self.update_turn_actions(player)

    # Trading toggle handlers
    def _action_toggle_trade_0(self, player: Player, action_id: str) -> None:
        self._toggle_trade(player, 0)

    def _action_toggle_trade_1(self, player: Player, action_id: str) -> None:
        self._toggle_trade(player, 1)

    def _action_toggle_trade_2(self, player: Player, action_id: str) -> None:
        self._toggle_trade(player, 2)

    def _action_toggle_trade_3(self, player: Player, action_id: str) -> None:
        self._toggle_trade(player, 3)

    def _action_toggle_trade_4(self, player: Player, action_id: str) -> None:
        self._toggle_trade(player, 4)

    # Keybind handlers for dice keys 1-6 (respects preference)
    def _action_dice_key_1(self, player: Player, action_id: str) -> None:
        self._handle_dice_key(player, 1)

    def _action_dice_key_2(self, player: Player, action_id: str) -> None:
        self._handle_dice_key(player, 2)

    def _action_dice_key_3(self, player: Player, action_id: str) -> None:
        self._handle_dice_key(player, 3)

    def _action_dice_key_4(self, player: Player, action_id: str) -> None:
        self._handle_dice_key(player, 4)

    def _action_dice_key_5(self, player: Player, action_id: str) -> None:
        self._handle_dice_key(player, 5)

    def _action_dice_key_6(self, player: Player, action_id: str) -> None:
        self._handle_dice_key(player, 6)

    # Shift+key handlers for trading by value (Quentin C style)
    def _action_dice_trade_1(self, player: Player, action_id: str) -> None:
        self._handle_dice_trade(player, 1)

    def _action_dice_trade_2(self, player: Player, action_id: str) -> None:
        self._handle_dice_trade(player, 2)

    def _action_dice_trade_3(self, player: Player, action_id: str) -> None:
        self._handle_dice_trade(player, 3)

    def _action_dice_trade_4(self, player: Player, action_id: str) -> None:
        self._handle_dice_trade(player, 4)

    def _action_dice_trade_5(self, player: Player, action_id: str) -> None:
        self._handle_dice_trade(player, 5)

    def _action_dice_trade_6(self, player: Player, action_id: str) -> None:
        self._handle_dice_trade(player, 6)

    def _handle_dice_key(self, player: Player, key_num: int) -> None:
        """
        Handle a dice key press (1-6).

        Behavior depends on user's dice keeping style preference:
        - PlayPalace style: Toggle die at index (key_num - 1) for keys 1-5
        - Quentin C style: Keep first trading die with face value key_num
        """
        user = self.get_user(player)
        if not user:
            return

        style = user.preferences.dice_keeping_style

        if style == DiceKeepingStyle.PLAYPALACE:
            # Toggle by index (only keys 1-5 work)
            if key_num <= 5:
                self._toggle_trade(player, key_num - 1)
        else:
            # Quentin C style: keep (unmark from trading) by face value
            self._keep_by_value(player, key_num)

    def _handle_dice_trade(self, player: Player, value: int) -> None:
        """
        Handle shift+key press for trading by value.

        Only works in Quentin C style. Silent in PlayPalace style.
        """
        user = self.get_user(player)
        if not user:
            return

        style = user.preferences.dice_keeping_style

        if style == DiceKeepingStyle.QUENTIN_C:
            self._trade_by_value(player, value)
        # Silent in PlayPalace style

    def _keep_by_value(self, player: Player, value: int) -> None:
        """
        Keep the first trading die with the given face value (Quentin C style).

        Silent if no trading die with that value exists.
        """
        tradeoff_player: TradeoffPlayer = player  # type: ignore

        if self.phase != "trading" or tradeoff_player.trades_confirmed:
            return

        # Find first die with this value that is marked for trading
        for i, die_val in enumerate(tradeoff_player.rolled_dice):
            if die_val == value and i in tradeoff_player.trading_indices:
                tradeoff_player.trading_indices.remove(i)
                user = self.get_user(player)
                if user:
                    user.speak_l("tradeoff-keeping", value=value)
                self.update_all_turn_actions()
                self.rebuild_player_menu(player)
                return
        # No matching die found - silent

    def _trade_by_value(self, player: Player, value: int) -> None:
        """
        Trade the first keeping die with the given face value (Quentin C style).

        Silent if no keeping die with that value exists.
        """
        tradeoff_player: TradeoffPlayer = player  # type: ignore

        if self.phase != "trading" or tradeoff_player.trades_confirmed:
            return

        # Find first die with this value that is NOT marked for trading
        for i, die_val in enumerate(tradeoff_player.rolled_dice):
            if die_val == value and i not in tradeoff_player.trading_indices:
                tradeoff_player.trading_indices.append(i)
                user = self.get_user(player)
                if user:
                    user.speak_l("tradeoff-trading", value=value)
                self.update_all_turn_actions()
                self.rebuild_player_menu(player)
                return
        # No matching die found - silent

    def _toggle_trade(self, player: Player, index: int) -> None:
        """Toggle whether a die is being traded."""
        tradeoff_player: TradeoffPlayer = player  # type: ignore

        if self.phase != "trading" or tradeoff_player.trades_confirmed:
            return

        if index >= len(tradeoff_player.rolled_dice):
            return

        die_value = tradeoff_player.rolled_dice[index]
        user = self.get_user(player)

        if index in tradeoff_player.trading_indices:
            tradeoff_player.trading_indices.remove(index)
            # Now keeping this die
            if user:
                user.speak_l("tradeoff-keeping", value=die_value)
        else:
            tradeoff_player.trading_indices.append(index)
            # Now trading this die
            if user:
                user.speak_l("tradeoff-trading", value=die_value)

        self.update_all_turn_actions()
        self.rebuild_player_menu(player)

    def _action_confirm_trades(self, player: Player, action_id: str) -> None:
        """Confirm the player's trade selections."""
        tradeoff_player: TradeoffPlayer = player  # type: ignore

        if self.phase != "trading" or tradeoff_player.trades_confirmed:
            return

        tradeoff_player.trades_confirmed = True
        tradeoff_player.dice_traded_count = len(tradeoff_player.trading_indices)

        # Store traded dice for later reveal
        tradeoff_player.traded_dice = [
            tradeoff_player.rolled_dice[i] for i in tradeoff_player.trading_indices
        ]

        # Move non-traded dice to hand, traded dice to pool
        for i, die_val in enumerate(tradeoff_player.rolled_dice):
            if i in tradeoff_player.trading_indices:
                self.pool.append(die_val)
            else:
                tradeoff_player.hand.append(die_val)

        # Clear rolled dice
        tradeoff_player.rolled_dice = []
        tradeoff_player.trading_indices = []

        # Check if all players have confirmed
        self._check_all_traded()

        self.update_all_turn_actions()
        self.rebuild_all_menus()

    def _check_all_traded(self) -> None:
        """Check if all players have confirmed their trades."""
        active_players = self.get_active_players()
        all_confirmed = all(p.trades_confirmed for p in active_players)

        if all_confirmed:
            # Reveal what each player traded
            for p in active_players:
                tp: TradeoffPlayer = p  # type: ignore
                if tp.traded_dice:
                    dice_str = ", ".join(str(d) for d in sorted(tp.traded_dice))
                    self.broadcast_l("tradeoff-player-traded", player=p.name, dice=dice_str)
                else:
                    self.broadcast_l("tradeoff-player-traded-none", player=p.name)

            # Move to taking phase if there are dice in the pool
            if self.pool:
                self._start_taking_phase()
            else:
                # No trades, skip to next iteration or scoring
                self._end_iteration()

    # Taking phase handlers
    def _action_take_1(self, player: Player, action_id: str) -> None:
        self._take_die(player, 1)

    def _action_take_2(self, player: Player, action_id: str) -> None:
        self._take_die(player, 2)

    def _action_take_3(self, player: Player, action_id: str) -> None:
        self._take_die(player, 3)

    def _action_take_4(self, player: Player, action_id: str) -> None:
        self._take_die(player, 4)

    def _action_take_5(self, player: Player, action_id: str) -> None:
        self._take_die(player, 5)

    def _action_take_6(self, player: Player, action_id: str) -> None:
        self._take_die(player, 6)

    def _take_die(self, player: Player, value: int) -> None:
        """Take a die with the specified value from the pool."""
        tradeoff_player: TradeoffPlayer = player  # type: ignore

        if self.phase != "taking":
            return

        # Check if it's this player's turn
        if self.taking_index >= len(self.taking_order):
            return
        if self.taking_order[self.taking_index] != player.id:
            return

        # Check if they have dice to take
        if tradeoff_player.dice_taken_count >= tradeoff_player.dice_traded_count:
            return

        # Check if the value is in the pool
        if value not in self.pool:
            return

        # Take the die
        self.pool.remove(value)
        tradeoff_player.hand.append(value)
        tradeoff_player.dice_taken_count += 1

        self.broadcast_personal_l(
            player,
            "tradeoff-you-take",
            "tradeoff-player-takes",
            value=value,
        )

        # Round-robin: always advance to next player after taking one die
        self._advance_taker()

        self.update_all_turn_actions()
        self.rebuild_all_menus()

    def _start_taking_phase(self) -> None:
        """Start the taking phase."""
        self.phase = "taking"

        # Build taking order (lowest scorer first)
        active_players = self.get_active_players()

        # Sort by total score, with tiebreaker using dice sum
        def sort_key(p: TradeoffPlayer):
            score = self._get_player_score(p.name)
            # Tiebreaker: sum of current hand (lower goes first)
            dice_sum = sum(p.hand) if p.hand else sum(p.rolled_dice) if p.rolled_dice else 0
            return (score, dice_sum, random.random())  # Final random for complete ties

        sorted_players = sorted(active_players, key=sort_key)
        self.taking_order = [p.id for p in sorted_players if p.dice_traded_count > 0]
        self.taking_index = 0

        # Reset taken counts
        for p in active_players:
            p.dice_taken_count = 0

        if self.taking_order:
            self._announce_current_taker()
        else:
            # No one traded, end iteration
            self._end_iteration()

    def _announce_current_taker(self) -> None:
        """Announce whose turn it is to take."""
        if self.taking_index >= len(self.taking_order):
            return

        player = self.get_player_by_id(self.taking_order[self.taking_index])
        if player:
            user = self.get_user(player)
            if user:
                user.speak_l("tradeoff-your-turn-take")

            # Bot thinking time
            if player.is_bot:
                BotHelper.jolt_bot(player, ticks=random.randint(10, 20))

    def _advance_taker(self) -> None:
        """Advance to the next player in taking order (round-robin)."""
        # Check if pool is empty
        if not self.pool:
            self._end_iteration()
            return

        num_players = len(self.taking_order)
        if num_players == 0:
            self._end_iteration()
            return

        # Find next player who has dice left to take (wrap around)
        for _ in range(num_players):
            self.taking_index = (self.taking_index + 1) % num_players
            player = self.get_player_by_id(self.taking_order[self.taking_index])
            if player:
                tp: TradeoffPlayer = player  # type: ignore
                if tp.dice_taken_count < tp.dice_traded_count:
                    self._announce_current_taker()
                    return

        # No one has dice left to take
        self._end_iteration()

    def _end_iteration(self) -> None:
        """End the current iteration."""
        if self.iteration < 3:
            # Start next iteration
            self._start_iteration()
        else:
            # End of round, do scoring
            self._do_scoring()

    # View actions
    def _action_view_hand(self, player: Player, action_id: str) -> None:
        """View the player's current hand."""
        tradeoff_player: TradeoffPlayer = player  # type: ignore
        user = self.get_user(player)
        if not user:
            return

        if tradeoff_player.hand:
            hand_str = ", ".join(str(d) for d in sorted(tradeoff_player.hand))
            user.speak_l("tradeoff-hand-display", count=len(tradeoff_player.hand), dice=hand_str)
        else:
            user.speak_l("tradeoff-hand-display", count=0, dice="none")

    def _action_view_pool(self, player: Player, action_id: str) -> None:
        """View the current pool."""
        user = self.get_user(player)
        if not user:
            return

        if self.pool:
            pool_str = ", ".join(str(d) for d in sorted(self.pool))
            user.speak_l("tradeoff-pool-display", count=len(self.pool), dice=pool_str)
        else:
            user.speak_l("tradeoff-pool-display", count=0, dice="none")

    def _action_view_players(self, player: Player, action_id: str) -> None:
        """View all players' hands and what they traded."""
        user = self.get_user(player)
        if not user:
            return

        for p in self.get_active_players():
            tp: TradeoffPlayer = p  # type: ignore

            # Format hand
            if tp.hand:
                hand_str = ", ".join(str(d) for d in sorted(tp.hand))
            else:
                hand_str = "empty"

            # Format what they traded (stored in traded_dice from this iteration)
            if tp.traded_dice:
                traded_str = ", ".join(str(d) for d in sorted(tp.traded_dice))
                user.speak_l("tradeoff-player-info", player=p.name, hand=hand_str, traded=traded_str)
            else:
                user.speak_l("tradeoff-player-info-no-trade", player=p.name, hand=hand_str)

    # Game flow
    def on_start(self) -> None:
        """Called when the game starts."""
        self.status = "playing"
        self.game_active = True
        self.round = 0

        # Initialize turn order
        active_players = self.get_active_players()
        self.set_turn_players(active_players)

        # Set up TeamManager
        self._team_manager.team_mode = "individual"
        self._team_manager.setup_teams([p.name for p in active_players])

        # Update actions
        self.update_all_lobby_actions()
        self.update_all_options_actions()

        # Play music
        self.play_music("game_pig/mus.ogg")

        # Start first round
        self._start_round()

    def _start_round(self) -> None:
        """Start a new round."""
        self.round += 1
        self.iteration = 0
        self.pool = []

        # Reset player state for new round
        for p in self.get_active_players():
            tp: TradeoffPlayer = p  # type: ignore
            tp.hand = []
            tp.rolled_dice = []
            tp.trading_indices = []
            tp.trades_confirmed = False
            tp.traded_dice = []
            tp.dice_traded_count = 0
            tp.dice_taken_count = 0
            tp.round_score = 0

        self.broadcast_l("tradeoff-round-start", round=self.round)
        self._start_iteration()

    def _start_iteration(self) -> None:
        """Start a new trading iteration."""
        self.iteration += 1
        self.phase = "trading"
        self.pool = []

        self.broadcast_l("tradeoff-iteration", iteration=self.iteration)

        # Roll dice for each player
        active_players = self.get_active_players()
        for p in active_players:
            tp: TradeoffPlayer = p  # type: ignore
            tp.rolled_dice = roll_dice(5, 6)
            tp.trading_indices = list(range(5))  # All dice traded by default
            tp.trades_confirmed = False
            tp.traded_dice = []
            tp.dice_traded_count = 0
            tp.dice_taken_count = 0

            # Tell the player what they rolled
            user = self.get_user(p)
            if user:
                dice_str = ", ".join(str(d) for d in tp.rolled_dice)
                user.speak_l("tradeoff-you-rolled", dice=dice_str)

        # Jolt bots
        for p in active_players:
            if p.is_bot:
                BotHelper.jolt_bot(p, ticks=random.randint(15, 30))

        self.update_all_turn_actions()
        self.rebuild_all_menus()

    def _format_set_description(self, locale: str, set_name: str, dice: list[int]) -> str:
        """Format a concise description of a set."""
        sorted_dice = sorted(dice)

        if set_name == "triple":
            return Localization.get(locale, "tradeoff-set-triple", value=sorted_dice[0])
        elif set_name == "group":
            return Localization.get(locale, "tradeoff-set-group", value=sorted_dice[0])
        elif set_name == "mini_straight":
            return Localization.get(locale, "tradeoff-set-mini-straight", low=sorted_dice[0], high=sorted_dice[-1])
        elif set_name == "straight":
            return Localization.get(locale, "tradeoff-set-straight", low=sorted_dice[0], high=sorted_dice[-1])
        elif set_name == "double_triple":
            # Find the two values
            from collections import Counter
            counts = Counter(sorted_dice)
            values = sorted(counts.keys())
            return Localization.get(locale, "tradeoff-set-double-triple", v1=values[0], v2=values[1])
        elif set_name == "double_group":
            from collections import Counter
            counts = Counter(sorted_dice)
            values = sorted(counts.keys())
            return Localization.get(locale, "tradeoff-set-double-group", v1=values[0], v2=values[1])
        elif set_name == "all_groups":
            return Localization.get(locale, "tradeoff-set-all-groups")
        elif set_name == "all_triplets":
            return Localization.get(locale, "tradeoff-set-all-triplets")
        else:
            return set_name

    def _do_scoring(self) -> None:
        """Score all players' hands at the end of a round."""
        self.phase = "scoring"
        self.play_sound("game_pig/bank.ogg")

        active_players = self.get_active_players()
        for p in active_players:
            tp: TradeoffPlayer = p  # type: ignore

            # Find best scoring combination
            sets = find_best_scoring(tp.hand)
            total_points = sum(s[2] for s in sets)
            tp.round_score = total_points

            user = self.get_user(p)
            locale = user.locale if user else "en"

            if sets:
                # Format each set description
                set_descriptions = []
                for set_name, dice_used, points in sets:
                    desc = self._format_set_description(locale, set_name, dice_used)
                    set_descriptions.append(desc)

                # Join all sets into one line
                sets_str = Localization.format_list_and(locale, set_descriptions)
                self.broadcast_l("tradeoff-player-scored", player=p.name, points=total_points, sets=sets_str)
            else:
                self.broadcast_l("tradeoff-no-sets", player=p.name)

            # Track in team manager
            self._team_manager.add_to_team_round_score(p.name, total_points)

        # Commit round scores
        self._team_manager.commit_round_scores()

        # Show round scores
        self.broadcast_l("tradeoff-round-scores", round=self.round)
        for p in active_players:
            tp: TradeoffPlayer = p  # type: ignore
            total = self._get_player_score(p.name)
            self.broadcast_l("tradeoff-score-line", player=p.name, round_points=tp.round_score, total=total)

        # Find leader
        best_score = 0
        leader = None
        for p in active_players:
            score = self._get_player_score(p.name)
            if score > best_score:
                best_score = score
                leader = p

        if leader:
            self.broadcast_l("tradeoff-leader", player=leader.name, score=best_score)

        # Check for winner
        for p in active_players:
            score = self._get_player_score(p.name)
            if score >= self.options.target_score:
                self._end_game()
                return

        # Start next round
        self._team_manager.reset_round_scores()
        self._start_round()

    def _end_game(self) -> None:
        """End the game and announce winner(s)."""
        active_players = self.get_active_players()

        # Find highest score
        high_score = max(self._get_player_score(p.name) for p in active_players)
        winners = [p for p in active_players if self._get_player_score(p.name) == high_score]

        self.play_sound("game_pig/win.ogg")

        if len(winners) == 1:
            self.broadcast_l("tradeoff-winner", player=winners[0].name, score=high_score)
        else:
            winner_names = [w.name for w in winners]
            for p in self.players:
                user = self.get_user(p)
                if user:
                    names_str = Localization.format_list_and(user.locale, winner_names)
                    user.speak_l("tradeoff-winners-tie", players=names_str, score=high_score)

        # Show final scores
        self._show_final_results()

    def _show_final_results(self) -> None:
        """Show final game results."""
        active_players = self.get_active_players()

        lines = ["Final Scores:"]
        sorted_players = sorted(
            active_players,
            key=lambda p: self._get_player_score(p.name),
            reverse=True,
        )
        for i, p in enumerate(sorted_players, 1):
            score = self._get_player_score(p.name)
            lines.append(f"{i}. {p.name}: {score} points")

        self.finish_game()
        self.show_game_end_menu(lines)

    def on_tick(self) -> None:
        """Called every tick."""
        super().on_tick()

        if not self.game_active:
            return

        # In trading phase, all players act simultaneously
        # In taking phase, only the current taker acts (handled below)
        if self.phase == "trading":
            self._process_trading_bots()
        elif self.phase == "taking":
            self._process_taking_bot()

    def _process_trading_bots(self) -> None:
        """Process all bot actions during trading phase."""
        for player in self.players:
            if not player.is_bot or player.is_spectator:
                continue

            tp: TradeoffPlayer = player  # type: ignore
            if tp.trades_confirmed:
                continue

            # Count down thinking time
            if player.bot_think_ticks > 0:
                player.bot_think_ticks -= 1
                continue

            # Execute pending action
            if player.bot_pending_action:
                action_id = player.bot_pending_action
                player.bot_pending_action = None
                self.execute_action(player, action_id)
                continue

            # Ask for new action
            action_id = self.bot_think(tp)
            if action_id:
                player.bot_pending_action = action_id

    def _process_taking_bot(self) -> None:
        """Process bot action during taking phase (only current taker)."""
        if self.taking_index >= len(self.taking_order):
            return

        current_taker = self.get_player_by_id(self.taking_order[self.taking_index])
        if not current_taker or not current_taker.is_bot:
            return

        tp: TradeoffPlayer = current_taker  # type: ignore

        # Count down thinking time
        if current_taker.bot_think_ticks > 0:
            current_taker.bot_think_ticks -= 1
            return

        # Execute pending action
        if current_taker.bot_pending_action:
            action_id = current_taker.bot_pending_action
            current_taker.bot_pending_action = None
            self.execute_action(current_taker, action_id)
            return

        # Ask for new action
        action_id = self.bot_think(tp)
        if action_id:
            current_taker.bot_pending_action = action_id

    def bot_think(self, player: TradeoffPlayer) -> str | None:
        """Bot AI decision making."""
        if self.phase == "trading":
            return bot_think_trading(self, player)
        elif self.phase == "taking":
            return bot_think_taking(self, player)
        return None
