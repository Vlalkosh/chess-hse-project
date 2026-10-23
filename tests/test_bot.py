"""Check bot decisions, search depth, terminal scores and cancellation."""

from threading import Event

import pytest

from chess_engine import bot
from chess_engine.bot import MATE_SCORE, SearchResult, analyze, choose_move, minimax
from chess_engine.game import Game, Move


def test_bot_returns_legal_move_without_changing_game():
    """Check searching returns a legal move and preserves the original game state."""
    game = Game()
    before = game.copy()
    move = choose_move(game)
    assert move in game.legal_moves()
    assert game.board == before.board
    assert game.turn == before.turn
    assert game.moves == before.moves
    assert game.captured == before.captured
    assert game.castling_rights == before.castling_rights
    assert game.en_passant == before.en_passant
    assert game.halfmove_clock == before.halfmove_clock
    assert game.position_counts == before.position_counts


def test_bot_finds_mate_in_one():
    """Check the bot finds the immediate mating queen move."""
    game = Game()
    for text in ("f2f3", "e7e5", "g2g4"):
        game.play(Move.from_text(text))
    assert choose_move(game) == Move.from_text("d8h4")


def test_bot_captures_undefended_queen():
    """Check the bot takes a queen that has no defender in the test position."""
    game = Game()
    for text in ("e2e4", "e7e5", "d1h5", "b8c6", "h5e5"):
        game.play(Move.from_text(text))
    assert choose_move(game) == Move.from_text("c6e5")


def test_bot_returns_none_after_game_ends():
    """Check no bot move is returned after checkmate."""
    game = Game()
    for text in ("f2f3", "e7e5", "g2g4", "d8h4"):
        game.play(Move.from_text(text))
    assert choose_move(game) is None


def test_bot_sees_reply_to_queen_capture(make_position):
    """Check the bot avoids a pawn capture that loses its queen to a rook."""
    game = make_position({"g1": "K", "g8": "k", "d1": "Q", "d8": "r", "d5": "p"})
    assert choose_move(game) != Move.from_text("d1d5")


def test_search_reports_fixed_depth_nodes_and_white_score(make_position):
    """Check search statistics and score direction when Black moves against a queen."""
    game = make_position({"e1": "K", "e8": "k", "a1": "Q"}, turn="black")
    result = analyze(game)
    assert result.depth == 3
    assert result.nodes > 0
    assert result.score > 0
    assert result.elapsed > 0
    assert not result.cancelled
    assert result.move in game.legal_moves()


@pytest.mark.parametrize("pieces, turn, expected", [
    ({"a8": "k", "c6": "K", "b6": "Q"}, "black", 0),
    ({"a8": "k", "c7": "K", "b8": "Q"}, "black", MATE_SCORE),
    ({"a1": "K", "c2": "k", "b1": "q"}, "white", -MATE_SCORE),
])
def test_search_checks_game_end_even_at_depth_boundary(make_position, pieces, turn, expected):
    """Check leaf positions are scored as mate or stalemate before static evaluation."""
    game = make_position(pieces, turn=turn)
    assert minimax(game, 0, SearchResult()) == expected


def test_search_stops_at_three_plies(monkeypatch):
    """Check every statically evaluated leaf is exactly three plies from the root."""
    seen_lengths = []
    original_evaluate = bot.evaluate

    def record_leaf(position):
        """Record the leaf's history length before returning its normal evaluation."""
        seen_lengths.append(len(position.moves))
        return original_evaluate(position)

    monkeypatch.setattr(bot, "evaluate", record_leaf)
    result = analyze(Game())
    assert result.depth == 3
    assert seen_lengths and set(seen_lengths) == {3}


def test_search_can_be_cancelled_without_changing_position(monkeypatch):
    """Check cancellation returns no completed move and preserves the original position."""
    game = Game()
    before = game.copy()
    stop_event = Event()
    original_evaluate = bot.evaluate

    def evaluate_and_cancel(position):
        """Request cancellation at a leaf, then return its normal evaluation."""
        stop_event.set()
        return original_evaluate(position)

    monkeypatch.setattr(bot, "evaluate", evaluate_and_cancel)
    result = analyze(game, stop_event=stop_event)
    assert result.cancelled
    assert result.depth == 0
    assert result.move is None
    assert game.board == before.board
    assert game.position_counts == before.position_counts
