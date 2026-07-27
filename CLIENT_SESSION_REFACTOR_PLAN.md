# Client Session Refactor Plan

## 1. Purpose

This document defines a focused refactor of the boundary between the presentation layer and the game source.

The project currently supports two execution modes:

1. A local hot-seat game backed directly by `GameEngine`.
2. A multiplayer game backed by an authoritative WebSocket server.

Both modes use the same `DisplayManager`, but they currently reach it through different combinations of objects and callbacks. The purpose of this refactor is to introduce one explicit `GameSession` abstraction that represents either a local or a remote game.

The refactor is intended to simplify the client before matchmaking, reconnection, rooms, and spectators are implemented. It is not intended to change game rules, server authority, network messages, rendering behavior, or persistence.

---

## 2. Executive Summary

The current presentation API exposes one logical game through several separate dependencies:

- A board-like object.
- An engine-like command target.
- A per-frame update callback.
- An event source.
- An event bus used by presentation services.

In local mode, most of these responsibilities are provided by `GameEngine`. In remote mode, they are distributed between:

- `NetworkClient`
- `RemoteGameEngineProxy`
- `SnapshotBoardView`
- `NetworkEventAdapter`
- A closure created in `client/main.py`

This design works, but it makes `DisplayManager` aware of composition details and forces remote components to imitate separate parts of the local object graph.

The target design introduces:

```text
GameSession
├── LocalGameSession
└── RemoteGameSession
```

`DisplayManager` will depend on one `GameSession` instead of knowing whether the game is local or remote.

The recommended implementation is incremental:

1. Introduce the interface and two session implementations without deleting the existing remote adapters.
2. Migrate `DisplayManager`, `main.py`, and `client/main.py` to the session API.
3. Verify local and multiplayer behavior.
4. Optionally consolidate the internal remote adapters after the boundary is stable.

---

## 3. Current Architecture

### 3.1 Local mode

The current local composition is effectively:

```text
main.py
  └── DisplayManager()
        ├── creates Board
        ├── creates GameEngine
        ├── uses GameEngine.wait()
        ├── uses GameEngine.snapshot()
        ├── subscribes observers to GameEngine
        └── sends commands to GameEngine
```

`DisplayManager` detects local mode when no board or engine is supplied. It then creates the standard board and `GameEngine` internally.

This makes the view layer a composition root. It also means that constructing the graphical window has the side effect of constructing the game domain.

### 3.2 Remote mode

The current multiplayer composition is:

```text
client/main.py
  ├── NetworkClient
  ├── RemoteGameEngineProxy
  │     └── SnapshotBoardView
  ├── NetworkEventAdapter
  ├── update_remote_game() closure
  └── DisplayManager(
          board=proxy.board,
          game_engine=proxy,
          game_updater=update_remote_game,
          event_source=event_adapter,
          starts_game=False,
      )
```

The remote game is therefore presented to the view as four separate values:

1. `proxy.board`
2. `proxy`
3. `update_remote_game`
4. `event_adapter`

The view must know how these values relate to one another and which combinations are valid.

### 3.3 Current command flow

The current remote command path is approximately:

```text
OpenCV mouse event
  → MouseCommandExtractor
  → GameCommandSender
  → input.Controller
  → RemoteGameEngineProxy
  → NetworkClient
  → WebSocket
```

The current remote event path is approximately:

```text
WebSocket
  → NetworkClient
  → RemoteGameEngineProxy
  → client/main.py update closure
  → NetworkEventAdapter
  → EventBus
  → PieceAnimator / MovesLogData / SoundPlayer
```

None of these individual components is inherently invalid. The problem is that the relationship between them is implicit and assembled differently in each entry point.

---

## 4. Problems Addressed by the Refactor

### 4.1 One concept is exposed as several dependencies

A running game is one application-level concept, but `DisplayManager` receives it as a board, engine, updater, event source, and start-mode flag.

This creates invalid combinations that must be rejected at runtime, such as:

- A board without an engine.
- A remote engine without a remote updater.
- An event source that does not belong to the supplied engine.
- Incorrect `starts_game` configuration.

An explicit session object makes those combinations impossible by construction.

### 4.2 `DisplayManager` has composition responsibilities

The presentation layer currently decides whether it should create a standard board and local engine. That responsibility belongs in an application entry point or session factory.

`DisplayManager` should manage:

