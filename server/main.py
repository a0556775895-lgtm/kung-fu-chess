"""Command-line entry point for the multiplayer WebSocket server."""
"""מחבר את כל התשתיות ויוצר את השרת סופית :)"""
import asyncio
import logging
from pathlib import Path

from server import config
from server.dal.database import connect_database, init_schema
from server.dal.unit_of_work import SqliteUnitOfWork
from server.services.auth import AuthService
from server.transport.game_server import GameServer

logger = logging.getLogger(__name__)


def create_server(database_path: str | Path = config.DATABASE_PATH) -> GameServer:
    """Compose a persistent AuthService and the WebSocket transport."""
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    schema_connection = connect_database(database_path)
    try:
        init_schema(schema_connection)
        schema_connection.commit()
    finally:
        schema_connection.close()

    def unit_of_work_factory():
        return SqliteUnitOfWork(
            connect_database(database_path),
            close_connection=True,
        )

    return GameServer(auth_service=AuthService(unit_of_work_factory))


async def run_server() -> None:
    """Start the server, report its address, and keep it alive until stopped."""
    server = create_server()
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
