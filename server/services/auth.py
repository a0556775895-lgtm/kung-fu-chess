"""Registration and password verification without SQL or transport concerns."""

from dataclasses import dataclass
import hashlib
import hmac
import secrets

from networking.login_protocol import LoginProtocolError, validate_username
from server.dal.repository import DuplicateUsernameError


PBKDF2_ITERATIONS = 600_000
SALT_SIZE_BYTES = 16
MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_BYTES = 1024


class AuthError(ValueError):
    """A stable authentication failure suitable for later protocol mapping."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class PasswordPolicy:
    """Length limits that preserve Unicode and whitespace without composition rules."""

    minimum_characters: int = MIN_PASSWORD_LENGTH
    maximum_bytes: int = MAX_PASSWORD_BYTES


class AuthService:
    """Register and authenticate persistent users through a unit-of-work factory."""

    def __init__(
        self,
        unit_of_work_factory,
        *,
        iterations: int = PBKDF2_ITERATIONS,
        salt_factory=secrets.token_bytes,
        password_policy: PasswordPolicy = PasswordPolicy(),
    ):
        if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
            raise ValueError("INVALID_PBKDF2_ITERATIONS")
        if not callable(unit_of_work_factory):
            raise TypeError("UNIT_OF_WORK_FACTORY_NOT_CALLABLE")
        if not callable(salt_factory):
            raise TypeError("SALT_FACTORY_NOT_CALLABLE")
        if password_policy.minimum_characters <= 0:
            raise ValueError("INVALID_MINIMUM_PASSWORD_LENGTH")
        if password_policy.maximum_bytes <= 0:
            raise ValueError("INVALID_MAXIMUM_PASSWORD_BYTES")

        self._unit_of_work_factory = unit_of_work_factory
        self._iterations = iterations
        self._salt_factory = salt_factory
        self._password_policy = password_policy
        self._dummy_salt = self._new_salt()

    def register(self, username: str, password: str):
        """Validate, hash and atomically persist one new account."""
        self._validate_registration_username(username)
        password_bytes = self._validate_new_password(password)
        salt = self._new_salt()
        password_hash = self._derive_hash(password_bytes, salt)

        try:
            with self._unit_of_work_factory() as unit_of_work:
                return unit_of_work.users.create_user(
                    username=username,
                    password_hash=password_hash,
                    salt=salt,
                )
        except DuplicateUsernameError as exc:
            raise AuthError("username_taken") from exc

    def login(self, username: str, password: str):
        """Return the matching account or one generic invalid-credentials error."""
        try:
            validate_username(username)
            password_bytes = self._password_bytes(password)
        except (LoginProtocolError, AuthError):
            raise AuthError("invalid_credentials") from None

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.users.get_by_username(username)

        salt = user.salt if user is not None else self._dummy_salt
        candidate_hash = self._derive_hash(password_bytes, salt)
        if user is None or not hmac.compare_digest(candidate_hash, user.password_hash):
            raise AuthError("invalid_credentials")
        return user

    def _validate_registration_username(self, username: str) -> None:
        try:
            validate_username(username)
        except LoginProtocolError as exc:
            raise AuthError("invalid_username") from exc

    def _validate_new_password(self, password: str) -> bytes:
        password_bytes = self._password_bytes(password)
        if len(password) < self._password_policy.minimum_characters:
            raise AuthError("invalid_password")
        return password_bytes

    def _password_bytes(self, password: str) -> bytes:
        if not isinstance(password, str):
            raise AuthError("invalid_password")
        encoded = password.encode("utf-8")
        if not encoded or len(encoded) > self._password_policy.maximum_bytes:
            raise AuthError("invalid_password")
        return encoded

    def _new_salt(self) -> bytes:
        salt = self._salt_factory(SALT_SIZE_BYTES)
        if not isinstance(salt, bytes) or len(salt) != SALT_SIZE_BYTES:
            raise ValueError("INVALID_GENERATED_SALT")
        return salt

    def _derive_hash(self, password_bytes: bytes, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password_bytes,
            salt,
            self._iterations,
        )