- Window lifecycle.
- Input extraction.
- Presentation timing.
- Rendering.
- Presentation observers.

It should not decide how a game is created or whether authority is local or remote.

### 4.3 Remote objects imitate unrelated local objects

`RemoteGameEngineProxy` imitates part of `GameEngine`, while `SnapshotBoardView` separately imitates part of `Board`. `NetworkEventAdapter` then recreates the event interface.

This arrangement was a reasonable low-risk way to add multiplayer without rewriting the view. It becomes less suitable as the remote lifecycle gains:

- Matchmaking states.
- Connection instability.
- Reconnection.
- Session tokens.
- Room membership.
- Spectator roles.
- Match replacement.

These behaviors belong to one remote session lifecycle, not to several loosely connected adapters.

### 4.4 Local and remote lifecycle rules are scattered

The current caller must know:

- Local mode advances authoritative game time.
- Remote mode only pumps network messages.
- Local mode publishes `GameStarted`.
- Remote mode receives game lifecycle events from the server.
- Local mode owns a `Board`.
- Remote mode owns a snapshot-backed board facade.
- Remote mode must close its network thread.

A session abstraction can own these differences while exposing one stable presentation contract.

### 4.5 Future stages would increase accidental complexity

Stages E and F introduce remote-only lifecycle states. Adding them directly to the current composition would likely add more callbacks and flags to `DisplayManager`.

The session boundary should be established before those stages so the view can consume connection and match state without learning network orchestration details.

---

## 5. Goals

The refactor must:

1. Give `DisplayManager` one dependency representing the active game.
2. Keep all game rules authoritative in `GameEngine` locally and on the server remotely.
3. Preserve the existing snapshot-driven rendering model.
4. Preserve the existing event-driven animation, move log, and audio behavior.
5. Preserve the current WebSocket protocol and serializers.
6. Keep the local game independent of a server process.
7. Make local and remote composition explicit in their respective entry points.
8. Provide a natural place for future connection and matchmaking state.
9. Allow an incremental migration with continuously passing tests.
10. Avoid a broad rewrite of the client or view.

---

## 6. Non-Goals

This refactor must not:

1. Change chess or Kung Fu Chess rules.
2. Change `GameEngine` timing or collision behavior.
3. Change the WebSocket wire protocol.
4. Change authentication, SQLite, ELO, or game-result persistence.
5. Move the server-authoritative clock to the client.
6. Introduce client-side game-rule validation.
7. Implement matchmaking, reconnection, rooms, or spectators.
8. Merge all client code into one large class.
9. Remove useful transport/domain boundaries only to reduce the file count.
10. Require the local game to connect to a local WebSocket server.

---

## 7. Target Architecture

### 7.1 High-level structure

```text
                         ┌──────────────────────┐
                         │    DisplayManager    │
                         │ rendering and input  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     GameSession      │
                         │ presentation-facing  │
                         │ application contract │
                         └──────────┬───────────┘
                                    │
                   ┌────────────────┴────────────────┐
                   ▼                                 ▼
        ┌──────────────────────┐          ┌──────────────────────┐
        │   LocalGameSession   │          │  RemoteGameSession   │
        │ Board + GameEngine   │          │ NetworkClient +      │
        │ local authority      │          │ remote read model    │
        └──────────────────────┘          └──────────────────────┘
```

### 7.2 Recommended contract

The contract should contain only behavior required by the presentation layer:

```python
from typing import Protocol

from engine.snapshot import GameSnapshot
from model.position import Position


class GameSession(Protocol):
    @property
    def board(self):
        """Return the read-only board lookup used by selection/input code."""
        ...

    @property
    def bus(self):
        """Return the presentation event bus used by services such as audio."""
        ...

    def start(self) -> None:
        """Start or activate the session. Must be safe to call once."""
        ...

    def update(self, dt_ms: int) -> None:
        """Advance local authority or pump remote messages."""
        ...

    def snapshot(
        self,
        selected_cell: Position | None = None,
    ) -> GameSnapshot:
        """Return the newest presentation snapshot."""
        ...

    def request_move(
        self,
        source: Position,
        destination: Position,
    ):
        """Request a move through the correct authority."""
        ...

    def request_jump(self, source: Position):
        """Request a jump through the correct authority."""
        ...

    def subscribe(self, observer):
        """Subscribe a presentation observer and return an unsubscribe callable."""
        ...

    def close(self) -> None:
        """Release session-owned resources. Must be idempotent."""
        ...
```

