"""Coordinate graphical lobby actions with the public NetworkClient facade."""

from client.network_client import ConnectionState
from view.lobby.lobby_state import (
    LobbyAction,
    LobbyScreen,
    LobbyViewState,
)


_LOBBY_ERROR_MESSAGES = {
    "match_timeout": "No opponent found. Please try again.",
}


class LobbyController:
    """Own pre-game UI state without rendering or speaking WebSocket."""

    def __init__(self, network_client):
        self._network_client = network_client
        self._screen = LobbyScreen.WELCOME
        self._room_code_input = ""
        self._error = None
        self._handled_lobby_error = None
        self._operation = None
        self._cancel_pending = False
        self._exit_requested = False

    @property
    def view_state(self) -> LobbyViewState:
        """Return an immutable snapshot for the renderer."""
        return LobbyViewState(
            self._screen,
            self._room_code_input,
            self._network_client.room_code,
            self._error,
        )

    @property
    def exit_requested(self) -> bool:
        """Whether the user chose to close the multiplayer client."""
        return self._exit_requested

    def update(self) -> bool:
        """Synchronize recoverable network state and report game readiness."""
        status = self._network_client.connection_status.state
        if status is ConnectionState.CONNECTED:
            return True
        if status is ConnectionState.FAILED:
            failure = self._network_client.failure
            raise ConnectionError("lobby_connection_failed") from failure

        lobby_error = self._network_client.lobby_error
        if lobby_error is None:
            self._handled_lobby_error = None
        elif lobby_error != self._handled_lobby_error:
            self._handled_lobby_error = lobby_error
            self._error = _LOBBY_ERROR_MESSAGES.get(
                lobby_error,
                lobby_error,
            )
            if self._operation == "join":
                self._screen = LobbyScreen.JOIN_ROOM
            elif (
                self._operation == "create"
                and status is ConnectionState.WAITING_IN_ROOM
            ):
                self._screen = LobbyScreen.WAITING_FOR_ROOM
            else:
                self._screen = LobbyScreen.MENU
                self._operation = None

        if (
            self._cancel_pending
            and status is ConnectionState.LOBBY
        ):
            self._screen = LobbyScreen.MENU
            self._operation = None
            self._cancel_pending = False
            self._error = None
        return False

    def handle_action(self, action: LobbyAction) -> None:
        """Apply one semantic click while enforcing valid screen transitions."""
        if action is LobbyAction.START and self._screen is LobbyScreen.WELCOME:
            self._screen = LobbyScreen.MENU
            return

        if action is LobbyAction.QUICK_MATCH and self._screen is LobbyScreen.MENU:
            self._network_client.start_matchmaking()
            self._screen = LobbyScreen.WAITING_FOR_MATCH
            self._operation = "match"
            self._error = None
            return

        if action is LobbyAction.CREATE_ROOM and self._screen is LobbyScreen.MENU:
            self._network_client.create_room()
            self._screen = LobbyScreen.WAITING_FOR_ROOM
            self._operation = "create"
            self._error = None
            return

        if (
            action is LobbyAction.SHOW_JOIN_ROOM
            and self._screen is LobbyScreen.MENU
        ):
            self._screen = LobbyScreen.JOIN_ROOM
            self._error = None
            return

        if (
            action is LobbyAction.SUBMIT_ROOM_CODE
            and self._screen is LobbyScreen.JOIN_ROOM
        ):
            if not 4 <= len(self._room_code_input) <= 12:
                self._error = "Room code must contain 4-12 characters"
                return
            self._network_client.join_room(self._room_code_input)
            self._screen = LobbyScreen.WAITING_FOR_MATCH
            self._operation = "join"
            self._error = None
            return

        if action is LobbyAction.BACK and self._screen is LobbyScreen.JOIN_ROOM:
            self._screen = LobbyScreen.MENU
            self._room_code_input = ""
            self._error = None
            return

        if (
            action is LobbyAction.CANCEL_ROOM
            and self._screen is LobbyScreen.WAITING_FOR_ROOM
            and self._network_client.room_code is not None
        ):
            self._network_client.cancel_room()
            self._cancel_pending = True
            return

        if (
            action is LobbyAction.EXIT
            and self._screen in {
                LobbyScreen.WELCOME,
                LobbyScreen.MENU,
                LobbyScreen.WAITING_FOR_MATCH,
            }
        ):
            self._exit_requested = True

    def append_room_code_character(self, character: str) -> None:
        """Append one ASCII letter or digit to the editable room code."""
        if (
            self._screen is LobbyScreen.JOIN_ROOM
            and len(character) == 1
            and character.isascii()
            and character.isalnum()
            and len(self._room_code_input) < 12
        ):
            self._room_code_input += character.upper()
            self._error = None

    def remove_room_code_character(self) -> None:
        """Remove the final room-code character on Backspace."""
        if self._screen is LobbyScreen.JOIN_ROOM:
            self._room_code_input = self._room_code_input[:-1]
            self._error = None

    def paste_room_code(self, text: str) -> None:
        """Replace the editable field with one validated clipboard value."""
        if self._screen is not LobbyScreen.JOIN_ROOM:
            return
        normalized = text.strip().upper() if isinstance(text, str) else ""
        if (
            not 4 <= len(normalized) <= 12
            or not normalized.isascii()
            or not normalized.isalnum()
        ):
            self._error = "Clipboard does not contain a valid room code"
            return
        self._room_code_input = normalized
        self._error = None
