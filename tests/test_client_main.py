"""Composition tests for the graphical network-client entry point."""

import pytest

import client.main as client_main


class _FakeNetworkClient:
    instances = []

    def __init__(self, uri):
        self.uri = uri
        self.started = False
        self.closed = False
        self.is_connected = True
        self.failure = None
        self.instances.append(self)

    def start(self):
        self.started = True

    def close(self):
        self.closed = True


class _FakeProxy:
    def __init__(self, network_client):
        self.network_client = network_client
        self.board = object()
        self.processed = 0

    def process_network_messages(self):
        self.processed += 1

    def drain_events(self):
        return []


def test_run_client_composes_remote_display_and_closes_network(monkeypatch):
    captured = {}

    class FakeDisplay:
        def __init__(self, board, proxy, **options):
            captured.update(board=board, proxy=proxy, options=options)

        def run(self):
            captured["options"]["game_updater"](16)

    _FakeNetworkClient.instances = []
    monkeypatch.setattr(client_main, "NetworkClient", _FakeNetworkClient)
    monkeypatch.setattr(client_main, "RemoteGameEngineProxy", _FakeProxy)
    monkeypatch.setattr(client_main, "DisplayManager", FakeDisplay)

    client_main.run_client("ws://example.test:9000")

    network = _FakeNetworkClient.instances[0]
    assert network.uri == "ws://example.test:9000"
    assert network.started and network.closed
    assert captured["proxy"].processed == 1
    assert captured["options"]["event_source"] is not captured["proxy"]
    assert captured["options"]["starts_game"] is False


def test_run_client_closes_network_when_display_fails(monkeypatch):
    class FailingDisplay:
        def __init__(self, *_args, **_kwargs):
            pass

        def run(self):
            raise RuntimeError("display_failed")

    _FakeNetworkClient.instances = []
    monkeypatch.setattr(client_main, "NetworkClient", _FakeNetworkClient)
    monkeypatch.setattr(client_main, "RemoteGameEngineProxy", _FakeProxy)
    monkeypatch.setattr(client_main, "DisplayManager", FailingDisplay)

    with pytest.raises(RuntimeError, match="display_failed"):
        client_main.run_client()

    assert _FakeNetworkClient.instances[0].closed