The exact return types of `request_move` and `request_jump` may initially remain compatible with the current implementations. They should not be generalized prematurely.

### 7.3 Why the session exposes a board view

The existing `input.Controller` requires cell lookup to support selection behavior, including switching selection between friendly pieces. Removing the board property immediately would broaden the refactor unnecessarily.

The first phase should therefore expose a read-only board-like object:

- `Board` in local mode.
- `SnapshotBoardView` in remote mode.

A later refactor may replace this with session-level query methods such as `piece_at(position)`. That is not required for the initial migration.

### 7.4 Why the event bus remains available

`SoundPlayer` currently subscribes to the raw event bus, while other presentation components use the observer-shaped `subscribe()` API.

The first phase should preserve both APIs to avoid combining this refactor with an event-contract rewrite. Once the session boundary is stable, event consumption can be unified separately if desired.

---

## 8. Component Responsibilities

### 8.1 `GameSession`

`GameSession` is a presentation-facing application contract. It is not a domain model and must not contain game rules.

It defines:

- How the presentation obtains snapshots.
- How commands are submitted.
- How presentation events are observed.
- How per-frame work is performed.
- How the session lifecycle is started and closed.

### 8.2 `LocalGameSession`

`LocalGameSession` owns:

- Creation or injection of a local `Board`.
- A local `GameEngine`.
- Advancing authoritative time through `GameEngine.wait(dt_ms)`.
- Publishing the local `GameStarted` event through `GameEngine.start_game()`.
- Delegating snapshots and commands to `GameEngine`.

It does not own:

- OpenCV.
- Rendering.
- Mouse coordinate conversion.
- WebSockets.
- Server services.

Suggested shape:

```python
class LocalGameSession:
    def __init__(self, board=None, engine=None):
        if board is None and engine is None:
            board = create_standard_board()
            engine = GameEngine(board)
        elif board is None or engine is None:
            raise ValueError("BOARD_AND_ENGINE_REQUIRED")

        self._board = board
        self._engine = engine
        self._started = False

    @property
    def board(self):
        return self._board

    @property
    def bus(self):
        return self._engine.bus

    def start(self):
        if self._started:
            return
        self._started = True
        self._engine.start_game()

    def update(self, dt_ms):
        self._engine.wait(dt_ms)

    def snapshot(self, selected_cell=None):
        return self._engine.snapshot(selected_cell)

    def request_move(self, source, destination):
        return self._engine.request_move(source, destination)

    def request_jump(self, source):
        return self._engine.request_jump(source)

    def subscribe(self, observer):
        return self._engine.subscribe(observer)

    def close(self):
        pass
```

### 8.3 `RemoteGameSession`

`RemoteGameSession` owns the remote client-side game lifecycle:

- `NetworkClient`.
- The newest authoritative snapshot.
- The snapshot-backed board view.
- Outbound command requests.
- Ordered processing of `STATE`, `EVENT`, `OK`, and `ERR`.
- Adaptation of wire events to presentation events.
- Network shutdown.

During the conservative migration, it may delegate internally to:

- `RemoteGameEngineProxy`.
- `SnapshotBoardView`.
- `NetworkEventAdapter`.

The session must not:

- Advance authoritative game time.
- Resolve captures or movement.
- Apply game rules.
- Predict server results.
- Mutate the authoritative board locally.

Suggested conservative implementation:

```python
class RemoteGameSession:
    def __init__(self, network_client):
        self._network_client = network_client
        self._proxy = RemoteGameEngineProxy(network_client)
        self._events = NetworkEventAdapter()

    @property
    def board(self):
        return self._proxy.board

    @property
    def bus(self):
        return self._events.bus

    def start(self):
        # NetworkClient may already be started by a factory during handshake.
        pass

    def update(self, _dt_ms):
        self._proxy.process_network_messages()
        for event in self._proxy.drain_events():
            self._events.publish(event)
        if not self._network_client.is_connected:
            raise ConnectionError(
                "server_connection_closed"
            ) from self._network_client.failure

    def snapshot(self, selected_cell=None):
        return self._proxy.snapshot(selected_cell)

    def request_move(self, source, destination):
        return self._proxy.request_move(source, destination)

    def request_jump(self, source):
        return self._proxy.request_jump(source)

    def subscribe(self, observer):
        return self._events.subscribe(observer)

    def close(self):
        self._network_client.close()
```

