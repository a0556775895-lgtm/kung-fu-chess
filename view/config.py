from pathlib import Path

from rules.piece_rules import get_airborne_duration

BOARD_ROWS = 8
BOARD_COLS = 8

# Local presentation timing and pixel size; these never affect server game rules.
WINDOW_SIZE = (480, 480)
FRAME_DELAY_MS = 30
MAX_DT_MS = 100

ASSETS_ROOT = Path("view") / "asset" / "pieces"
BOARD_IMAGE_PATH = Path("view") / "asset" / "board.png"
BACKGROUND_IMAGE_PATH = Path("view") / "asset" / "background.png"
SIDE_PANEL_IMAGE_PATH = Path("view") / "asset" / "side_panel.png"
GAME_OVER_WHITE_WIN_IMAGE_PATH = (
    Path("view") / "asset" / "game_over_white_win.png"
)
GAME_OVER_BLACK_WIN_IMAGE_PATH = (
    Path("view") / "asset" / "game_over_black_win.png.png"
)

PIECE_KINDS = ("P", "N", "B", "R", "Q", "K")
PIECE_COLORS = ("W", "B")
ANIMATION_STATES = ("idle", "move", "jump", "short_rest", "long_rest")

JUMP_DURATION_MS = get_airborne_duration()   # single source of truth: rules.piece_rules

HIGHLIGHT_IMAGE_PATH = Path("view") / "asset" / "highlight.png"
SOUNDS_ROOT = Path("view") / "asset" / "sounds"

# HUD: side panels flanking the board, each showing side_panel.png (name
# plaque on top, log parchment in the middle). Width is derived from that
# image's own aspect ratio (376:816) at the board's height, so it's drawn
# at native proportions instead of being stretched.
SCORE_PANEL_WIDTH = 221
SCORE_TEXT_COLOR = (255, 255, 255, 255)  # BGRA white
SCORE_FONT_SIZE = 0.8
# x offset (from the left panel's own left edge) for name/score text --
# lands inside side_panel.png's plaque, which sits on the board-facing
# half of the top section (the other half is the circular badge shape).
SCORE_LEFT_TEXT_X = 124

# HUD: moves log table, positioned inside side_panel.png's middle
# parchment area (y ~109-368 at this panel height) so rows stay on the
# artwork instead of spilling onto the plaques above/below it.
MOVES_LOG_FONT_SIZE = 0.4
MOVES_LOG_HEADER_Y = 145
MOVES_LOG_BOTTOM_Y = 335
MOVES_LOG_ROW_HEIGHT = 18
MOVES_LOG_TIME_COL_X = 0     # offset from the panel's margin
MOVES_LOG_MOVE_COL_X = 70    # offset from the panel's margin
