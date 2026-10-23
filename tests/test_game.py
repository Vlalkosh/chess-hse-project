"""Check move generation, special moves, game results and draw claims."""

import pytest

from chess_engine.board import parse_square
from chess_engine.game import Game, Move


def position(pieces, turn="white", rights="", en_passant=None):
    """Build a test position with explicit pieces, turn, castling and en passant."""
    game = Game()
    game.board = [["."] * 8 for _ in range(8)]
    for square, piece in pieces.items():
        row, column = parse_square(square)
        game.board[row][column] = piece
    game.turn = turn
    game.castling_rights = rights
    game.en_passant = parse_square(en_passant) if en_passant else None
    game.position_counts = {game.position_key(): 1}
    return game


def play_moves(game, moves):
    """Play a whitespace-separated sequence of coordinate moves on the supplied game."""
    for text in moves.split():
        game.play(Move.from_text(text))


def perft(game, depth):
    """Count legal move sequences of exactly the requested depth.

    Use copied boards without recording history, so draw rules do not cut the tree short.
    """
    if depth == 0:
        return 1
    moves = game.legal_moves()
    if depth == 1:
        return len(moves)
    total = 0
    for move in moves:
        child = game.copy()
        child._apply_move(move)
        total += perft(child, depth - 1)
    return total


@pytest.mark.parametrize("depth, expected", [(1, 20), (2, 400), (3, 8902)])
def test_initial_move_tree(depth, expected):
    """Check starting-position move counts against known totals through three plies."""
    assert perft(Game(), depth) == expected


def test_copy_keeps_all_mutable_state_independent():
    """Check board rows and history containers are independent after copying."""
    game = Game()
    child = game.copy()
    child.board[6][0] = "."
    child.moves.append(Move.from_text("a2a4"))
    child.captured.append("p")
    child.position_counts.clear()
    assert game.board[6][0] == "P"
    assert game.moves == []
    assert game.captured == []
    assert len(game.position_counts) == 1


@pytest.mark.parametrize("rows, rights, expected", [
    (["r...k..r", "p.ppqpb.", "bn..pnp.", "...PN...",
      ".p..P...", "..N..Q.p", "PPPBBPPP", "R...K..R"], "KQkq", 2039),
    (["........", "..p.....", "...p....", "KP.....r",
      ".R...p.k", "........", "....P.P.", "........"], "", 191),
])
def test_move_tree_in_special_positions(rows, rights, expected):
    """Check known move counts in positions with castling and en passant possibilities."""
    game = Game()
    game.board = [list(row) for row in rows]
    game.castling_rights = rights
    game.position_counts = {game.position_key(): 1}
    assert perft(game, 2) == expected


@pytest.mark.parametrize("text", ["e2e5", "e7e5", "a1a3", "c1h6", "e1e2"])
def test_illegal_move_does_not_change_game(text):
    """Check rejecting an illegal move preserves the game state."""
    game = Game()
    before = game.copy()
    with pytest.raises(ValueError):
        game.play(Move.from_text(text))
    assert game.board == before.board
    assert game.turn == before.turn
    assert game.moves == before.moves
    assert game.position_counts == before.position_counts


def test_move_and_turn():
    """Check a pawn double step updates the board, turn and en passant target."""
    game = Game()
    game.play(Move.from_text("e2e4"))
    assert game.board[6][4] == "."
    assert game.board[4][4] == "P"
    assert game.turn == "black"
    assert game.en_passant == parse_square("e3")


def test_legal_moves_do_not_change_game():
    """Check move generation preserves the board, rights, turn and history."""
    game = Game()
    before = game.copy()
    game.legal_moves()
    assert game.board == before.board
    assert game.turn == before.turn
    assert game.castling_rights == before.castling_rights
    assert game.en_passant == before.en_passant
    assert game.moves == before.moves


def test_pinned_rook_cannot_leave_king_in_check():
    """Check a pinned rook cannot expose its king but can capture the attacker."""
    game = position({"e1": "K", "a8": "k", "e2": "R", "e8": "r"})
    assert Move.from_text("e2d2") not in game.legal_moves()
    assert Move.from_text("e2e8") in game.legal_moves()


def test_kings_cannot_stand_next_to_each_other():
    """Check the king cannot move onto a square attacked by the opposing king."""
    game = position({"e1": "K", "e3": "k"})
    assert Move.from_text("e1e2") not in game.legal_moves()


