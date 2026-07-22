"""One monotonic authoritative tick loop for all active Matches."""

import asyncio
import time

from server import config


async def run_tick_loop(
    registry,
    interval_ms: int = config.TICK_INTERVAL_MS,
    max_step_ms: int = config.MAX_TICK_STEP_MS,
    clock=time.monotonic,
    sleep=asyncio.sleep,
) -> None:
    """Measure real elapsed time, preserve fractions, and advance all Matches."""
    last_time = clock()
    remainder_ms = 0.0

    while True:
        await sleep(interval_ms / 1000)
        now = clock()
        elapsed_ms = (now - last_time) * 1000 + remainder_ms
        last_time = now

        whole_ms = int(elapsed_ms)
        remainder_ms = elapsed_ms - whole_ms
        if whole_ms > 0:
            advance_matches(registry, whole_ms, max_step_ms)


def advance_matches(registry, elapsed_ms: int, max_step_ms: int) -> None:
    """Advance a stable Match snapshot in bounded steps, then broadcast one STATE."""
    if elapsed_ms < 0:
        raise ValueError("NEGATIVE_ELAPSED_TIME")
    if max_step_ms <= 0:
        raise ValueError("INVALID_MAX_TICK_STEP")
    if elapsed_ms == 0:
        return

    matches = registry.values()
    remaining_ms = elapsed_ms
    while remaining_ms > 0:
        step_ms = min(remaining_ms, max_step_ms)
        for match in matches:
            match.advance_time(step_ms)
        remaining_ms -= step_ms

    for match in matches:
        match.broadcast_state()
