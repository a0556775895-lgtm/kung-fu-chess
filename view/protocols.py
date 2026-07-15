from typing import Protocol


class Renderer(Protocol):
    """Every renderer in the project implements this — so DisplayManager
    can hold a generic list without an if-per-type."""

    def render(self, canvas, snapshot) -> None: ...


class Loader(Protocol):
    """Every loader in the project implements this — a one-time load
    from disk, without touching drawing."""

    def load(self) -> None: ...