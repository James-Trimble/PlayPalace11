"""Base game class and player dataclass."""

from dataclasses import dataclass, field
from typing import Any, Callable
from abc import ABC, abstractmethod
import threading

from mashumaro.mixins.json import DataClassJSONMixin
from mashumaro.config import BaseConfig

from ..users.base import User, MenuItem, EscapeBehavior
from ..users.bot import Bot
from ..game_utils.actions import (
    Action,
    ActionSet,
    MenuInput,
    EditboxInput,
    Visibility,
    ResolvedAction,
)
from ..game_utils.options import (
    GameOptions as DeclarativeGameOptions,
    get_option_meta,
    MenuOption,
)
from ..game_utils.game_result import GameResult, PlayerResult
from ..game_utils.teams import TeamManager
from ..game_utils.game_sound_mixin import GameSoundMixin
from ..game_utils.game_communication_mixin import GameCommunicationMixin
from ..game_utils.game_result_mixin import GameResultMixin
from ..game_utils.duration_estimate_mixin import DurationEstimateMixin
from ..game_utils.game_scores_mixin import GameScoresMixin
from ..game_utils.game_prediction_mixin import GamePredictionMixin
from ..game_utils.turn_management_mixin import TurnManagementMixin
from ..game_utils.menu_management_mixin import MenuManagementMixin
from ..game_utils.action_visibility_mixin import ActionVisibilityMixin
from ..game_utils.lobby_actions_mixin import LobbyActionsMixin, BOT_NAMES
from ..messages.localization import Localization
from ..ui.keybinds import Keybind, KeybindState


@dataclass
class ActionContext:
    """Context passed to action handlers when triggered by keybind."""

    menu_item_id: str | None = None  # ID of selected menu item when keybind pressed
    menu_index: int | None = None  # 1-based index of selected menu item
    from_keybind: bool = (
        False  # True if triggered by keybind, False if by menu selection
    )


@dataclass
class Player(DataClassJSONMixin):
    """
    A player in a game.

    This is a dataclass that gets serialized with the game state.
    The user field is not serialized - it's reattached on load.
    """

    id: str  # UUID - unique identifier (from user.uuid for humans, generated for bots)
    name: str  # Display name
    is_bot: bool = False
    is_spectator: bool = False
    # Bot AI state (serialized for persistence)
    bot_think_ticks: int = 0  # Ticks until bot can act
    bot_pending_action: str | None = None  # Action to execute when ready
    bot_target: int | None = None  # Game-specific target (e.g., score to reach)


# Re-export GameOptions from options module for backwards compatibility
GameOptions = DeclarativeGameOptions


