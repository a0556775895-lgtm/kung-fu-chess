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
from model.game_state import GameState
from model.piece import PieceState
from realtime.real_time_arbiter import RealTimeArbiter
from rules.rule_engine import RuleEngine
from view.renderer import render_snapshot, GameSnapshot, PieceSnapshot


class GameEngine:
    def __init__(self, board: Board):
        self._board = board
        self._game_state = GameState()
        self._arbiter = RealTimeArbiter(board)
        self._rule_engine = RuleEngine()

    def request_jump(self, source):
        if self._game_state.game_over:
            return
        piece = self._board.get_piece_at(source)
        if piece is None or piece.is_moving() or piece.state == PieceState.CAPTURED:
            return
        self._arbiter.start_jump(piece)

    def request_move(self, source, destination):
        if self._game_state.game_over:
            return _MoveResult(False, "game_over")

        piece = self._board.get_piece_at(source)
        if piece is not None and self._arbiter.has_active_motion(piece):
            return _MoveResult(False, "motion_in_progress")

        validation = self._rule_engine.validate_move(self._board, source, destination)
        if not validation.is_valid:
            return _MoveResult(False, validation.reason)

        self._arbiter.start_motion(piece, source, destination)
        return _MoveResult(True, "ok")

    def wait(self, milliseconds):
        arrival_events = self._arbiter.advance_time(milliseconds)
        if arrival_events.king_captured:
            self._game_state.end_game()

    def snapshot(self, selected_cell=None):
        pieces = [
            PieceSnapshot(
                kind=p.kind,
                color=str(p.color),
                cell=p.cell,
                state=p.state.name,
            )
            for row in self._board.get_grid()
            for p in row
            if p is not None and p.state != PieceState.CAPTURED
        ]
        return GameSnapshot(
            board_width=self._board.cols,
            board_height=self._board.rows,
            pieces=pieces,
            selected_cell=selected_cell,
            game_over=self._game_state.game_over,
        )

    @property
    def game_over(self):
        return self._game_state.game_over


class _MoveResult:
    def __init__(self, is_accepted, reason):
        self.is_accepted = is_accepted
        self.reason = reason
