"""Tests for the graphical lobby state machine, layout, and presentation."""

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from client.lobby_controller import LobbyController
from client.network_client import ConnectionState, ConnectionStatus
from view import config
from view.lobby import clipboard
from view.lobby.lobby_display import LobbyDisplay
from view.lobby.lobby_layout import (
    HITBOXES,
    Hitbox,
    action_at,
)
from view.lobby.lobby_renderer import LobbyRenderer
from view.lobby.lobby_state import (
    LobbyAction,
    LobbyScreen,
    LobbyViewState,
)


class _FakeLobbyNetwork:
    def __init__(self):
        self.state = ConnectionState.LOBBY
        self.room_code = None
        self.lobby_error = None
        self.failure = None
        self.calls = []

    @property
    def connection_status(self):
        return ConnectionStatus(self.state)

    def start_matchmaking(self):
        self.calls.append(("match",))

    def create_room(self):
        self.calls.append(("create",))

    def join_room(self, room_code):
        self.calls.append(("join", room_code))

    def cancel_room(self):
        self.calls.append(("cancel",))


def test_lobby_controller_runs_quick_match_and_reports_ready():
    network = _FakeLobbyNetwork()
    controller = LobbyController(network)

    assert controller.view_state.screen is LobbyScreen.WELCOME
    assert not controller.exit_requested
    controller.handle_action(LobbyAction.START)
    controller.handle_action(LobbyAction.QUICK_MATCH)

    assert network.calls == [("match",)]
    assert controller.view_state.screen is LobbyScreen.WAITING_FOR_MATCH
    assert not controller.update()

    network.state = ConnectionState.CONNECTED
    assert controller.update()


def test_lobby_controller_creates_and_cancels_room():
    network = _FakeLobbyNetwork()
    controller = LobbyController(network)
    controller.handle_action(LobbyAction.START)
    controller.handle_action(LobbyAction.CREATE_ROOM)

    assert network.calls == [("create",)]
    assert controller.view_state.created_room_code is None
    controller.handle_action(LobbyAction.CANCEL_ROOM)
    assert network.calls == [("create",)]

    network.room_code = "AB12"
    assert controller.view_state.created_room_code == "AB12"
    controller.handle_action(LobbyAction.CANCEL_ROOM)
    assert network.calls[-1] == ("cancel",)

    network.state = ConnectionState.LOBBY
    network.room_code = None
    controller.update()
    assert controller.view_state == LobbyViewState(LobbyScreen.MENU)


def test_lobby_controller_edits_joins_and_recovers_from_room_error():
    network = _FakeLobbyNetwork()
    controller = LobbyController(network)
    controller.handle_action(LobbyAction.START)
    controller.handle_action(LobbyAction.SHOW_JOIN_ROOM)

    controller.append_room_code_character("-")
    controller.append_room_code_character("a")
    controller.append_room_code_character("b")
    controller.handle_action(LobbyAction.SUBMIT_ROOM_CODE)
    assert "4-12" in controller.view_state.error

    controller.append_room_code_character("1")
    controller.append_room_code_character("2")
    controller.remove_room_code_character()
    controller.append_room_code_character("2")
    controller.handle_action(LobbyAction.SUBMIT_ROOM_CODE)

    assert network.calls == [("join", "AB12")]
    assert controller.view_state.screen is LobbyScreen.WAITING_FOR_MATCH

    network.lobby_error = "room_not_found"
    controller.update()
    assert controller.view_state.screen is LobbyScreen.JOIN_ROOM
    assert controller.view_state.error == "room_not_found"

    controller.append_room_code_character("3")
    controller.update()
    assert controller.view_state.screen is LobbyScreen.JOIN_ROOM

    network.lobby_error = None
    controller.handle_action(LobbyAction.BACK)
    assert controller.view_state == LobbyViewState(LobbyScreen.MENU)


def test_lobby_controller_limits_input_and_handles_failures_and_exit():
    network = _FakeLobbyNetwork()
    controller = LobbyController(network)
    controller.handle_action(LobbyAction.START)
    controller.handle_action(LobbyAction.SHOW_JOIN_ROOM)
    for character in "abcdefghijklmnop":
        controller.append_room_code_character(character)
    assert controller.view_state.room_code_input == "ABCDEFGHIJKL"

    network.failure = ValueError("socket failed")
    network.state = ConnectionState.FAILED
    with pytest.raises(ConnectionError, match="lobby_connection_failed"):
        controller.update()

    for screen_setup in (
        (),
        (LobbyAction.START,),
        (LobbyAction.START, LobbyAction.QUICK_MATCH),
    ):
        candidate = LobbyController(_FakeLobbyNetwork())
        for action in screen_setup:
            candidate.handle_action(action)
        candidate.handle_action(LobbyAction.EXIT)
        assert candidate.exit_requested