def test_pawn_attacks_empty_diagonal_but_not_cell_ahead():
    """Check pawn attacks follow diagonals rather than forward movement."""
    game = position({"e1": "K", "a8": "k", "e4": "p"})
    assert game.is_attacked(parse_square("d3"), "black")
    assert not game.is_attacked(parse_square("e3"), "black")


@pytest.mark.parametrize("turn, move, king, rook", [
    ("white", "e1g1", "g1", "f1"),
    ("white", "e1c1", "c1", "d1"),
    ("black", "e8g8", "g8", "f8"),
    ("black", "e8c8", "c8", "d8"),
])
def test_castling(turn, move, king, rook):
    """Check both castling sides for both colors move king and rook and clear rights."""
    game = position({"e1": "K", "a1": "R", "h1": "R",
                     "e8": "k", "a8": "r", "h8": "r"}, turn, "KQkq")
    game.play(Move.from_text(move))
    r, c = parse_square(king)
    assert game.board[r][c] == ("K" if turn == "white" else "k")
    r, c = parse_square(rook)
    assert game.board[r][c] == ("R" if turn == "white" else "r")
    assert ("K" if turn == "white" else "k") not in game.castling_rights
    assert ("Q" if turn == "white" else "q") not in game.castling_rights


@pytest.mark.parametrize("extra", [{"f8": "r"}, {"e7": "r"}, {"g8": "r"}, {"f1": "B"}])
def test_castling_blocked_or_attacked(extra):
    """Check castling is rejected through occupied or attacked king squares."""
    pieces = {"e1": "K", "h1": "R", "a8": "k"}
    pieces.update(extra)
    game = position(pieces, rights="K")
    assert Move.from_text("e1g1") not in game.legal_moves()


def test_rook_return_does_not_restore_castling():
    """Check moving a rook away and back does not restore its castling right."""
    game = position({"e1": "K", "h1": "R", "e8": "k"}, rights="K")
    play_moves(game, "h1h2 e8e7 h2h1 e7e8")
    assert Move.from_text("e1g1") not in game.legal_moves()


def test_capturing_rook_removes_castling_right():
    """Check a corner rook move and capture clear the corresponding castling rights."""
    game = position({"e1": "K", "h1": "R", "e8": "k", "h8": "r"},
                    turn="black", rights="Kk")
    game.play(Move.from_text("h8h1"))
    assert "K" not in game.castling_rights
    assert "k" not in game.castling_rights


def test_en_passant():
    """Check White's en passant capture moves the pawn and removes the captured pawn."""
    game = Game()
    play_moves(game, "e2e4 a7a6 e4e5 d7d5 e5d6")
    assert game.board[2][3] == "P"
    assert game.board[3][3] == "."
    assert game.board[3][4] == "."
    assert game.halfmove_clock == 0


def test_black_en_passant():
    """Check Black's en passant capture also updates the captured piece history."""
    game = position({"e1": "K", "e8": "k", "e4": "p", "d2": "P"})
    play_moves(game, "d2d4 e4d3")
    assert game.board[5][3] == "p"
    assert game.board[4][3] == "."
    assert game.board[4][4] == "."
    assert game.captured == ["P"]


def test_captured_promoted_piece_is_recorded_as_its_new_type():
    """Check capturing a promoted pawn records the promoted piece type."""
    game = position({"e1": "K", "e8": "k", "a7": "P", "b8": "r"})
    play_moves(game, "a7a8q b8a8")
    assert game.captured == ["Q"]


def test_en_passant_expires_after_one_turn():
    """Check en passant is unavailable after an intervening move."""
    game = Game()
    play_moves(game, "e2e4 a7a6 e4e5 d7d5 h2h3 a6a5")
    assert Move.from_text("e5d6") not in game.legal_moves()


def test_en_passant_cannot_expose_king():
    """Check en passant is rejected when removing both pawns exposes the king."""
    game = position({"h5": "K", "a8": "k", "a5": "r", "g5": "P", "f5": "p"},
                    en_passant="f6")
    assert Move.from_text("g5f6") not in game.legal_moves()


@pytest.mark.parametrize("promotion", ["q", "r", "b", "n"])
@pytest.mark.parametrize("turn, pawn, move", [
    ("white", "P", "a7a8"), ("black", "p", "a2a1"),
])
def test_promotion(turn, pawn, move, promotion):
    """Check every promotion choice places the correct piece for both colors."""
    game = position({"e1": "K", "e8": "k", move[:2]: pawn}, turn)
    game.play(Move.from_text(move + promotion))
    r, c = parse_square(move[2:])
    assert game.board[r][c] == (promotion.upper() if turn == "white" else promotion)


