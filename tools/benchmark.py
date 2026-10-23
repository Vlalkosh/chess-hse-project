"""Measure search time: python -m tools.benchmark."""

from chess_engine.bot import analyze
from chess_engine.game import Game, Move


def benchmark():
    """Search the starting and sample opening positions and print measurements.

    Report completed depth, visited nodes, elapsed seconds and the chosen move.
    """
    positions = {"start": Game(), "opening": Game()}
    opening = "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 d2d3 f8c5 c2c3 d7d6 e1g1 e8g8"
    for text in opening.split():
        positions["opening"].play(Move.from_text(text))
    for name, game in positions.items():
        result = analyze(game)
        print(f"{name}: depth={result.depth}, nodes={result.nodes}, "
              f"time={result.elapsed:.2f}s, move={result.move.notation()}", flush=True)


if __name__ == "__main__":
    benchmark()
