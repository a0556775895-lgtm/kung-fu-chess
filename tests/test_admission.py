"""In-memory tests for paired admission and authoritative config selection."""

from boardio.board_factory import STANDARD_GAME_CONFIG
from model.game_config import GameConfig
from model.piece import PieceColor
from networking.protocols.game import (
    JoinRequest,
    decode_state,
    parse_command_response,
    parse_config_response,
)
from server.game import admission as admission_module
from server.game.admission import GameAdmission
from server.game.game_registry import GameRegistry
from server.services.matchmaker import MatchmakingPlayer
from server.services.session_registry import ActiveSession


def _admission_with_predictable_ids():
    connection_ids = iter((
        "connection-1",
        "connection-2",
        "connection-3",
        "connection-4",
    ))
    game_ids = iter(("game-1", "game-2"))
    registry = GameRegistry()
    admission = GameAdmission(
        registry,
        connection_id_factory=lambda: next(connection_ids),
        game_id_factory=lambda: next(game_ids),
    )
    return registry, admission


def _player(token, user_id, username, request_id, config=STANDARD_GAME_CONFIG):
    return MatchmakingPlayer(
        ActiveSession(token, user_id, username, 1200),
        JoinRequest(request_id, token, config),
    )


def _drain(context):
    return [
        context.outbound.get_nowait()
        for _ in range(context.outbound.qsize())
    ]


def test_admit_pair_creates_unique_match_colors_and_personalized_state():
    registry, admission = _admission_with_predictable_ids()
    white = _player("white-token", 1, "Alice", "join-white")
    black = _player("black-token", 2, "Bob", "join-black")

    results = admission.admit_pair(white, black)

    white_result = results["white-token"]
    black_result = results["black-token"]
    assert white_result.is_accepted
    assert black_result.is_accepted
    assert white_result.match is black_result.match
    assert white_result.match.game_id == "game-1"
    assert len(registry) == 1
    assert white_result.context.color is PieceColor.WHITE
    assert black_result.context.color is PieceColor.BLACK
    assert white.session.game_id == black.session.game_id == "game-1"
    assert white.session.color is PieceColor.WHITE
    assert black.session.color is PieceColor.BLACK

    white_config, white_state_message = _drain(white_result.context)
    black_config, black_state_message = _drain(black_result.context)
    assert not parse_config_response(white_config).was_overridden
    assert not parse_config_response(black_config).was_overridden
    white_state = decode_state(white_state_message)
    black_state = decode_state(black_state_message)
    assert white_state.assigned_color == "w"
    assert black_state.assigned_color == "b"
    assert white_state.game_id == black_state.game_id == "game-1"
    assert white_state.player_names == {"w": "Alice", "b": "Bob"}
    assert black_state.player_names == {"w": "Alice", "b": "Bob"}


def test_first_player_config_is_authoritative_for_second(monkeypatch):
    _, admission = _admission_with_predictable_ids()
    alternate = GameConfig(1, 10, 10, "future")
    monkeypatch.setattr(
        admission_module,
        "is_supported_game_config",
        lambda _config: True,
    )
    white = _player("white-token", 1, "Alice", "join-white")
    black = _player(
        "black-token",
        2,
        "Bob",
        "join-black",
        alternate,
    )

    results = admission.admit_pair(white, black)

    black_config = parse_config_response(
        _drain(results["black-token"].context)[0]
    )
    assert black_config.was_overridden
    assert black_config.effective_config == STANDARD_GAME_CONFIG


def test_rejection_for_unsupported_config_does_not_create_match():
    registry, admission = _admission_with_predictable_ids()
    unsupported = GameConfig(1, 10, 10, "future")
    request = JoinRequest(
        "join-unsupported",
        "unsupported-token",
        unsupported,
    )

    rejection = admission.rejection_for(request)

    assert parse_command_response(rejection).reason == "unsupported_game_config"
    assert len(registry) == 0


def test_admit_pair_defensively_rejects_invalid_players_and_config():
    _, admission = _admission_with_predictable_ids()
    first = _player("same-token", 1, "Alice", "join-first")
    same = _player("same-token", 1, "Alice", "join-same")
    unsupported = _player(
        "other-token",
        2,
        "Bob",
        "join-other",
        GameConfig(1, 10, 10, "future"),
    )

    try:
        admission.admit_pair(first, same)
    except ValueError as exc:
        assert str(exc) == "PLAYERS_MUST_BE_DIFFERENT"
    else:
        raise AssertionError("same session was admitted twice")

    try:
        admission.admit_pair(first, unsupported)
    except ValueError as exc:
        assert str(exc) == "UNSUPPORTED_GAME_CONFIG"
    else:
        raise AssertionError("unsupported config entered a match")


def test_admit_pair_rejects_invalid_generated_game_id():
    admission = GameAdmission(
        GameRegistry(),
        game_id_factory=lambda: "",
    )

    try:
        admission.admit_pair(
            _player("white-token", 1, "Alice", "join-white"),
            _player("black-token", 2, "Bob", "join-black"),
        )
    except ValueError as exc:
        assert str(exc) == "INVALID_GAME_ID"
    else:
        raise AssertionError("empty game id was accepted")


def test_each_pair_gets_a_different_match_and_release_is_scoped():
    registry, admission = _admission_with_predictable_ids()
    first_pair = admission.admit_pair(
        _player("one", 1, "Alice", "join-one"),
        _player("two", 2, "Bob", "join-two"),
    )
    second_pair = admission.admit_pair(
        _player("three", 3, "Carol", "join-three"),
        _player("four", 4, "Dana", "join-four"),
    )

    first_context = first_pair["one"].context
    second_context = second_pair["three"].context
    admission.release(first_context)

    assert len(registry) == 2
    assert not first_pair["one"].match.has_connection(first_context)
    assert second_pair["three"].match.has_connection(second_context)
    admission.release(first_context)