@dataclass
class Game(
    ABC,
    DataClassJSONMixin,
    GameSoundMixin,
    GameCommunicationMixin,
    GameResultMixin,
    DurationEstimateMixin,
    GameScoresMixin,
    GamePredictionMixin,
    TurnManagementMixin,
    MenuManagementMixin,
    ActionVisibilityMixin,
    LobbyActionsMixin,
):
    """
    Abstract base class for all games.

    Games are dataclasses that can be serialized with Mashumaro.
    All game state must be stored in dataclass fields.

    Games are synchronous and state-based. They expose actions that
    players can take, and these actions modify state imperatively.

    Games have three phases:
    - waiting: Lobby phase, host can add bots and start
    - playing: Game in progress
    - finished: Game over
    """

    class Config(BaseConfig):
        # Serialize all fields (don't omit defaults - breaks state restoration)
        serialize_by_alias = True

    # Game state
    players: list[Player] = field(default_factory=list)
    round: int = 0
    game_active: bool = False
    status: str = "waiting"  # waiting, playing, finished
    host: str = ""  # Username of the host
    current_music: str = ""  # Currently playing music track
    current_ambience: str = ""  # Currently playing ambience loop
    turn_index: int = 0  # Current turn index (serialized for persistence)
    turn_direction: int = 1  # Turn direction: 1 = forward, -1 = reverse
    turn_skip_count: int = 0  # Number of players to skip on next advance
    turn_player_ids: list[str] = field(
        default_factory=list
    )  # Player IDs in turn order (serialized)
    # Round timer state (serialized for persistence)
    round_timer_state: str = "idle"  # idle, counting, paused
    round_timer_ticks: int = 0  # Remaining ticks in countdown
    # Sound scheduler state (serialized for persistence)
    scheduled_sounds: list = field(
        default_factory=list
    )  # [[tick, sound, vol, pan, pitch], ...]
    sound_scheduler_tick: int = 0  # Current tick counter
    # Action sets (serialized - actions are pure data now)
    player_action_sets: dict[str, list[ActionSet]] = field(default_factory=dict)
    # Team manager (serialized for persistence)
    _team_manager: TeamManager = field(default_factory=TeamManager)

    def __post_init__(self):
        """Initialize non-serialized state."""
        # These are runtime-only, not serialized
        self._users: dict[str, User] = {}  # player_id -> User
        self._table: Any = None  # Reference to Table (set by server)
        self._keybinds: dict[
            str, list[Keybind]
        ] = {}  # key -> list of Keybinds (allows same key for different states)
        self._pending_actions: dict[
            str, str
        ] = {}  # player_id -> action_id (waiting for input)
        self._action_context: dict[
            str, ActionContext
        ] = {}  # player_id -> context during action execution
        self._status_box_open: set[str] = set()  # player_ids with status box open
        self._actions_menu_open: set[str] = set()  # player_ids with actions menu open
        self._destroyed: bool = False  # Whether game has been destroyed
        # Duration estimation state
        self._estimate_threads: list[threading.Thread] = []  # Running simulation threads
        self._estimate_results: list[int] = []  # Collected tick counts
        self._estimate_errors: list[str] = []  # Collected errors
        self._estimate_running: bool = False  # Whether estimation is in progress
        self._estimate_lock: threading.Lock = threading.Lock()  # Protect results list

    def rebuild_runtime_state(self) -> None:
        """
        Rebuild non-serialized runtime state after deserialization.

        Called after loading a game from JSON. Subclasses should override
        this to rebuild any runtime-only objects not stored in serialized fields.
        Turn management and sound scheduling are now built into the base class
        using serialized fields, so they don't need rebuilding.

        Note: Estimation state is initialized clean by __post_init__.
        """
        pass

    # Abstract methods games must implement

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """Return the display name of this game (English fallback)."""
        ...

    @classmethod
    @abstractmethod
    def get_type(cls) -> str:
        """Return the type identifier for this game."""
        ...

    @classmethod
    def get_name_key(cls) -> str:
        """Return the localization key for this game's name."""
        return f"game-name-{cls.get_type()}"

    @classmethod
    def get_category(cls) -> str:
        """Return the category localization key for this game."""
        return "category-uncategorized"

    @classmethod
    def get_min_players(cls) -> int:
        """Return minimum number of players."""
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        """Return maximum number of players."""
        return 4

    @classmethod
    def get_leaderboard_types(cls) -> list[dict]:
        """Return additional leaderboard types this game supports.

        Override in subclasses to add game-specific leaderboards.
        Each dict should have:
        - "id": leaderboard type identifier (e.g., "best_single_turn")
        - "path": dot-separated path to value in custom_data
                  Use {player_id} or {player_name} as placeholders
                  e.g., "player_stats.{player_name}.best_turn"
                  OR for ratio calculations, use:
        - "numerator": path to numerator value
        - "denominator": path to denominator value
                  (values are summed across games, then divided)
        - "aggregate": how to combine values across games
                       "sum", "max", or "avg"
        - "format": entry format key suffix (e.g., "score" for leaderboard-score-entry)
        - "decimals": optional, number of decimal places (default 0)

        The server will look up localization keys like:
        - "leaderboard-type-{id}" for menu display (with underscores as hyphens)
        - "leaderboard-{format}-entry" for each entry
        """
        return []

    def prestart_validate(self) -> list[str] | list[tuple[str, dict]]:
        """Validate game configuration before starting.

        Returns a list of localization keys for any errors found,
        or a list of (error_key, kwargs) tuples for errors that need context.
        Override in subclasses to add game-specific validation.

        Examples:
            return ["pig-error-min-bank-too-high"]
            return [("scopa-error-not-enough-cards", {"decks": 1, "players": 4})]
        """
        return []

    def _validate_team_mode(self, team_mode: str) -> str | None:
        """Helper to validate team mode for current player count.

        Args:
            team_mode: Internal team mode string (e.g., "individual", "2v2").

        Returns:
            Localization key for error if invalid, None if valid.
        """
        active_players = self.get_active_players()
        num_players = len(active_players)

        # Parse old display format if needed
        if " " in team_mode or any(c.isupper() for c in team_mode if c != "v"):
            team_mode = TeamManager.parse_display_to_team_mode(team_mode)

        # Check if team mode is valid for player count
        if not TeamManager.is_valid_team_mode(team_mode, num_players):
            return "game-error-invalid-team-mode"

        return None

    @abstractmethod
    def on_start(self) -> None:
        """Called when the game starts."""
        ...

    def on_tick(self) -> None:
        """Called every tick (50ms). Handle bot AI here.

        Subclasses should call super().on_tick() to ensure base functionality runs.
        """
        # Check if duration estimation has completed
        self.check_estimate_completion()

    def on_round_timer_ready(self) -> None:
        """Called when round timer expires. Override in subclasses that use RoundTimer."""
        pass

    # Player management

    def attach_user(self, player_id: str, user: User) -> None:
        """Attach a user to a player by ID."""
        self._users[player_id] = user
        # Play current music/ambience for the joining user
        if self.current_music:
            user.play_music(self.current_music)
        if self.current_ambience:
            user.play_ambience(self.current_ambience)

    def get_user(self, player: Player) -> User | None:
        """Get the user for a player."""
        return self._users.get(player.id)

    def get_player_by_id(self, player_id: str) -> Player | None:
        """Get a player by ID (UUID)."""
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def get_player_by_name(self, name: str) -> Player | None:
        """Get a player by display name. Note: Names may not be unique."""
        for player in self.players:
            if player.name == name:
                return player
        return None

    @property
    def current_player(self) -> Player | None:
        """Get the current player based on turn_index and turn_player_ids."""
        if not self.turn_player_ids:
            return None
        index = self.turn_index % len(self.turn_player_ids)
        player_id = self.turn_player_ids[index]
        return self.get_player_by_id(player_id)

    @current_player.setter
    def current_player(self, player: Player | None) -> None:
        """Set the current player by updating turn_index."""
        if player is None or player.id not in self.turn_player_ids:
            return
        self.turn_index = self.turn_player_ids.index(player.id)

    @property
    def team_manager(self) -> TeamManager:
        """Get the team manager for this game."""
        return self._team_manager

    # Action Set System

    def get_action_sets(self, player: Player) -> list[ActionSet]:
        """Get ordered list of action sets for a player."""
        return self.player_action_sets.get(player.id, [])

    def get_action_set(self, player: Player, name: str) -> ActionSet | None:
        """Get a specific action set by name for a player."""
        for action_set in self.get_action_sets(player):
            if action_set.name == name:
                return action_set
        return None

    def add_action_set(self, player: Player, action_set: ActionSet) -> None:
        """Add an action set to a player (appended to end of list)."""
        if player.id not in self.player_action_sets:
            self.player_action_sets[player.id] = []
        self.player_action_sets[player.id].append(action_set)

    def remove_action_set(self, player: Player, name: str) -> None:
        """Remove an action set from a player by name."""
        if player.id in self.player_action_sets:
            self.player_action_sets[player.id] = [
                s for s in self.player_action_sets[player.id] if s.name != name
            ]

    def find_action(self, player: Player, action_id: str) -> Action | None:
        """Find an action by ID across all of a player's action sets."""
        for action_set in self.get_action_sets(player):
            action = action_set.get_action(action_id)
            if action:
                return action
        return None

    def resolve_action(self, player: Player, action: Action) -> ResolvedAction:
        """Resolve a single action's state for a player."""
        # Find the action set containing this action
        for action_set in self.get_action_sets(player):
            if action_set.get_action(action.id):
                return action_set.resolve_action(self, player, action)
        # Fallback - resolve with defaults
        return ResolvedAction(
            action=action,
            label=action.label,
            enabled=True,
            disabled_reason=None,
            visible=True,
        )

    def get_all_visible_actions(self, player: Player) -> list[ResolvedAction]:
        """Get all visible (enabled and not hidden) actions for a player, in order."""
        result = []
        for action_set in self.get_action_sets(player):
            result.extend(action_set.get_visible_actions(self, player))
        return result

    def get_all_enabled_actions(self, player: Player) -> list[ResolvedAction]:
        """Get all enabled actions for a player (for F5 menu), in order."""
        result = []
        for action_set in self.get_action_sets(player):
            result.extend(action_set.get_enabled_actions(self, player))
        return result

    def define_keybind(
        self,
        key: str,
        name: str,
        actions: list[str],
        *,
        requires_focus: bool = False,
        state: KeybindState = KeybindState.ALWAYS,
        players: list[str] | None = None,
        include_spectators: bool = False,
    ) -> None:
        """
        Define a keybind that triggers one or more actions.

        Args:
            key: The key combination (e.g., "space", "shift+b", "f5")
            name: Human-readable name for the keybind (e.g., "Roll dice")
            actions: List of action IDs this keybind triggers
            requires_focus: If True, must be focused on a valid menu item
            state: When the keybind is active (NEVER, IDLE, ACTIVE, ALWAYS)
            players: List of player names who can use (empty/None = all)
            include_spectators: Whether spectators can use this keybind
        """
        keybind = Keybind(
            name=name,
            default_key=key,
            actions=actions,
            requires_focus=requires_focus,
            state=state,
            players=players or [],
            include_spectators=include_spectators,
        )
        if key not in self._keybinds:
            self._keybinds[key] = []
        self._keybinds[key].append(keybind)

    def _get_keybind_for_action(self, action_id: str) -> str | None:
        """Get the keybind string for an action, if any."""
        for key, keybinds in self._keybinds.items():
            for keybind in keybinds:
                if action_id in keybind.actions:
                    return key
        return None

    def _is_player_spectator(self, player: Player) -> bool:
        """Check if a player is a spectator."""
        return player.is_spectator

    def get_active_players(self) -> list[Player]:
        """Get list of players who are not spectators (actually playing)."""
        return [p for p in self.players if not p.is_spectator]

    def get_active_player_count(self) -> int:
        """Get the number of active (non-spectator) players."""
        return len(self.get_active_players())

    def execute_action(
        self,
        player: Player,
        action_id: str,
        input_value: str | None = None,
        context: ActionContext | None = None,
    ) -> None:
        """Execute an action for a player, optionally with input value and context."""
        action = self.find_action(player, action_id)
        if not action:
            return

        # Check if action is enabled using declarative callback
        resolved = self.resolve_action(player, action)
        if not resolved.enabled:
            # Speak the reason to the player
            if resolved.disabled_reason:
                user = self.get_user(player)
                if user:
                    user.speak_l(resolved.disabled_reason)
            return

        # If action requires input and we don't have it yet
        if action.input_request is not None and input_value is None:
            # For bots, get input automatically
            if player.is_bot:
                # Set pending action so options methods can access action_id
                self._pending_actions[player.id] = action_id
                input_value = self._get_bot_input(action, player)
                # Clean up pending action for bot
                if player.id in self._pending_actions:
                    del self._pending_actions[player.id]
                if input_value is None:
                    return  # Bot couldn't provide input
            else:
                # For humans, request input and store pending action
                self._request_action_input(action, player)
                return

        # Look up the handler method by name on this game object
        handler = getattr(self, action.handler, None)
        if not handler:
            return

        # Store context for handlers that need it (e.g., keybind-triggered actions)
        self._action_context[player.id] = context or ActionContext()

        try:
            # Execute the action handler (always pass action_id for context)
            if action.input_request is not None and input_value is not None:
                # Handler expects input value: (player, input_value, action_id)
                handler(player, input_value, action_id)
            else:
                # Handler doesn't expect input: (player, action_id)
                handler(player, action_id)
        finally:
            # Clean up context
            self._action_context.pop(player.id, None)

    def get_action_context(self, player: Player) -> ActionContext:
        """Get the current action context for a player (for use in handlers)."""
        return self._action_context.get(player.id, ActionContext())

    def _get_menu_options_for_action(
        self, action: Action, player: Player
    ) -> list[str] | None:
        """Get menu options for an action, checking method first then MenuOption metadata."""
        req = action.input_request
        if not isinstance(req, MenuInput):
            return None

        # First try the method name
        options_method = getattr(self, req.options, None)
        if options_method:
            return options_method(player)

        # Fallback: check if this is a set_* action for a MenuOption
        if action.id.startswith("set_") and hasattr(self, "options"):
            option_name = action.id[4:]  # Remove "set_" prefix
            meta = get_option_meta(type(self.options), option_name)
            if meta and isinstance(meta, MenuOption):
                choices = meta.choices
                # Choices can be a list or a callable
                if callable(choices):
                    return choices(self, player)
                return list(choices)

        return None

    def _get_bot_input(self, action: Action, player: Player) -> str | None:
        """Get automatic input for a bot player."""
        req = action.input_request
        if isinstance(req, MenuInput):
            options = self._get_menu_options_for_action(action, player)
            if not options:
                return None
            if req.bot_select:
                # Look up bot_select method by name
                bot_select_method = getattr(self, req.bot_select, None)
                if bot_select_method:
                    return bot_select_method(player, options)
            # Default: pick first option
            return options[0]
        elif isinstance(req, EditboxInput):
            if req.bot_input:
                # Look up bot_input method by name
                bot_input_method = getattr(self, req.bot_input, None)
                if bot_input_method:
                    return bot_input_method(player)
            # Default: use default value
            return req.default
        return None

    def _request_action_input(self, action: Action, player: Player) -> None:
        """Request input from a human player for an action."""
        user = self.get_user(player)
        if not user:
            return

        req = action.input_request
        self._pending_actions[player.id] = action.id

        if isinstance(req, MenuInput):
            options = self._get_menu_options_for_action(action, player)
            if not options:
                # No options available
                del self._pending_actions[player.id]
                user.speak_l("no-options-available")
                return

            # Check if this is a MenuOption with localized choice labels
            menu_option_meta = None
            if action.id.startswith("set_") and hasattr(self, "options"):
                option_name = action.id[4:]  # Remove "set_" prefix
                meta = get_option_meta(type(self.options), option_name)
                if meta and isinstance(meta, MenuOption):
                    menu_option_meta = meta

            # Build menu items with localized labels if available
            items = []
            for opt in options:
                if menu_option_meta:
                    display_text = menu_option_meta.get_localized_choice(
                        opt, user.locale
                    )
                else:
                    display_text = opt
                items.append(MenuItem(text=display_text, id=opt))

            items.append(
                MenuItem(text=Localization.get(user.locale, "cancel"), id="_cancel")
            )
            user.show_menu(
                "action_input_menu",
                items,
                multiletter=True,
                escape_behavior=EscapeBehavior.SELECT_LAST,
            )

        elif isinstance(req, EditboxInput):
            # Show editbox for text input
            prompt = Localization.get(user.locale, req.prompt)
            user.show_editbox("action_input_editbox", prompt, req.default)

    def end_turn(self) -> None:
        """End the current player's turn. Call this from action handlers."""
        # Default behavior - can be overridden by games
        self.advance_turn()

    # Event handling

    def handle_event(self, player: Player, event: dict) -> None:
        """Handle an event from a player."""
        event_type = event.get("type")

        if event_type == "menu":
            menu_id = event.get("menu_id")
            selection_id = event.get("selection_id", "")

            if menu_id == "turn_menu":
                # If interacting with turn_menu, actions menu is no longer open
                self._actions_menu_open.discard(player.id)
                # Try by ID first, then by index
                action = (
                    self.find_action(player, selection_id) if selection_id else None
                )
                if action:
                    resolved = self.resolve_action(player, action)
                    if resolved.enabled:
                        self.execute_action(player, selection_id)
                        # Don't rebuild if action is waiting for input
                        if player.id not in self._pending_actions:
                            self.rebuild_all_menus()
                else:
                    # Fallback to index-based selection - use visible actions only
                    selection = event.get("selection", 1) - 1  # Convert to 0-based
                    visible = self.get_all_visible_actions(player)
                    if 0 <= selection < len(visible):
                        resolved = visible[selection]
                        self.execute_action(player, resolved.action.id)
                        # Don't rebuild if action is waiting for input
                        if player.id not in self._pending_actions:
                            self.rebuild_all_menus()

            elif menu_id == "actions_menu":
                # F5 menu - use selection_id directly
                if selection_id:
                    self._handle_actions_menu_selection(player, selection_id)

            elif menu_id == "status_box":
                user = self.get_user(player)
                if user:
                    user.remove_menu("status_box")
                    user.speak_l("status-box-closed")
                    self._status_box_open.discard(player.id)
                    self.rebuild_player_menu(player)

            elif menu_id == "game_over":
                # Handle game over menu - leave_game is the only selectable action
                # It's always the last item
                if selection_id == "leave_game":
                    self.execute_action(player, "leave_game")
                else:
                    # Index-based - any selection triggers leave
                    self.execute_action(player, "leave_game")

            elif menu_id == "action_input_menu":
                # Handle action input menu selection
                if player.id in self._pending_actions:
                    action_id = self._pending_actions.pop(player.id)
                    if selection_id != "_cancel":
                        # Execute the action with the selected input
                        self.execute_action(player, action_id, selection_id)
                self.rebuild_player_menu(player)

        elif event_type == "editbox":
            input_id = event.get("input_id", "")
            text = event.get("text", "")

            if input_id == "action_input_editbox":
                # Handle action input editbox submission
                if player.id in self._pending_actions:
                    action_id = self._pending_actions.pop(player.id)
                    if text:  # Non-empty input
                        self.execute_action(player, action_id, text)
                self.rebuild_player_menu(player)

        elif event_type == "keybind":
            key = event.get("key", "").lower()  # Normalize to lowercase
            menu_item_id = event.get("menu_item_id")
            menu_index = event.get("menu_index")

            # Handle modifiers - reconstruct full key string
            if event.get("shift") and not key.startswith("shift+"):
                key = f"shift+{key}"
            if event.get("control") and not key.startswith("ctrl+"):
                key = f"ctrl+{key}"
            if event.get("alt") and not key.startswith("alt+"):
                key = f"alt+{key}"

            # Look up keybinds for this key
            keybinds = self._keybinds.get(key)
            if keybinds is None:
                return

            # Check if player is a spectator
            is_spectator = self._is_player_spectator(player)

            # Build context for action handlers
            context = ActionContext(
                menu_item_id=menu_item_id,
                menu_index=menu_index,
                from_keybind=True,
            )

            # Try each keybind for this key (allows same key for different states)
            executed_any = False
            for keybind in keybinds:
                # Check if keybind can be used by this player in current state
                if not keybind.can_player_use(self, player, is_spectator):
                    continue

                # Check focus requirement
                if keybind.requires_focus and menu_item_id not in keybind.actions:
                    continue

                # Execute all enabled actions in the keybind
                for action_id in keybind.actions:
                    action = self.find_action(player, action_id)
                    if action:
                        resolved = self.resolve_action(player, action)
                        if resolved.enabled:
                            self.execute_action(player, action_id, context=context)
                            executed_any = True
                        elif resolved.disabled_reason:
                            # Speak the disabled reason to the player
                            user = self.get_user(player)
                            if user:
                                user.speak_l(resolved.disabled_reason)

            # Don't rebuild if action is waiting for input, status box is open, or actions menu is open
            if (
                executed_any
                and player.id not in self._pending_actions
                and player.id not in self._status_box_open
                and player.id not in self._actions_menu_open
            ):
                self.rebuild_all_menus()

    def _handle_actions_menu_selection(self, player: Player, action_id: str) -> None:
        """Handle selection from the F5 actions menu."""
        # Actions menu is no longer open
        self._actions_menu_open.discard(player.id)
        # Handle "go back" - just return to turn menu
        if action_id == "go_back":
            self.rebuild_player_menu(player)
            return
        action = self.find_action(player, action_id)
        if action:
            resolved = self.resolve_action(player, action)
            if resolved.enabled:
                self.execute_action(player, action_id)
        # Don't rebuild if action is waiting for input
        if player.id not in self._pending_actions:
            self.rebuild_player_menu(player)

    # Lobby system

    def destroy(self) -> None:
        """Request destruction of this game/table."""
        self._destroyed = True
        if self._table:
            self._table.destroy()

    # ==========================================================================
    # Action set creation
    # ==========================================================================

    def create_lobby_action_set(self, player: Player) -> ActionSet:
        """Create the lobby action set for a player."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="lobby")
        action_set.add(
            Action(
                id="start_game",
                label=Localization.get(locale, "start-game"),
                handler="_action_start_game",
                is_enabled="_is_start_game_enabled",
                is_hidden="_is_start_game_hidden",
            )
        )
        action_set.add(
            Action(
                id="add_bot",
                label=Localization.get(locale, "add-bot"),
                handler="_action_add_bot",
                is_enabled="_is_add_bot_enabled",
                is_hidden="_is_add_bot_hidden",
                input_request=EditboxInput(
                    prompt="enter-bot-name",
                    default="",
                    bot_input="_bot_input_add_bot",
                ),
            )
        )
        action_set.add(
            Action(
                id="remove_bot",
                label=Localization.get(locale, "remove-bot"),
                handler="_action_remove_bot",
                is_enabled="_is_remove_bot_enabled",
                is_hidden="_is_remove_bot_hidden",
            )
        )
        action_set.add(
            Action(
                id="toggle_spectator",
                label=Localization.get(locale, "spectate"),
                handler="_action_toggle_spectator",
                is_enabled="_is_toggle_spectator_enabled",
                is_hidden="_is_toggle_spectator_hidden",
                get_label="_get_toggle_spectator_label",
            )
        )
        action_set.add(
            Action(
                id="leave_game",
                label=Localization.get(locale, "leave-table"),
                handler="_action_leave_game",
                is_enabled="_is_leave_game_enabled",
                is_hidden="_is_leave_game_hidden",
            )
        )
        return action_set

    def create_estimate_action_set(self, player: Player) -> ActionSet:
        """Create the estimate duration action set for a player."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="estimate")
        action_set.add(
            Action(
                id="estimate_duration",
                label=Localization.get(locale, "estimate-duration"),
                handler="_action_estimate_duration",
                is_enabled="_is_estimate_duration_enabled",
                is_hidden="_is_estimate_duration_hidden",
            )
        )
        return action_set

    def create_standard_action_set(self, player: Player) -> ActionSet:
        """Create the standard action set (F5, save) for a player."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="standard")
        action_set.add(
            Action(
                id="show_actions",
                label=Localization.get(locale, "actions-menu"),
                handler="_action_show_actions_menu",
                is_enabled="_is_show_actions_enabled",
                is_hidden="_is_show_actions_hidden",
            )
        )
        action_set.add(
            Action(
                id="save_table",
                label=Localization.get(locale, "save-table"),
                handler="_action_save_table",
                is_enabled="_is_save_table_enabled",
                is_hidden="_is_save_table_hidden",
            )
        )

        # Common status actions (available during play)
        action_set.add(
            Action(
                id="whose_turn",
                label=Localization.get(locale, "whose-turn"),
                handler="_action_whose_turn",
                is_enabled="_is_whose_turn_enabled",
                is_hidden="_is_whose_turn_hidden",
            )
        )
        action_set.add(
            Action(
                id="check_scores",
                label=Localization.get(locale, "check-scores"),
                handler="_action_check_scores",
                is_enabled="_is_check_scores_enabled",
                is_hidden="_is_check_scores_hidden",
            )
        )
        action_set.add(
            Action(
                id="check_scores_detailed",
                label=Localization.get(locale, "check-scores-detailed"),
                handler="_action_check_scores_detailed",
                is_enabled="_is_check_scores_detailed_enabled",
                is_hidden="_is_check_scores_detailed_hidden",
            )
        )
        action_set.add(
            Action(
                id="predict_outcomes",
                label=Localization.get(locale, "predict-outcomes"),
                handler="_action_predict_outcomes",
                is_enabled="_is_predict_outcomes_enabled",
                is_hidden="_is_predict_outcomes_hidden",
            )
        )

        return action_set

    def setup_keybinds(self) -> None:
        """Define all keybinds for the game."""
        # Lobby keybinds
        self.define_keybind(
            "enter", "Start game", ["start_game"], state=KeybindState.IDLE
        )
        self.define_keybind("b", "Add bot", ["add_bot"], state=KeybindState.IDLE)
        self.define_keybind(
            "shift+b", "Remove bot", ["remove_bot"], state=KeybindState.IDLE
        )
        self.define_keybind(
            "f3",
            "Toggle spectator",
            ["toggle_spectator"],
            state=KeybindState.IDLE,
            include_spectators=True,
        )
        self.define_keybind(
            "q",
            "Leave table",
            ["leave_game"],
            state=KeybindState.ALWAYS,
            include_spectators=True,
        )
        # Standard keybinds
        self.define_keybind(
            "escape",
            "Actions menu",
            ["show_actions"],
            state=KeybindState.ALWAYS,
            include_spectators=True,
        )
        self.define_keybind(
            "ctrl+s", "Save table", ["save_table"], state=KeybindState.ALWAYS
        )

        # Status keybinds (during play)
        self.define_keybind(
            "t",
            "Whose turn",
            ["whose_turn"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )
        self.define_keybind(
            "s",
            "Check scores",
            ["check_scores"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )
        self.define_keybind(
            "shift+s",
            "Detailed scores",
            ["check_scores_detailed"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )
        self.define_keybind(
            "ctrl+r",
            "Predict outcomes",
            ["predict_outcomes"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )

    def create_turn_action_set(self, player: Player) -> ActionSet | None:
        """Create the turn action set for a player.

        Override in subclasses to add game-specific turn actions.
        Returns None by default (no turn actions).
        """
        return None

    def setup_player_actions(self, player: Player) -> None:
        """Set up action sets for a player. Called when player joins."""
        # Create and add action sets in order (first = appears first in menu)
        # Turn actions first (if any), then lobby, options, standard
        turn_set = self.create_turn_action_set(player)
        if turn_set:
            self.add_action_set(player, turn_set)

        lobby_set = self.create_lobby_action_set(player)
        self.add_action_set(player, lobby_set)

        # Only add options if the game defines them
        if hasattr(self, "options"):
            options_set = self.create_options_action_set(player)
            self.add_action_set(player, options_set)

        # Add estimate action set (after options)
        estimate_set = self.create_estimate_action_set(player)
        self.add_action_set(player, estimate_set)

        standard_set = self.create_standard_action_set(player)
        self.add_action_set(player, standard_set)

    # Player helpers

    def get_human_count(self) -> int:
        """Get the number of human players."""
        return sum(1 for p in self.players if not p.is_bot)

    def get_bot_count(self) -> int:
        """Get the number of bot players."""
        return sum(1 for p in self.players if p.is_bot)

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> Player:
        """Create a new player. Override in subclasses for custom player types."""
        return Player(id=player_id, name=name, is_bot=is_bot)

    def add_player(self, name: str, user: User) -> Player:
        """Add a player to the game."""
        is_bot = hasattr(user, "is_bot") and user.is_bot
        player = self.create_player(user.uuid, name, is_bot=is_bot)
        self.players.append(player)
        self.attach_user(player.id, user)
        # Set up action sets for the new player
        self.setup_player_actions(player)
        return player

    def initialize_lobby(self, host_name: str, host_user: User) -> None:
        """Initialize the game in lobby mode with a host."""
        self.host = host_name
        self.status = "waiting"
        self.setup_keybinds()
        self.add_player(host_name, host_user)
        self.rebuild_all_menus()

    # Declarative options system support

    def create_options_action_set(self, player: Player) -> ActionSet:
        """Create the options action set for a player.

        If the game's options class uses declarative options (option_field),
        this will auto-generate the action set. Otherwise, subclasses should
        override this method.
        """
        if hasattr(self.options, "create_options_action_set"):
            return self.options.create_options_action_set(self, player)
        # Fallback for non-declarative options
        return ActionSet(name="options")

    def _handle_option_change(self, option_name: str, value: str) -> None:
        """Handle a declarative option change (for int/menu options).

        This is called by auto-generated option actions.
        No broadcast needed - screen readers speak the updated list item.
        """
        meta = get_option_meta(type(self.options), option_name)
        if not meta:
            return

        success, converted = meta.validate_and_convert(value)
        if not success:
            return

        # Set the option value
        setattr(self.options, option_name, converted)

        # Update labels and rebuild menus
        if hasattr(self.options, "update_options_labels"):
            self.options.update_options_labels(self)
        self.rebuild_all_menus()

    def _handle_option_toggle(self, option_name: str) -> None:
        """Handle a declarative boolean option toggle.

        This is called by auto-generated toggle actions.
        No broadcast needed - screen readers speak the updated list item.
        """
        meta = get_option_meta(type(self.options), option_name)
        if not meta:
            return

        # Toggle the value
        current = getattr(self.options, option_name)
        new_value = not current
        setattr(self.options, option_name, new_value)

        # Update labels and rebuild menus
        if hasattr(self.options, "update_options_labels"):
            self.options.update_options_labels(self)
        self.rebuild_all_menus()

    # Generic option action handlers (extract option_name from action_id)

    def _action_set_option(self, player: Player, value: str, action_id: str) -> None:
        """Generic handler for setting an option value.

        Extracts the option name from action_id (e.g., "set_total_rounds" -> "total_rounds")
        and delegates to _handle_option_change.
        """
        option_name = action_id.removeprefix("set_")
        self._handle_option_change(option_name, value)

    def _action_toggle_option(self, player: Player, action_id: str) -> None:
        """Generic handler for toggling a boolean option.

        Extracts the option name from action_id (e.g., "toggle_show_hints" -> "show_hints")
        and delegates to _handle_option_toggle.
        """
        option_name = action_id.removeprefix("toggle_")
        self._handle_option_toggle(option_name)
