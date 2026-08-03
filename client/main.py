"""Command-line entry point for one graphical multiplayer client."""
"""אחראי להרכיב את כל רכיבי הלקוח"""
import argparse
import logging

from networking.logging_utils import (
    close_managed_handlers,
    configure_rotating_logger,
    safe_filename_component,
)
from client import config as client_config
from client.cli_auth import AuthAction, AuthCredentials, prompt_credentials
from client.lobby_controller import LobbyController
from client.network_client import (
    AuthenticationRejectedError,
    ConnectionState,
    NetworkClient,
)
from client.network_event_adapter import NetworkEventAdapter
from client.remote_game_engine_proxy import RemoteGameEngineProxy
from client.view.display_manager import DisplayManager
from client.view.lobby.lobby_display import LobbyDisplay
from client.view.hud.connection_status.connection_status_renderer import (
    ConnectionNotice,
    ConnectionStatusRenderer,
)


DEFAULT_SERVER_URI = "ws://127.0.0.1:8765"
logger = logging.getLogger(__name__)


def run_client(
    credentials: AuthCredentials,
    server_uri: str = DEFAULT_SERVER_URI,
) -> None:
    """Connect, compose the remote game view, and close networking on exit."""
    network_client = NetworkClient(
        server_uri,
        credentials.username,
        credentials.password,
        register=credentials.action is AuthAction.REGISTER,
    )
    network_client.authenticate()
    logger.info(
        "client authenticated user_id=%s username=%s",
        network_client.auth_response.user_id,
        network_client.auth_response.username,
    )
    try:
        lobby = LobbyDisplay(LobbyController(network_client))
        if not lobby.run():
            return

        proxy = RemoteGameEngineProxy(network_client)
        logger.info(
            "game view opened game_id=%s role=%s",
            network_client.initial_state.game_id,
            network_client.initial_state.role,
        )
        event_adapter = NetworkEventAdapter()

        def update_remote_game(_dt_ms: int) -> None:
            """Pump ordered server messages without advancing authoritative time."""
            proxy.process_network_messages()
            for event in proxy.drain_events():
                event_adapter.publish(event)

        def connection_notice():
            """Combine local transport and opponent lifecycle into one overlay."""
            status = network_client.connection_status
            if status.state is ConnectionState.RECONNECTING:
                return ConnectionNotice(
                    "Reconnecting...",
                    status.seconds_remaining,
                )
            if status.state is ConnectionState.FAILED:
                return ConnectionNotice("Reconnect failed")
            opponent_seconds = proxy.opponent_reconnect_seconds
            if opponent_seconds is not None:
                return ConnectionNotice(
                    (
                        "Opponent disconnected"
                        if proxy.can_control
                        else "Player disconnected"
                    ),
                    opponent_seconds,
                )
            if not proxy.can_control:
                room_code = network_client.room_code
                return ConnectionNotice(
                    (
                        f"Spectating room {room_code}"
                        if room_code is not None
                        else "Spectating"
                    )
                )
            return None

        display = DisplayManager(
            proxy.board,
            proxy,
            game_updater=update_remote_game,
            event_source=event_adapter,
            starts_game=False,
            input_enabled=proxy.can_control,
            extra_renderers=(
                ConnectionStatusRenderer(connection_notice),
            ),
        )
        display.run()
    finally:
        logger.info("client connection closing username=%s", credentials.username)
        network_client.close()


def main(argv=None) -> None:
    """Parse the server address and launch one graphical client process."""
    parser = argparse.ArgumentParser(description="Kung Fu Chess network client")
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER_URI,
        help=f"WebSocket server URI (default: {DEFAULT_SERVER_URI})",
    )
    args = parser.parse_args(argv)
    credentials = prompt_credentials()
    safe_username = safe_filename_component(credentials.username)
    application_logger = configure_rotating_logger(
        "client",
        client_config.LOG_DIRECTORY / f"client_{safe_username}.log",
        max_bytes=client_config.LOG_MAX_BYTES,
        backup_count=client_config.LOG_BACKUP_COUNT,
        include_console=True,
    )
    try:
        run_client(credentials, args.server)
    except AuthenticationRejectedError as exc:
        logger.error("authentication rejected: %s", exc.reason)
    except KeyboardInterrupt:
        logger.info("client stopped")
    finally:
        close_managed_handlers(application_logger)


if __name__ == "__main__":  # pragma: no cover
    main()
