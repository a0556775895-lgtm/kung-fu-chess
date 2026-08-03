# CLAUDE.md

answer me always in hebrew!!!

This file provides guidance to Claude Code when working with this repository.

## Project

Kung Fu Chess is a real-time chess variant. There are no turns: both players can move simultaneously, movement takes time, pieces can jump, and every action is followed by a cooldown. The application uses an authoritative WebSocket server and graphical OpenCV clients; there is no local-game mode.

The repository documentation and many comments are in Hebrew.

## Commands

Install all dependencies from the repository root:

```powershell
pip install -r requirements.txt
```

Start the server and then two clients in separate terminals:

```powershell
python -m server.main
python -m client.main
```

Run all tests:

```powershell
python -m pytest DOCS/tests -q
```

Run the complete suite with the configured coverage threshold:

```powershell
.\DOCS\run_tests.ps1
```

Run a single test:

```powershell
python -m pytest DOCS/tests/test_suite.py::test_piece_moving_state
python -m pytest DOCS/tests/integration/test_text_scripts.py -k 05_capture
```

Coverage configuration is in `DOCS/config/coverage.ini`. Generated coverage and pytest files belong under `DOCS/tests/reports/` and `DOCS/tests/.pytest_cache/` and are ignored by Git.

## Repository layout

Only four project roots are used:

```text
client/       graphical client, input handling, transport and assets
server/       authoritative game engine, rules, persistence and WebSocket server
networking/   models, events, protocols and serializers shared by client and server
DOCS/         tests, plans, tool configuration and supporting documentation
```

The root additionally contains repository-level files such as `README.md`, `CLAUDE.md`, `requirements.txt` and `.gitignore`.

### Client

- `client/main.py` is the graphical client entry point.
- `client/input/` translates mouse actions into requests; `InputController` lives in `input_controller.py`.
- `client/transport/` owns the WebSocket connection and adapts server events to the view-facing interfaces.
- `client/view/` contains OpenCV rendering, animation and HUD components.
- `client/assets/` contains images, sprites and sounds.
- The client does not import server rules or calculate authoritative action timing. It renders snapshots and event durations received from the server.

### Server

- `server/main.py` is the server entry point.
- `server/engine/game_engine.py` coordinates the board, rules and real-time arbiter.
- `server/rules/` validates movement and calculates authoritative durations.
- `server/realtime/` schedules motions and resolves arrivals, collisions and captures.
- `server/models/` owns server-only board and game-state models.
- `server/boardio/` builds and parses boards.
- `server/game/`, `server/services/`, `server/transport/` and `server/dal/` implement matches, authentication, WebSocket transport and SQLite persistence.
- Runtime databases and logs belong in `server/data/` and `server/logs/` and are ignored by Git.

### Shared networking layer

- `networking/models/` contains shared wire-facing models such as `Position`, `Piece`, `GameConfig`, snapshots and `STANDARD_GAME_CONFIG`.
- `networking/events.py` contains the shared game events.
- `networking/event_bus.py` provides in-process event dispatch.
- `networking/protocols/` defines message contracts.
- `networking/serializers/` converts models to and from network payloads.
- `networking/logging_utils.py` provides logging helpers used on both sides.

Do not introduce imports from `client` into `server`, from `server` into `client`, or from either side into `networking`. Shared contracts belong in `networking`.

## Runtime flow

```text
mouse input
  -> InputController
  -> RemoteGameEngineProxy
  -> NetworkClient
  -> WebSocket server
  -> GameController / Match
  -> GameEngine
  -> EventBus / ServerBroadcaster
  -> STATE or EVENT messages
  -> client adapter / view
```

The server alone advances game time and decides legality, movement, arrival, capture, jump, rest, promotion, score and game-over state.

## Tests and text scenarios

All tests live in `DOCS/tests/`. Headless `.kfc` scenarios and their parser/runner live under `DOCS/tests/texttests/` and `DOCS/tests/integration/scripts/`. They may exercise the server engine directly for deterministic integration testing; this does not constitute a supported local application mode.

## View conventions

- `client/view/config.py` centralizes display constants and paths.
- `client/view/geometry.py` is the source of truth for board/cell geometry.
- `DisplayManager` is wired to the remote proxy by `client.main`.
- Asset paths are rooted at `client/assets/`; image loading must remain safe for Unicode filesystem paths.
- See `DOCS/plans/client_view.md` for the view architecture and `DOCS/plans/server_plan.md` for the server development history.
