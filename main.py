"""Start the graphical chess game or print the initial board in console mode."""

import sys

from chess_engine.board import create_initial_board, print_board


def main() -> None:
    """Print the starting board in console mode or open the graphical game.

    Report missing graphics dependencies and window startup errors before exiting.
    """
    if "--console" in sys.argv:
        print_board(create_initial_board())
        return
    # Delay graphics imports so console mode also works without Pillow or Tkinter.
    try:
        import tkinter as tk
        from chess_engine.gui import run
    except ModuleNotFoundError as error:
        if error.name == "PIL":
            print("To use the graphical interface, install the dependencies: "
                  "python -m pip install -r requirements.txt", file=sys.stderr)
            raise SystemExit(1) from error
        if error.name == "tkinter":
            print("Install Python with Tcl/Tk support.", file=sys.stderr)
            raise SystemExit(1) from error
        raise
    try:
        run()
    except tk.TclError as error:
        print(f"Could not open the window: {error}", file=sys.stderr)
        print("Check that your Python installation includes Tcl/Tk support.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
