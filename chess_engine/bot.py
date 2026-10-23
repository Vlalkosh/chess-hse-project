"""A minimax bot with a fixed search depth of three plies."""

from dataclasses import dataclass
from time import perf_counter

from chess_engine.evaluation import evaluate
from chess_engine.game import Game, Move


SEARCH_DEPTH = 3
MATE_SCORE = 100_000


class SearchCancelled(Exception):
    """Stop a search when its cancellation event has been set."""


@dataclass
class SearchResult:
    """Store the chosen move, White's score and search measurements.

    A finished game or cancelled search has no chosen move.
    Depth is measured in plies, and elapsed time is measured in seconds.
    """
    move: Move | None = None
    score: int | None = None  # Positive scores favor White.
    depth: int = 0
    nodes: int = 0
    elapsed: float = 0.0
    cancelled: bool = False


def minimax(game: Game, depth: int, stats: SearchResult,
            ply: int = 0, stop_event=None) -> int:
    """Return the best score for the side to move, using White's perspective.

    Depth is the number of plies left; ply is the distance from the search root.
    Update the shared node counter and raise SearchCancelled when requested.
    Check game endings before evaluating a leaf position.
    """
    if stop_event is not None and stop_event.is_set():
        raise SearchCancelled
    stats.nodes += 1

    # At a leaf, checking for one legal move is enough.
    if depth == 0 and game.has_legal_move():
        outcome = game.automatic_draw()
    else:
        moves = game.legal_moves()
        outcome = game.result(moves)
    # Distance favors a quicker win and a later loss when mate scores are compared.
    if outcome == "white_wins":
        return MATE_SCORE - ply
    if outcome == "black_wins":
        return -MATE_SCORE + ply
    if outcome is not None:
        return 0
    if depth == 0:
        return evaluate(game)

    # All scores use White's perspective: White maximizes and Black minimizes.
    if game.turn == "white":
        best = -2 * MATE_SCORE
        for move in moves:
            score = minimax(game.after(move), depth - 1, stats, ply + 1, stop_event)
            best = max(best, score)
    else:
        best = 2 * MATE_SCORE
        for move in moves:
            score = minimax(game.after(move), depth - 1, stats, ply + 1, stop_event)
            best = min(best, score)
    return best


def analyze(game: Game, stop_event=None) -> SearchResult:
    """Search three plies and return the chosen move with its statistics.

    Leave the supplied game unchanged. Return no move if the game is over;
    mark the result as cancelled if the stop event interrupts the search.
    """
    started = perf_counter()
    stats = SearchResult(nodes=1)
    moves = game.legal_moves()
    if game.result(moves) is not None:
        stats.elapsed = perf_counter() - started
        return stats

    best_score = -2 * MATE_SCORE if game.turn == "white" else 2 * MATE_SCORE
    best_move = None
    try:
        for move in moves:
            score = minimax(game.after(move), SEARCH_DEPTH - 1, stats, 1, stop_event)
            if (best_move is None
                    or (game.turn == "white" and score > best_score)
                    or (game.turn == "black" and score < best_score)):
                best_score = score
                best_move = move
        stats.move = best_move
        stats.score = best_score
        stats.depth = SEARCH_DEPTH
    except SearchCancelled:
        stats.cancelled = True
    stats.elapsed = perf_counter() - started
    return stats


def choose_move(game: Game) -> Move | None:
    """Return the bot's move, or None if the game is over.

    Search a copy of each position without changing the supplied game.
    """
    return analyze(game).move
