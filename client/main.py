"""Command-line entry point for one graphical multiplayer client."""

import argparse
import logging

from client.network_client import NetworkClient
from client.network_event_adapter import NetworkEventAdapter
from client.remote_game_engine_proxy import RemoteGameEngineProxy
from view.display_manager import DisplayManager


DEFAULT_SERVER_URI = "ws://127.0.0.1:8765"
logger = logging.getLogger(__name__)


def run_client(server_uri: str = DEFAULT_SERVER_URI) -> None:
    """Connect, compose the remote game view, and close networking on exit."""
    network_client = NetworkClient(server_uri)
    network_client.start()
    try:
        proxy = RemoteGameEngineProxy(network_client)
        event_adapter = NetworkEventAdapter()

        def update_remote_game(_dt_ms: int) -> None:
            """Pump ordered server messages without advancing authoritative time."""
            proxy.process_network_messages()
            for event in proxy.drain_events():
                event_adapter.publish(event)
            if not network_client.is_connected:
                raise ConnectionError("server_connection_closed") from network_client.failure

        display = DisplayManager(
            proxy.board,
            proxy,
            game_updater=update_remote_game,
            event_source=event_adapter,
            starts_game=False,
        )
        display.run()
    finally:
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        run_client(args.server)
    except KeyboardInterrupt:
        logger.info("client stopped")


if __name__ == "__main__":  # pragma: no cover
    main()
