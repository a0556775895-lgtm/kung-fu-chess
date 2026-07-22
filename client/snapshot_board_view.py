"""Read-only board lookup backed by the latest authoritative snapshot."""

from engine.snapshot import GameSnapshot, PieceSnapshot
from model.position import Position


class SnapshotBoardView:
    """Provide the board queries needed by input code without owning game state."""

    def __init__(self, snapshot: GameSnapshot):
        """Index the initial server snapshot by cell."""
        self._snapshot = snapshot
        self._pieces_by_cell = {}
        self.update(snapshot)

    @property
    def rows(self) -> int:
        """Return the authoritative board height."""
        return self._snapshot.board_height

    @property
    def cols(self) -> int:
        """Return the authoritative board width."""
        return self._snapshot.board_width

    @property
    def snapshot(self) -> GameSnapshot:
        """Expose the immutable snapshot currently represented by this view."""
        return self._snapshot

    def update(self, snapshot: GameSnapshot) -> None:
        """Replace the read model and rebuild its position lookup atomically."""
        if not isinstance(snapshot, GameSnapshot):
            raise TypeError("SNAPSHOT_REQUIRED")
        pieces_by_cell = {piece.cell: piece for piece in snapshot.pieces}
        if len(pieces_by_cell) != len(snapshot.pieces):
            raise ValueError("DUPLICATE_PIECE_CELL")
        self._snapshot = snapshot
        self._pieces_by_cell = pieces_by_cell

    def get_piece_at(self, position: Position) -> PieceSnapshot | None:
        """Return the piece snapshot at a cell, matching Board.get_piece_at()."""
        return self._pieces_by_cell.get(position)
