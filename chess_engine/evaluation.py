"""Simple evaluation: piece values and a small center bonus."""

from chess_engine.game import Game


# Scores are measured in hundredths of a pawn.
VALUES = {"p": 100, "n": 300, "b": 300, "r": 500, "q": 900, "k": 0}


def material_balance(game: Game) -> int:
    """Return White's material value minus Black's, in centipawns."""
    balance = 0
    for row in game.board:
        for piece in row:
            if piece == ".":
                continue
            if piece.isupper():
                balance += VALUES[piece.lower()]
            else:
                balance -= VALUES[piece.lower()]
    return balance


def evaluate(game: Game) -> int:
    """Return material and center bonuses from White's perspective.

    Positive scores favor White regardless of whose turn it is. Pawns, knights
    and bishops receive a small bonus in the center; game endings are checked by the bot.
    """
    score = material_balance(game)
    for row in range(2, 6):
        for column in range(2, 6):
            piece = game.board[row][column]
            if piece.lower() not in ("p", "n", "b"):
                continue
            # Reward the central 4 by 4 area, with a larger bonus on d4/e4/d5/e5.
            bonus = 10
            if row in (3, 4) and column in (3, 4):
                bonus = 20
            if piece.isupper():
                score += bonus
            else:
                score -= bonus
    return score
