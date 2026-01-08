"""
Declarative Options System for PlayPalace Games.

This module provides a way to define game options declaratively, reducing
boilerplate code for option handling, validation, and UI generation.

Usage:
    @dataclass
    class MyGameOptions(GameOptions):
        target_score: int = option_field(
            IntOption(default=50, min_val=10, max_val=1000,
                      label="game-set-target-score",
                      prompt="game-enter-target-score",
                      change_msg="game-option-changed-target"))
        team_mode: str = option_field(
            MenuOption(default="individual",
                       choices=["individual", "2v2"],
                       label="game-set-team-mode",
                       prompt="game-select-team-mode",
                       change_msg="game-option-changed-team"))
        show_hints: bool = option_field(
            BoolOption(default=False,
                       label="my-game-toggle-hints",
                       change_msg="my-game-option-changed-hints"))
"""

from dataclasses import dataclass, field, fields
from typing import Any, Callable, TYPE_CHECKING

from mashumaro.mixins.json import DataClassJSONMixin

from .actions import Action, ActionSet, EditboxInput, MenuInput
from ..messages.localization import Localization

if TYPE_CHECKING:
    from ..games.base import Game, Player


@dataclass
class OptionMeta:
    """Metadata for a game option."""

    default: Any
    label: str  # Localization key for the option label
    change_msg: str  # Localization key for the change announcement
    prompt: str = ""  # Localization key for input prompt (if applicable)

    def get_label(self, locale: str, value: Any) -> str:
        """Get the localized label with current value interpolated."""
        raise NotImplementedError

    def get_label_kwargs(self, value: Any) -> dict[str, Any]:
        """Get kwargs for label localization."""
        raise NotImplementedError

    def get_change_kwargs(self, value: Any) -> dict[str, Any]:
        """Get kwargs for change message localization."""
        raise NotImplementedError

    def create_action(
        self,
        option_name: str,
        game: "Game",
        player: "Player",
        current_value: Any,
        locale: str,
    ) -> Action:
        """Create an Action for this option."""
        raise NotImplementedError

    def validate_and_convert(self, value: str) -> tuple[bool, Any]:
        """Validate and convert input string to the option's type.

        Returns (success, converted_value). If success is False, converted_value
        is the original string.
        """
        raise NotImplementedError


@dataclass
class IntOption(OptionMeta):
    """Integer option with min/max validation."""

    min_val: int = 0
    max_val: int = 100
    value_key: str = (
        "score"  # Key used in localization (e.g., "score", "points", "sides")
    )

    def get_label_kwargs(self, value: Any) -> dict[str, Any]:
        return {self.value_key: value}

    def get_change_kwargs(self, value: Any) -> dict[str, Any]:
        return {self.value_key: value}

    def create_action(
        self,
        option_name: str,
        game: "Game",
        player: "Player",
        current_value: Any,
        locale: str,
    ) -> Action:
        label = Localization.get(
            locale, self.label, **self.get_label_kwargs(current_value)
        )
        return Action(
            id=f"set_{option_name}",
            label=label,
            handler="_action_set_option",  # Generic handler extracts option_name from action_id
            input_request=EditboxInput(
                prompt=self.prompt,
                default=str(current_value),
            ),
        )

    def validate_and_convert(self, value: str) -> tuple[bool, Any]:
        try:
            int_val = int(value)
            int_val = max(self.min_val, min(self.max_val, int_val))
            return True, int_val
        except ValueError:
            return False, value


@dataclass
class MenuOption(OptionMeta):
    """Menu selection option."""

    choices: list[str] | Callable[["Game", "Player"], list[str]] = field(
        default_factory=list
    )
    value_key: str = "mode"  # Key used in localization

    def get_label_kwargs(self, value: Any) -> dict[str, Any]:
        return {self.value_key: value}

    def get_change_kwargs(self, value: Any) -> dict[str, Any]:
        return {self.value_key: value}

    def create_action(
        self,
        option_name: str,
        game: "Game",
        player: "Player",
        current_value: Any,
        locale: str,
    ) -> Action:
        label = Localization.get(
            locale, self.label, **self.get_label_kwargs(current_value)
        )

        return Action(
            id=f"set_{option_name}",
            label=label,
            handler="_action_set_option",  # Generic handler extracts option_name from action_id
            input_request=MenuInput(
                prompt=self.prompt,
                options=f"_options_for_{option_name}",
            ),
        )

    def validate_and_convert(self, value: str) -> tuple[bool, Any]:
        # For menu options, the value comes from a predefined list, so it's valid
        return True, value


