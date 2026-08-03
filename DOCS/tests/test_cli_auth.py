"""Tests for command-line account credential collection."""

from client.cli_auth import (
    ACTION_HELP,
    PASSWORD_MISMATCH,
    USERNAME_HELP,
    AuthAction,
    AuthCredentials,
    prompt_credentials,
)


def test_prompt_credentials_collects_login_with_hidden_password_function():
    answers = iter(["login", "Alice"])
    password_prompts = []

    credentials = prompt_credentials(
        input_func=lambda _prompt: next(answers),
        password_func=lambda prompt: password_prompts.append(prompt) or "secret value",
    )

    assert credentials == AuthCredentials(AuthAction.LOGIN, "Alice", "secret value")
    assert password_prompts == ["Password: "]
    assert "secret value" not in repr(credentials)


def test_prompt_credentials_collects_registration_after_confirmation():
    answers = iter(["2", "דנה-3"])
    passwords = iter(["first password", "different", "final password", "final password"])
    messages = []

    credentials = prompt_credentials(
        input_func=lambda _prompt: next(answers),
        password_func=lambda _prompt: next(passwords),
        output_func=messages.append,
    )

    assert credentials == AuthCredentials(
        AuthAction.REGISTER,
        "דנה-3",
        "final password",
    )
    assert messages == [PASSWORD_MISMATCH]


def test_prompt_credentials_retries_invalid_action_and_username():
    answers = iter(["unknown", "1", "A", "player_2"])
    messages = []

    credentials = prompt_credentials(
        input_func=lambda _prompt: next(answers),
        password_func=lambda _prompt: "password",
        output_func=messages.append,
    )

    assert credentials.username == "player_2"
    assert credentials.action is AuthAction.LOGIN
    assert messages == [ACTION_HELP, USERNAME_HELP]
