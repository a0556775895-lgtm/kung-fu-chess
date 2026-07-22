# CLAUDE.md
answer me always in hebrew!!!

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Kung Fu Chess — a real-time chess variant (no turns; both sides move simultaneously). A piece sent to a destination moves at constant speed and arrives after a duration proportional to distance, rather than instantly. Displayed via an OpenCV window (`main.py`). Documentation and comments in the repo are largely in Hebrew.

Key rule differences from standard chess:
- **Real-time movement**: all pieces can move concurrently; duration is proportional to distance (1000ms/cell), except the Knight, which always takes a fixed 3000ms.
- **Jump**: right-click on a piece sends it into a jump — immune to normal capture for a fixed window (airborne), but vulnerable to an enemy piece arriving on the same cell during that window.
- **Rest (cooldown)**: after a move or jump, a piece enters a rest period (`LONG_REST` after a move, `SHORT_REST` after a jump) during which it cannot act.
- **Pawn promotion** to Queen on reaching the back rank.
- **Scoring**: capturing a piece scores points (Pawn=1, Knight/Bishop=3, Rook=5, Queen=9, King=0 but ends the game). Shown in the HUD.
- Standard movement rules per piece type (including blocking by intervening pieces) — no check/checkmate/castling/en passant.

## Commands

Install dependencies:
```
pip install opencv-python numpy
```

Run the game (opens a graphical window with the standard opening position):
```
python main.py
```

Run the full test suite (unit tests + `.kfc` script-driven integration tests), also requires `pytest`, `pytest-cov`:
```
python -m pytest tests/
```

Run with coverage report (term + HTML via `htmlcov/`):
```
./run_tests.ps1
```
equivalent to: `python -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html`

Run a single test:
```
python -m pytest tests/test_suite.py::test_piece_moving_state
python -m pytest tests/integration/test_text_scripts.py -k 05_capture
```

Coverage config (`.coveragerc`) omits `tests/`, `old/`, `main.py`, and most of `view/` (rendering/asset-loading code not exercised by unit tests) — only `view/renderer.py` (`GameSnapshot`/`PieceSnapshot`/`render_snapshot`) and the HUD/observer code are expected to carry coverage.

## Architecture

The project is layered; each layer only knows about the layer(s) below it:

```
model     — pure state: where each piece is, its color/kind/lifecycle state. No movement rules, timing, or drawing.
rules     — stateless: is a move legal, which cells does it cross, how long will it take. Never touches the board.
realtime  — RealTimeArbiter: owns every in-flight motion, advances a simulated clock, resolves arrivals/collisions/captures.
engine    — GameEngine: the single public entry point. Coordinates Board/RuleEngine/RealTimeArbiter, decides game_over.
view      — board, pieces, animation, mouse input, HUD — everything actually touching the screen.
```

Directory map:
```
model/      Position, Piece (PieceColor/PieceState enums), Board, GameState
rules/      piece_rules (legality/path/duration/promotion per piece kind), piece_factory, RuleEngine
realtime/   Motion, RealTimeArbiter — the real-time simulation clock and arrival/collision resolution
engine/     GameEngine — the only class other layers should call into for game commands
input/      BoardMapper (pixel <-> cell), Controller (click -> selection/move translation)
boardio/    BoardParser (text -> Board), board_printer (Board/snapshot -> text)
view/       OpenCV display layer: board/pieces/animation rendering, HUD, mouse input, DisplayManager
texttests/  Textual DSL (`.kfc` scripts) for running game scenarios headlessly
tests/      pytest unit tests (tests/test_suite.py) and integration tests (tests/integration/, driving .kfc scripts)
tools/      one-off scripts for generating graphical assets
```

### Typical move flow

Mouse click → `Controller.handle_click` (or `view/input/commands.py` `ClickCommand`/`JumpCommand` via `LocalCommandSender`) → `GameEngine.request_move`/`request_jump` → `RuleEngine.validate_move` checks legality → `RealTimeArbiter.start_motion`/`start_jump` schedules it against the simulated clock. Every frame, `GameEngine.wait(dt_ms)` advances that clock; arrivals are resolved (captures, collisions, promotions, friendly-destination stop-short) and reported to observers.

### Observer pattern

`GameEngine.subscribe(observer)` lets view components listen for game events (`on_arrival`, `on_motion_started`, `on_jump_started`, `on_game_over`) without the engine knowing anything about animation, drawing, or the HUD. `PieceAnimator` and `MovesLogData` are external observers. Capture scoring is authoritative engine state and the HUD reads it from `GameSnapshot.scores`.

### RealTimeArbiter timing/collision rules (`realtime/real_time_arbiter.py`)

- N cells crossed = N × 1000ms for all pieces except the Knight, which is always 3000ms regardless of distance.
- A jump lasts a fixed duration (piece stays on its cell, becomes briefly capture-immune).
- If two enemy motions arrive at each other's source in the same tick, the one scheduled first wins; the other's arrival is silently dropped (it was already captured).
- If a moving piece arrives at a cell occupied by an airborne enemy, the arriving piece is captured instead; the airborne piece is unaffected.
- If a piece arrives at a cell occupied by a friendly piece, it stops one cell short along its path instead of capturing; if that cell is also occupied, the move is dropped entirely.
- Promotion is applied at arrival, not at move request time.

### Two front-ends over the same core

`main.py` runs the graphical OpenCV interface through `DisplayManager`. `texttests/` runs the exact same `Controller`/`GameEngine` core headlessly via a text DSL (`click x y` / `jump x y` / `wait ms` / `print board`), parsed from `Board:`/`Commands:` script files (`.kfc`, see `tests/integration/scripts/`). This is the mechanism used to write integration tests without a display — the core (`model`/`rules`/`realtime`/`engine`) has no dependency on how it's rendered.

### View layer conventions

- `view/config.py` holds every global constant (board size, window size, frame delay, asset paths, piece kinds/colors, animation state names) — other view modules import from there rather than redefining values.
- `view/geometry.py`'s `BoardGeometry` is the single source of truth for cell/board pixel sizing, injected into whichever components need it (`board/`, `pieces/`, `selection/`, `input/`).
- `view/renderer.py` defines `GameSnapshot`/`PieceSnapshot`, the read-only rendering-facing view of game state built by `GameEngine.snapshot()`; text and graphical rendering both consume this snapshot rather than live `Board`/`Piece` objects.
- `DisplayManager` is the only class allowed to call `cv2` directly, and only for `imshow`/`waitKey`/`setMouseCallback`/window-resize detection — never for drawing (all drawing goes through `Img`, see `view/img.py`).
- Sprite assets live under `view/asset/pieces/<Kind><Color>/states/<state>/{config.json,sprites/*.png}` (folder naming is `Kind+Color`, the reverse of the `Piece` model's `Color+Kind`). See [view_architecture_spec.md](view_architecture_spec.md) for the detailed (though not perfectly current — cross-check against actual `view/` contents, e.g. `view/selection/`) design spec of the Loader/Renderer split, animation state machine, and HUD components.