@dataclass
class BoolOption(OptionMeta):
    """Boolean toggle option."""

    value_key: str = "enabled"  # Key used in localization

    def __post_init__(self):
        # Bool options don't need a prompt - they just toggle
        self.prompt = ""

    def get_label_kwargs(self, value: Any) -> dict[str, Any]:
        return {self.value_key: "on" if value else "off"}

    def get_change_kwargs(self, value: Any) -> dict[str, Any]:
        return {self.value_key: "on" if value else "off"}

    def create_action(
        self,
        option_name: str,
        game: "Game",
        player: "Player",
        current_value: Any,
        locale: str,
    ) -> Action:
        # Get localized on/off value
        on_off_key = "option-on" if current_value else "option-off"
        on_off = Localization.get(locale, on_off_key)
        label = Localization.get(locale, self.label, **{self.value_key: on_off})
        return Action(
            id=f"toggle_{option_name}",
            label=label,
            handler="_action_toggle_option",  # Generic handler extracts option_name from action_id
            # No input_request - toggles directly
        )

    def validate_and_convert(self, value: str) -> tuple[bool, Any]:
        # For bool options, we just flip the value
        return True, value.lower() in ("true", "1", "yes")


def option_field(meta: OptionMeta) -> Any:
    """Create a dataclass field with option metadata attached.

    Usage:
        target_score: int = option_field(IntOption(default=50, ...))
    """
    return field(default=meta.default, metadata={"option_meta": meta})


def get_option_meta(options_class: type, field_name: str) -> OptionMeta | None:
    """Get the OptionMeta for a field, if it has one."""
    for f in fields(options_class):
        if f.name == field_name:
            return f.metadata.get("option_meta")
    return None


def get_all_option_metas(options_class: type) -> dict[str, OptionMeta]:
    """Get all OptionMeta instances from an options class."""
    result = {}
    for f in fields(options_class):
        meta = f.metadata.get("option_meta")
        if meta is not None:
            result[f.name] = meta
    return result


@dataclass
class GameOptions(DataClassJSONMixin):
    """Base class for game options with declarative option support.

    Subclasses should use option_field() for options that need auto-generated
    UI and handlers:

        @dataclass
        class MyOptions(GameOptions):
            target_score: int = option_field(IntOption(...))
            difficulty: str = option_field(MenuOption(...))

            # Regular fields without option_field work normally
            internal_state: int = 0
    """

    def get_option_metas(self) -> dict[str, OptionMeta]:
        """Get all option metadata for this options instance."""
        return get_all_option_metas(type(self))

    def create_options_action_set(self, game: "Game", player: "Player") -> ActionSet:
        """Create an ActionSet with all declared options."""
        user = game.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="options")

        for name, meta in self.get_option_metas().items():
            current_value = getattr(self, name)
            action = meta.create_action(name, game, player, current_value, locale)
            action_set.add(action)

        return action_set

    def update_options_labels(self, game: "Game") -> None:
        """Update all option labels to reflect current values."""
        for player in game.players:
            options_set = game.get_action_set(player, "options")
            if not options_set:
                continue

            user = game.get_user(player)
            locale = user.locale if user else "en"

            for name, meta in self.get_option_metas().items():
                current_value = getattr(self, name)
                action_id = (
                    f"set_{name}"
                    if not isinstance(meta, BoolOption)
                    else f"toggle_{name}"
                )

                # For bool options, get localized on/off value
                if isinstance(meta, BoolOption):
                    on_off_key = "option-on" if current_value else "option-off"
                    on_off = Localization.get(locale, on_off_key)
                    label = Localization.get(
                        locale, meta.label, **{meta.value_key: on_off}
                    )
                else:
                    label = Localization.get(
                        locale, meta.label, **meta.get_label_kwargs(current_value)
                    )

                options_set.set_label(action_id, label)
