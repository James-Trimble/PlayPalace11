"""Action system for games."""

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mashumaro.mixins.json import DataClassJSONMixin

if TYPE_CHECKING:
    pass


@dataclass
class MenuInput(DataClassJSONMixin):
    """
    Request menu selection before action executes.

    The options and bot_select are method names (strings) that will be
    looked up on the game object at execution time.
    """

    prompt: str  # Localization key for menu title/prompt
    options: str  # Method name that returns list[str]
    bot_select: str | None = None  # Method name for bot auto-selection


@dataclass
class EditboxInput(DataClassJSONMixin):
    """
    Request text input before action executes.

    The bot_input is a method name (string) that will be looked up
    on the game object at execution time.
    """

    prompt: str  # Localization key for prompt
    default: str = ""  # Default value (static string only now)
    bot_input: str | None = None  # Method name for bot auto-input


@dataclass
class Action(DataClassJSONMixin):
    """
    A game action with imperative state management.

    Actions are pure data - the handler is a method name (string) that
    will be looked up on the game object at execution time. This allows
    actions to be serialized and survive game object replacement.

    Handler method signature: (self, player) or (self, player, input_value)
    """

    id: str
    label: str  # Static label, updated via ActionSet.set_label()
    handler: str  # Method name on game object (e.g., "_action_roll")
    enabled: bool = False  # Whether action can be executed
    hidden: bool = (
        False  # Whether action is hidden from menu (still keybindable if enabled)
    )
    input_request: MenuInput | EditboxInput | None = (
        None  # Optional input before execution
    )


@dataclass
class ActionSet(DataClassJSONMixin):
    """
    A named group of actions for a player.

    Players have an ordered list of ActionSets (e.g., "turn" before "lobby").
    Games manage action availability imperatively via enable/disable/show/hide.
    """

    name: str  # e.g., "turn", "lobby", "hand"
    _actions: dict[str, Action] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def add(self, action: Action) -> None:
        """Add an action to this set."""
        self._actions[action.id] = action
        if action.id not in self._order:
            self._order.append(action.id)

    def remove(self, action_id: str) -> None:
        """Remove an action from this set."""
        if action_id in self._actions:
            del self._actions[action_id]
        if action_id in self._order:
            self._order.remove(action_id)

    def enable(self, *action_ids: str) -> None:
        """Enable actions (make executable)."""
        for aid in action_ids:
            if aid in self._actions:
                self._actions[aid].enabled = True

    def disable(self, *action_ids: str) -> None:
        """Disable actions (make non-executable)."""
        for aid in action_ids:
            if aid in self._actions:
                self._actions[aid].enabled = False

    def show(self, *action_ids: str) -> None:
        """Show actions in menu."""
        for aid in action_ids:
            if aid in self._actions:
                self._actions[aid].hidden = False

    def hide(self, *action_ids: str) -> None:
        """Hide actions from menu (still keybindable if enabled)."""
        for aid in action_ids:
            if aid in self._actions:
                self._actions[aid].hidden = True

    def set_label(self, action_id: str, label: str) -> None:
        """Set action label imperatively."""
        if action_id in self._actions:
            self._actions[action_id].label = label

    def get_action(self, action_id: str) -> Action | None:
        """Get an action by ID."""
        return self._actions.get(action_id)

    def get_visible_actions(self) -> list[Action]:
        """Get enabled, non-hidden actions in order."""
        return [
            self._actions[aid]
            for aid in self._order
            if aid in self._actions
            and self._actions[aid].enabled
            and not self._actions[aid].hidden
        ]

    def get_enabled_actions(self) -> list[Action]:
        """Get all enabled actions in order (for F5 menu)."""
        return [
            self._actions[aid]
            for aid in self._order
            if aid in self._actions and self._actions[aid].enabled
        ]

    def copy(self) -> "ActionSet":
        """Deep copy for templates."""
        return copy.deepcopy(self)
