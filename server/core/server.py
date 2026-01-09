"""Main server class that ties everything together."""

import asyncio
from pathlib import Path

import json

from .tick import TickScheduler
from ..network.websocket_server import WebSocketServer, ClientConnection
from ..persistence.database import Database
from ..auth.auth import AuthManager
from ..tables.manager import TableManager
from ..users.network_user import NetworkUser
from ..users.base import MenuItem, EscapeBehavior
from ..users.preferences import UserPreferences, DiceKeepingStyle
from ..games.registry import GameRegistry, get_game_class
from ..messages.localization import Localization


VERSION = "11.0.0"

# Default paths based on module location
_MODULE_DIR = Path(__file__).parent.parent
_DEFAULT_LOCALES_DIR = _MODULE_DIR / "locales"


class Server:
    """
    Main PlayPalace v11 server.

    Coordinates all components: network, auth, tables, games, and persistence.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        db_path: str = "playpalace.db",
        locales_dir: str | Path | None = None,
    ):
        self.host = host
        self.port = port

        # Initialize components
        self._db = Database(db_path)
        self._auth: AuthManager | None = None
        self._tables = TableManager()
        self._tables._server = self  # Enable callbacks from TableManager
        self._ws_server: WebSocketServer | None = None
        self._tick_scheduler: TickScheduler | None = None

        # User tracking
        self._users: dict[str, NetworkUser] = {}  # username -> NetworkUser
        self._user_states: dict[str, dict] = {}  # username -> UI state

        # Initialize localization
        if locales_dir is None:
            locales_dir = _DEFAULT_LOCALES_DIR
        Localization.init(Path(locales_dir))

    async def start(self) -> None:
        """Start the server."""
        print(f"Starting PlayPalace v{VERSION} server...")

        # Connect to database
        self._db.connect()
        self._auth = AuthManager(self._db)

        # Load existing tables
        self._load_tables()

        # Start WebSocket server
        self._ws_server = WebSocketServer(
            host=self.host,
            port=self.port,
            on_connect=self._on_client_connect,
            on_disconnect=self._on_client_disconnect,
            on_message=self._on_client_message,
        )
        await self._ws_server.start()

        # Start tick scheduler
        self._tick_scheduler = TickScheduler(self._on_tick)
        await self._tick_scheduler.start()

        print(f"Server running on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the server."""
        print("Stopping server...")

        # Save all tables
        self._save_tables()

        # Stop tick scheduler
        if self._tick_scheduler:
            await self._tick_scheduler.stop()

        # Stop WebSocket server
        if self._ws_server:
            await self._ws_server.stop()

        # Close database
        self._db.close()

        print("Server stopped.")

    def _load_tables(self) -> None:
        """Load tables from database and restore their games."""
        from ..users.bot import Bot

        tables = self._db.load_all_tables()
        for table in tables:
            self._tables.add_table(table)

            # Restore game from JSON if present
            if table.game_json:
                game_class = get_game_class(table.game_type)
                if not game_class:
                    print(f"WARNING: Could not find game class for {table.game_type}")
                    continue

                # Deserialize game and rebuild runtime state
                game = game_class.from_json(table.game_json)
                game.rebuild_runtime_state()
                table.game = game
                game._table = table

                # Setup keybinds (runtime only, not serialized)
                game.setup_keybinds()
                # Attach bots (humans will be attached when they reconnect)
                # Action sets are already restored from serialization
                for player in game.players:
                    if player.is_bot:
                        bot_user = Bot(player.name)
                        game.attach_user(player.id, bot_user)

        print(f"Loaded {len(tables)} tables from database.")

        # Delete all tables from database after loading to prevent stale data
        # on subsequent restarts. Tables will be re-saved on shutdown.
        self._db.delete_all_tables()

    def _save_tables(self) -> None:
        """Save all tables to database."""
        tables = self._tables.save_all()
        self._db.save_all_tables(tables)
        print(f"Saved {len(tables)} tables to database.")

    def _on_tick(self) -> None:
        """Called every tick (50ms)."""
        # Tick all tables
        self._tables.on_tick()

        # Flush queued messages for all users
        self._flush_user_messages()

    def _flush_user_messages(self) -> None:
        """Send all queued messages for all users."""
        for username, user in self._users.items():
            messages = user.get_queued_messages()
            if messages and self._ws_server:
                client = self._ws_server.get_client_by_username(username)
                if client:
                    for msg in messages:
                        asyncio.create_task(client.send(msg))

    async def _on_client_connect(self, client: ClientConnection) -> None:
        """Handle new client connection."""
        print(f"Client connected: {client.address}")

    async def _on_client_disconnect(self, client: ClientConnection) -> None:
        """Handle client disconnection."""
        print(f"Client disconnected: {client.address}")
        if client.username:
            # Clean up user state
            self._users.pop(client.username, None)
            self._user_states.pop(client.username, None)

    async def _on_client_message(self, client: ClientConnection, packet: dict) -> None:
        """Handle incoming message from client."""
        packet_type = packet.get("type")

        if packet_type == "authorize":
            await self._handle_authorize(client, packet)
        elif not client.authenticated:
            # Ignore non-auth packets from unauthenticated clients
            return
        elif packet_type == "menu":
            await self._handle_menu(client, packet)
        elif packet_type == "keybind":
            await self._handle_keybind(client, packet)
        elif packet_type == "editbox":
            await self._handle_editbox(client, packet)
        elif packet_type == "chat":
            await self._handle_chat(client, packet)
        elif packet_type == "ping":
            await self._handle_ping(client)

    async def _handle_authorize(self, client: ClientConnection, packet: dict) -> None:
        """Handle authorization packet."""
        username = packet.get("username", "")
        password = packet.get("password", "")

        # Try to authenticate or register
        if not self._auth.authenticate(username, password):
            # Try to register
            if not self._auth.register(username, password):
                # Username taken with different password
                await client.send(
                    {
                        "type": "disconnect",
                        "reason": "Invalid credentials",
                        "reconnect": False,
                    }
                )
                return

        # Authentication successful
        client.username = username
        client.authenticated = True

        # Create network user with preferences
        user_record = self._auth.get_user(username)
        locale = user_record.locale if user_record else "en"
        preferences = UserPreferences()
        if user_record and user_record.preferences_json:
            try:
                prefs_data = json.loads(user_record.preferences_json)
                preferences = UserPreferences.from_dict(prefs_data)
            except (json.JSONDecodeError, KeyError):
                pass  # Use defaults on error
        user = NetworkUser(username, locale, client, preferences=preferences)
        self._users[username] = user

        # Send success response
        await client.send(
            {
                "type": "authorize_success",
                "username": username,
                "version": VERSION,
            }
        )

        # Send game list
        print(f"DEBUG: Sending game list to {username}")
        await self._send_game_list(client)

        # Check if user is in a table
        print(f"DEBUG: Checking if {username} is in a table")
        table = self._tables.find_user_table(username)
        print(f"DEBUG: table = {table}")

        if table and table.game:
            # Rejoin table - use same approach as _restore_saved_table
            game = table.game

            # Attach user to table and game
            table.attach_user(username, user)
            player = game.get_player_by_name(username)
            if player:
                game.attach_user(player.id, user)

                # Set user state so menu selections are handled correctly
                self._user_states[username] = {
                    "menu": "in_game",
                    "table_id": table.table_id,
                }

                # Rebuild menu for this player
                game.rebuild_player_menu(player)
        else:
            # Show main menu
            self._show_main_menu(user)

    # Available languages
    LANGUAGES = {
        "en": "English",
        "pt": "Português",
        "zh": "中文",
    }
    LANGUAGES_ENGLISH = {
        "en": "English",
        "pt": "Portuguese",
        "zh": "Chinese",
    }

    async def _send_game_list(self, client: ClientConnection) -> None:
        """Send the list of available games to the client."""
        games = []
        for game_class in GameRegistry.get_all():
            games.append(
                {
                    "type": game_class.get_type(),
                    "name": game_class.get_name(),
                }
            )

        await client.send(
            {
                "type": "update_options_lists",
                "games": games,
                "languages": self.LANGUAGES,
            }
        )

    def _show_main_menu(self, user: NetworkUser) -> None:
        """Show the main menu to a user."""
        print(
            f"DEBUG: _show_main_menu called for {user.username} with locale {user.locale}"
        )
        items = [
            MenuItem(text=Localization.get(user.locale, "play"), id="play"),
            MenuItem(
                text=Localization.get(user.locale, "saved-tables"), id="saved_tables"
            ),
            MenuItem(text=Localization.get(user.locale, "options"), id="options"),
            MenuItem(text=Localization.get(user.locale, "logout"), id="logout"),
        ]
        user.show_menu(
            "main_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        user.play_music("mainmus.ogg")
        user.stop_ambience()
        self._user_states[user.username] = {"menu": "main_menu"}

    def _show_categories_menu(self, user: NetworkUser) -> None:
        """Show game categories menu."""
        categories = GameRegistry.get_by_category()
        items = []
        for category_key in sorted(categories.keys()):
            category_name = Localization.get(user.locale, category_key)
            items.append(MenuItem(text=category_name, id=f"category_{category_key}"))
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))

        user.show_menu(
            "categories_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "categories_menu"}

    def _show_games_menu(self, user: NetworkUser, category: str) -> None:
        """Show games in a category."""
        categories = GameRegistry.get_by_category()
        games = categories.get(category, [])

        items = []
        for game_class in games:
            game_name = Localization.get(user.locale, game_class.get_name_key())
            items.append(MenuItem(text=game_name, id=f"game_{game_class.get_type()}"))
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))

        user.show_menu(
            "games_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "games_menu", "category": category}

    def _show_tables_menu(self, user: NetworkUser, game_type: str) -> None:
        """Show available tables for a game."""
        tables = self._tables.get_waiting_tables(game_type)
        game_class = get_game_class(game_type)
        game_name = (
            Localization.get(user.locale, game_class.get_name_key())
            if game_class
            else game_type
        )

        items = [
            MenuItem(
                text=Localization.get(user.locale, "create-table"), id="create_table"
            )
        ]

        for table in tables:
            player_count = table.player_count
            items.append(
                MenuItem(
                    text=Localization.get(
                        user.locale,
                        "table-listing",
                        host=table.host,
                        count=player_count,
                    ),
                    id=f"table_{table.table_id}",
                )
            )

        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))

        user.show_menu(
            "tables_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "tables_menu",
            "game_type": game_type,
            "game_name": game_name,
        }

    # Dice keeping style display names
    DICE_KEEPING_STYLES = {
        DiceKeepingStyle.PLAYPALACE: "PlayPalace style",
        DiceKeepingStyle.QUENTIN_C: "Quentin C style",
    }

    def _show_options_menu(self, user: NetworkUser) -> None:
        """Show options menu."""
        current_lang = self.LANGUAGES.get(user.locale, "English")
        prefs = user.preferences

        # Turn sound option
        turn_sound_status = Localization.get(
            user.locale,
            "option-on" if prefs.play_turn_sound else "option-off",
        )

        # Clear kept dice option
        clear_kept_status = Localization.get(
            user.locale,
            "option-on" if prefs.clear_kept_on_roll else "option-off",
        )

        # Dice keeping style option
        dice_style_name = self.DICE_KEEPING_STYLES.get(
            prefs.dice_keeping_style, "PlayPalace style"
        )

        items = [
            MenuItem(
                text=Localization.get(
                    user.locale, "language-option", language=current_lang
                ),
                id="language",
            ),
            MenuItem(
                text=Localization.get(
                    user.locale, "turn-sound-option", status=turn_sound_status
                ),
                id="turn_sound",
            ),
            MenuItem(
                text=Localization.get(
                    user.locale, "clear-kept-option", status=clear_kept_status
                ),
                id="clear_kept",
            ),
            MenuItem(
                text=Localization.get(
                    user.locale, "dice-keeping-style-option", style=dice_style_name
                ),
                id="dice_keeping_style",
            ),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "options_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "options_menu"}

    def _show_language_menu(self, user: NetworkUser) -> None:
        """Show language selection menu."""
        items = []
        for lang_code, lang_name in self.LANGUAGES.items():
            prefix = "* " if lang_code == user.locale else ""
            english_name = self.LANGUAGES_ENGLISH.get(lang_code, lang_name)
            # Add English name in parentheses if different from native name
            if english_name != lang_name:
                display = f"{prefix}{lang_name} ({english_name})"
            else:
                display = f"{prefix}{lang_name}"
            items.append(MenuItem(text=display, id=f"lang_{lang_code}"))
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "language_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "language_menu"}

    def _show_saved_tables_menu(self, user: NetworkUser) -> None:
        """Show saved tables menu."""
        saved = self._db.get_user_saved_tables(user.username)

        if not saved:
            user.speak_l("no-saved-tables")
            self._show_main_menu(user)
            return

        items = []
        for record in saved:
            items.append(MenuItem(text=record.save_name, id=f"saved_{record.id}"))
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))

        user.show_menu(
            "saved_tables_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "saved_tables_menu"}

    def _show_saved_table_actions_menu(self, user: NetworkUser, save_id: int) -> None:
        """Show actions for a saved table (restore, delete)."""
        items = [
            MenuItem(text=Localization.get(user.locale, "restore-table"), id="restore"),
            MenuItem(
                text=Localization.get(user.locale, "delete-saved-table"), id="delete"
            ),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "saved_table_actions_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "saved_table_actions_menu",
            "save_id": save_id,
        }

    async def _handle_menu(self, client: ClientConnection, packet: dict) -> None:
        """Handle menu selection."""
        username = client.username
        if not username:
            return

        user = self._users.get(username)
        if not user:
            return

        selection_id = packet.get("selection_id", "")

        state = self._user_states.get(username, {})
        current_menu = state.get("menu")

        # Check if user is in a table - delegate all events to game
        table = self._tables.find_user_table(username)
        if table and table.game:
            player = table.game.get_player_by_name(username)
            if player:
                table.game.handle_event(player, packet)
                # Check if player left the game
                if not table.game.get_player_by_name(username):
                    table.remove_member(username)
                    self._show_main_menu(user)
            return

        # Handle menu selections based on current menu
        if current_menu == "main_menu":
            await self._handle_main_menu_selection(user, selection_id)
        elif current_menu == "categories_menu":
            await self._handle_categories_selection(user, selection_id, state)
        elif current_menu == "games_menu":
            await self._handle_games_selection(user, selection_id, state)
        elif current_menu == "tables_menu":
            await self._handle_tables_selection(user, selection_id, state)
        elif current_menu == "join_menu":
            await self._handle_join_selection(user, selection_id, state)
        elif current_menu == "options_menu":
            await self._handle_options_selection(user, selection_id)
        elif current_menu == "language_menu":
            await self._handle_language_selection(user, selection_id)
        elif current_menu == "dice_keeping_style_menu":
            await self._handle_dice_keeping_style_selection(user, selection_id)
        elif current_menu == "saved_tables_menu":
            await self._handle_saved_tables_selection(user, selection_id, state)
        elif current_menu == "saved_table_actions_menu":
            await self._handle_saved_table_actions_selection(user, selection_id, state)

    async def _handle_main_menu_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle main menu selection."""
        if selection_id == "play":
            self._show_categories_menu(user)
        elif selection_id == "saved_tables":
            self._show_saved_tables_menu(user)
        elif selection_id == "options":
            self._show_options_menu(user)
        elif selection_id == "logout":
            user.speak_l("goodbye")
            await user.connection.send({"type": "disconnect", "reconnect": False})

    async def _handle_options_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle options menu selection."""
        if selection_id == "language":
            self._show_language_menu(user)
        elif selection_id == "turn_sound":
            # Toggle turn sound
            prefs = user.preferences
            prefs.play_turn_sound = not prefs.play_turn_sound
            self._save_user_preferences(user)
            self._show_options_menu(user)
        elif selection_id == "clear_kept":
            # Toggle clear kept on roll
            prefs = user.preferences
            prefs.clear_kept_on_roll = not prefs.clear_kept_on_roll
            self._save_user_preferences(user)
            self._show_options_menu(user)
        elif selection_id == "dice_keeping_style":
            self._show_dice_keeping_style_menu(user)
        elif selection_id == "back":
            self._show_main_menu(user)

    def _show_dice_keeping_style_menu(self, user: NetworkUser) -> None:
        """Show dice keeping style selection menu."""
        items = []
        current_style = user.preferences.dice_keeping_style
        for style, name in self.DICE_KEEPING_STYLES.items():
            prefix = "* " if style == current_style else ""
            items.append(MenuItem(text=f"{prefix}{name}", id=f"style_{style.value}"))
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "dice_keeping_style_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "dice_keeping_style_menu"}

    async def _handle_dice_keeping_style_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle dice keeping style selection."""
        if selection_id.startswith("style_"):
            style_value = selection_id[6:]  # Remove "style_" prefix
            style = DiceKeepingStyle.from_str(style_value)
            user.preferences.dice_keeping_style = style
            self._save_user_preferences(user)
            style_name = self.DICE_KEEPING_STYLES.get(style, "PlayPalace style")
            user.speak_l("dice-keeping-style-changed", style=style_name)
            self._show_options_menu(user)
            return
        # Back or invalid
        self._show_options_menu(user)

    def _save_user_preferences(self, user: NetworkUser) -> None:
        """Save user preferences to database."""
        prefs_json = json.dumps(user.preferences.to_dict())
        self._db.update_user_preferences(user.username, prefs_json)

    async def _handle_language_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle language selection."""
        if selection_id.startswith("lang_"):
            lang_code = selection_id[5:]  # Remove "lang_" prefix
            if lang_code in self.LANGUAGES:
                user.set_locale(lang_code)
                self._db.update_user_locale(user.username, lang_code)
                user.speak_l("language-changed", language=self.LANGUAGES[lang_code])
                self._show_options_menu(user)
                return
        # Back or invalid
        self._show_options_menu(user)

    async def _handle_categories_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle category selection."""
        if selection_id.startswith("category_"):
            category = selection_id[9:]  # Remove "category_" prefix
            self._show_games_menu(user, category)
        elif selection_id == "back":
            self._show_main_menu(user)

    async def _handle_games_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle game selection."""
        if selection_id.startswith("game_"):
            game_type = selection_id[5:]  # Remove "game_" prefix
            self._show_tables_menu(user, game_type)
        elif selection_id == "back":
            self._show_categories_menu(user)

    async def _handle_tables_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle tables menu selection."""
        game_type = state.get("game_type", "")

        if selection_id == "create_table":
            table = self._tables.create_table(game_type, user.username, user)

            # Create game immediately and initialize lobby
            game_class = get_game_class(game_type)
            if game_class:
                game = game_class()
                table.game = game
                game._table = table  # Enable game to call table.destroy()
                game.initialize_lobby(user.username, user)

                user.speak_l(
                    "table-created",
                    host=user.username,
                    game=state.get("game_name", game_type),
                )
                min_players = game_class.get_min_players()
                max_players = game_class.get_max_players()
                user.speak_l(
                    "waiting-for-players",
                    current=len(game.players),
                    min=min_players,
                    max=max_players,
                )
            self._user_states[user.username] = {
                "menu": "in_game",
                "table_id": table.table_id,
            }

        elif selection_id.startswith("table_"):
            table_id = selection_id[6:]  # Remove "table_" prefix
            table = self._tables.get_table(table_id)
            if table:
                # Show join options
                items = [
                    MenuItem(
                        text=Localization.get(user.locale, "join-as-player"),
                        id="join_player",
                    ),
                    MenuItem(
                        text=Localization.get(user.locale, "join-as-spectator"),
                        id="join_spectator",
                    ),
                    MenuItem(text=Localization.get(user.locale, "back"), id="back"),
                ]
                user.show_menu(
                    "join_menu", items, escape_behavior=EscapeBehavior.SELECT_LAST
                )
                self._user_states[user.username] = {
                    "menu": "join_menu",
                    "table_id": table_id,
                    "game_type": game_type,
                }
            else:
                user.speak_l("table-not-exists")
                self._show_tables_menu(user, game_type)

        elif selection_id == "back":
            category = None
            for cat, games in GameRegistry.get_by_category().items():
                if any(g.get_type() == game_type for g in games):
                    category = cat
                    break
            if category:
                self._show_games_menu(user, category)
            else:
                self._show_categories_menu(user)

    async def _handle_join_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle join menu selection."""
        table_id = state.get("table_id")
        table = self._tables.get_table(table_id)

        if not table or not table.game:
            user.speak_l("table-not-exists")
            self._show_tables_menu(user, state.get("game_type", ""))
            return

        game = table.game

        if selection_id == "join_player":
            if len(game.players) >= game.get_max_players():
                user.speak_l("table-full")
                self._show_tables_menu(user, state.get("game_type", ""))
                return

            # Add player to game
            table.add_member(user.username, user, as_spectator=False)
            game.add_player(user.username, user)
            game.broadcast_l("table-joined", player=user.username)
            game.rebuild_all_menus()
            self._user_states[user.username] = {"menu": "in_game", "table_id": table_id}

        elif selection_id == "join_spectator":
            table.add_member(user.username, user, as_spectator=True)
            user.speak_l("spectator-joined", host=table.host)
            # TODO: spectator viewing - for now just track membership
            self._user_states[user.username] = {"menu": "in_game", "table_id": table_id}

        elif selection_id == "back":
            self._show_tables_menu(user, state.get("game_type", ""))

    async def _handle_saved_tables_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle saved tables menu selection."""
        if selection_id.startswith("saved_"):
            save_id = int(selection_id[6:])  # Remove "saved_" prefix
            self._show_saved_table_actions_menu(user, save_id)
        elif selection_id == "back":
            self._show_main_menu(user)

    async def _handle_saved_table_actions_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle saved table actions (restore/delete)."""
        save_id = state.get("save_id")
        if not save_id:
            self._show_main_menu(user)
            return

        if selection_id == "restore":
            await self._restore_saved_table(user, save_id)
        elif selection_id == "delete":
            self._db.delete_saved_table(save_id)
            user.speak_l("saved-table-deleted")
            self._show_saved_tables_menu(user)
        elif selection_id == "back":
            self._show_saved_tables_menu(user)

    async def _restore_saved_table(self, user: NetworkUser, save_id: int) -> None:
        """Restore a saved table."""
        import json
        from ..users.bot import Bot

        record = self._db.get_saved_table(save_id)
        if not record:
            user.speak_l("table-not-exists")
            self._show_main_menu(user)
            return

        # Get the game class
        game_class = get_game_class(record.game_type)
        if not game_class:
            user.speak_l("game-type-not-found")
            self._show_main_menu(user)
            return

        # Parse members from saved state
        members_data = json.loads(record.members_json)
        human_players = [m for m in members_data if not m.get("is_bot", False)]

        # Check all human players are available
        missing_players = []
        for member in human_players:
            member_username = member.get("username")
            if member_username not in self._users:
                missing_players.append(member_username)
            else:
                # Check they're not already in a table
                existing_table = self._tables.find_user_table(member_username)
                if existing_table:
                    missing_players.append(member_username)

        if missing_players:
            user.speak_l("missing-players", players=", ".join(missing_players))
            self._show_saved_tables_menu(user)
            return

        # All players available - create table and restore game
        table = self._tables.create_table(record.game_type, user.username, user)

        # Load game from JSON and rebuild runtime state
        game = game_class.from_json(record.game_json)
        game.rebuild_runtime_state()
        table.game = game
        game._table = table  # Enable game to call table.destroy()

        # Update host to the restorer
        game.host = user.username

        # Attach users and transfer all human players
        for member in members_data:
            member_username = member.get("username")
            is_bot = member.get("is_bot", False)

            if is_bot:
                # Recreate bot
                bot_user = Bot(member_username)
                game.attach_user(member_username, bot_user)
            else:
                # Attach human user
                member_user = self._users.get(member_username)
                if member_user:
                    table.add_member(member_username, member_user, as_spectator=False)
                    game.attach_user(member_username, member_user)
                    self._user_states[member_username] = {
                        "menu": "in_game",
                        "table_id": table.table_id,
                    }

        # Setup keybinds (runtime only, not serialized)
        # Action sets are already restored from serialization
        game.setup_keybinds()

        # Rebuild menus for all players
        game.rebuild_all_menus()

        # Notify all players
        game.broadcast_l("table-restored")

        # Delete the saved table now that it's been restored
        self._db.delete_saved_table(save_id)

    def on_table_destroy(self, table) -> None:
        """Handle table destruction. Called by TableManager."""
        if not table.game:
            return
        # Return all human players to main menu
        for player in table.game.players:
            if not player.is_bot:
                player_user = self._users.get(player.name)
                if player_user:
                    self._show_main_menu(player_user)

    def on_table_save(self, table, username: str) -> None:
        """Handle table save request. Called by TableManager."""
        import json
        from datetime import datetime

        game = table.game
        if not game:
            return

        # Generate save name
        save_name = f"{game.get_name()} - {datetime.now():%Y-%m-%d %H:%M}"

        # Get game JSON
        game_json = game.to_json()

        # Build members list (includes bot status)
        members_data = []
        for player in game.players:
            members_data.append(
                {
                    "username": player.name,
                    "is_bot": player.is_bot,
                }
            )
        members_json = json.dumps(members_data)

        # Save to database
        self._db.save_user_table(
            username=username,
            save_name=save_name,
            game_type=table.game_type,
            game_json=game_json,
            members_json=members_json,
        )

        # Broadcast save message and destroy the table
        game.broadcast_l("table-saved-destroying")
        game.destroy()

    async def _handle_keybind(self, client: ClientConnection, packet: dict) -> None:
        """Handle keybind press."""
        username = client.username
        if not username:
            return

        user = self._users.get(username)
        table = self._tables.find_user_table(username)
        if table and table.game:
            player = table.game.get_player_by_name(username)
            if player:
                table.game.handle_event(player, packet)
                # Check if player left the game
                if user and not table.game.get_player_by_name(username):
                    table.remove_member(username)
                    self._show_main_menu(user)

    async def _handle_editbox(self, client: ClientConnection, packet: dict) -> None:
        """Handle editbox submission."""
        username = client.username
        if not username:
            return

        user = self._users.get(username)
        table = self._tables.find_user_table(username)
        if table and table.game:
            player = table.game.get_player_by_name(username)
            if player:
                table.game.handle_event(player, packet)
                # Check if player left the game
                if user and not table.game.get_player_by_name(username):
                    table.remove_member(username)
                    self._show_main_menu(user)

    async def _handle_chat(self, client: ClientConnection, packet: dict) -> None:
        """Handle chat message."""
        username = client.username
        if not username:
            return

        convo = packet.get("convo", "table")
        message = packet.get("message", "")
        language = packet.get("language", "English")

        if convo == "table":
            table = self._tables.find_user_table(username)
            if table:
                for member_name in [m.username for m in table.members]:
                    user = self._users.get(member_name)
                    if user:
                        await user.connection.send(
                            {
                                "type": "chat",
                                "convo": "table",
                                "sender": username,
                                "message": message,
                                "language": language,
                            }
                        )
        elif convo == "global":
            # Broadcast to all users
            if self._ws_server:
                await self._ws_server.broadcast(
                    {
                        "type": "chat",
                        "convo": "global",
                        "sender": username,
                        "message": message,
                        "language": language,
                    }
                )

    async def _handle_ping(self, client: ClientConnection) -> None:
        """Handle ping request - respond immediately with pong."""
        await client.send({"type": "pong"})


async def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the server."""
    server = Server(host=host, port=port)
    await server.start()

    try:
        # Run forever
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()
