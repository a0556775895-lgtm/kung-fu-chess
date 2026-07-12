"""Top-level orchestrator: owns the final game-over decision.

Until this step, `RealTimeArbiter` both DETECTED a royal-piece capture
and DECIDED the game was over, by calling `Board.end_game()` directly
from `_execute_arrival`. Per ARCHITECTURE_PLAN.md section 8 item 10,
that decision belongs here instead:

  - `RealTimeArbiter` now only *reports* a capture
    (`consume_royal_capture`); it no longer calls `end_game()` itself.
  - `GameEngine` is the only caller of `Board.end_game()`.

This is the layer callers (currently `main.py`; `app.py` later, in
step 12) talk to instead of `Board` directly. It mirrors `Board`'s
public surface (click/wait/print_board/jump) so `main.py` only needs an
import swap, not a rewrite -- see the diff in that file.

STEP 11 UPDATE: `print_board()` no longer delegates to `Board` (that
method was removed from `Board` -- see `model/board.py`'s docstring).
Printing is entirely `view/renderer.py`'s responsibility now; GameEngine
just hands it the grid via `Board.get_grid()`. GameEngine itself still
doesn't do any formatting or printing -- it's a pass-through to the view
layer, same as it's a pass-through to Board for everything else.
"""

from model.board import Board
from view.renderer import print_board as render_board


class GameEngine:
    def __init__(self, board_lines):
        self._board = Board(board_lines)

    def click(self, x, y):
        self._board.click(x, y)

    def wait(self, milliseconds):
        self._board.wait(milliseconds)

        # Must run AFTER board.wait(): that call is what drives
        # arbiter.tick(), which is what may set the flag we're reading
        # here. This is the one place the royal-capture decision is
        # actually made now (see module docstring).
        if self._board.consume_royal_capture():
            self._board.end_game()

    def jump(self, x, y):
        self._board.jump(x, y)

    def print_board(self):
        render_board(self._board.get_grid())

    @property
    def game_over(self):
        return self._board.game_over