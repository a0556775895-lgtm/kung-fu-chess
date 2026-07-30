"""Client-only runtime configuration."""

from pathlib import Path


LOG_DIRECTORY = Path("logs") / "clients"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3
