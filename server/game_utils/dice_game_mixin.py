"""
Mixin for dice-based games that use the DiceSet keep/lock mechanics.

Provides shared functionality for games like Threes and Yahtzee that have
dice toggling via 1-5/1-6 keys depending on user preferences.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .actions import Action, ActionSet
from ..ui.keybinds import KeybindState
from ..users.preferences import DiceKeepingStyle

if TYPE_CHECKING:
    from ..games.base import Player


class DiceGameMixin:
    """
    Mixin providing dice toggle actions for games using DiceSet.

    Supports two dice keeping styles:
    - PlayPalace style: Keys 1-5 toggle dice by index
    - Quentin C style: Keys 1-6 keep by face value, shift+1-6 unkeep by value

    Expects the game class to have:
    - self.get_user(player) -> User
    - self.get_action_set(player, name) -> ActionSet
    - self.update_all_turn_actions()
    - self.rebuild_player_menu(player)
    - Player objects with a `dice: DiceSet` attribute

    Usage:
        class MyGame(Game, DiceGameMixin):
            def create_turn_action_set(self, player):
                action_set = ActionSet(name="turn")
                self.add_dice_toggle_actions(action_set)
                # ... add other actions
                return action_set

            def setup_keybinds(self):
                super().setup_keybinds()
                self.setup_dice_keybinds()
    """

    def add_dice_toggle_actions(self, action_set: ActionSet, num_dice: int = 5) -> None:
        """
        Add dice toggle actions to an action set.

        Adds both index-based toggle actions (for menu items) and
        keybind-triggered actions that respect user preferences.

        Args:
            action_set: The ActionSet to add actions to.
            num_dice: Number of dice (default 5).
        """
        # Menu item actions - always toggle by index
        for i in range(num_dice):
            action_set.add(
                Action(
                    id=f"toggle_die_{i}",
                    label=f"Die {i + 1}",
                    handler=f"_action_toggle_die_{i}",
                    hidden=True,
                )
            )

        # Keybind actions for keys 1-6 (respects user preference)
        # These are hidden but enabled - they're only triggered via keybinds
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
            # Shift+key actions for Quentin C style unkeeping
            action_set.add(
                Action(
                    id=f"dice_unkeep_{v}",
                    label=f"Unkeep {v}",
                    handler=f"_action_dice_unkeep_{v}",
                    hidden=True,
                    enabled=True,
                )
            )

    def setup_dice_keybinds(self, num_dice: int = 5) -> None:
        """
        Set up keybinds for dice toggling.

        Defines keybinds for both styles:
        - Keys 1-6 trigger dice_key_X (style determines behavior)
        - Shift+1-6 trigger dice_unkeep_X (Quentin C style only)

        Args:
            num_dice: Number of dice (default 5).
        """
        # Keys 1-6 for keeping/toggling
        for v in range(1, 7):
            self.define_keybind(
                str(v),
                f"Dice key {v}",
                [f"dice_key_{v}"],
                state=KeybindState.ACTIVE,
            )
            # Shift+1-6 for unkeeping (Quentin C style)
            self.define_keybind(
                f"shift+{v}",
                f"Unkeep dice {v}",
                [f"dice_unkeep_{v}"],
                state=KeybindState.ACTIVE,
            )

    # Individual toggle handlers for menu items (always by index)
    def _action_toggle_die_0(self, player: Player, action_id: str) -> None:
        self._toggle_die(player, 0)

    def _action_toggle_die_1(self, player: Player, action_id: str) -> None:
        self._toggle_die(player, 1)

    def _action_toggle_die_2(self, player: Player, action_id: str) -> None:
        self._toggle_die(player, 2)

    def _action_toggle_die_3(self, player: Player, action_id: str) -> None:
        self._toggle_die(player, 3)

    def _action_toggle_die_4(self, player: Player, action_id: str) -> None:
        self._toggle_die(player, 4)

    # Keybind handlers for dice keys 1-6
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

    # Shift+key handlers for unkeeping by value
    def _action_dice_unkeep_1(self, player: Player, action_id: str) -> None:
        self._handle_dice_unkeep(player, 1)

    def _action_dice_unkeep_2(self, player: Player, action_id: str) -> None:
        self._handle_dice_unkeep(player, 2)

    def _action_dice_unkeep_3(self, player: Player, action_id: str) -> None:
        self._handle_dice_unkeep(player, 3)

    def _action_dice_unkeep_4(self, player: Player, action_id: str) -> None:
        self._handle_dice_unkeep(player, 4)

    def _action_dice_unkeep_5(self, player: Player, action_id: str) -> None:
        self._handle_dice_unkeep(player, 5)

    def _action_dice_unkeep_6(self, player: Player, action_id: str) -> None:
        self._handle_dice_unkeep(player, 6)

    def _handle_dice_key(self, player: Player, key_num: int) -> None:
        """
        Handle a dice key press (1-6).

        Behavior depends on user's dice keeping style preference:
        - PlayPalace style: Toggle die at index (key_num - 1) for keys 1-5
        - Quentin C style: Keep first unkept die with face value key_num
        """
        user = self.get_user(player)
        if not user:
            return

        style = user.preferences.dice_keeping_style

        if style == DiceKeepingStyle.PLAYPALACE:
            # Toggle by index (only keys 1-5 work)
            if key_num <= 5:
                self._toggle_die(player, key_num - 1)
        else:
            # Quentin C style: keep by face value
            self._keep_by_value(player, key_num)

    def _handle_dice_unkeep(self, player: Player, value: int) -> None:
        """
        Handle shift+key press for unkeeping by value.

        Only works in Quentin C style. Silent in PlayPalace style.
        """
        user = self.get_user(player)
        if not user:
            return

        style = user.preferences.dice_keeping_style

        if style == DiceKeepingStyle.QUENTIN_C:
            self._unkeep_by_value(player, value)
        # Silent in PlayPalace style

    def _toggle_die(self, player: Player, die_index: int) -> None:
        """
        Toggle keeping a die by index.

        Handles the common logic for toggling dice in games using DiceSet.
        Speaks the appropriate message (keeping/rerolling/locked).
        """
        if not hasattr(player, "dice"):
            return

        user = self.get_user(player)
        result = player.dice.toggle_keep(die_index)

        if result is None:
            # Die is locked
            if user:
                user.speak_l("dice-locked")
            return

        die_val = player.dice.get_value(die_index)
        if result:
            # Now kept
            if user:
                user.speak_l("dice-keeping", value=die_val)
        else:
            # Now unkept
            if user:
                user.speak_l("dice-rerolling", value=die_val)

        self.update_all_turn_actions()
        self.rebuild_player_menu(player)

    def _keep_by_value(self, player: Player, value: int) -> None:
        """
        Keep the first unkept die with the given face value.

        Used in Quentin C style. Silent if no unkept die with that value exists.
        """
        if not hasattr(player, "dice"):
            return

        user = self.get_user(player)
        dice = player.dice

        # Find first unkept, unlocked die with this value
        for i in range(dice.num_dice):
            if not dice.is_locked(i) and not dice.is_kept(i):
                if dice.get_value(i) == value:
                    dice.keep(i)
                    if user:
                        user.speak_l("dice-keeping", value=value)
                    self.update_all_turn_actions()
                    self.rebuild_player_menu(player)
                    return

        # No matching die found - silent

    def _unkeep_by_value(self, player: Player, value: int) -> None:
        """
        Unkeep the first kept die with the given face value.

        Used in Quentin C style. Silent if no kept die with that value exists.
        """
        if not hasattr(player, "dice"):
            return

        user = self.get_user(player)
        dice = player.dice

        # Find first kept (but not locked) die with this value
        for i in range(dice.num_dice):
            if dice.is_kept(i) and not dice.is_locked(i):
                if dice.get_value(i) == value:
                    dice.unkeep(i)
                    if user:
                        user.speak_l("dice-rerolling", value=value)
                    self.update_all_turn_actions()
                    self.rebuild_player_menu(player)
                    return

        # No matching die found - silent

    def update_dice_action_labels(
        self, player: Player, turn_set: ActionSet, num_dice: int = 5
    ) -> None:
        """
        Update dice toggle action labels based on current dice state.

        Args:
            player: The player whose dice to check.
            turn_set: The turn action set to update.
            num_dice: Number of dice (default 5).
        """
        if not hasattr(player, "dice"):
            return

        for i in range(num_dice):
            action_id = f"toggle_die_{i}"
            die_val = player.dice.get_value(i)

            if player.dice.is_locked(i):
                turn_set.set_label(action_id, f"{die_val} (locked)")
            elif player.dice.is_kept(i):
                turn_set.set_label(action_id, f"{die_val} (kept)")
            else:
                turn_set.set_label(action_id, str(die_val))
