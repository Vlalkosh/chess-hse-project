"""Check the starting board, independent rows and coordinate conversion."""

import pytest

from chess_engine.board import create_initial_board, parse_square, print_board


def test_initial_position():
    """Check all pieces and empty squares in the starting board."""
    board = create_initial_board()

    expected = [
        list("rnbqkbnr"),
        list("pppppppp"),
        list("........"),
        list("........"),
        list("........"),
        list("........"),
        list("PPPPPPPP"),
        list("RNBQKBNR"),
    ]

    assert board == expected


def test_rows_are_independent():
    """Check changing one empty row does not change other rows."""
    board = create_initial_board()

    board[2][0] = "P"

    assert board[3][0] == "."
    assert board[4][0] == "."
    assert board[5][0] == "."


def test_boards_are_independent():
    """Check separate starting boards do not share mutable rows."""
    first_board = create_initial_board()
    second_board = create_initial_board()

    first_board[1][0] = "."

    assert second_board[1][0] == "p"


@pytest.mark.parametrize(
    "square, expected",
    [
        ("a8", (0, 0)),
        ("h8", (0, 7)),
        ("a1", (7, 0)),
        ("h1", (7, 7)),
        ("e2", (6, 4)),
        (" E2 ", (6, 4)),
    ],
)
def test_parse_square(square, expected):
    """Check square names, letter case and whitespace map to the expected indices."""
    assert parse_square(square) == expected


@pytest.mark.parametrize(
    "square",
    ["", "   ", "e", "e22", "a0", "a9", "i2", "2e", "e 2", "\u04302"],
)
def test_parse_square_rejects_invalid_input(square):
    """Check malformed or out-of-range square names raise ValueError."""
    with pytest.raises(ValueError):
        parse_square(square)


def test_print_board_shows_coordinates(capsys):
    """Check printed rows include rank labels and the final file labels."""
    board = create_initial_board()

    print_board(board)

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 9
    assert lines[0] == "8 r n b q k b n r"
    assert lines[7] == "1 R N B Q K B N R"
    assert lines[8] == "  a b c d e f g h"
