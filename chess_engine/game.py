"""Chess rules and game state, independent of the graphical interface."""

from dataclasses import dataclass
from copy import copy as shallow_copy

from chess_engine.board import create_initial_board, parse_square


KNIGHT_STEPS = [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                (1, -2), (1, 2), (2, -1), (2, 1)]
BISHOP_STEPS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
ROOK_STEPS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
KING_STEPS = BISHOP_STEPS + ROOK_STEPS


def inside(row: int, column: int) -> bool:
    """Return whether row and column are valid indices on the 8 by 8 board."""
    return 0 <= row < 8 and 0 <= column < 8


def piece_color(piece: str) -> str | None:
    """Return white or black for a piece letter, or None for an empty square."""
    if piece == ".":
        return None
    if piece.isupper():
        return "white"
    return "black"


def opposite(color: str) -> str:
    """Return the other color for a valid white or black color name."""
    return "black" if color == "white" else "white"


def square_name(square: tuple[int, int]) -> str:
    """Convert valid (row, column) indices to a square name such as e2."""
    row, column = square
    return "abcdefgh"[column] + str(8 - row)


@dataclass(frozen=True)
class Move:
    """Store a move's start, end and optional promotion letter.

    Coordinates are (row, column) pairs. Promotion is q, r, b or n, or an empty
    string for other moves. Frozen fields let moves be compared without changing them.
    """
    start: tuple[int, int]
    end: tuple[int, int]
    promotion: str = ""

    def notation(self) -> str:
        """Return coordinate notation such as e2e4 or a7a8q."""
        start = square_name(self.start)
        end = square_name(self.end)
        return start + end + self.promotion

    @classmethod
    def from_text(cls, text: str):
        """Parse coordinate notation and return a Move.

        Raise ValueError for invalid squares or promotion letters. This checks the
        text format only; Game.play checks whether the move is legal in the position.
        """
        text = text.strip().lower()
        if len(text) not in (4, 5):
            raise ValueError("Enter a move such as e2e4 or a7a8q.")
        promotion = text[4:]
        if promotion and promotion not in ("q", "r", "b", "n"):
            raise ValueError("Choose q, r, b or n for promotion.")
        start = parse_square(text[:2])
        end = parse_square(text[2:4])
        return cls(start, end, promotion)


