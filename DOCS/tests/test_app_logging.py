"""Tests for rotating, redacted application and match logs."""

import logging
from pathlib import Path
import uuid

import pytest

from networking.logging_utils import (
    close_managed_handlers,
    configure_rotating_logger,
    safe_filename_component,
)
from server.logging.match_activity_logger import MatchActivityLogger


@pytest.fixture
def log_directory():
    """Use an isolated ignored directory without relying on Windows TEMP."""
    directory = Path.cwd() / f"kfc_log_test_{uuid.uuid4().hex}"
    directory.mkdir()
    try:
        yield directory
    finally:
        for file in directory.iterdir():
            file.unlink()
        directory.rmdir()


def test_rotating_logger_redacts_credentials_and_rotates(log_directory):
    path = log_directory / "application.log"
    logger = configure_rotating_logger(
        "test.redaction",
        path,
        max_bytes=180,
        backup_count=2,
        include_console=False,
    )

    for index in range(12):
        logger.info("safe event number=%s payload=%s", index, "x" * 40)
    logger.info(
        "password=secret session_token=token-value "
        "LOGIN req-1 Alice hidden-password"
    )
    close_managed_handlers(logger)

    combined = "".join(
        file.read_text(encoding="utf-8")
        for file in log_directory.glob("application.log*")
    )
    assert "secret" not in combined
    assert "token-value" not in combined
    assert "hidden-password" not in combined
    assert "<redacted>" in combined
    assert (log_directory / "application.log.1").exists()


def test_reconfiguring_namespace_replaces_only_managed_handlers(log_directory):
    logger = logging.getLogger("test.reconfigure")
    unmanaged = logging.NullHandler()
    logger.addHandler(unmanaged)

    configure_rotating_logger(
        logger.name,
        log_directory / "first.log",
        max_bytes=1000,
        backup_count=1,
        include_console=True,
    )
    configure_rotating_logger(
        logger.name,
        log_directory / "second.log",
        max_bytes=1000,
        backup_count=1,
        include_console=False,
    )

    assert unmanaged in logger.handlers
    assert len(logger.handlers) == 2
    close_managed_handlers(logger)
    logger.removeHandler(unmanaged)


@pytest.mark.parametrize(
    "arguments,reason",
    [
        (("", 100, 1), "INVALID_LOGGER_NAMESPACE"),
        (("test.invalid", 0, 1), "INVALID_LOG_MAX_BYTES"),
        (("test.invalid", True, 1), "INVALID_LOG_MAX_BYTES"),
        (("test.invalid", 100, -1), "INVALID_LOG_BACKUP_COUNT"),
        (("test.invalid", 100, True), "INVALID_LOG_BACKUP_COUNT"),
    ],
)
def test_rotating_logger_validates_configuration(
    log_directory,
    arguments,
    reason,
):
    namespace, max_bytes, backup_count = arguments
    with pytest.raises(ValueError, match=reason):
        configure_rotating_logger(
            namespace,
            log_directory / "invalid.log",
            max_bytes=max_bytes,
            backup_count=backup_count,
            include_console=False,
        )


def test_safe_filename_component_preserves_names_without_allowing_paths():
    assert safe_filename_component("שרה כהן") == "שרה_כהן"
    assert safe_filename_component("../Alice/Bob") == "_Alice_Bob"
    assert len(safe_filename_component("a" * 100)) == 64
    with pytest.raises(ValueError, match="INVALID_FILENAME_COMPONENT"):
        safe_filename_component("")
    with pytest.raises(ValueError, match="INVALID_FILENAME_COMPONENT"):
        safe_filename_component("...")


def test_match_activity_logger_writes_context_and_closes_once(log_directory):
    path = log_directory / "game-1.log"
    logger = configure_rotating_logger(
        "test.game.game-1",
        path,
        max_bytes=1000,
        backup_count=1,
        include_console=False,
    )
    activity = MatchActivityLogger("game-1", logger)

    activity.record(
        "command_accepted",
        server_time_ms=125,
        request_id="move-1",
        user_id=7,
        command="MoveCommand",
        ignored=None,
    )
    activity.close()
    activity.close()
    activity.record("after_close", server_time_ms=126)

    content = path.read_text(encoding="utf-8")
    assert "game_id=game-1" in content
    assert "event=command_accepted" in content
    assert "request_id=move-1" in content
    assert "user_id=7" in content
    assert "after_close" not in content
    assert activity.is_closed


def test_match_activity_logger_validates_dependencies():
    with pytest.raises(ValueError, match="INVALID_GAME_ID"):
        MatchActivityLogger("", logging.getLogger("test.game.invalid"))
    with pytest.raises(TypeError, match="LOGGER_REQUIRED"):
        MatchActivityLogger("game-1", object())