def test_checkmate_and_finished_game():
    """Check checkmate is detected and further moves are rejected."""
    game = Game()
    play_moves(game, "f2f3 e7e5 g2g4 d8h4")
    assert game.is_in_check("white")
    assert game.result() == "black_wins"
    with pytest.raises(ValueError):
        game.play(Move.from_text("a2a3"))


def test_stalemate():
    """Check a side with no legal move and no check is stalemated."""
    game = position({"a8": "k", "c6": "K", "b6": "Q"}, turn="black")
    assert not game.is_in_check("black")
    assert game.result() == "stalemate"


@pytest.mark.parametrize("extra, expected", [
    ({}, True), ({"c1": "B"}, True), ({"b1": "N"}, True),
    ({"c1": "B", "f8": "b"}, True),
    ({"b1": "N", "g1": "N"}, False),
    ({"c1": "B", "g8": "b"}, False), ({"a2": "P"}, False),
])
def test_insufficient_material(extra, expected):
    """Check the supported insufficient-material cases and contrasting positions."""
    pieces = {"e1": "K", "e8": "k"}
    pieces.update(extra)
    assert position(pieces).insufficient_material() == expected


def test_threefold_claim_and_fivefold_automatic_draw():
    """Check three repetitions allow a claim and five end the game automatically."""
    game = Game()
    cycle = "g1f3 g8f6 f3g1 f6g8"
    play_moves(game, cycle + " " + cycle)
    assert game.result() is None
    assert game.draw_reason() == "threefold_repetition"
    claimed = game.copy()
    claimed.claim_draw()
    assert claimed.result() == "threefold_repetition"
    play_moves(game, cycle + " " + cycle)
    assert game.result() == "fivefold_repetition"


def test_draw_claim_with_intended_move_does_not_play_it():
    """Check an intended repetition move allows a draw claim without changing history."""
    game = Game()
    play_moves(game, "g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1")
    assert game.draw_reason() is None
    before = game.copy()
    game.claim_draw(Move.from_text("f6g8"))
    assert game.result() == "threefold_repetition"
    assert game.board == before.board
    assert game.moves == before.moves


def test_fifty_move_claim_and_seventy_five_move_draw():
    """Check the claim threshold and automatic draw threshold for quiet plies."""
    game = position({"e1": "K", "e8": "k", "a1": "R"})
    game.halfmove_clock = 99
    assert game.draw_reason() is None
    assert game.draw_reason(Move.from_text("a1a2")) == "fifty_moves"
    game.halfmove_clock = 100
    assert game.draw_reason() == "fifty_moves"
    game.halfmove_clock = 150
    assert game.result() == "seventy_five_moves"


def test_checkmate_has_priority_over_seventy_five_moves():
    """Check a mating move wins even when the halfmove clock reaches 150."""
    game = position({"a8": "k", "c7": "K", "b6": "Q"})
    game.halfmove_clock = 149
    game.play(Move.from_text("b6b8"))
    assert game.result() == "white_wins"


def test_position_key_ignores_unavailable_en_passant():
    """Check an unusable en passant target does not change repetition identity."""
    game = Game()
    game.play(Move.from_text("e2e4"))
    other = game.copy()
    other.en_passant = None
    assert game.position_key() == other.position_key()


def test_position_key_includes_available_en_passant():
    """Check a legal en passant capture changes repetition identity."""
    game = position({"e1": "K", "e8": "k", "e5": "P", "d5": "p"}, en_passant="d6")
    other = game.copy()
    other.en_passant = None
    assert game.position_key() != other.position_key()


def test_position_key_ignores_en_passant_that_exposes_king():
    """Check a pinned en passant capture is ignored for repetition identity."""
    game = position({"h5": "K", "a8": "k", "a5": "r", "g5": "P", "f5": "p"},
                    en_passant="f6")
    other = game.copy()
    other.en_passant = None
    assert game.position_key() == other.position_key()


@pytest.mark.parametrize("text", ["", "e2", "e2e4qq", "e2e4k", "z2e4"])
def test_invalid_move_notation(text):
    """Check invalid move lengths, squares and promotion letters raise ValueError."""
    with pytest.raises(ValueError):
        Move.from_text(text)
