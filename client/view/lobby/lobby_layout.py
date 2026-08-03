"""Reference-space hitboxes aligned with the 1536x1024 lobby artwork."""

from dataclasses import dataclass

from client.view.lobby.lobby_state import LobbyAction, LobbyScreen


REFERENCE_WIDTH = 1536
REFERENCE_HEIGHT = 1024


@dataclass(frozen=True, slots=True)
class Hitbox:
    """One clickable rectangle expressed in original artwork pixels."""

    left: int
    top: int
    right: int
    bottom: int
    action: LobbyAction

    def contains(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> bool:
        """Test a window-space point after scaling it to reference space."""
        reference_x = x * REFERENCE_WIDTH / width
        reference_y = y * REFERENCE_HEIGHT / height
        return (
            self.left <= reference_x <= self.right
            and self.top <= reference_y <= self.bottom
        )


HITBOXES = {
    LobbyScreen.WELCOME: (
        Hitbox(455, 750, 1085, 965, LobbyAction.START),
    ),
    LobbyScreen.MENU: (
        Hitbox(400, 380, 1135, 510, LobbyAction.QUICK_MATCH),
        Hitbox(400, 520, 1135, 655, LobbyAction.CREATE_ROOM),
        Hitbox(400, 660, 1135, 795, LobbyAction.SHOW_JOIN_ROOM),
        Hitbox(400, 800, 1135, 935, LobbyAction.EXIT),
    ),
    LobbyScreen.JOIN_ROOM: (
        Hitbox(485, 580, 1045, 755, LobbyAction.SUBMIT_ROOM_CODE),
        Hitbox(470, 755, 1050, 930, LobbyAction.BACK),
    ),
    LobbyScreen.WAITING_FOR_ROOM: (
        Hitbox(1080, 445, 1230, 610, LobbyAction.COPY_ROOM_CODE),
        Hitbox(470, 685, 1045, 865, LobbyAction.CANCEL_ROOM),
    ),
    LobbyScreen.WAITING_FOR_MATCH: (
        Hitbox(520, 805, 1015, 965, LobbyAction.EXIT),
    ),
}


def action_at(
    screen: LobbyScreen,
    x: int,
    y: int,
    width: int,
    height: int,
) -> LobbyAction | None:
    """Return the first semantic action whose scaled hitbox was clicked."""
    for hitbox in HITBOXES.get(screen, ()):
        if hitbox.contains(x, y, width, height):
            return hitbox.action
    return None
