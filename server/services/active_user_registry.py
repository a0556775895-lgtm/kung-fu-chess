"""In-memory ownership of authenticated usernames currently connected."""
import unicodedata


class ActiveUserRegistry:
    """Prevent one persistent account from owning two live connections."""

    def __init__(self):
        """Start with no active usernames."""
        self._usernames = {}

    def claim(self, username: str) -> bool:
        """Reserve username case-insensitively, returning False when already active."""
        key = _identity_key(username)
        if key in self._usernames:
            return False
        self._usernames[key] = username
        return True

    def release(self, username: str) -> bool:
        """Release username regardless of casing, returning whether it was active."""
        return self._usernames.pop(_identity_key(username), None) is not None

    def is_active(self, username: str) -> bool:
        """Return whether an equivalent username is currently reserved."""
        return _identity_key(username) in self._usernames

    def active_usernames(self) -> tuple[str, ...]:
        """Return the preserved display spelling of every active username."""
        return tuple(self._usernames.values())

    def __len__(self) -> int:
        """Return the number of active username claims."""
        return len(self._usernames)


def _identity_key(username: str) -> str:
    if not isinstance(username, str) or not username:
        raise ValueError("INVALID_USERNAME")
    return unicodedata.normalize("NFKC", username).casefold()
