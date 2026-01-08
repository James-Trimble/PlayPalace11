"""Authentication and session management."""

import hashlib
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..persistence.database import Database, UserRecord


class AuthManager:
    """
    Handles user authentication and session management.

    Uses SHA-256 for password hashing (simple but sufficient for this use case).
    """

    def __init__(self, database: "Database"):
        self._db = database
        self._sessions: dict[str, str] = {}  # session_token -> username

    def hash_password(self, password: str) -> str:
        """Hash a password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        return self.hash_password(password) == password_hash

    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate a user.

        Returns True if credentials are valid.
        """
        user = self._db.get_user(username)
        if not user:
            return False
        return self.verify_password(password, user.password_hash)

    def register(self, username: str, password: str, locale: str = "en") -> bool:
        """
        Register a new user.

        Returns True if registration successful, False if username taken.
        """
        if self._db.user_exists(username):
            return False

        password_hash = self.hash_password(password)
        self._db.create_user(username, password_hash, locale)
        return True

    def get_user(self, username: str) -> "UserRecord | None":
        """Get a user record."""
        return self._db.get_user(username)

    def create_session(self, username: str) -> str:
        """Create a session token for a user."""
        token = secrets.token_hex(32)
        self._sessions[token] = username
        return token

    def validate_session(self, token: str) -> str | None:
        """Validate a session token and return the username."""
        return self._sessions.get(token)

    def invalidate_session(self, token: str) -> None:
        """Invalidate a session token."""
        self._sessions.pop(token, None)

    def invalidate_user_sessions(self, username: str) -> None:
        """Invalidate all sessions for a user."""
        to_remove = [t for t, u in self._sessions.items() if u == username]
        for token in to_remove:
            del self._sessions[token]
