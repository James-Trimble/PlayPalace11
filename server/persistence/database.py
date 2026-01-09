"""SQLite database for persistence."""

import sqlite3
import json
from pathlib import Path
from dataclasses import dataclass

from ..tables.table import Table


@dataclass
class UserRecord:
    """A user record from the database."""

    id: int
    username: str
    password_hash: str
    locale: str = "en"
    preferences_json: str = "{}"


@dataclass
class SavedTableRecord:
    """A saved table record from the database."""

    id: int
    username: str
    save_name: str
    game_type: str
    game_json: str
    members_json: str
    saved_at: str


class Database:
    """
    SQLite database for PlayPalace persistence.

    Stores users and tables as specified in persistence.md.
    """

    def __init__(self, db_path: str | Path = "playpalace.db"):
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Connect to the database and create tables if needed."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        cursor = self._conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                locale TEXT DEFAULT 'en',
                preferences_json TEXT DEFAULT '{}'
            )
        """)

        # Migration: Add preferences_json column if it doesn't exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "preferences_json" not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN preferences_json TEXT DEFAULT '{}'"
            )

        # Tables table (game tables)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tables (
                table_id TEXT PRIMARY KEY,
                game_type TEXT NOT NULL,
                host TEXT NOT NULL,
                members_json TEXT NOT NULL,
                game_json TEXT,
                status TEXT DEFAULT 'waiting'
            )
        """)

        # Saved tables (user-saved game states)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_tables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                save_name TEXT NOT NULL,
                game_type TEXT NOT NULL,
                game_json TEXT NOT NULL,
                members_json TEXT NOT NULL,
                saved_at TEXT NOT NULL
            )
        """)

        self._conn.commit()

    # User operations

    def get_user(self, username: str) -> UserRecord | None:
        """Get a user by username."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, locale, preferences_json FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        if row:
            return UserRecord(
                id=row["id"],
                username=row["username"],
                password_hash=row["password_hash"],
                locale=row["locale"] or "en",
                preferences_json=row["preferences_json"] or "{}",
            )
        return None

    def create_user(
        self, username: str, password_hash: str, locale: str = "en"
    ) -> UserRecord:
        """Create a new user."""
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, locale) VALUES (?, ?, ?)",
            (username, password_hash, locale),
        )
        self._conn.commit()
        return UserRecord(
            id=cursor.lastrowid,
            username=username,
            password_hash=password_hash,
            locale=locale,
        )

    def user_exists(self, username: str) -> bool:
        """Check if a user exists."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        return cursor.fetchone() is not None

    def update_user_locale(self, username: str, locale: str) -> None:
        """Update a user's locale."""
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE users SET locale = ? WHERE username = ?", (locale, username)
        )
        self._conn.commit()

    def update_user_preferences(self, username: str, preferences_json: str) -> None:
        """Update a user's preferences."""
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE users SET preferences_json = ? WHERE username = ?",
            (preferences_json, username),
        )
        self._conn.commit()

    # Table operations

    def save_table(self, table: Table) -> None:
        """Save a table to the database."""
        cursor = self._conn.cursor()

        # Serialize members
        members_json = json.dumps(
            [
                {"username": m.username, "is_spectator": m.is_spectator}
                for m in table.members
            ]
        )

        cursor.execute(
            """
            INSERT OR REPLACE INTO tables (table_id, game_type, host, members_json, game_json, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                table.table_id,
                table.game_type,
                table.host,
                members_json,
                table.game_json,
                table.status,
            ),
        )
        self._conn.commit()

    def load_table(self, table_id: str) -> Table | None:
        """Load a table from the database."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM tables WHERE table_id = ?", (table_id,))
        row = cursor.fetchone()
        if not row:
            return None

        # Deserialize members
        members_data = json.loads(row["members_json"])
        from ..tables.table import TableMember

        members = [
            TableMember(username=m["username"], is_spectator=m["is_spectator"])
            for m in members_data
        ]

        return Table(
            table_id=row["table_id"],
            game_type=row["game_type"],
            host=row["host"],
            members=members,
            game_json=row["game_json"],
            status=row["status"],
        )

    def load_all_tables(self) -> list[Table]:
        """Load all tables from the database."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT table_id FROM tables")
        tables = []
        for row in cursor.fetchall():
            table = self.load_table(row["table_id"])
            if table:
                tables.append(table)
        return tables

    def delete_table(self, table_id: str) -> None:
        """Delete a table from the database."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM tables WHERE table_id = ?", (table_id,))
        self._conn.commit()

    def delete_all_tables(self) -> None:
        """Delete all tables from the database."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM tables")
        self._conn.commit()

    def save_all_tables(self, tables: list[Table]) -> None:
        """Save multiple tables."""
        for table in tables:
            self.save_table(table)

    # Saved table operations (user-saved game states)

    def save_user_table(
        self,
        username: str,
        save_name: str,
        game_type: str,
        game_json: str,
        members_json: str,
    ) -> SavedTableRecord:
        """Save a table state to a user's saved tables."""
        from datetime import datetime

        saved_at = datetime.now().isoformat()

        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO saved_tables (username, save_name, game_type, game_json, members_json, saved_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (username, save_name, game_type, game_json, members_json, saved_at),
        )
        self._conn.commit()

        return SavedTableRecord(
            id=cursor.lastrowid,
            username=username,
            save_name=save_name,
            game_type=game_type,
            game_json=game_json,
            members_json=members_json,
            saved_at=saved_at,
        )

    def get_user_saved_tables(self, username: str) -> list[SavedTableRecord]:
        """Get all saved tables for a user."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM saved_tables WHERE username = ? ORDER BY saved_at DESC",
            (username,),
        )
        records = []
        for row in cursor.fetchall():
            records.append(
                SavedTableRecord(
                    id=row["id"],
                    username=row["username"],
                    save_name=row["save_name"],
                    game_type=row["game_type"],
                    game_json=row["game_json"],
                    members_json=row["members_json"],
                    saved_at=row["saved_at"],
                )
            )
        return records

    def get_saved_table(self, save_id: int) -> SavedTableRecord | None:
        """Get a saved table by ID."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM saved_tables WHERE id = ?", (save_id,))
        row = cursor.fetchone()
        if not row:
            return None

        return SavedTableRecord(
            id=row["id"],
            username=row["username"],
            save_name=row["save_name"],
            game_type=row["game_type"],
            game_json=row["game_json"],
            members_json=row["members_json"],
            saved_at=row["saved_at"],
        )

    def delete_saved_table(self, save_id: int) -> None:
        """Delete a saved table."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM saved_tables WHERE id = ?", (save_id,))
        self._conn.commit()
