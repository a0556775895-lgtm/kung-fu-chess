"""Small command-line prompt for the multiplayer display name."""

from networking.login_protocol import LoginProtocolError, validate_username


USERNAME_HELP = (
    "Username must contain 2-20 letters, numbers, underscores, or hyphens."
)


def prompt_username(input_func=None, output_func=print) -> str:
    """Prompt until the user enters a username accepted by the wire protocol."""
    if input_func is None:
        input_func = input

    while True:
        username = input_func("Username: ").strip()
        try:
            validate_username(username)
        except LoginProtocolError:
            output_func(USERNAME_HELP)
            continue
        return username
