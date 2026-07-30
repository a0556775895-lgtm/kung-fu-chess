"""Command-line entry point for the multiplayer WebSocket server."""
"""מחבר את כל התשתיות ויוצר את השרת סופית :)"""
import asyncio
import logging
from pathlib import Path

from app_logging import (
    close_managed_handlers,
    configure_rotating_logger,
    safe_filename_component,
)
from server import config
from server.dal.database import connect_database, init_schema
from server.dal.unit_of_work import SqliteUnitOfWork
from server.services.auth import AuthService
from server.services.game_completion import GameCompletionService
from server.logging.match_activity_logger import MatchActivityLogger
from server.transport.game_server import GameServer

logger = logging.getLogger(__name__)


def create_server(
    database_path: str | Path = config.DATABASE_PATH,
    *,
    match_logger_factory=None,
) -> GameServer:
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

    return GameServer(
        auth_service=AuthService(unit_of_work_factory),
        completion_service=GameCompletionService(unit_of_work_factory),
        match_logger_factory=match_logger_factory,
    )


def create_match_activity_logger(game_id: str) -> MatchActivityLogger:
    """Create the rotating logger owned by one production Match."""
    safe_game_id = safe_filename_component(game_id)
    activity_logger = configure_rotating_logger(
        f"kung_fu_chess.game.{safe_game_id}",
        config.GAME_LOG_DIRECTORY / f"game_{safe_game_id}.log",
        max_bytes=config.LOG_MAX_BYTES,
        backup_count=config.LOG_BACKUP_COUNT,
        include_console=False,
    )
    return MatchActivityLogger(game_id, activity_logger)


async def run_server() -> None:
    """Start the server, report its address, and keep it alive until stopped."""
    server = create_server(
        match_logger_factory=create_match_activity_logger,
    )
    await server.start()
    logger.info("server listening on port %d", server.bound_port)
    try:
        await server.serve_forever()
    finally:
        await server.close()


def main() -> None:
    """Configure logging and run the asynchronous server lifecycle."""
    application_logger = configure_rotating_logger(
        "server",
        config.SERVER_LOG_PATH,
        max_bytes=config.LOG_MAX_BYTES,
        backup_count=config.LOG_BACKUP_COUNT,
        include_console=True,
    )
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("server stopped")
    finally:
        close_managed_handlers(application_logger)


if __name__ == "__main__":  # pragma: no cover
    main()
