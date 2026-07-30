"""Focused tests for DisplayManager's injected game-update boundary."""

from types import SimpleNamespace

from model.position import Position
from view.display_manager import DisplayManager


def test_display_update_uses_injected_updater_and_remote_snapshot():
    calls = []
    snapshot = object()
    display = DisplayManager.__new__(DisplayManager)
    display._moves_log_data = SimpleNamespace(tick=lambda dt: calls.append(("tick", dt)))
    display._game_updater = lambda dt: calls.append(("update_game", dt))
    display._controller = SimpleNamespace(selected_position=Position(3, 2))
    display._game_engine = SimpleNamespace(
        snapshot=lambda selected: calls.append(("snapshot", selected)) or snapshot
    )
    display._piece_animator = SimpleNamespace(
        update=lambda dt, state: calls.append(("animate", dt, state))
    )

    display.update(16)

    assert calls == [
        ("tick", 16),
        ("update_game", 16),
        ("snapshot", Position(3, 2)),
        ("animate", 16, snapshot),
    ]
    assert display._last_snapshot is snapshot


def test_display_ignores_mouse_input_while_spectating():
    display = DisplayManager.__new__(DisplayManager)
    display._input_enabled = False
    display._extractor = SimpleNamespace(
        extract_left_click=lambda *_args: (_ for _ in ()).throw(
            AssertionError("spectator input was parsed")
        )
    )
    display._command_sender = SimpleNamespace(
        send=lambda _command: (_ for _ in ()).throw(
            AssertionError("spectator command was sent")
        )
    )

    display._on_mouse(1, 10, 10, 0, None)
