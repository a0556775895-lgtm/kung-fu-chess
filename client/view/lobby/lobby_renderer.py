"""Load and render the graphical lobby artwork."""

import cv2
import numpy as np

from client.view import config
from client.view.img import Img
from client.view.lobby.lobby_state import LobbyScreen, LobbyViewState


class LobbyRenderer:
    """Compose full lobby frames from static artwork and small text overlays."""

    def __init__(self):
        self._size = config.LOBBY_WINDOW_SIZE
        self._backgrounds = {
            LobbyScreen.WELCOME: self._load(config.WELCOME_IMAGE_PATH),
            LobbyScreen.MENU: self._load(config.LOBBY_MENU_IMAGE_PATH),
            LobbyScreen.JOIN_ROOM: self._load(config.JOIN_ROOM_IMAGE_PATH),
            LobbyScreen.WAITING_FOR_ROOM: self._load(
                config.ROOM_CREATED_IMAGE_PATH
            ),
        }
        self._waiting_frames = tuple(
            Img().read(path, (400, 600)).img
            for path in sorted(config.WAITING_ANIMATION_ROOT.glob("*.png"))
        )
        if not self._waiting_frames:
            raise FileNotFoundError("waiting_animation_frames_missing")

    def render(self, state: LobbyViewState, elapsed_ms: int) -> Img:
        """Return one complete frame for the supplied immutable view state."""
        background_screen = (
            LobbyScreen.MENU
            if state.screen is LobbyScreen.WAITING_FOR_MATCH
            else state.screen
        )
        canvas = Img()
        canvas.img = self._backgrounds[background_screen].img.copy()

        if state.screen is LobbyScreen.WAITING_FOR_MATCH:
            frame_index = (
                elapsed_ms // config.LOBBY_ANIMATION_FRAME_MS
            ) % len(self._waiting_frames)
            self._alpha_composite(
                canvas.img,
                self._waiting_frames[frame_index],
                280,
                20,
            )
        elif state.screen is LobbyScreen.JOIN_ROOM:
            self._draw_centered(
                canvas.img,
                state.room_code_input,
                center=(480, 307),
                font_scale=1.25,
                color=(55, 45, 35),
                thickness=3,
            )
        elif state.screen is LobbyScreen.WAITING_FOR_ROOM:
            room_code = state.created_room_code or "CREATING..."
            self._draw_centered(
                canvas.img,
                room_code,
                center=(455, 330),
                font_scale=1.35,
                color=(55, 45, 35),
                thickness=3,
            )

        if state.error:
            error_center = {
                LobbyScreen.MENU: (480, 615),
                LobbyScreen.JOIN_ROOM: (480, 350),
                LobbyScreen.WAITING_FOR_ROOM: (480, 420),
            }.get(state.screen, (480, 615))
            self._draw_centered(
                canvas.img,
                state.error,
                center=error_center,
                font_scale=0.55,
                color=(40, 40, 210),
                thickness=2,
            )
        return canvas

    def _load(self, path) -> Img:
        return Img().read(path, self._size)

    @staticmethod
    def _draw_centered(
        image,
        text: str,
        *,
        center: tuple[int, int],
        font_scale: float,
        color,
        thickness: int,
    ) -> None:
        text_size, _ = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            thickness,
        )
        x = center[0] - text_size[0] // 2
        y = center[1] + text_size[1] // 2
        cv2.putText(
            image,
            text,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )

    @staticmethod
    def _alpha_composite(background, overlay, x: int, y: int) -> None:
        """Blend one BGRA overlay without mutating either loaded asset."""
        height, width = overlay.shape[:2]
        target = background[y:y + height, x:x + width]
        if overlay.shape[2] == 3:
            target[:] = overlay
            return

        alpha = overlay[..., 3:4].astype(np.float32) / 255.0
        blended = (
            overlay[..., :3].astype(np.float32) * alpha
            + target.astype(np.float32) * (1.0 - alpha)
        )
        target[:] = blended.astype(np.uint8)
