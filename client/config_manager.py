"""Configuration manager for Play Palace client.

Handles client-side configuration including:
- User credentials (config.json - private)
- Server management with unique IDs and nicknames (option_profiles.json - shareable)
- Global default options (option_profiles.json - shareable)
- Per-server option overrides (option_profiles.json - shareable)
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

def get_item_from_dict(dictionary: dict, key_path: (str, tuple), *, create_mode: bool= False):
  """Return the item in a dictionary, typically a nested layer dict.
  Optionally create keys that don't exist, or require the full path to exist already.
  This function supports an infinite number of layers."""
  if isinstance(key_path, str)  and len(key_path)>0:
    if key_path[0] == "/": key_path = key_path[1:]
    if key_path[-1] == "/": key_path = key_path[:-1]
    key_path = key_path.split("/")
  scope= dictionary
  for l in range(len(key_path)):
    if key_path[l] == "": continue
    layer= key_path[l]
    if layer not in scope:
      if not create_mode: raise KeyError(f"Key '{layer}' not in "+ (("nested dictionary "+ '/'.join(key_path[:l])) if l>0 else "root dictionary")+ ".")
      scope[layer] = {}
    scope= scope[layer]
  return scope

def set_item_in_dict(dictionary: dict, key_path: (str, tuple), value, *, create_mode: bool= False) -> bool:
  """Modify the value of an item in a dictionary.
  Optionally create keys that don't exist, or require the full path to exist already.
  This function supports an infinite number of layers."""
  if isinstance(key_path, str) and len(key_path)>0:
    if key_path[0] == "/": key_path = key_path[1:]
    if key_path[-1] == "/": key_path = key_path[:-1]
    key_path = key_path.split("/")
  if not key_path or key_path[-1] == "": raise ValueError("No dictionary key path was specified.")
  final_key = key_path.pop(-1)
  obj = get_item_from_dict(dictionary, key_path, create_mode = create_mode)
  if not isinstance(obj, dict): raise TypeError(f"Expected type 'dict', instead got '{type(obj)}'.")
  if not create_mode and final_key not in obj: raise KeyError(f"Key '{final_key}' not in dictionary '{key_path}'.")
  obj[final_key] = value
  return True

def delete_item_from_dict(dictionary: dict, key_path: (str, tuple), *, delete_empty_layers: bool = True) -> bool:
  """Delete an item in a dictionary.
  Optionally delete layers that are empty.
  This function supports an infinite number of layers."""
  if isinstance(key_path, str) and len(key_path)>0:
    if key_path[0] == "/": key_path = key_path[1:]
    if key_path[-1] == "/": key_path = key_path[:-1]
    key_path = key_path.split("/")
  if not key_path or key_path[-1] == "": raise ValueError("No dictionary key path was specified.")
  final_key = key_path.pop(-1)
  obj = get_item_from_dict(dictionary, key_path)
  if not isinstance(obj, dict): raise TypeError(f"Expected type 'dict', instead got '{type(obj)}'.")
  if final_key not in obj: return False
  del obj[final_key]
  if not delete_empty_layers: return True
  # Walk from deepest to shallowest, removing empty dicts
  for i in range(len(key_path), 0, -1):
    try:
      obj = get_item_from_dict(dictionary, key_path[:i])
      if isinstance(obj, dict) and not obj:  # Empty dict
        if i == 1:
          del dictionary[key_path[0]]
        else:
          parent = get_item_from_dict(dictionary, key_path[:i-1])
          del parent[key_path[i-1]]
    except KeyError:
      break
  return True


class ConfigManager:
    """Manages client configuration and per-server settings.

    Uses two separate files:
    - config.json: Contains username, password (private, not shareable)
    - option_profiles.json: Contains server list and options (shareable, no credentials)
    """

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize the config manager.

        Args:
            base_path: Base directory path. Defaults to ~/.playpalace/
        """
        if base_path is None:
            base_path = Path.home() / ".playpalace"

        self.base_path = base_path
        self.config_path = base_path / "config.json"
        self.profiles_path = base_path / "option_profiles.json"

        self.config = self._load_config()
        self.profiles = self._load_profiles()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file (credentials only)."""
        if not self.config_path.exists():
            return self._get_default_config()

        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure (credentials only)."""
        return {
            "username": "",
            "password": "",
            "last_server_id": None,  # ID of last connected server
        }

    def _load_profiles(self) -> Dict[str, Any]:
        """Load option profiles from file (shareable, no credentials)."""
        if not self.profiles_path.exists():
            return self._get_default_profiles()

        try:
            with open(self.profiles_path, "r") as f:
                profiles = json.load(f)
                # Migrate old combined config if needed
                return self._migrate_profiles(profiles)
        except Exception as e:
            print(f"Error loading profiles: {e}")
            return self._get_default_profiles()

    def _get_default_profiles(self) -> Dict[str, Any]:
        """Get default profiles structure (shareable)."""
        return {
            "client_options_defaults": {
                "audio": {"music_volume": 20, "ambience_volume": 20},
                "social": {
                    "mute_global_chat": False,
                    "mute_table_chat": False,
                    "include_language_filters_for_table_chat": False,
                    "chat_input_language": "English",
                    "language_subscriptions": {},
                },
                "interface": {
                    "invert_multiline_enter_behavior": False,
                    "play_typing_sounds": True,
                },
                "local_table": {
                    "start_as_visible": "always",
                    "start_with_password": "never",
                    "default_password_text": "",
                    "creation_notifications": {}},  # Will be populated dynamically
            },
            "servers": {},  # server_id -> server info dict
        }

    def _migrate_profiles(self, profiles: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate profiles to fix data issues.

        Args:
            profiles: The loaded profiles dictionary

        Returns:
            Migrated profiles dictionary
        """
        needs_save = False

        # Migration: Fix "check" -> "Czech" in language subscriptions
        # Check default profile language subscriptions
        if "client_options_defaults" in profiles:
            defaults = profiles["client_options_defaults"]
            if "social" in defaults:
                # Fix language subscriptions
                if "language_subscriptions" in defaults["social"]:
                    lang_subs = defaults["social"]["language_subscriptions"]
                    if "Check" in lang_subs:
                        lang_subs["Czech"] = lang_subs.pop("Check")
                        needs_save = True
                        print(
                            "Migrated language subscription: 'Check' -> 'Czech' in default profile"
                        )

                # Fix chat_input_language
                if "chat_input_language" in defaults["social"]:
                    chat_lang = defaults["social"]["chat_input_language"]
                    if chat_lang == "Check":
                        defaults["social"]["chat_input_language"] = "Czech"
                        needs_save = True
                        print(
                            "Migrated chat_input_language: 'Check' -> 'Czech' in default profile"
                        )

        # Check each server override for language subscriptions
        if "servers" in profiles:
            for server_id, server_info in profiles["servers"].items():
                if "options_overrides" in server_info:
                    overrides = server_info["options_overrides"]
                    if "social" in overrides:
                        # Fix language subscriptions
                        if "language_subscriptions" in overrides["social"]:
                            lang_subs = overrides["social"]["language_subscriptions"]
                            if "Check" in lang_subs:
                                lang_subs["Czech"] = lang_subs.pop("Check")
                                needs_save = True
                                print(
                                    "Migrated language subscription: 'Check' -> 'Czech' in server {server_id}"
                                )

                        # Fix chat_input_language
                        if "chat_input_language" in overrides["social"]:
                            chat_lang = overrides["social"]["chat_input_language"]
                            if chat_lang == "Check":
                                overrides["social"]["chat_input_language"] = "Czech"
                                needs_save = True
                                print(
                                    "Migrated chat_input_language: 'Check' -> 'Czech' in server {server_id}"
                                )

        # Migration: Rename table_creations to local_table/creation_notifications
        # and add new default options to local_table
        if "client_options_defaults" in profiles:
            defaults = profiles["client_options_defaults"]
            if "table_creations" in defaults:
                table_creations_value = defaults.pop("table_creations")
                if "local_table" not in defaults:
                    defaults["local_table"] = {}
                # Build local_table with proper ordering (new options before creation_notifications)
                new_local_table = {
                    "start_as_visible": defaults["local_table"].get("start_as_visible", "always"),
                    "start_with_password": defaults["local_table"].get("start_with_password", "never"),
                    "default_password_text": defaults["local_table"].get("default_password_text", ""),
                    "creation_notifications": table_creations_value,
                }
                # Preserve any other existing keys in local_table
                for key, value in defaults["local_table"].items():
                    if key not in new_local_table:
                        new_local_table[key] = value
                defaults["local_table"] = new_local_table
                needs_save = True
                print("Migrated 'table_creations' -> 'local_table/creation_notifications' in default profile")

        # Check each server override for table_creations
        if "servers" in profiles:
            for server_id, server_info in profiles["servers"].items():
                if "options_overrides" in server_info:
                    overrides = server_info["options_overrides"]
                    if "table_creations" in overrides:
                        table_creations_value = overrides.pop("table_creations")
                        if "local_table" not in overrides:
                            overrides["local_table"] = {}
                        # Build local_table with proper ordering
                        new_local_table = {
                            "start_as_visible": overrides["local_table"].get("start_as_visible", "always"),
                            "start_with_password": overrides["local_table"].get("start_with_password", "never"),
                            "default_password_text": overrides["local_table"].get("default_password_text", ""),
                            "creation_notifications": table_creations_value,
                        }
                        # Preserve any other existing keys in local_table
                        for key, value in overrides["local_table"].items():
                            if key not in new_local_table:
                                new_local_table[key] = value
                        overrides["local_table"] = new_local_table
                        needs_save = True
                        print(f"Migrated 'table_creations' -> 'local_table/creation_notifications' in server {server_id}")

        # Save immediately if migration occurred
        if needs_save:
            self.profiles = profiles
            self.save_profiles()
            print("Profile migration completed and saved to disk.")

        return profiles

    def _deep_merge(
        self, base: Dict[str, Any], override: Dict[str, Any], override_wins: bool = True
    ) -> Dict[str, Any]:
        """Deep merge two dictionaries with configurable precedence.

        Supports infinite nesting depth.

        Args:
            base: Base dictionary
            override: Dictionary to merge into base
            override_wins: If True, override values take precedence on conflicts.
                           If False, base values take precedence (override fills missing keys only).

        Returns:
            Merged dictionary
        """
        result = self._deep_copy(base)

        for key, value in override.items():
            if key not in result:
                result[key] = self._deep_copy(value)
            elif isinstance(value, dict) and isinstance(result[key], dict):
                result[key] = self._deep_merge(result[key], value, override_wins)
            elif override_wins:
                result[key] = self._deep_copy(value)
            # else: base wins, keep existing value

        return result

    def save_config(self):
        """Save credentials configuration to file."""
        try:
            # Create config directory if it doesn't exist
            self.base_path.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def save_profiles(self):
        """Save option profiles to file."""
        try:
            # Create config directory if it doesn't exist
            self.base_path.mkdir(parents=True, exist_ok=True)

            with open(self.profiles_path, "w") as f:
                json.dump(self.profiles, f, indent=2)
        except Exception as e:
            print(f"Error saving profiles: {e}")

    def save(self):
        """Save both config and profiles."""
        self.save_config()
        self.save_profiles()

    def get_username(self) -> str:
        """Get saved username."""
        return self.config.get("username", "")

    def get_password(self) -> str:
        """Get saved password."""
        return self.config.get("password", "")

    def set_credentials(self, username: str, password: str):
        """Set username and password.

        Args:
            username: Username
            password: Password
        """
        self.config["username"] = username
        self.config["password"] = password
        self.save_config()

    def get_last_server_id(self) -> Optional[str]:
        """Get ID of last connected server."""
        return self.config.get("last_server_id")

    def get_server_by_id(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get server info by ID.

        Args:
            server_id: Unique server ID

        Returns:
            Server info dict or None if not found
        """
        return self.profiles["servers"].get(server_id)

    def get_servers_by_url(self, url: str) -> List[Dict[str, Any]]:
        """Get all servers matching a URL.

        Args:
            url: Server URL

        Returns:
            List of server info dicts
        """
        servers = []
        for server_id, server_info in self.profiles["servers"].items():
            if server_info["url"] == url:
                servers.append(server_info)
        return servers

    def get_all_servers(self) -> Dict[str, Dict[str, Any]]:
        """Get all servers.

        Returns:
            Dict mapping server_id to server info
        """
        return self.profiles["servers"]

    def add_or_get_server(self, url: str, nickname: Optional[str] = None) -> str:
        """Add a new server or get existing one.

        If multiple servers exist with the same URL, returns None to signal
        that the caller should prompt the user to choose.

        Args:
            url: Server URL
            nickname: Optional nickname for the server

        Returns:
            Server ID, or None if user needs to choose from multiple
        """
        # Check if server(s) with this URL already exist
        existing = self.get_servers_by_url(url)

        if len(existing) == 0:
            # Create new server entry
            server_id = str(uuid.uuid4())
            self.profiles["servers"][server_id] = {
                "server_id": server_id,
                "url": url,
                "nickname": nickname,
                "first_connected": datetime.now().isoformat(),
                "last_connected": datetime.now().isoformat(),
                "options_overrides": {},
            }
            self.config["last_server_id"] = server_id
            self.save()
            return server_id
        elif len(existing) == 1:
            # Update last connected time
            server_id = existing[0]["server_id"]
            self.profiles["servers"][server_id]["last_connected"] = (
                datetime.now().isoformat()
            )
            self.config["last_server_id"] = server_id
            self.save()
            return server_id
        else:
            # Multiple servers with same URL - caller needs to prompt user
            return None

    def create_new_server(self, url: str, nickname: Optional[str] = None) -> str:
        """Force creation of a new server entry.

        Args:
            url: Server URL
            nickname: Optional nickname

        Returns:
            New server ID
        """
        server_id = str(uuid.uuid4())
        self.profiles["servers"][server_id] = {
            "server_id": server_id,
            "url": url,
            "nickname": nickname,
            "first_connected": datetime.now().isoformat(),
            "last_connected": datetime.now().isoformat(),
            "options_overrides": {},
        }
        self.config["last_server_id"] = server_id
        self.save()
        return server_id

    def update_server_last_connected(self, server_id: str):
        """Update last connected timestamp for a server.

        Args:
            server_id: Server ID
        """
        if server_id in self.profiles["servers"]:
            self.profiles["servers"][server_id]["last_connected"] = (
                datetime.now().isoformat()
            )
            self.config["last_server_id"] = server_id
            self.save()

    def set_server_nickname(self, server_id: str, nickname: str):
        """Set or update server nickname.

        Args:
            server_id: Server ID
            nickname: New nickname
        """
        if server_id in self.profiles["servers"]:
            self.profiles["servers"][server_id]["nickname"] = nickname
            self.save_profiles()

    def get_server_display_name(self, server_id: str) -> str:
        """Get display name for a server (nickname or URL).

        Args:
            server_id: Server ID

        Returns:
            Display name
        """
        server = self.get_server_by_id(server_id)
        if server:
            return server["nickname"] or server["url"]
        return "Unknown Server"

    def get_client_options(self, server_id: Optional[str] = None) -> Dict[str, Any]:
        """Get client options for a server (defaults + overrides).

        Args:
            server_id: Server ID, or None for just defaults

        Returns:
            Complete options dict with overrides applied
        """
        # Start with defaults
        options = self._deep_copy(self.profiles["client_options_defaults"])

        # Apply server-specific overrides if provided
        if server_id and server_id in self.profiles["servers"]:
            overrides = self.profiles["servers"][server_id].get("options_overrides", {})
            options = self._deep_merge(options, overrides)

        return options

    def set_client_option(
        self, key_path: str, value: Any, server_id: Optional[str] = None, *, create_mode: bool = False
    ):
        """Set a client option (either default or server-specific override).

        Args:
            key_path: Path to the option (e.g., "audio/music_volume", "social/language_subscriptions/English")
            value: Option value
            server_id: Server ID for override, or None for default
            create_mode: If True, create intermediate dictionaries as needed
        """
        if server_id is None:
            # Set default
            target = self.profiles["client_options_defaults"]
        else:
            # Set server override
            if server_id not in self.profiles["servers"]:
                return
            target = self.profiles["servers"][server_id].setdefault(
                "options_overrides", {}
            )

        success = set_item_in_dict(target, key_path, value, create_mode= create_mode)
        if success: self.save_profiles()

    def clear_server_override(self, server_id: str, key_path: str, *, delete_empty_layers: bool= True):
        """Clear a server-specific override (revert to default).

        Args:
            server_id: Server ID
            key_path: Path to the option (e.g., "audio/music_volume")
            delete_empty_layers: If True, delete intermediate dictionaries if empty
        """
        if server_id not in self.profiles["servers"]:
            return

        overrides = self.profiles["servers"][server_id].get("options_overrides", {})

        success = delete_item_from_dict(overrides, key_path, delete_empty_layers= delete_empty_layers)
        if success: self.save_profiles()

    def _deep_copy(self, obj: Any) -> Any:
        """Deep copy a nested dict/list structure."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj

