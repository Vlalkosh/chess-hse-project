"""Check material values, center bonuses and White's score perspective."""

from chess_engine.evaluation import evaluate, material_balance
from chess_engine.game import Game


def test_initial_position_is_balanced():
    """Check the starting material and evaluation scores are both zero."""
    assert evaluate(Game()) == 0
    assert material_balance(Game()) == 0


def test_evaluation_uses_white_perspective_for_both_turns(make_position):
    """Check changing the side to move does not reverse White's score."""
    game = make_position({"e1": "K", "e8": "k", "a2": "P"})
    assert evaluate(game) == 100
    game.turn = "black"
    assert evaluate(game) == 100
    assert material_balance(game) == 100


def test_color_mirror_reverses_evaluation(make_position):
    """Check swapping colors and reversing ranks negates the evaluation."""
    game = make_position({"g1": "K", "e8": "k", "f3": "N", "c6": "b", "e4": "P", "a7": "p"})
    other = game.copy()
    other.board = [[piece.swapcase() for piece in row] for row in reversed(game.board)]
    other.turn = "black"
    assert evaluate(game) == -evaluate(other)


def test_knight_prefers_center_to_corner(make_position):
    """Check a central knight receives a higher score than a corner knight."""
    center = make_position({"e1": "K", "e8": "k", "d4": "N"})
    corner = make_position({"e1": "K", "e8": "k", "a1": "N"})
    assert evaluate(center) > evaluate(corner)


def test_material_matters_more_than_center_bonus(make_position):
    """Check a queen outweighs the center bonus of a knight."""
    queen = make_position({"e1": "K", "e8": "k", "a1": "Q"})
    centered_knight = make_position({"e1": "K", "e8": "k", "d4": "N"})
    assert evaluate(queen) > evaluate(centered_knight)