The current closure in `client/main.py` becomes `RemoteGameSession.update()`.

### 8.4 `DisplayManager`

After the migration, `DisplayManager` owns presentation only.

Its constructor becomes conceptually:

```python
class DisplayManager:
    def __init__(self, session: GameSession):
        self._session = session
```

It uses:

```python
self._session.board
self._session.update(dt_ms)
self._session.snapshot(selected_position)
self._session.subscribe(observer)
self._session.bus
self._session.request_move(...)
self._session.request_jump(...)
```

It must no longer:

- Create the standard board.
- Create `GameEngine`.
- Detect local mode.
- Accept `game_updater`.
- Accept `event_source`.
- Accept `starts_game`.

### 8.5 Entry points

Entry points become the composition roots.

Local:

```text
main.py
  → LocalGameSession
  → DisplayManager(session)
```

Remote:

```text
client/main.py
  → credentials
  → NetworkClient
  → RemoteGameSession
  → DisplayManager(session)
```

This makes resource ownership and shutdown explicit.

---

## 9. Proposed File Structure

The conservative version should add:

```text
client/
├── session.py                  # GameSession Protocol
├── local_game_session.py       # LocalGameSession
├── remote_game_session.py      # RemoteGameSession
├── network_client.py           # unchanged transport role
├── remote_game_engine_proxy.py # retained initially
├── snapshot_board_view.py      # retained initially
└── network_event_adapter.py    # retained initially
```

An alternative is a `client/session/` package:

```text
client/session/
├── __init__.py
├── protocol.py
├── local.py
└── remote.py
```

For the current project size, three flat files under `client/` are simpler and avoid creating another package layer.

After the migration is stable, an optional consolidation may reduce the structure to:

```text
client/
├── game_session.py
├── local_game_session.py
├── remote_game_session.py
├── network_client.py
├── cli_auth.py
└── main.py
```

This cleanup is optional. Correct ownership is more important than minimizing the number of files.

---

## 10. File-by-File Change Plan

### 10.1 New: `client/session.py`

Add the `GameSession` protocol.

Requirements:

- No OpenCV dependency.
- No WebSocket dependency.
- No game-rule logic.
- Type only what the view actually consumes.
- Keep imports limited to shared snapshot and position types.

### 10.2 New: `client/local_game_session.py`

Move local game composition out of `DisplayManager`.

Responsibilities:

- Create the standard board and engine by default.
- Support injected board/engine pairs for tests.
- Delegate the session contract to `GameEngine`.
- Ensure `start_game()` is emitted once.
- Provide idempotent `close()`.

### 10.3 New: `client/remote_game_session.py`

Move the remote update closure and ownership of presentation events out of `client/main.py`.

Initial dependencies:

- `NetworkClient`
- `RemoteGameEngineProxy`
- `NetworkEventAdapter`

Requirements:

- Do not advance server time.
- Process messages in queue order.
- Preserve existing sequence handling.
- Publish events in accepted sequence order.
- Surface connection closure consistently.
- Close `NetworkClient` exactly once.

### 10.4 Modify: `view/display_manager.py`

Replace:

```python
board
game_engine
game_updater
event_source
starts_game
```

with:

```python
session
```

Other changes:

- Build `Controller` with `session.board` and `session`.
- Build `GameCommandSender` with the session.
- Subscribe observers through `session.subscribe`.
- Build `SoundPlayer` with `session.bus`.
- Call `session.start()` at run start.
- Call `session.update(dt_ms)` during update.
- Read snapshots through `session.snapshot(...)`.
- Decide whether `DisplayManager` or the entry point closes the session, and document one owner.

Recommended ownership:

- `DisplayManager.run()` closes presentation resources only.
- The entry point owns and closes the session in `finally`.

This prevents a window component from owning a reusable application/network resource.

### 10.5 Modify: `view/input/commands.py`

Rename engine-oriented fields to session-oriented fields where appropriate.

The command sender should depend on the smallest command interface:

```python
class GameCommandTarget(Protocol):
    def request_jump(self, source): ...
```

The existing `Controller` may continue handling click selection and move requests.

Avoid making `commands.py` import concrete `LocalGameSession` or `RemoteGameSession`.

