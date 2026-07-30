"""OpenCV window loop for the pre-game graphical lobby."""

import cv2

from view import config
from view.lobby.clipboard import copy_text
from view.lobby.lobby_layout import action_at
from view.lobby.lobby_renderer import LobbyRenderer
from view.lobby.lobby_state import LobbyAction, LobbyScreen


WINDOW_NAME = "KungFu Chess"


class LobbyDisplay:
    """Translate mouse and keyboard input into semantic controller actions."""

    def __init__(self, controller, renderer=None, clipboard_writer=None):
        self._controller = controller
        self._renderer = renderer or LobbyRenderer()
        self._clipboard_writer = clipboard_writer or copy_text
        self._width, self._height = config.LOBBY_WINDOW_SIZE
        self._window_created = False

    def run(self) -> bool:
        """Show lobby screens until a game is ready or the user exits."""
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
        self._window_created = True
        cv2.setMouseCallback(WINDOW_NAME, self._on_mouse)
        started_at = cv2.getTickCount()
        tick_frequency = cv2.getTickFrequency()

        try:
            while not self._controller.exit_requested:
                if self._controller.update():
                    return True

                elapsed_ms = int(
                    (cv2.getTickCount() - started_at)
                    / tick_frequency
                    * 1000
                )
                frame = self._renderer.render(
                    self._controller.view_state,
                    elapsed_ms,
                )
                cv2.imshow(WINDOW_NAME, frame.img)
                key = cv2.waitKey(config.FRAME_DELAY_MS)
                self._handle_key(key)
            return False
        finally:
            if self._window_created:
                cv2.destroyWindow(WINDOW_NAME)
                self._window_created = False

    def _on_mouse(self, event, x, y, _flags, _parameter) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        action = action_at(
            self._controller.view_state.screen,
            x,
            y,
            self._width,
            self._height,
        )
        if action is not None:
            if action is LobbyAction.COPY_ROOM_CODE:
                room_code = self._controller.view_state.created_room_code
                if room_code is not None:
                    self._clipboard_writer(room_code)
            else:
                self._controller.handle_action(action)

    def _handle_key(self, key: int) -> None:
        if key < 0:
            return
        key &= 0xFF
        screen = self._controller.view_state.screen

        if key == 27:
            if screen is LobbyScreen.JOIN_ROOM:
                action = LobbyAction.BACK
            elif screen is LobbyScreen.WAITING_FOR_ROOM:
                action = LobbyAction.CANCEL_ROOM
            else:
                action = LobbyAction.EXIT
            self._controller.handle_action(action)
        elif key in (10, 13):
            self._controller.handle_action(LobbyAction.SUBMIT_ROOM_CODE)
        elif key in (8, 127):
            self._controller.remove_room_code_character()
        elif 32 <= key <= 126:
            self._controller.append_room_code_character(chr(key))
