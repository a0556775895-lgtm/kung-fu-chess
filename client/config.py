"""Client-only runtime configuration."""

from pathlib import Path


CLIENT_ROOT = Path(__file__).resolve().parent
LOG_DIRECTORY = CLIENT_ROOT / "logs"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3
