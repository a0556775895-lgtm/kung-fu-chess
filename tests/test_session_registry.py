"""Unit tests for temporary authenticated session ownership."""

import pytest

from model.piece import PieceColor
from server.services.session_registry import SessionRegistry, SessionState


def _registry(*tokens):
    token_iterator = iter(tokens or ("token-1",))
    return SessionRegistry(token_factory=lambda: next(token_iterator))


def test_create_preserves_identity_and_blocks_case_variant():
    registry = _registry("token-1", "token-2")

    session = registry.create(7, "Alice", 1200)

    assert session.user_id == 7
    assert session.username == "Alice"
    assert session.rating == 1200
    assert session.is_connected
    assert session.game_id is None
    assert session.color is None
    assert session.state is SessionState.LOBBY
    assert registry.get("token-1") is session
    assert registry.create(8, "alice", 1300) is None
    assert registry.is_active("ALICE")
    assert registry.active_usernames() == ("Alice",)
    assert len(registry) == 1


def test_release_by_token_allows_username_to_be_reclaimed():
    registry = _registry("token-1", "token-2")
    registry.create(1, "David", 1200)

    assert registry.release("token-1")
    assert not registry.is_active("david")
    assert not registry.release("token-1")
    assert registry.create(1, "david", 1200).token == "token-2"


def test_mark_disconnected_retains_game_seat_token_and_username():
    registry = _registry("token-1", "token-2")
    session = registry.create(1, "Alice", 1200)
    session.game_id = "game-1"
    session.color = PieceColor.WHITE

    retained = registry.mark_disconnected("token-1")

    assert retained is session
    assert not session.is_connected
    assert session.game_id == "game-1"
    assert session.color is PieceColor.WHITE
    assert registry.get("token-1") is session
    assert registry.is_active("alice")
    assert registry.create(2, "ALICE", 1200) is None
    assert len(registry) == 1


def test_mark_disconnected_is_idempotent_and_reports_missing_session():
    registry = _registry("token-1")
    session = registry.create(1, "Alice", 1200)

    assert registry.mark_disconnected("token-1") is session
    assert registry.mark_disconnected("token-1") is session
    assert registry.mark_disconnected("missing-token") is None


def test_mark_connected_and_clear_restore_then_release_registry_state():
    registry = _registry("token-1", "token-2")
    first = registry.create(1, "Alice", 1200)
    registry.create(2, "Bob", 1200)
    registry.mark_disconnected("token-1")

    assert registry.mark_connected("token-1") is first
    assert first.is_connected
    assert registry.mark_connected("missing-token") is None
    assert registry.clear() == 2
    assert registry.clear() == 0
    assert len(registry) == 0
    assert registry.active_usernames() == ()


def test_unicode_equivalent_names_share_one_identity():
    registry = _registry("token-1", "token-2")
    composed = "Café"
    decomposed = "Cafe\u0301"

    assert registry.create(1, composed, 1200) is not None
    assert registry.create(2, decomposed, 1200) is None


def test_distinct_usernames_can_be_active_together():
    registry = _registry("token-1", "token-2")

    assert registry.create(1, "Alice", 1200)
    assert registry.create(2, "Bob", 1300)
    assert registry.active_usernames() == ("Alice", "Bob")


@pytest.mark.parametrize(
    "arguments,reason",
    [
        ((True, "Alice", 1200), "INVALID_USER_ID"),
        ((1, None, 1200), "INVALID_USERNAME"),
        ((1, "Alice", -1), "INVALID_RATING"),
    ],
)
def test_registry_rejects_invalid_account_data(arguments, reason):
    registry = _registry()

    with pytest.raises(ValueError, match=reason):
        registry.create(*arguments)


def test_registry_validates_factory_tokens_and_collisions():
    with pytest.raises(TypeError, match="TOKEN_FACTORY_NOT_CALLABLE"):
        SessionRegistry(token_factory=1)

    invalid = SessionRegistry(token_factory=lambda: "")
    with pytest.raises(ValueError, match="INVALID_SESSION_TOKEN"):
        invalid.create(1, "Alice", 1200)

    collision = SessionRegistry(token_factory=lambda: "same-token")
    collision.create(1, "Alice", 1200)
    with pytest.raises(RuntimeError, match="SESSION_TOKEN_COLLISION"):
        collision.create(2, "Bob", 1200)


@pytest.mark.parametrize(
    "operation",
    ["get", "mark_disconnected", "mark_connected", "release"],
)
def test_registry_rejects_invalid_lookup_token(operation):
    registry = _registry()

    with pytest.raises(ValueError, match="INVALID_SESSION_TOKEN"):
        getattr(registry, operation)("")
