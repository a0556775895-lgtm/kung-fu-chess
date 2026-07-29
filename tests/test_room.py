"""Unit tests for the F1 room model and its in-memory registry."""

import pytest

from boardio.board_factory import STANDARD_GAME_CONFIG, create_board
from engine.game_engine import GameEngine
from model.piece import PieceColor
from server.game.game_result import FinishReason, GameResult
from server.game.match import Match
from server.game.room import Room, RoomStatus
from server.game.room_registry import RoomRegistry


def _make_match(game_id="room-game") -> Match:
    return Match(
        game_id,
        GameEngine(create_board(STANDARD_GAME_CONFIG)),
        STANDARD_GAME_CONFIG,
    )


def _make_room(room_code="AB12") -> Room:
    return Room(room_code, "creator-token", STANDARD_GAME_CONFIG)


def test_room_derives_waiting_active_and_finished_status():
    room = _make_room()
    match = _make_match()

    assert room.status is RoomStatus.WAITING
    assert room.match is None

    room.attach_match(match)

    assert room.status is RoomStatus.ACTIVE
    assert room.match is match

    match.finish(GameResult(PieceColor.WHITE, FinishReason.RESIGN, 60_000))

    assert room.status is RoomStatus.FINISHED


def test_room_can_cancel_only_before_a_match_is_attached():
    room = _make_room()

    assert room.cancel() is True
    assert room.status is RoomStatus.CANCELLED
    assert room.cancel() is False

    with pytest.raises(ValueError, match="ROOM_CANCELLED"):
        room.attach_match(_make_match())

    active_room = _make_room("CD34")
    active_room.attach_match(_make_match("active-game"))

    with pytest.raises(ValueError, match="ROOM_ALREADY_ACTIVE"):
        active_room.cancel()


@pytest.mark.parametrize("room_code", ["abc1", "ABC", "ABCDEFGHIJKLM", "AB-1", 1234])
def test_room_rejects_invalid_codes(room_code):
    with pytest.raises(ValueError, match="INVALID_ROOM_CODE"):
        Room(room_code, "token", STANDARD_GAME_CONFIG)


@pytest.mark.parametrize("creator_token", ["", None, "x" * 257])
def test_room_rejects_invalid_creator_tokens(creator_token):
    with pytest.raises(ValueError, match="INVALID_CREATOR_TOKEN"):
        Room("AB12", creator_token, STANDARD_GAME_CONFIG)


def test_room_rejects_invalid_config_match_and_second_match():
    with pytest.raises(ValueError, match="INVALID_GAME_CONFIG"):
        Room("AB12", "token", object())

    room = _make_room()
    with pytest.raises(ValueError, match="INVALID_MATCH"):
        room.attach_match(object())

    room.attach_match(_make_match())
    with pytest.raises(ValueError, match="ROOM_ALREADY_ACTIVE"):
        room.attach_match(_make_match("other-game"))


def test_room_registry_adds_lists_finds_and_removes_rooms():
    registry = RoomRegistry()
    first = _make_room()
    second = _make_room("CD34")

    registry.add(first)
    registry.add(second)

    assert len(registry) == 2
    assert "AB12" in registry
    assert registry.get("AB12") is first
    assert registry.values() == (first, second)
    assert registry.remove("AB12") is first
    assert "AB12" not in registry


def test_room_registry_rejects_invalid_duplicate_and_missing_values():
    registry = RoomRegistry()
    room = _make_room()

    with pytest.raises(ValueError, match="INVALID_ROOM"):
        registry.add(object())

    registry.add(room)
    with pytest.raises(ValueError, match="ROOM_ALREADY_EXISTS"):
        registry.add(room)

    with pytest.raises(KeyError, match="ROOM_NOT_FOUND"):
        registry.get("MISSING")
    with pytest.raises(KeyError, match="ROOM_NOT_FOUND"):
        registry.remove("MISSING")
