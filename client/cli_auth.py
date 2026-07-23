"""Command-line collection of account credentials before opening the GUI."""
"""יוצר את השיחה עם המשתמש בטרמינל"""
from dataclasses import dataclass, field
from enum import Enum
import getpass

from networking.auth_protocol import AuthProtocolError, validate_username


USERNAME_HELP = (
    "Username must contain 2-20 letters, numbers, underscores, or hyphens."
)
ACTION_HELP = "Choose Login or Register."
PASSWORD_MISMATCH = "Passwords do not match. Try again."


class AuthAction(str, Enum):
    """The account operation requested by the user."""

    LOGIN = "LOGIN"
    REGISTER = "REGISTER"


@dataclass(frozen=True, slots=True)
class AuthCredentials:
    """Credentials collected locally and passed to the network client."""

    action: AuthAction
    username: str
    password: str = field(repr=False)


#main func
def prompt_credentials(
    input_func=None,
    password_func=None,
    output_func=print,
) -> AuthCredentials:
    """Prompt until an operation, username and matching password are supplied."""
    if input_func is None:#אפשר להזריק פונקציות בשביל בדיקה ללא קלט אמיתי. לצורך בדיקות
        input_func = input
    if password_func is None:
        password_func = getpass.getpass

    action = _prompt_action(input_func, output_func)
    username = _prompt_username(input_func, output_func)
    password = _prompt_password(action, password_func, output_func)
    return AuthCredentials(action, username, password)


def _prompt_action(input_func, output_func) -> AuthAction:
    aliases = {
        "1": AuthAction.LOGIN,
        "login": AuthAction.LOGIN,
        "l": AuthAction.LOGIN,
        "2": AuthAction.REGISTER,
        "register": AuthAction.REGISTER,
        "r": AuthAction.REGISTER,
    }
    while True:
        answer = input_func("Choose [1] Login or [2] Register: ").strip().casefold()
        action = aliases.get(answer)
        if action is not None:
            return action
        output_func(ACTION_HELP)


def _prompt_username(input_func, output_func) -> str:
    while True:
        username = input_func("Username: ").strip()
        try:
            validate_username(username)
        except AuthProtocolError:
            output_func(USERNAME_HELP)
            continue
        return username


def _prompt_password(action, password_func, output_func) -> str:
    while True:
        password = password_func("Password: ")
        if action is AuthAction.LOGIN:
            return password
        confirmation = password_func("Confirm password: ")
        if password == confirmation:
            return password
        output_func(PASSWORD_MISMATCH)
