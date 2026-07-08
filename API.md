# API Reference — Class Variables and Accessors

This file lists the primary classes, the instance variables they hold, and the methods or properties that read or mutate those variables. Use it as a quick reference when changing stateful behaviour.

- **Board** ([board.py](board.py))
  - Variables: `_grid`, `_rows`, `_cols`, `_current_time`, `_game_over`, `_pending_move`, `_geometry`, `_selection_controller`
  - Legacy test-facing properties (wrappers): `_pending_source`, `_pending_destination`, `_pending_arrival_time`, `_pending_finish_time`, `_selected_position`
  - Key methods: `click(x, y)`, `wait(milliseconds)`, `print_board()`, `jump(x, y)`, `get_rows()`, `_parse_board()`, `_execute_arrival()`, `_finish_pending_move()`, `_is_path_clear()`

- **Piece** ([piece.py](piece.py))
  - Variables: `_color`, `_symbol`, `_move_time`, `_jump_duration`, `_board`, `_state`, `_jump_finish_time`
  - Accessors / properties: `color`, `move_time`, `symbol`, `get_board()`, `set_board(board)`, `state` (getter/setter)
  - Key methods: `is_valid_move(...)` (abstract), `get_path_cells(...)`, `start_jump(current_time)`, `finish_jump()`, `is_airborne()`, `should_finish_jump(current_time)`, `is_royal()`

- **PieceFactory** ([PieceFactory.py](PieceFactory.py))
  - No persistent instance state (factory)
  - Key method: `create_piece(token)` — returns a `Piece` instance from a token like `wP` or `bQ`.

- **PendingMove** ([pending_move.py](pending_move.py))
  - Variables: `_source`, `_destination`, `_arrival_time`, `_finish_time`, `_executed`
  - Key methods: `set_move(source, destination, arrival_time, finish_time)`, `clear()`, `mark_executed()`
  - Properties: `source`, `destination`, `arrival_time`, `finish_time`, `executed`
  - Helper queries: `is_arrival_pending(current_time)`, `is_finish_pending(current_time)`

- **BoardGeometry** ([board_geometry.py](board_geometry.py))
  - Variables: `rows`, `cols`, `cell_size`
  - Key methods: `update_dimensions(rows, cols)`, `pixel_to_cell(x, y)`, `is_inside_board(row, col)`

- **SelectionController** ([selection_controller.py](selection_controller.py))
  - Variables: `_selected_position` (internal)
  - Accessors: `selected_position` (property getter/setter)
  - Key methods: `handle_click(row, col)`, `_try_select_piece(row, col)`, `_handle_selected_click(row, col)` — `_handle_selected_click` sets up the `PendingMove` using the board reference.

---

If you prefer this content merged into `README.md` instead, tell me and I will append it there.
