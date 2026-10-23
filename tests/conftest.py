"""Provide reusable position factories for evaluation and bot tests."""

import pytest

from chess_engine.board import parse_square
from chess_engine.game import Game


@pytest.fixture
def make_position():
    """Return a factory for building small evaluation and tactics positions."""
    def create(pieces, turn="white"):
        """Place the supplied pieces on an empty board and initialize repetition counts."""
        game = Game()
        game.board = [["."] * 8 for _ in range(8)]
        for square, piece in pieces.items():
            row, column = parse_square(square)
            game.board[row][column] = piece
        game.turn = turn
        game.castling_rights = ""
        game.position_counts = {game.position_key(): 1}
        return game

    return create
