from pathlib import Path

BOARD_ROWS = 8
BOARD_COLS = 8

WINDOW_SIZE = (640, 640)      # (width, height) בפיקסלים
FRAME_DELAY_MS = 30           # תזמון לולאה - waitKey
MAX_DT_MS = 100               # clamp - מונע קפיצת כלים אחרי השהיה של המחשב

ASSETS_ROOT = Path("view") / "assest" / "PIECES1"
BOARD_IMAGE_PATH = Path("view") / "assest" / "board.png"

PIECE_KINDS = ("P", "N", "B", "R", "Q", "K")
PIECE_COLORS = ("W", "B")
ANIMATION_STATES = ("idle", "move", "jump", "short_rest", "long_rest")

JUMP_DURATION_MS = 1000   # תואם ל-hardcode בפועל ב-RealTimeArbiter.start_jump