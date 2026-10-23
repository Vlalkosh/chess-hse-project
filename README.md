# Chess Engine

A desktop chess game with a graphical board, chess rules implemented in Python, and a simple minimax bot.

## Features

- Play against the computer as White or Black, or play with another person on the same computer.
- Select moves with the mouse and see legal destinations, the last move, and check highlights.
- Castling, en passant, pawn promotion, checkmate, stalemate, and common draw conditions.
- Undo moves, view move history, and save or load games in JSON format.
- See captured pieces, material balance, position evaluation, and search statistics.
- Three board themes: Classic, Night, and Halloween.
- A resizable board that automatically rotates when you play as Black.

## Installing

### 0. Requirements

- Python 3.11 or newer. The instructions below use Python 3.13.
- Tkinter with Tcl/Tk support for the graphical interface.
- Pillow for loading and resizing piece images.

Dependencies are listed in `requirements.txt`. Piece images are included in the repository, so the game does not need an internet connection after installation.

### 1. macOS

Download and install Python 3.13 from the [official Python website](https://www.python.org/downloads/macos/).

On this repository's GitHub page, select **Code > Download ZIP** and extract the archive. Open Terminal and enter the extracted project folder. For example, if it is in Downloads:

```bash
cd ~/Downloads/chess-hse-project-master
```

If the folder has a different name or location, adjust this path. For an existing local copy, use that project's folder instead.

Check Python and Tkinter:

```bash
python3.13 --version
python3.13 -m tkinter
```

The second command should open a small test window. Close it before continuing. If it fails, check that you are using the Python installation from python.org with Tcl/Tk support. Tkinter is supplied with Python and is not installed through pip.

Create a local virtual environment, install the dependencies, and start the game:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

For later launches, open Terminal in the project folder and run:

```bash
.venv/bin/python main.py
```

### 2. Windows

Download and install Python 3.13 from the [official Python website](https://www.python.org/downloads/windows/). Include the Python launcher and Tcl/Tk support when installing.

On this repository's GitHub page, select **Code > Download ZIP** and extract the archive. Open PowerShell and enter the extracted project folder. For example, if it is in Downloads:

```powershell
cd "$HOME\Downloads\chess-hse-project-master"
```

If the folder has a different name or location, adjust this path. For an existing local copy, use that project's folder instead.

Check Python and Tkinter:

```powershell
py -3.13 --version
py -3.13 -m tkinter
```

Close the Tkinter test window, then create a local virtual environment, install the dependencies, and start the game:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

For later launches, open PowerShell in the project folder and run:

```powershell
.\.venv\Scripts\python.exe main.py
```

These commands use the virtual environment directly, so activation is not required. Create `.venv` locally on each computer instead of copying it between systems.

## Usage

Click **New game** and choose **White**, **Black**, or **Two players**. Select a piece, then click a highlighted destination. When a pawn reaches the last rank, choose its promotion piece in the dialog.

- **Undo move** takes back one move in two-player mode. Against the bot, it also takes back the bot's reply if it has already moved.
- **Save...** writes the game to JSON. **Load...** restores a game by replaying and validating its moves.
- **Claim draw** claims a draw by threefold repetition or the fifty-move rule. If the claim depends on an intended next move, click the button and select that move. **Cancel claim** returns to normal play.
- Use the theme selector to change the board's appearance during a game.

Checkmate, stalemate, common insufficient-material positions, fivefold repetition, and the seventy-five-move rule are detected automatically.

### Console output

To print the initial board without opening a window:

```bash
python3.13 main.py --console
```

On Windows, use `py -3.13 main.py --console`. This option only prints the board; it does not start an interactive console game and does not require Pillow.

## How the bot works

The bot uses minimax with a fixed depth of **3 plies**: its move, the opponent's reply, and its next move. White chooses the highest score; Black chooses the lowest. Checkmate and draws are checked before evaluating a position, including at the search boundary.

Evaluation combines material with a small center bonus for pawns, knights, and bishops. Scores are measured in centipawns: a pawn is 100, a knight or bishop is 300, a rook is 500, and a queen is 900. Positive scores favor White; negative scores favor Black.

The search runs in a background thread to keep the window responsive. Starting a new game, undoing a move, or closing the window cancels an obsolete search.

The bot has no search extensions or time limit. It can miss threats beyond three plies, and calculation time depends on the position. Draw claims by threefold repetition and the fifty-move rule are handled during play but are not simulated inside the search tree. Insufficient-material detection covers common cases rather than every possible position in which checkmate is impossible.

## Testing

Run these commands from the project folder.

### macOS

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m tools.benchmark
```

### Windows

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m tools.benchmark
```

Tests cover chess rules, board copying, tactical examples, the three-ply search limit, game storage, and interface handlers. Interface tests require a working graphical Tk session. The benchmark reports search depth, visited positions, calculation time, and the selected move for two sample positions.

## Project structure

```text
chess-hse-project-master/
├── assets/                 # Piece images and their licenses
├── chess_engine/
│   ├── board.py            # Initial board and square coordinates
│   ├── game.py             # Game state, legal moves, and chess rules
│   ├── bot.py              # Minimax search
│   ├── evaluation.py       # Material and center bonuses
│   ├── gui.py              # Tkinter window and event handlers
│   ├── storage.py          # JSON saving and loading
│   ├── piece_images.py     # Image loading and resizing
│   └── themes.py           # Interface colors
├── tests/                  # Automated checks
├── tools/benchmark.py      # Search measurements
├── main.py                 # Entry point
├── requirements.txt        # Game dependencies
└── requirements-dev.txt    # Test dependencies
```

## Credits

The Chessnut piece set is by Alexis Luengas and is distributed under Apache License 2.0. The Skulls piece set is by Maurizio Monge and is distributed under the MIT License. See [assets/README.md](assets/README.md) and the license files in each image folder for sources and attribution.