class Game:
    """Keep the board, turn, special move rights and game history.

    Legal moves and results are calculated here without using the interface.
    Position counts track repetition; the halfmove clock counts plies since
    the last pawn move or capture.
    """
    def __init__(self):
        """Create the starting position with all castling rights and empty history."""
        self.board = create_initial_board()
        self.turn = "white"
        # K/Q allow White to castle on the king/queen side; k/q do the same for Black.
        self.castling_rights = "KQkq"
        # The en passant target is the empty square behind a double-stepped pawn.
        self.en_passant = None
        self.halfmove_clock = 0
        self.moves = []
        self.captured = []
        self.claimed_draw = None
        self.position_counts = {self.position_key(): 1}

    def copy(self):
        """Return an independent copy of the position and its mutable history.

        Simulated moves on the copy must not change the original game.
        """
        # Copy the current position without creating the initial board again.
        result = shallow_copy(self)
        # Mutable fields need their own copies; strings and integers can be shared.
        result.board = [row.copy() for row in self.board]
        result.moves = self.moves.copy()
        result.captured = self.captured.copy()
        result.position_counts = self.position_counts.copy()

        return result

    def is_attacked(self, square: tuple[int, int], by_color: str) -> bool:
        """Return whether the given color attacks a square.

        Check pawn diagonals, knight and king steps, and sliding piece paths directly.
        Attacks are separate from legal moves, including attacks on empty squares.
        """
        row, column = square
        pawn = "P" if by_color == "white" else "p"
        pawn_row = row + (1 if by_color == "white" else -1)
        for dc in (-1, 1):
            if inside(pawn_row, column + dc):
                if self.board[pawn_row][column + dc] == pawn:
                    return True

        knight = "N" if by_color == "white" else "n"
        king = "K" if by_color == "white" else "k"
        for dr, dc in KNIGHT_STEPS:
            r, c = row + dr, column + dc
            if inside(r, c) and self.board[r][c] == knight:
                return True
        for dr, dc in KING_STEPS:
            r, c = row + dr, column + dc
            if inside(r, c) and self.board[r][c] == king:
                return True

        for directions, attackers in ((BISHOP_STEPS, "bq"), (ROOK_STEPS, "rq")):
            for dr, dc in directions:
                r, c = row + dr, column + dc
                while inside(r, c):
                    piece = self.board[r][c]
                    if piece != ".":
                        if piece_color(piece) == by_color and piece.lower() in attackers:
                            return True
                        break
                    r += dr
                    c += dc
        return False

    def is_in_check(self, color: str) -> bool:
        """Return whether the requested color's king is attacked.

        Raise ValueError if the board has no king of that color.
        """
        king = "K" if color == "white" else "k"
        for row in range(8):
            for column in range(8):
                if self.board[row][column] == king:
                    return self.is_attacked((row, column), opposite(color))
        raise ValueError("The position has no king of the requested color.")

    def _pawn_moves(self, row: int, column: int) -> list[Move]:
        """Return pawn moves for the current turn, including captures and promotions.

        Include a starting double step and available en passant. King safety is
        checked later when these moves are filtered into legal moves.
        """
        moves = []
        direction = -1 if self.turn == "white" else 1
        start_row = 6 if self.turn == "white" else 1
        next_row = row + direction
        if not inside(next_row, column):
            return moves

        destinations = []
        if self.board[next_row][column] == ".":
            destinations.append((next_row, column))
            if row == start_row and self.board[row + 2 * direction][column] == ".":
                destinations.append((row + 2 * direction, column))

        for dc in (-1, 1):
            c = column + dc
            if not inside(next_row, c):
                continue
            target = self.board[next_row][c]
            if piece_color(target) == opposite(self.turn) and target.lower() != "k":
                destinations.append((next_row, c))
            elif (next_row, c) == self.en_passant and target == ".":
                enemy_pawn = "p" if self.turn == "white" else "P"
                if self.board[row][c] == enemy_pawn:
                    destinations.append((next_row, c))

        for end in destinations:
            if end[0] in (0, 7):
                for promotion in ("q", "r", "b", "n"):
                    moves.append(Move((row, column), end, promotion))
            else:
                moves.append(Move((row, column), end))
        return moves

    def _castling_moves(self, row: int, column: int) -> list[Move]:
        """Return available castling moves for the king on its home square.

        Require the castling right, the rook, an empty path and safe king squares.
        Castling is not allowed while the king is in check.
        """
        home_row = 7 if self.turn == "white" else 0
        if (row, column) != (home_row, 4) or self.is_in_check(self.turn):
            return []
        rook = "R" if self.turn == "white" else "r"
        moves = []
        # Right, rook column, empty columns, king path, final king column.
        options = [("K", 7, (5, 6), (5, 6), 6),
                   ("Q", 0, (1, 2, 3), (3, 2), 2)]
        for right, rook_column, empty, path, end_column in options:
            if self.turn == "black":
                right = right.lower()
            if right not in self.castling_rights or self.board[row][rook_column] != rook:
                continue
            blocked = False
            for c in empty:
                if self.board[row][c] != ".":
                    blocked = True
                    break
            if blocked:
                continue

            attacked = False
            for c in path:
                if self.is_attacked((row, c), opposite(self.turn)):
                    attacked = True
                    break
            if attacked:
                continue

            moves.append(Move((row, column), (row, end_column)))
        return moves

    def pseudo_legal_moves(self) -> list[Move]:
        """Return moves for the current side before the final king safety check.

        Use each piece's movement pattern and stop sliding pieces at blockers.
        Do not generate captures of the opposing king.
        """
        moves = []
        for row in range(8):
            for column in range(8):
                piece = self.board[row][column]
                if piece_color(piece) != self.turn:
                    continue
                kind = piece.lower()
                if kind == "p":
                    moves.extend(self._pawn_moves(row, column))
                    continue
                if kind == "n":
                    directions = KNIGHT_STEPS
                elif kind == "b":
                    directions = BISHOP_STEPS
                elif kind == "r":
                    directions = ROOK_STEPS
                else:
                    directions = KING_STEPS

                for dr, dc in directions:
                    r, c = row + dr, column + dc
                    while inside(r, c):
                        target = self.board[r][c]
                        if piece_color(target) == self.turn or target.lower() == "k":
                            break
                        moves.append(Move((row, column), (r, c)))
                        if target != "." or kind in ("n", "k"):
                            break
                        r += dr
                        c += dc
                if kind == "k":
                    moves.extend(self._castling_moves(row, column))
        return moves

    def iter_legal_moves(self):
        """Yield moves that leave the moving side's king safe.

        Test each candidate on a copy so that the current game stays unchanged.
        """
        for move in self.pseudo_legal_moves():
            next_game = self.copy()
            next_game._apply_move(move)
            # _apply_move switches turns; test the king of the side that just moved.
            if not next_game.is_in_check(self.turn):
                yield move

    def legal_moves(self) -> list[Move]:
        """Return all legal moves for the current side as a list."""
        return list(self.iter_legal_moves())

    def has_legal_move(self) -> bool:
        """Return whether at least one legal move exists, stopping at the first one."""
        for move in self.iter_legal_moves():
            return True
        return False

    def _apply_move(self, move: Move) -> None:
        """Apply an already checked move without recording repetition or move history.

        Update captures, promotion, castling, en passant, the halfmove clock and turn.
        Use play for user moves; this internal method does not validate legality.
        """
        row, column = move.start
        end_row, end_column = move.end
        piece = self.board[row][column]
        target = self.board[end_row][end_column]

        # En passant removes a pawn beside the start square, not on the destination.
        if piece.lower() == "p" and move.end == self.en_passant and target == ".":
            target = self.board[row][end_column]
            self.board[row][end_column] = "."

        if target != ".":
            self.captured.append(target)

        self.board[row][column] = "."
        self.board[end_row][end_column] = piece

        # A two-column king move is castling, so move its rook as well.
        if piece.lower() == "k" and abs(end_column - column) == 2:
            rook_column = 7 if end_column == 6 else 0
            new_rook_column = 5 if end_column == 6 else 3
            self.board[row][new_rook_column] = self.board[row][rook_column]
            self.board[row][rook_column] = "."

        if move.promotion:
            promoted = move.promotion.upper() if self.turn == "white" else move.promotion
            self.board[end_row][end_column] = promoted

        if piece == "K":
            self.castling_rights = self.castling_rights.replace("K", "").replace("Q", "")
        elif piece == "k":
            self.castling_rights = self.castling_rights.replace("k", "").replace("q", "")
        rook_squares = {(7, 7): "K", (7, 0): "Q", (0, 7): "k", (0, 0): "q"}
        # A rook leaving its home square or being captured there removes the right.
        for square, right in rook_squares.items():
            if move.start == square or move.end == square:
                self.castling_rights = self.castling_rights.replace(right, "")

        self.en_passant = None
        if piece.lower() == "p" and abs(end_row - row) == 2:
            self.en_passant = ((row + end_row) // 2, column)

        # Pawn moves and captures restart the fifty/seventy-five-move counter.
        if piece.lower() == "p" or target != ".":
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1
        self.turn = opposite(self.turn)

    def position_key(self) -> tuple:
        """Return a hashable description of the position for repetition counting.

        Include piece placement, turn and castling rights. Include the en passant
        square only if a legal en passant capture is available.
        """
        # An en passant target matters for repetition only when it changes legal moves.
        effective_en_passant = None
        if self.en_passant is not None:
            end_row, end_column = self.en_passant
            row = end_row + (1 if self.turn == "white" else -1)
            pawn = "P" if self.turn == "white" else "p"
            enemy_pawn = "p" if self.turn == "white" else "P"
            for dc in (-1, 1):
                column = end_column + dc
                if not inside(row, column) or self.board[row][column] != pawn:
                    continue
                if self.board[row][end_column] != enemy_pawn:
                    continue
                next_game = self.copy()
                next_game._apply_move(Move((row, column), self.en_passant))
                if not next_game.is_in_check(self.turn):
                    effective_en_passant = self.en_passant
        rows = tuple("".join(row) for row in self.board)
        return rows, self.turn, self.castling_rights, effective_en_passant

    def after(self, move: Move):
        """Return a new game after an already legal move, including updated history.

        Used for search and intended draw claims; do not validate the move again.
        """
        result = self.copy()
        result._apply_move(move)
        result._record_move(move)
        return result

    def _record_move(self, move: Move) -> None:
        """Update move history and repetition counts after applying a move."""
        self.moves.append(move)
        key = self.position_key()
        self.position_counts[key] = self.position_counts.get(key, 0) + 1

    def play(self, move: Move) -> None:
        """Validate and play a move, then record it in the game history.

        Raise ValueError without changing the game if it is over or the move is illegal.
        """
        if self.result() is not None:
            raise ValueError("The game is already over.")
        if move not in self.legal_moves():
            raise ValueError("This move is not legal.")
        self._apply_move(move)
        self._record_move(move)

    def insufficient_material(self) -> bool:
        """Detect common positions where neither side has mating material.

        Cover bare kings, a single minor piece, and bishops on one square color.
        This is not a general test for every possible dead position.
        """
        minor_pieces = []
        for row in range(8):
            for column in range(8):
                kind = self.board[row][column].lower()
                if kind in ("p", "r", "q"):
                    return False
                if kind in ("b", "n"):
                    minor_pieces.append((kind, (row + column) % 2))
        if len(minor_pieces) <= 1:
            return True
        # Bishops restricted to the same square color cannot deliver mate.
        square_colors = set()
        for kind, color in minor_pieces:
            if kind != "b":
                return False
            square_colors.add(color)

        return len(square_colors) == 1

    def result(self, legal_moves: list[Move] | None = None) -> str | None:
        """Return a result code, or None if the game can continue.

        Check claimed draws, checkmate or stalemate, then automatic draws.
        Accept a precomputed legal move list to avoid generating it twice.
        """
        if self.claimed_draw is not None:
            return self.claimed_draw
        if legal_moves is None:
            legal_moves = self.legal_moves()
        if not legal_moves:
            if self.is_in_check(self.turn):
                return opposite(self.turn) + "_wins"
            return "stalemate"
        return self.automatic_draw()

    def automatic_draw(self) -> str | None:
        """Return a draw code for an existing claim or an automatic draw.

        Detect insufficient material, fivefold repetition and 150 quiet plies.
        The caller must rule out checkmate first because checkmate takes priority.
        """
        if self.claimed_draw is not None:
            return self.claimed_draw
        if self.insufficient_material():
            return "insufficient_material"
        if self.position_counts.get(self.position_key(), 0) >= 5:
            return "fivefold_repetition"
        if self.halfmove_clock >= 150:
            return "seventy_five_moves"
        return None

    def draw_reason(self, move: Move | None = None) -> str | None:
        """Return a valid threefold or fifty-move claim reason, or None.

        An optional intended move is checked on a copy and is not played here.
        Raise ValueError for an illegal intended move while the game is ongoing.
        """
        if self.result() is not None:
            return None
        position = self
        if move is not None:
            if move not in self.legal_moves():
                raise ValueError("Cannot claim a draw with an illegal move.")
            position = self.after(move)
        if position.position_counts.get(position.position_key(), 0) >= 3:
            return "threefold_repetition"
        if position.halfmove_clock >= 100:
            return "fifty_moves"
        return None

    def claim_draw(self, move: Move | None = None) -> None:
        """Record a valid draw claim without playing the optional intended move.

        Raise ValueError if neither repetition nor the fifty-move rule permits a claim.
        """
        reason = self.draw_reason(move)
        if reason is None:
            raise ValueError("There is no valid reason to claim a draw yet.")
        self.claimed_draw = reason