### 10.6 Modify: `input/controller.py`

The minimal migration only renames the injected `game_engine` concept to a command target or session.

No selection behavior should change.

The controller must remain unaware of:

- Local versus remote mode.
- WebSockets.
- Authentication.
- Matchmaking.
- Connection state.

### 10.7 Modify: `main.py`

Compose local mode explicitly:

```python
session = LocalGameSession()
try:
    DisplayManager(session).run()
finally:
    session.close()
```

Logging behavior remains unchanged.

### 10.8 Modify: `client/main.py`

Keep authentication and network construction, then wrap the connection in a remote session:

```python
network_client = NetworkClient(...)
network_client.start()
session = RemoteGameSession(network_client)
try:
    DisplayManager(session).run()
finally:
    session.close()
```

Remove:

- Direct construction of `RemoteGameEngineProxy`.
- Direct construction of `NetworkEventAdapter`.
- The `update_remote_game` closure.
- The multi-argument `DisplayManager` composition.

### 10.9 Initially unchanged

The conservative phase should leave these behaviorally unchanged:

- `client/network_client.py`
- `client/remote_game_engine_proxy.py`
- `client/snapshot_board_view.py`
- `client/network_event_adapter.py`
- `engine/game_engine.py`
- `networking/protocols/game.py`
- `networking/serializers/snapshot.py`
- All server modules

---

## 11. Incremental Migration Strategy

### Phase 1: Define the boundary

1. Add the `GameSession` protocol.
2. Add `LocalGameSession`.
3. Add unit tests for local delegation and lifecycle.
4. Do not modify the view yet.

Exit condition:

- Existing tests remain green.
- Local session tests prove that commands, snapshots, events, and time delegation work.

### Phase 2: Wrap the current remote client

1. Add `RemoteGameSession`.
2. Move the current remote update closure into it.
3. Keep the existing proxy, board view, and event adapter internally.
4. Add isolated tests using a fake `NetworkClient`.

Exit condition:

- Existing remote proxy tests remain green.
- New tests prove message pumping, event forwarding, connection failure, and idempotent close.

### Phase 3: Migrate `DisplayManager`

1. Change its constructor to require a session.
2. Remove local-mode detection and implicit engine construction.
3. Replace direct engine/updater/event-source use with session calls.
4. Update dependency-injection tests.

Exit condition:

- No local/remote branching remains in `DisplayManager`.
- Display behavior and renderer order remain unchanged.

### Phase 4: Migrate entry points

1. Update `main.py` to create `LocalGameSession`.
2. Update `client/main.py` to create `RemoteGameSession`.
3. Ensure each entry point closes its session.
4. Remove the remote update closure.

Exit condition:

- Local game launches successfully.
- Server plus two graphical clients launch successfully.
- Shutdown does not leave a network thread alive.

### Phase 5: Optional internal consolidation

Only after the new boundary is stable:

1. Move snapshot ownership from `RemoteGameEngineProxy` into `RemoteGameSession`.
2. Move event adaptation into the remote session or a shared presentation-event codec.
3. Remove adapters that no longer have an independent responsibility.
4. Keep `NetworkClient` as the transport boundary.

This phase should be approved separately because it increases the change surface without being required for the initial architectural improvement.

---

## 12. Testing Strategy

### 12.1 Contract tests

Create a reusable set of behavioral tests for both session implementations where applicable:

- `snapshot()` returns a `GameSnapshot`.
- `request_move()` reaches the underlying command authority.
- `request_jump()` reaches the underlying command authority.
- `subscribe()` returns a functioning unsubscribe callable.
- `close()` is idempotent.

Not every local behavior applies remotely. For example, only local mode advances authoritative time.

### 12.2 `LocalGameSession` tests

Test:

1. Default construction creates a valid standard game.
2. Injected board and engine must be supplied together.
3. `start()` publishes `GameStarted` once.
4. Repeated `start()` does not publish duplicate lifecycle events.
5. `update(dt_ms)` delegates exactly once to `GameEngine.wait(dt_ms)`.
6. Move and jump requests are delegated.
7. Snapshots preserve selected-cell metadata.
8. `close()` is safe and idempotent.

### 12.3 `RemoteGameSession` tests

Use a fake or stub `NetworkClient`.

Test:

