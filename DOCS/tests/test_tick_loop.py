"""Tests for the simple server-wide authoritative tick loop."""

import asyncio

import pytest

from server.game.tick_loop import advance_matches, run_tick_loop


class _RecordingMatch:
    def __init__(self):
        self.steps = []
        self.broadcasts = 0

    def advance_time(self, milliseconds):
        self.steps.append(milliseconds)

    def broadcast_state(self):
        self.broadcasts += 1


class _Registry:
    def __init__(self, *matches):
        self._matches = matches

    def values(self):
        return self._matches


def test_advance_matches_chunks_delay_and_broadcasts_once():
    first = _RecordingMatch()
    second = _RecordingMatch()

    advance_matches(_Registry(first, second), elapsed_ms=130, max_step_ms=50)

    assert first.steps == [50, 50, 30]
    assert second.steps == [50, 50, 30]
    assert first.broadcasts == second.broadcasts == 1


def test_advance_matches_rejects_invalid_time_values():
    with pytest.raises(ValueError, match="NEGATIVE_ELAPSED_TIME"):
        advance_matches(_Registry(), elapsed_ms=-1, max_step_ms=50)
    with pytest.raises(ValueError, match="INVALID_MAX_TICK_STEP"):
        advance_matches(_Registry(), elapsed_ms=10, max_step_ms=0)


def test_tick_loop_carries_fractional_milliseconds_forward():
    class _StopLoop(Exception):
        pass

    async def scenario():
        match = _RecordingMatch()
        times = iter((10.0, 10.0497, 10.0994))
        sleep_calls = 0

        def clock():
            return next(times)

        async def fake_sleep(_):
            nonlocal sleep_calls
            sleep_calls += 1
            if sleep_calls == 3:
                raise _StopLoop

        with pytest.raises(_StopLoop):
            await run_tick_loop(
                _Registry(match),
                interval_ms=50,
                max_step_ms=50,
                clock=clock,
                sleep=fake_sleep,
            )

        assert match.steps == [49, 50]
        assert match.broadcasts == 2

    asyncio.run(scenario())
