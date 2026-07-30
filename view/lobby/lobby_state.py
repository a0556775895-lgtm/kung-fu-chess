"""Presentation state and user actions for the graphical lobby."""

from dataclasses import dataclass
from enum import Enum


class LobbyScreen(str, Enum):
    """One full-screen lobby presentation."""

    WELCOME = "WELCOME"
    MENU = "MENU"
    JOIN_ROOM = "JOIN_ROOM"
    WAITING_FOR_MATCH = "WAITING_FOR_MATCH"
    WAITING_FOR_ROOM = "WAITING_FOR_ROOM"


class LobbyAction(str, Enum):
    """A semantic action produced by mouse or keyboard input."""

    START = "START"
    QUICK_MATCH = "QUICK_MATCH"
    CREATE_ROOM = "CREATE_ROOM"
    SHOW_JOIN_ROOM = "SHOW_JOIN_ROOM"
    SUBMIT_ROOM_CODE = "SUBMIT_ROOM_CODE"
    BACK = "BACK"
    CANCEL_ROOM = "CANCEL_ROOM"
    COPY_ROOM_CODE = "COPY_ROOM_CODE"
    EXIT = "EXIT"


@dataclass(frozen=True, slots=True)
class LobbyViewState:
    """Immutable data needed to draw one lobby frame."""

    screen: LobbyScreen
    room_code_input: str = ""
    created_room_code: str | None = None
    error: str | None = None
