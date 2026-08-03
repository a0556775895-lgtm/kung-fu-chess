"""Tests for the network-independent connection overlay."""

import pytest

from client.view.hud.connection_status.connection_status_renderer import (
    ConnectionNotice,
    ConnectionStatusRenderer,
)


class _Canvas:
    def __init__(self):
        self.calls = []

    def put_text(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def test_connection_renderer_draws_notice_and_countdown():
    canvas = _Canvas()
    renderer = ConnectionStatusRenderer(
        lambda: ConnectionNotice("Reconnecting...", 12)
    )

    renderer.render(canvas, object())

    assert len(canvas.calls) == 2
    assert canvas.calls[0][0][0] == "Reconnecting... (12)"
    assert canvas.calls[1][0][0] == "Reconnecting... (12)"


def test_connection_renderer_skips_missing_notice():
    canvas = _Canvas()
    ConnectionStatusRenderer(lambda: None).render(canvas, object())
    assert canvas.calls == []


def test_connection_renderer_validates_provider_and_notice():
    with pytest.raises(TypeError, match="NOTICE_PROVIDER_NOT_CALLABLE"):
        ConnectionStatusRenderer(None)

    renderer = ConnectionStatusRenderer(lambda: "Reconnecting")
    with pytest.raises(TypeError, match="INVALID_CONNECTION_NOTICE"):
        renderer.render(_Canvas(), object())