def test_lobby_controller_returns_create_error_to_menu():
    network = _FakeLobbyNetwork()
    controller = LobbyController(network)
    controller.handle_action(LobbyAction.START)
    controller.handle_action(LobbyAction.CREATE_ROOM)
    network.lobby_error = "room_limit_reached"

    controller.update()

    assert controller.view_state.screen is LobbyScreen.MENU
    assert controller.view_state.error == "room_limit_reached"


def test_lobby_controller_shows_friendly_match_timeout():
    network = _FakeLobbyNetwork()
    controller = LobbyController(network)
    controller.handle_action(LobbyAction.START)
    controller.handle_action(LobbyAction.QUICK_MATCH)
    network.state = ConnectionState.LOBBY
    network.lobby_error = "match_timeout"

    controller.update()

    assert controller.view_state.screen is LobbyScreen.MENU
    assert controller.view_state.error == (
        "No opponent found. Please try again."
    )


def test_lobby_controller_keeps_room_visible_when_cancel_is_rejected():
    network = _FakeLobbyNetwork()
    controller = LobbyController(network)
    controller.handle_action(LobbyAction.START)
    controller.handle_action(LobbyAction.CREATE_ROOM)
    network.state = ConnectionState.WAITING_IN_ROOM
    network.room_code = "AB12"
    network.lobby_error = "room_not_owned"

    controller.update()

    assert controller.view_state.screen is LobbyScreen.WAITING_FOR_ROOM
    assert controller.view_state.error == "room_not_owned"


def test_lobby_layout_scales_reference_hitboxes():
    start = HITBOXES[LobbyScreen.WELCOME][0]
    assert start.contains(480, 540, 960, 640)
    assert not start.contains(10, 10, 960, 640)
    assert (
        action_at(LobbyScreen.MENU, 480, 365, 960, 640)
        is LobbyAction.CREATE_ROOM
    )
    assert action_at(LobbyScreen.MENU, 10, 10, 960, 640) is None
    assert action_at(LobbyScreen.WAITING_FOR_MATCH, 480, 560, 960, 640) is (
        LobbyAction.EXIT
    )
    assert action_at(LobbyScreen.WAITING_FOR_ROOM, 720, 330, 960, 640) is (
        LobbyAction.COPY_ROOM_CODE
    )


def test_lobby_clipboard_uses_windows_clip_without_shell(monkeypatch):
    captured = {}

    def fake_run(command, **options):
        captured.update(command=command, options=options)

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)
    clipboard.copy_text("AB12")

    assert captured["command"] == ["clip"]
    assert captured["options"]["input"] == "AB12"
    assert captured["options"]["check"] is True


def test_lobby_renderer_draws_every_screen_and_animation_frame():
    renderer = LobbyRenderer()
    expected_shape = (
        config.LOBBY_WINDOW_SIZE[1],
        config.LOBBY_WINDOW_SIZE[0],
        3,
    )

    welcome = renderer.render(LobbyViewState(LobbyScreen.WELCOME), 0)
    menu = renderer.render(
        LobbyViewState(LobbyScreen.MENU, error="Try again"),
        0,
    )
    join = renderer.render(
        LobbyViewState(LobbyScreen.JOIN_ROOM, "AB12"),
        0,
    )
    room = renderer.render(
        LobbyViewState(
            LobbyScreen.WAITING_FOR_ROOM,
            created_room_code="CD34",
        ),
        0,
    )
    creating = renderer.render(
        LobbyViewState(LobbyScreen.WAITING_FOR_ROOM),
        0,
    )
    waiting_first = renderer.render(
        LobbyViewState(LobbyScreen.WAITING_FOR_MATCH),
        0,
    )
    waiting_second = renderer.render(
        LobbyViewState(LobbyScreen.WAITING_FOR_MATCH),
        config.LOBBY_ANIMATION_FRAME_MS,
    )

    assert all(
        frame.img.shape == expected_shape
        for frame in (welcome, menu, join, room, creating, waiting_first)
    )
    assert not np.array_equal(waiting_first.img, waiting_second.img)


def test_lobby_renderer_requires_waiting_animation_frames(monkeypatch):
    empty_root = SimpleNamespace(glob=lambda _pattern: ())
    monkeypatch.setattr(config, "WAITING_ANIMATION_ROOT", empty_root)
    with pytest.raises(
        FileNotFoundError,
        match="waiting_animation_frames_missing",
    ):
        LobbyRenderer()


