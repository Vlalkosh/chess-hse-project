"""Create and print boards and convert square names to board coordinates."""

def create_initial_board() -> list[list[str]]:
    """Return a new 8 by 8 board in the starting position.

    Uppercase letters represent White, lowercase letters represent Black,
    and a dot represents an empty square. Each row is a separate list.
    """
    board = []

    board.append(list("rnbqkbnr"))
    board.append(list("pppppppp"))

    for _ in range(4):
        board.append(["."] * 8)

    board.append(list("PPPPPPPP"))
    board.append(list("RNBQKBNR"))

    return board


def print_board(board: list[list[str]]) -> None:
    """Print the board with rank and file labels."""
    rank = 8
    for row in board:
        print(rank, " ".join(row))
        rank -= 1
    print("  a b c d e f g h")


def parse_square(square: str) -> tuple[int, int]:
    """Return (row, column) for a square name such as e2.

    Rows run from 0 at rank 8 to 7 at rank 1; columns run from a to h.
    Ignore surrounding whitespace and letter case; raise ValueError for invalid names.
    """
    square = square.strip().lower()

    if len(square) != 2:
        raise ValueError("Enter a square such as e2: a letter from a to h and a digit from 1 to 8.")

    if square[0] not in "abcdefgh" or square[1] not in "12345678":
        raise ValueError("Enter a square such as e2: a letter from a to h and a digit from 1 to 8.")

    column = "abcdefgh".index(square[0])
    row = 8 - int(square[1])

    return row, column
