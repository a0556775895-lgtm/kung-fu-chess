"""Unit tests for queue accounting used by the connection writer."""

import asyncio

from server.transport.connection import ConnectionContext, ConnectionRole


def test_dropping_oldest_message_keeps_queue_join_accounting_balanced():
    async def scenario():
        context = ConnectionContext(
            connection_id="slow",
            game_id="default",
            role=ConnectionRole.PLAYER,
            outbound=asyncio.Queue(maxsize=1),
        )
        context.enqueue("old")
        context.enqueue("new")

        assert context.outbound.get_nowait() == "new"
        context.outbound.task_done()
        await asyncio.wait_for(context.outbound.join(), timeout=0.1)
        assert context.dropped_messages == 1

    asyncio.run(scenario())
