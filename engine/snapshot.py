"""Read-only data transferred from the game engine to renderers or clients."""

from dataclasses import dataclass, field

from model.position import Position


@dataclass(frozen=True)
class PieceSnapshot:
    id: str
    kind: str
    color: str
    cell: Position
    state: str


@dataclass(frozen=True)
class MotionSnapshot:
    piece_id: str
    source: Position
    destination: Position
    start_time_ms: int
    arrival_time_ms: int


@dataclass(frozen=True)
class GameSnapshot:
    board_width: int
    board_height: int
    pieces: list[PieceSnapshot]
    selected_cell: Position | None
    game_over: bool
    active_motions: list[MotionSnapshot] = field(default_factory=list)
    airborne_until: dict[str, int] = field(default_factory=dict)
    resting_until: dict[str, int] = field(default_factory=dict)
    scores: dict[str, int] = field(default_factory=lambda: {"w": 0, "b": 0})
    winner_color: str | None = None
    server_time_ms: int = 0
    game_id: str | None = None
    role: str | None = None
    assigned_color: str | None = None
    sequence: int = 0
