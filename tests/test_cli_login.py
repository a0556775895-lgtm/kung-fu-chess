"""Tests for the command-line username prompt."""

from client.cli_login import USERNAME_HELP, prompt_username


def test_prompt_username_returns_first_valid_name():
    prompts = []

    username = prompt_username(
        input_func=lambda prompt: prompts.append(prompt) or "Alice",
    )

    assert username == "Alice"
    assert prompts == ["Username: "]


def test_prompt_username_retries_after_invalid_name():
    answers = iter(["A", "Alice Smith", "  player_2  "])
    messages = []

    username = prompt_username(
        input_func=lambda _prompt: next(answers),
        output_func=messages.append,
    )

    assert username == "player_2"
    assert messages == [USERNAME_HELP, USERNAME_HELP]
