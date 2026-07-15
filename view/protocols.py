from typing import Protocol


class Renderer(Protocol):
    """כל renderer בפרויקט מיישם את זה - כדי ש-DisplayManager
    יוכל להחזיק רשימה גנרית בלי if לפי סוג."""

    def render(self, canvas, snapshot) -> None: ...


class Loader(Protocol):
    """כל loader בפרויקט מיישם את זה - טעינה חד-פעמית מהדיסק,
    בלי לגעת בציור."""

    def load(self) -> None: ...