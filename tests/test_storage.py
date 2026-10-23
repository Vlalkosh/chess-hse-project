"""Check JSON round trips, move replay and rejection of invalid saves."""

import json

import pytest

from chess_engine.game import Game, Move
from chess_engine.storage import load_game, save_game


def test_save_and_load(tmp_path):
    """Check saving and replaying restores all recorded game state."""
    game = Game()
    for text in ("e2e4", "d7d5", "e4d5", "d8d5", "b1c3"):
        game.play(Move.from_text(text))
    path = tmp_path / "game.json"
    save_game(game, path)
    restored = load_game(path)
    assert restored.board == game.board
    assert restored.turn == game.turn
    assert restored.moves == game.moves
    assert restored.captured == game.captured
    assert restored.castling_rights == game.castling_rights
    assert restored.en_passant == game.en_passant
    assert restored.halfmove_clock == game.halfmove_clock
    assert restored.position_counts == game.position_counts


def test_claimed_draw_survives_save(tmp_path):
    """Check a draw claimed with an intended move remains valid after loading."""
    game = Game()
    for text in "g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1".split():
        game.play(Move.from_text(text))
    game.claim_draw(Move.from_text("f6g8"))
    path = tmp_path / "draw.json"
    save_game(game, path)
    assert load_game(path).result() == "threefold_repetition"


@pytest.mark.parametrize("data", [
    [], {}, {"version": 2, "moves": []}, {"version": True, "moves": []},
    {"version": 1, "moves": "e2e4"}, {"version": 1, "moves": [7]},
    {"version": 1, "moves": ["e2e5"]},
    {"version": 1, "moves": [], "claimed_draw": "fifty_moves"},
    {"version": 1, "moves": [], "claimed_draw": "unknown"},
])
def test_load_rejects_invalid_data(tmp_path, data):
    """Check unsupported save structures, moves and draw claims raise ValueError."""
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_game(path)


@pytest.mark.parametrize("content", [b"{", b"\xff\xfe\xfa"])
def test_load_rejects_broken_file(tmp_path, content):
    """Check malformed JSON and invalid text encoding raise ValueError."""
    path = tmp_path / "bad.json"
    path.write_bytes(content)
    with pytest.raises(ValueError):
        load_game(path)


def test_load_missing_file(tmp_path):
    """Check loading a nonexistent path reports FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_game(tmp_path / "missing.json")


@pytest.mark.parametrize("moves", [
    "e2e4 a7a6 e4e5 d7d5 e5d6",
    "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 d2d3 f8c5 e1g1 e8g8",
])
def test_special_moves_survive_save_and_replay(tmp_path, moves):
    """Check en passant and castling are reconstructed by replaying saved moves."""
    game = Game()
    for text in moves.split():
        game.play(Move.from_text(text))
    path = tmp_path / "special.json"
    save_game(game, path)
    restored = load_game(path)
    assert restored.board == game.board
    assert restored.captured == game.captured
    assert restored.castling_rights == game.castling_rights
    assert restored.position_counts == game.position_counts
