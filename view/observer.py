from typing import Protocol
from realtime.real_time_arbiter import ArrivalEvent
from model.position import Position


class GameObserver(Protocol):
    """כל מי שרוצה 'לשמוע' אירועי משחק - נרשם דרך GameEngine.subscribe().
    מחליף polling מכוער על snapshot בכל frame."""

    def on_arrival(self, event: ArrivalEvent) -> None:
        """נקרא בכל מהלך שמגיע ליעד - גם בלי תפיסה."""
        ...

    def on_motion_started(self, piece, source: Position,
                           destination: Position, duration_ms: int) -> None:
        """נקרא כשתנועה רגילה מתחילה - דרוש לאינטרפולציה חזותית."""
        ...

    def on_jump_started(self, piece, position: Position) -> None:
        """נקרא כשקפיצה מתחילה. duration תמיד קבוע (config.JUMP_DURATION_MS)."""
        ...

    def on_game_over(self) -> None:
        """נקרא פעם אחת, כשמלך נתפס."""
        ...