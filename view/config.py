from pathlib import Path

from rules.piece_rules import get_airborne_duration

BOARD_ROWS = 8
BOARD_COLS = 8

WINDOW_SIZE = (640, 640)      # (width, height) in pixels
FRAME_DELAY_MS = 30           # loop timing - waitKey
MAX_DT_MS = 100               # clamp - prevents pieces from jumping after the machine stalls

ASSETS_ROOT = Path("view") / "assest" / "PIECES1"
BOARD_IMAGE_PATH = Path("view") / "assest" / "board.png"

PIECE_KINDS = ("P", "N", "B", "R", "Q", "K")
PIECE_COLORS = ("W", "B")
ANIMATION_STATES = ("idle", "move", "jump", "short_rest", "long_rest")

JUMP_DURATION_MS = get_airborne_duration()   # single source of truth: rules.piece_rules

HIGHLIGHT_IMAGE_PATH = Path("view") / "assest" / "highlight.png"

# HUD: side panels flanking the board (score, etc.). board_origin_x uses
# this to leave room on the left, matching an equal-width panel on the right.
SCORE_PANEL_WIDTH = 160
PANEL_BG_COLOR = (40, 40, 40)          # BGR
SCORE_TEXT_COLOR = (255, 255, 255, 255)  # BGRA white
SCORE_FONT_SIZE = 0.8
