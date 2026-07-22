"""Unit tests for temporary active-username ownership."""

import pytest

from server.services.active_user_registry import ActiveUserRegistry


def test_claim_preserves_display_name_and_blocks_case_variant():
    registry = ActiveUserRegistry()

    assert registry.claim("Alice")
    assert not registry.claim("alice")
    assert registry.is_active("ALICE")
    assert registry.active_usernames() == ("Alice",)
    assert len(registry) == 1


def test_release_is_case_insensitive_and_name_can_be_reclaimed():
    registry = ActiveUserRegistry()
    registry.claim("David")

    assert registry.release("DAVID")
    assert not registry.is_active("david")
    assert not registry.release("David")
    assert registry.claim("david")


def test_unicode_equivalent_names_share_one_identity():
    registry = ActiveUserRegistry()
    composed = "Café"
    decomposed = "Cafe\u0301"

    assert registry.claim(composed)
    assert not registry.claim(decomposed)


def test_distinct_usernames_can_be_active_together():
    registry = ActiveUserRegistry()

    assert registry.claim("Alice")
    assert registry.claim("Bob")
    assert registry.active_usernames() == ("Alice", "Bob")


@pytest.mark.parametrize("username", [None, ""])
def test_registry_rejects_missing_username(username):
    registry = ActiveUserRegistry()

    with pytest.raises(ValueError, match="INVALID_USERNAME"):
        registry.claim(username)
