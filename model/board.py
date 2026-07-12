from model.position import Position
from model.game_state import GameState
from boardio.board_parser import parse_board
from input.board_mapper import BoardMapper
from input.controller import Controller
from realtime.real_time_arbiter import RealTimeArbiter


class Board:
    """Board storage + execution.

    Step 9 update: the single `PendingMove` + the `_execute_arrival` /
    `_finish_pending_move` logic are gone. Both are replaced by
    `RealTimeArbiter` (`realtime/real_time_arbiter.py`), which owns a
    whole collection of concurrent `Motion`s -- one per piece with an
    active move -- instead of Board holding one pending move for the
    entire board. This is what removes the old global "one move at a
    time" lock from `click()`, enabling multiple pieces to move at once
    (ARCHITECTURE_PLAN.md, section 6).

    Board itself is now closer to a pure grid: it stores pieces and
    exposes `place_piece`/`remove_piece`/`end_game` so the arbiter can
    mutate it without reaching into `_grid` directly. Promotion and the
    airborne-capture rule moved into the arbiter along with arrival
    execution -- still open questions per ARCHITECTURE_PLAN.md section 7,
    item 1-2, just relocated rather than resolved.

    Step 10 update: `end_game()` is unchanged, but Board is no longer the
    thing that decides WHEN to call it for a royal capture -- that
    decision moved to `engine/game_engine.py`. Board just forwards the
    arbiter's report via `consume_royal_capture()` and exposes `game_over`
    as a read-only property so GameEngine can check it without reaching
    into `_game_state` directly.

    Step 11 update: `print_board()` is gone. Printing is now entirely
    `view/renderer.py`'s job -- Board only exposes the grid as data via
    `get_grid()`. This removes the last piece of I/O responsibility from
    Board, leaving it as storage + execution only, per the "Model לא
    בודק חוקיות" / grid-ownership principles in ARCHITECTURE_PLAN.md
    section 9.

    BREAKING CHANGE (flagged, not silently dropped): the legacy
    `_pending_source` / `_pending_destination` / `_pending_arrival_time` /
    `_pending_finish_time` test-facing properties (see API.md) are
    removed in this step. They assumed a single pending move existed,
    which is no longer true once multiple motions can be active at once
    -- there is no longer one canonical "the" pending move to point them
    at. Tests relying on them will need to move to inspecting the
    relevant `Motion` via the arbiter instead.
    """

    CELL_SIZE = 100

    def __init__(self, board_lines):
        """Create a Board from text lines.

        `board_lines` is a list of strings where each token is space-separated.
        """
        self._game_state = GameState()

        self._board_mapper = BoardMapper(0, 0, self.CELL_SIZE)
        self._controller = Controller(self)
        self._arbiter = RealTimeArbiter(self)

        self._grid, self._rows, self._cols = parse_board(board_lines)
        self._board_mapper.update_dimensions(self._rows, self._cols)

    @property
    def _selected_position(self):
        return self._controller.selected_position

    @_selected_position.setter
    def _selected_position(self, value):
        self._controller.selected_position = value

    def click(self, x, y):
        if self._game_state.game_over:
            return

        position = self._pixel_to_position(x, y)

        if not self.is_inside_board(position):
            return

        self._controller.handle_click(position)

    def wait(self, milliseconds):
        self._game_state.advance_time(milliseconds)
        current_time = self._game_state.current_time

        self._arbiter.tick(current_time)

        for row in self._grid:
            for piece in row:
                if piece is not None and piece.should_finish_jump(current_time):
                    piece.finish_jump()

    def get_grid(self):
        """Return the grid (list of rows of Piece/None).

        Public, read-only: this is Board's only remaining connection to
        textual output. `view/renderer.py` is the sole caller -- it turns
        this into printed lines; Board itself no longer prints anything
        (step 11).
        """
        return self._grid

    def _pixel_to_position(self, x, y):
        return self._board_mapper.pixel_to_position(x, y)

    def is_inside_board(self, position: Position) -> bool:
        """Public: required by rule_engine.BoardView."""
        return self._board_mapper.is_inside_board(position)

    def _is_path_clear(self, piece, source: Position, destination: Position) -> bool:
        from rules import piece_rules

        path = piece_rules.get_path_cells(piece.kind, piece.color, source, destination)

        for cell in path:
            if self._grid[cell.row][cell.col] is not None:
                return False

        return True

    def get_rows(self):
        return self._rows

    def get_piece_at(self, position: Position):
        """Return the piece at `position`, or None if empty.

        Public: required by rule_engine.BoardView.
        """
        return self._grid[position.row][position.col]

    def is_path_clear(self, piece, source: Position, destination: Position) -> bool:
        """Return True if no piece blocks the path for this move.

        Public: required by rule_engine.BoardView.
        """
        return self._is_path_clear(piece, source, destination)

    def place_piece(self, position: Position, piece):
        """Put `piece` at `position` in the grid.

        Public: used by `realtime/real_time_arbiter.py` to execute a
        motion's arrival. The arbiter mutates the grid ONLY through this
        and `remove_piece` -- it never reaches into `Board._grid`
        directly, keeping Board the single owner of grid storage.
        """
        self._grid[position.row][position.col] = piece

    def remove_piece(self, position: Position):
        """Clear the cell at `position`. Public: see `place_piece`."""
        self._grid[position.row][position.col] = None

    def end_game(self):
        """Mark the game over.

        Public: used by `engine/game_engine.py` when it decides to act on
        a royal-piece capture reported via `consume_royal_capture()`.
        (Step 10: previously called directly by
        `realtime/real_time_arbiter.py` -- see that module's docstring.)
        """
        self._game_state.end_game()

    def consume_royal_capture(self) -> bool:
        """Report (and clear) whether a royal piece was captured since
        the last call.

        Step 10: delegates to the arbiter, which detects this during
        arrival execution but no longer decides what to do about it --
        that decision now belongs to `engine/game_engine.py`.
        """
        return self._arbiter.consume_royal_capture()

    @property
    def game_over(self):
        """Read-only: whether the game has ended.

        Step 10: exposed so `engine/game_engine.py` can check state
        without reaching into `_game_state` directly.
        """
        return self._game_state.game_over

    @property
    def current_time(self):
        return self._game_state.current_time

    def schedule_move(self, source, destination, arrival_time, finish_time):
        """Register a move for the piece at `source`.

        Delegates to `RealTimeArbiter` instead of holding a single
        `PendingMove` -- multiple pieces can each have an active `Motion`
        at once (ARCHITECTURE_PLAN.md, section 6). The arbiter is also
        what marks the piece MOVING (see `RealTimeArbiter.schedule`).
        """
        piece = self.get_piece_at(source)
        self._arbiter.schedule(
            piece, source, destination, self.current_time, arrival_time, finish_time
        )

    def jump(self, x, y):
        if self._game_state.game_over:
            return

        position = self._pixel_to_position(x, y)

        if not self.is_inside_board(position):
            return

        piece = self._grid[position.row][position.col]

        if piece is None:
            return

        # Was: `self._pending_source == position` (a single global slot).
        # Now checked per-piece via the arbiter, since many pieces can
        # each have their own active Motion at once.
        if self._arbiter.has_active_motion(piece):
            return

        if piece.is_airborne():
            return

        piece.start_jump(self._game_state.current_time)