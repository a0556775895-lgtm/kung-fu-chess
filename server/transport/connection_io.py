"""Coordinated reader and single-writer loops for an admitted connection."""

import asyncio


async def run_connection_io(context, controller) -> None:
    """Run reader and writer together; stop both when either side finishes."""
    reader = asyncio.create_task(
        _reader_loop(context, controller),
        name=f"reader-{context.connection_id}",
    )
    writer = asyncio.create_task(
        _writer_loop(context),
        name=f"writer-{context.connection_id}",
    )
    tasks = {reader, writer}

    done = set()
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    for task in done:
        exception = task.exception()
        if exception is not None:
            raise exception


async def _reader_loop(context, controller) -> None:
    """Read client commands and queue their correlated controller responses."""
    async for message in context.websocket:
        context.enqueue(controller.handle_message(context, message))


async def _writer_loop(context) -> None:
    """Be the sole owner of websocket.send for one admitted connection."""
    while True:
        message = await context.outbound.get()
        try:
            await context.websocket.send(message)
        finally:
            context.outbound.task_done()