1. Initial snapshot and assigned role are exposed.
2. `update()` drains all currently queued messages.
3. Accepted events are published in order.
4. Duplicate or stale sequences retain existing proxy behavior.
5. `update()` never advances authoritative time locally.
6. Commands are encoded and queued through the existing proxy/client path.
7. A closed connection is surfaced with its original failure as the cause.
8. `close()` closes the network client once and remains idempotent.

### 12.4 `DisplayManager` injection tests

Use a fake session and avoid opening a real OpenCV window where possible.

Test:

1. The constructor requires exactly one session.
2. The same session supplies board lookup, commands, events, and snapshots.
3. `update(dt_ms)` calls `session.update(dt_ms)` once.
4. Snapshot selection is passed correctly.
5. Observers are unsubscribed during shutdown.
6. Presentation shutdown does not accidentally close a session if entry points own it.

### 12.5 Integration tests

Retain all existing tests, especially:

- WebSocket server round trip.
- Remote proxy ordering.
- Network event adaptation.
- Client main composition.
- Local display-manager injection.

Add or update:

1. Local composition smoke test.
2. Remote composition smoke test with a fake network client.
3. Real server plus two clients round trip through `RemoteGameSession`.
4. Network shutdown test proving no client thread survives.

### 12.6 Manual verification

Local:

```powershell
python main.py
```

Verify:

- Board opens.
- Selection works.
- Move and jump work.
- Animation, score, move log, sound, and game-over rendering still work.
- Escape closes the window cleanly.

Remote:

```powershell
python -m server.main
python -m client.main
python -m client.main
```

Verify:

- Authentication and JOIN still work.
- White and black are assigned correctly.
- Both clients receive the same authoritative state.
- Animation and events remain synchronized.
- Closing either client stops its network thread.

---

## 13. Acceptance Criteria

The conservative refactor is complete when:

1. `DisplayManager` accepts one required `GameSession`.
2. `DisplayManager` does not create `Board` or `GameEngine`.
3. `DisplayManager` contains no local/remote mode branch.
4. `client/main.py` contains no remote message-pumping closure.
5. `main.py` explicitly composes `LocalGameSession`.
6. `client/main.py` explicitly composes `RemoteGameSession`.
7. Local mode remains server-independent.
8. Remote mode remains server-authoritative.
9. No server, protocol, serializer, or game-rule behavior changes.
10. All existing tests pass.
11. New session tests pass.
12. Manual local and two-client graphical verification passes.
13. Session shutdown is idempotent and leaves no background network thread.
14. The current 100% measured-logic coverage threshold remains satisfied, unless coverage policy is separately revised.

---

## 14. Risks and Mitigations

### 14.1 Duplicate game-start events

Risk:

Both `DisplayManager` and `LocalGameSession` could call `start_game()`.

Mitigation:

- Remove start ownership from `DisplayManager`.
- Make `LocalGameSession.start()` idempotent.
- Add a test that exactly one `GameStarted` event is published.

### 14.2 Double network shutdown

Risk:

`DisplayManager`, `client/main.py`, and `RemoteGameSession` could all attempt to close `NetworkClient`.

Mitigation:

- Declare the entry point as the session owner.
- Make `RemoteGameSession.close()` idempotent.
- Keep presentation-resource cleanup separate from session cleanup.

### 14.3 Event ordering regression

Risk:

Moving the message-pumping closure may change the order between `STATE`, `EVENT`, and presentation updates.

Mitigation:

- Move the existing logic without rewriting it.
- Preserve queue-drain order.
- Test ordered state/event sequences.
- Delay adapter consolidation until a later phase.

### 14.4 Local and remote behavior accidentally diverge

Risk:

A broad interface may imply semantics that cannot be identical in both modes.

Mitigation:

- Document that `update()` has mode-specific internals.
- Keep authority rules explicit.
- Do not force the remote session to imitate `GameEngine.wait()`.
- Expose only presentation-required behavior.

### 14.5 Interface becomes a “god object”

Risk:

Future features may add authentication, matchmaking, rooms, and UI dialogs directly to `GameSession`.

Mitigation:

- Keep authentication and lobby flows outside an active game session.
- Introduce a separate lobby/application state abstraction when Stage E begins.
- Limit `GameSession` to one active or pending match.
- Expose connection status as immutable state/events rather than transport operations.

### 14.6 File count does not decrease immediately

Risk:

