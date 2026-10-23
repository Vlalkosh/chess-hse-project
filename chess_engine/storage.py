"""Save move history and validate it again when loading the game."""

import json
from pathlib import Path

from chess_engine.game import Game, Move


def save_game(game: Game, path: Path) -> None:
    """Write move notation, save version and an optional draw claim to a JSON file.

    Store history rather than a raw board so it can be validated during loading.
    File system errors are left for the caller to handle.
    """
    data = {
        "version": 1,
        "moves": [move.notation() for move in game.moves],
        "claimed_draw": game.claimed_draw,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_game(path: Path) -> Game:
    """Return a game rebuilt from a validated JSON move history.

    Check the save version, replay every move and verify an optional draw claim.
    Raise ValueError for invalid content; leave file system errors to the caller.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("The file does not contain a valid JSON game.") from error

    # Require an actual integer: bool is an int subclass but is not a save version.
    if not isinstance(data, dict) or type(data.get("version")) is not int:
        raise ValueError("Unknown save format.")
    if data["version"] != 1:
        raise ValueError("This save version is not supported.")
    moves = data.get("moves")
    if not isinstance(moves, list):
        raise ValueError("The save must contain a list of move strings.")
    for move in moves:
        if not isinstance(move, str):
            raise ValueError("The save must contain a list of move strings.")

    game = Game()
    for number, text in enumerate(moves, start=1):
        try:
            game.play(Move.from_text(text))
        except ValueError as error:
            raise ValueError(f"Invalid move #{number}: {text}.") from error

    claimed = data.get("claimed_draw")
    if claimed is not None:
        if claimed not in ("threefold_repetition", "fifty_moves"):
            raise ValueError("Unknown draw claim reason.")
        # The claim may refer to this position or to an intended next move.
        valid = game.draw_reason() == claimed
        if not valid and game.result() is None:
            for move in game.legal_moves():
                if game.draw_reason(move) == claimed:
                    valid = True
                    break
        if not valid:
            raise ValueError("The save contains an invalid draw claim.")
        game.claimed_draw = claimed
    return game
