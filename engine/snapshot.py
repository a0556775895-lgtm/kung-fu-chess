"""Read-only data transferred from the game engine to renderers or clients."""

from dataclasses import dataclass, field

from model.position import Position


@dataclass(frozen=True)
class PieceSnapshot:
    """Serializable read-only identity, location and lifecycle state of one piece."""

    id: str
    kind: str
    color: str
    cell: Position
    state: str


@dataclass(frozen=True)
class MotionSnapshot:
    """Authoritative timing and route of one move currently in flight."""

    piece_id: str
    source: Position
    destination: Position
    start_time_ms: int
    arrival_time_ms: int


@dataclass(frozen=True)
class GameSnapshot:
    """Complete client-facing game state, including synchronization metadata."""

    board_width: int
    board_height: int
    pieces: list[PieceSnapshot]
    selected_cell: Position | None
    game_over: bool
    active_motions: list[MotionSnapshot] = field(default_factory=list)
    airborne_until: dict[str, int] = field(default_factory=dict)
    resting_until: dict[str, int] = field(default_factory=dict)
    scores: dict[str, int] = field(default_factory=lambda: {"w": 0, "b": 0})
    player_names: dict[str, str] = field(
        default_factory=lambda: {"w": "White", "b": "Black"}
    )
    winner_color: str | None = None
    server_time_ms: int = 0
    game_id: str | None = None
    role: str | None = None
    assigned_color: str | None = None
    sequence: int = 0