The conservative migration adds three files before any adapters are removed.

Mitigation:

- Measure success by ownership and dependency direction, not immediate file count.
- Consolidate only after responsibilities become redundant.
- Avoid deleting independently testable transport components merely for cosmetic reduction.

---

## 15. Estimated Scope

### Conservative migration

Expected scope:

- 2–3 new files.
- 6–8 modified files.
- Approximately 150–250 lines added or moved.
- Existing remote adapters retained.
- Low implementation risk.

### Full consolidation

Expected total scope:

- 10–14 affected files.
- Approximately 300–500 lines added, moved, or rewritten.
- 2–3 adapter files may become removable.
- Medium implementation risk due to event ordering and network lifecycle.

These are planning estimates, not fixed limits. The refactor should stop after the conservative phase if the remaining adapters still have clear, independently testable responsibilities.

---

## 16. Recommended Sequencing with the Server Roadmap

The recommended project order is:

1. Complete D5: pure ELO calculation.
2. Complete D6: atomic game-result and rating persistence.
3. Perform the conservative `GameSession` refactor.
4. Verify local and multiplayer behavior.
5. Begin Stage E matchmaking and reconnection.
6. Consider remote-adapter consolidation only when Stage E requirements make the benefit concrete.

D5 and D6 are server-side work and do not depend on the client refactor. Completing them first avoids mixing persistence changes with presentation-boundary changes.

The session refactor should occur before Stage E because reconnection and matchmaking introduce additional remote lifecycle states that should be owned by a coherent client-side abstraction.

---

## 17. Design Decisions

### Decision 1: Keep local mode direct

Local mode continues to call `GameEngine` in-process. It does not use WebSocket or the server controller.

Reason:

- Preserves offline play.
- Keeps local startup simple.
- Avoids unnecessary transport overhead.
- Matches the existing product plan.

### Decision 2: Keep the server authoritative remotely

`RemoteGameSession` does not contain rules or advance game time.

Reason:

- Prevents client/server divergence.
- Preserves security and deterministic authority.
- Keeps reconnect based on full authoritative snapshots.

### Decision 3: Introduce a session, not a universal engine interface

The abstraction is named `GameSession`, not `GameEngine`.

Reason:

- A remote connection is not a game engine.
- The remote side owns transport and lifecycle, not simulation.
- The name avoids implying identical local and remote authority.

### Decision 4: Preserve existing adapters initially

The first migration wraps existing behavior rather than rewriting it.

Reason:

- Smaller regression surface.
- Existing tests remain useful.
- Allows the architectural boundary to be validated independently.

### Decision 5: Entry points own composition and session lifetime

`main.py` and `client/main.py` construct and close their sessions.

Reason:

- Resource ownership is explicit.
- `DisplayManager` stays focused on presentation.
- Network shutdown is not tied implicitly to an OpenCV component.

---

## 18. Open Questions to Resolve Before Implementation

1. Should `GameSession.start()` be called by the entry point or by `DisplayManager.run()`?
   - Recommendation: call it from the entry point immediately before `DisplayManager.run()`.

2. Should the entry point or `DisplayManager` own session shutdown?
   - Recommendation: the entry point owns shutdown in `finally`.

3. Should `GameSession` expose `board`, or only `get_piece_at()`?
   - Recommendation: expose the current read-only board facade during the conservative migration.

4. Should raw `bus` access remain part of the session contract?
   - Recommendation: retain it temporarily for `SoundPlayer`, then consider one unified event subscription contract separately.

5. Should the remote adapters be removed in the same change?
   - Recommendation: no. Treat consolidation as a separate, optional phase.

6. Where should future connection state live?
   - Recommendation: immutable state/events on `RemoteGameSession`; authentication and lobby workflows remain outside the active session.

---

## 19. Final Recommendation

Proceed with the conservative session refactor rather than merging files solely to reduce their number.

The key improvement is:

```text
DisplayManager(board, engine, updater, event_source, starts_game)
```

becoming:

```text
DisplayManager(session)
```

This creates a stable presentation boundary, moves composition into the entry points, keeps local and remote authority explicit, and prepares the client for matchmaking and reconnection without changing the server or game core.

The initial implementation should preserve the existing proxy, snapshot board view, and network event adapter internally. File consolidation should happen only after the new boundary is proven and only where a component no longer has an independent responsibility.
