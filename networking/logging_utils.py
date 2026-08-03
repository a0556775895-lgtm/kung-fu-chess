"""Shared, rotating, redacted file-logging infrastructure."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import unicodedata


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_MANAGED_HANDLER = "_kung_fu_chess_managed_handler"
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password|session[_-]?token|token)\b"
    r"(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,]+)"
)
_AUTH_COMMAND = re.compile(
    r"(?i)\b(REGISTER|LOGIN)(\s+\S+\s+\S+\s+)(\S+)"
)


class RedactingFormatter(logging.Formatter):
    """Format one record and remove credentials from the final text."""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        text = _SENSITIVE_ASSIGNMENT.sub(
            lambda match: (
                f"{match.group(1)}{match.group(2)}<redacted>"
            ),
            text,
        )
        return _AUTH_COMMAND.sub(
            lambda match: (
                f"{match.group(1)}{match.group(2)}<redacted>"
            ),
            text,
        )


def configure_rotating_logger(
    namespace: str,
    log_path: str | Path,
    *,
    max_bytes: int,
    backup_count: int,
    include_console: bool,
) -> logging.Logger:
    """Configure one logger namespace without disturbing unrelated loggers."""
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("INVALID_LOGGER_NAMESPACE")
    if (
        isinstance(max_bytes, bool)
        or not isinstance(max_bytes, int)
        or max_bytes <= 0
    ):
        raise ValueError("INVALID_LOG_MAX_BYTES")
    if (
        isinstance(backup_count, bool)
        or not isinstance(backup_count, int)
        or backup_count < 0
    ):
        raise ValueError("INVALID_LOG_BACKUP_COUNT")

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(namespace)
    close_managed_handlers(logger)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = RedactingFormatter(LOG_FORMAT)
    file_handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    setattr(file_handler, _MANAGED_HANDLER, True)
    logger.addHandler(file_handler)

    if include_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        setattr(console_handler, _MANAGED_HANDLER, True)
        logger.addHandler(console_handler)
    return logger


def close_managed_handlers(logger: logging.Logger) -> None:
    """Close only handlers installed by this project."""
    for handler in tuple(logger.handlers):
        if getattr(handler, _MANAGED_HANDLER, False):
            logger.removeHandler(handler)
            handler.close()


def safe_filename_component(value: str) -> str:
    """Return a readable Windows-safe component for a user-controlled value."""
    if not isinstance(value, str) or not value:
        raise ValueError("INVALID_FILENAME_COMPONENT")
    normalized = unicodedata.normalize("NFKC", value)
    safe = "".join(
        character
        if character.isalnum() or character in {"-", "_", "."}
        else "_"
        for character in normalized
    ).strip(" .")
    if not safe:
        raise ValueError("INVALID_FILENAME_COMPONENT")
    return safe[:64]
