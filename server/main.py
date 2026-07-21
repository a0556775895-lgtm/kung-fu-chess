"""Command-line entry point for the multiplayer WebSocket server."""

import asyncio
import logging

from server.transport.game_server import GameServer

logger = logging.getLogger(__name__)


async def run_server() -> None:
    """Start the server, report its address, and keep it alive until stopped."""
    server = GameServer()
    await server.start()
    logger.info("server listening on port %d", server.bound_port)
    try:
        await server.serve_forever()
    finally:
        await server.close()


def main() -> None:
    """Configure logging and run the asynchronous server lifecycle."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("server stopped")


if __name__ == "__main__":  # pragma: no cover
    main()
