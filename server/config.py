"""Central configuration defaults for the multiplayer server."""

from pathlib import Path


HOST = "127.0.0.1"
PORT = 8765
DATABASE_PATH = Path("data") / "kung_fu_chess.db"
DEFAULT_GAME_ID = "default"
TICK_INTERVAL_MS = 50
MAX_TICK_STEP_MS = 50
