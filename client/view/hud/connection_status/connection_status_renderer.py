"""Render an optional connection notice over the existing board canvas."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConnectionNotice:
    """Presentation-only text and optional countdown."""

    text: str
    seconds_remaining: int | None = None


class ConnectionStatusRenderer:
    """Draw notices without depending on sockets, tokens, or client classes."""

    def __init__(self, notice_provider):
        if not callable(notice_provider):
            raise TypeError("NOTICE_PROVIDER_NOT_CALLABLE")
        self._notice_provider = notice_provider

    def render(self, canvas, _snapshot) -> None:
        """Draw one high-contrast status line when the provider has a notice."""
        notice = self._notice_provider()
        if notice is None:
            return
        if not isinstance(notice, ConnectionNotice):
            raise TypeError("INVALID_CONNECTION_NOTICE")

        text = notice.text
        if notice.seconds_remaining is not None:
            text = f"{text} ({notice.seconds_remaining})"
        canvas.put_text(text, 22, 42, 0.8, color=(0, 0, 0, 255), thickness=4)
        canvas.put_text(
            text,
            20,
            40,
            0.8,
            color=(255, 255, 255, 255),
            thickness=2,
        )
