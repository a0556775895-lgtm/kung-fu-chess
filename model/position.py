# קואורדינטת תא על הלוח — value object בלתי-ניתן לשינוי.
from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """An immutable (row, col) board coordinate."""

    row: int
    col: int