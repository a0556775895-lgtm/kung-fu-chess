from pathlib import Path

import winsound

from bus.event_bus import EventBus
from engine.events import Arrival, GameOver, GameStarted, JumpStarted, MotionStarted
from model.position import Position
from realtime.real_time_arbiter import ArrivalEvent
from view.audio.sound_player import SoundPlayer


def test_sound_player_maps_game_events_to_windows_wav_files(monkeypatch):
    played = []
    monkeypatch.setattr(
        winsound,
        "PlaySound",
        lambda path, flags: played.append((Path(path).name, flags)),
    )
    bus = EventBus()
    player = SoundPlayer(bus)
    piece = object()

    bus.publish(GameStarted())
    bus.publish(MotionStarted(piece, Position(0, 0), Position(0, 1), 1000))
    bus.publish(JumpStarted(piece, Position(0, 1)))
    bus.publish(Arrival(ArrivalEvent(
        piece, Position(0, 0), Position(0, 1), captured_piece=object()
    )))
    bus.publish(GameOver())

    assert [filename for filename, _flags in played] == [
        "opening.wav",
        "click.wav",
        "jump.wav",
        "eat.wav",
        "game_over.wav",
    ]
    assert all(
        flags == winsound.SND_FILENAME | winsound.SND_ASYNC
        for _filename, flags in played
    )

    player.close()


def test_plain_arrival_is_silent_and_close_stops_future_sounds(monkeypatch):
    played = []
    monkeypatch.setattr(
        winsound,
        "PlaySound",
        lambda path, flags: played.append((path, flags)),
    )
    bus = EventBus()
    player = SoundPlayer(bus)
    piece = object()

    bus.publish(Arrival(ArrivalEvent(
        piece, Position(0, 0), Position(0, 1), captured_piece=None
    )))
    player.close()
    player.close()
    bus.publish(GameStarted())

    assert played == []