def test_lobby_renderer_alpha_composite_supports_rgb_and_rgba():
    background = np.zeros((2, 2, 3), dtype=np.uint8)
    rgb = np.full((1, 1, 3), 100, dtype=np.uint8)
    LobbyRenderer._alpha_composite(background, rgb, 0, 0)
    assert tuple(background[0, 0]) == (100, 100, 100)

    rgba = np.array([[[200, 100, 50, 128]]], dtype=np.uint8)
    LobbyRenderer._alpha_composite(background, rgba, 1, 1)
    assert tuple(background[1, 1]) == (100, 50, 25)


class _RecordingLobbyController:
    def __init__(self, screen=LobbyScreen.MENU):
        self.screen = screen
        self.room_code = None
        self.exit_requested = False
        self.actions = []
        self.characters = []
        self.removed = 0
        self.ready = False

    @property
    def view_state(self):
        return LobbyViewState(
            self.screen,
            created_room_code=self.room_code,
        )

    def update(self):
        return self.ready

    def handle_action(self, action):
        self.actions.append(action)
        if action is LobbyAction.EXIT:
            self.exit_requested = True

    def append_room_code_character(self, character):
        self.characters.append(character)

    def remove_room_code_character(self):
        self.removed += 1


class _FakeLobbyRenderer:
    def render(self, _state, _elapsed_ms):
        return SimpleNamespace(img=np.zeros((640, 960, 3), dtype=np.uint8))


def test_lobby_display_runs_until_exit_and_releases_window(monkeypatch):
    controller = _RecordingLobbyController()
    display = LobbyDisplay(controller, _FakeLobbyRenderer())
    destroyed = []
    monkeypatch.setattr(cv2, "namedWindow", lambda *_args: None)
    monkeypatch.setattr(cv2, "setMouseCallback", lambda *_args: None)
    monkeypatch.setattr(cv2, "getTickCount", lambda: 10)
    monkeypatch.setattr(cv2, "getTickFrequency", lambda: 1.0)
    monkeypatch.setattr(cv2, "imshow", lambda *_args: None)
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: 27)
    monkeypatch.setattr(cv2, "destroyWindow", destroyed.append)

    assert not display.run()
    assert controller.actions == [LobbyAction.EXIT]
    assert destroyed == ["KungFu Chess"]


def test_lobby_display_returns_when_game_is_ready(monkeypatch):
    controller = _RecordingLobbyController()
    controller.ready = True
    display = LobbyDisplay(controller, _FakeLobbyRenderer())
    monkeypatch.setattr(cv2, "namedWindow", lambda *_args: None)
    monkeypatch.setattr(cv2, "setMouseCallback", lambda *_args: None)
    monkeypatch.setattr(cv2, "getTickCount", lambda: 10)
    monkeypatch.setattr(cv2, "getTickFrequency", lambda: 1.0)
    monkeypatch.setattr(cv2, "destroyWindow", lambda _name: None)

    assert display.run()


def test_lobby_display_translates_mouse_and_keyboard():
    controller = _RecordingLobbyController()
    copied = []
    display = LobbyDisplay(
        controller,
        _FakeLobbyRenderer(),
        clipboard_writer=copied.append,
    )

    display._on_mouse(cv2.EVENT_RBUTTONDOWN, 480, 365, 0, None)
    display._on_mouse(cv2.EVENT_LBUTTONDOWN, 10, 10, 0, None)
    display._on_mouse(cv2.EVENT_LBUTTONDOWN, 480, 365, 0, None)
    assert controller.actions == [LobbyAction.CREATE_ROOM]

    controller.screen = LobbyScreen.WAITING_FOR_ROOM
    display._on_mouse(cv2.EVENT_LBUTTONDOWN, 720, 330, 0, None)
    assert copied == []
    controller.room_code = "AB12"
    display._on_mouse(cv2.EVENT_LBUTTONDOWN, 720, 330, 0, None)
    assert copied == ["AB12"]

    display._handle_key(-1)
    display._handle_key(13)
    display._handle_key(8)
    display._handle_key(ord("a"))
    assert controller.actions[-1] is LobbyAction.SUBMIT_ROOM_CODE
    assert controller.removed == 1
    assert controller.characters == ["a"]

    controller.screen = LobbyScreen.JOIN_ROOM
    display._handle_key(27)
    controller.screen = LobbyScreen.WAITING_FOR_ROOM
    display._handle_key(27)
    assert controller.actions[-2:] == [
        LobbyAction.BACK,
        LobbyAction.CANCEL_ROOM,
    ]
