"""Test window handlers using a hidden test window."""

from types import SimpleNamespace
from threading import Event
import tkinter as tk
from tkinter import ttk

import pytest

from chess_engine.board import parse_square
from chess_engine.bot import SearchResult
from chess_engine.game import Move
from chess_engine.gui import ChessApp


@pytest.fixture(scope="module")
def tk_root():
    """Provide a hidden Tk root for GUI tests and destroy it after the module.

    Skip these tests if a graphical Tcl/Tk session cannot be created.
    """
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"A graphical Tcl/Tk session is unavailable: {error}")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def app(tk_root):
    """Provide a fresh two-player interface and clean up its callbacks and widgets."""
    root = tk_root
    application = ChessApp(root)
    application.side.set("Two players")
    application.new_game()
    yield application
    for callback in root.tk.call("after", "info"):
        root.after_cancel(callback)
    for child in root.winfo_children():
        child.destroy()


def click(app, square):
    """Send a simulated click to the center of a named board square."""
    x, y = app.board_to_screen(parse_square(square))
    app.on_click(SimpleNamespace(x=x + app.cell_size // 2, y=y + app.cell_size // 2))


def test_clicks_make_move_and_update_history(app):
    """Check selecting a piece and destination updates the game and history widget."""
    click(app, "e2")
    assert app.selected == parse_square("e2")
    click(app, "e4")
    assert app.game.moves == [Move.from_text("e2e4")]
    assert app.game.turn == "black"
    assert "e2e4" in app.log.get(0)


def test_illegal_click_does_not_move_piece(app):
    """Check clicking an illegal destination leaves the piece and history unchanged."""
    click(app, "e2")
    click(app, "e5")
    assert app.game.moves == []
    assert app.game.board[6][4] == "P"


def test_undo_in_two_player_mode(app):
    """Check undo removes a single move and restores the previous side to move."""
    click(app, "e2")
    click(app, "e4")
    app.undo_move()
    assert app.game.moves == []
    assert app.game.board[6][4] == "P"
    assert app.game.turn == "white"


def test_undo_bot_reply_restores_human_turn(app):
    """Check undo removes a completed human and bot move pair."""
    app.bot_color = "black"
    app.game.play(Move.from_text("e2e4"))
    app.game.play(Move.from_text("e7e5"))
    app.undo_move()
    assert app.game.moves == []
    assert app.game.turn == "white"


def test_old_bot_answer_is_ignored_after_new_game(app):
    """Check a new game cancels search and ignores a queued reply from the old game."""
    generation = app.generation
    stop_event = Event()
    app.search_cancel = stop_event
    app.new_game()
    assert stop_event.is_set()
    app.answers.put((generation, Move.from_text("e2e4"), None))
    app.poll_bot()
    assert app.game.moves == []


def test_bot_thread_applies_legal_reply(app, monkeypatch):
    """Check a worker result is applied and its search statistics appear in the interface."""
    app.bot_color = "black"
    app.game.play(Move.from_text("e2e4"))
    app.refresh()
    result = SearchResult(move=Move.from_text("e7e5"), score=-25, depth=3,
                          nodes=150, elapsed=0.1)
    monkeypatch.setattr("chess_engine.gui.analyze", lambda *args, **kwargs: result)
    app.start_bot()
    answer = app.answers.get(timeout=2)
    app.answers.put(answer)
    app.poll_bot()
    assert app.game.moves[-1] == Move.from_text("e7e5")
    assert not app.busy
    assert app.game.turn == "white"
    assert app.last_search == result
    assert "150" in app.search_info.get()
    assert "-0.25" in app.score_text.get()


@pytest.mark.parametrize("flipped", [False, True])
def test_board_coordinate_conversion(app, flipped):
    """Check square-to-pixel conversion reverses correctly in both board orientations."""
    app.flipped = flipped
    for row in range(8):
        for column in range(8):
            x, y = app.board_to_screen((row, column))
            assert app.screen_to_board(x + app.cell_size // 2, y + app.cell_size // 2) == (row, column)
    assert app.screen_to_board(0, 0) is None


def test_invalid_save_does_not_replace_current_game(app, monkeypatch, tmp_path):
    """Check loading broken JSON reports one error and preserves the current game."""
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    original = app.game
    errors = []
    monkeypatch.setattr("chess_engine.gui.filedialog.askopenfilename", lambda **kwargs: str(path))
    monkeypatch.setattr("chess_engine.gui.messagebox.showerror", lambda *args, **kwargs: errors.append(args))
    app.load()
    assert app.game is original
    assert len(errors) == 1


@pytest.mark.parametrize("width, height", [(420, 530), (900, 750)])
def test_resizing_preserves_coordinate_conversion(app, width, height):
    """Check resized cells still map clicks to the correct board squares."""
    old_size = app.cell_size
    app.resize_board(SimpleNamespace(width=width, height=height))
    assert app.cell_size != old_size
    for square in ("a8", "h1", "e2", "d5"):
        cell = parse_square(square)
        x, y = app.board_to_screen(cell)
        assert app.screen_to_board(x + app.cell_size / 2, y + app.cell_size / 2) == cell
    click(app, "e2")
    click(app, "e4")
    assert app.game.moves[-1] == Move.from_text("e2e4")


def test_captured_piece_and_material_are_shown(app):
    """Check capture labels and material balance update after a capture and undo."""
    for text in ("e2e4", "d7d5", "e4d5"):
        app.game.play(Move.from_text(text))
    app.refresh()
    assert "♟" in app.white_captures.get()
    assert "+1" in app.material_text.get()
    app.undo_move()
    assert app.game.captured == []
    assert app.material_text.get() == "Material is equal"


def test_promotion_uses_selected_piece(app, monkeypatch):
    """Check a promotion chosen through the interface is applied to the board and history."""
    app.game.board = [["."] * 8 for _ in range(8)]
    app.game.board[7][4] = "K"
    app.game.board[0][4] = "k"
    app.game.board[1][0] = "P"
    app.game.castling_rights = ""
    app.game.position_counts = {app.game.position_key(): 1}
    app.refresh()
    monkeypatch.setattr(app, "choose_promotion", lambda: "n")
    click(app, "a7")
    click(app, "a8")
    assert app.game.board[0][0] == "N"
    assert app.game.moves[-1].promotion == "n"


def test_new_game_clears_previous_search(app):
    """Check starting again clears old search statistics and captured pieces."""
    app.last_search = SearchResult(move=Move.from_text("e2e4"), depth=2, nodes=150)
    app.new_game()
    assert app.last_search is None
    assert app.game.captured == []


def test_new_game_dialog_applies_side_and_fixed_depth(app):
    """Check settings show the fixed depth and apply Black's board orientation and opponent."""
    app.show_new_game_dialog()
    content = app.settings_window.winfo_children()[0]
    selectors = [widget for widget in content.winfo_children() if isinstance(widget, ttk.Combobox)]
    assert len(selectors) == 1
    selectors[0].set("Black")
    assert any(isinstance(widget, tk.Label) and widget.cget("text") == "Bot depth: 3 plies"
               for widget in content.winfo_children())
    start = [widget for widget in content.winfo_children() if isinstance(widget, ttk.Button)][0]
    start.invoke()
    assert app.bot_color == "white"
    assert app.flipped


def test_result_dialog_can_be_closed_and_game_restarted(app):
    """Check checkmate appears in the result dialog and a new game resets the result."""
    for text in ("f2f3", "e7e5", "g2g4", "d8h4"):
        app.game.play(Move.from_text(text))
    app.refresh()
    app.show_result()
    assert app.result_window.winfo_exists()
    assert app.score_text.get() == "Result: 0–1"
    app.result_window.destroy()
    app.new_game()
    assert app.outcome is None
    assert app.game.moves == []


def test_promotion_dialog_returns_clicked_piece(app):
    """Check clicking Bishop returns the bishop promotion letter."""
    def select_bishop():
        """Choose the bishop button after the promotion dialog opens."""
        dialog = [child for child in app.root.winfo_children() if isinstance(child, tk.Toplevel)][0]
        options = [child for child in dialog.winfo_children() if isinstance(child, tk.Frame)][0]
        buttons = [child for child in options.winfo_children() if isinstance(child, tk.Button)]
        buttons[2].invoke()

    app.root.after(0, select_bishop)
    assert app.choose_promotion() == "b"


@pytest.mark.parametrize("name", ["Classic", "Night", "Halloween"])
def test_theme_switch_keeps_current_game_and_selection(app, name):
    """Check changing themes preserves the game and selection while updating colors and images."""
    click(app, "e2")
    click(app, "e4")
    click(app, "e7")
    game = app.game
    generation = app.generation
    app.theme_name.set(name)
    app.apply_theme()
    assert app.game is game
    assert app.game.moves == [Move.from_text("e2e4")]
    assert app.selected == parse_square("e7")
    assert app.generation == generation
    assert app.root.cget("background") == app.theme["bg"]
    assert len(app.piece_images.images) == 12


def test_missing_images_fall_back_to_symbols(app, tmp_path):
    """Check unavailable image files leave text symbols on the board."""
    app.piece_images.directory = tmp_path
    app.piece_images.originals.clear()
    app.piece_images.current = None
    app.draw_board()
    assert app.piece_images.images == {}
    assert any(app.canvas.type(item) == "text" for item in app.canvas.find_all())


def test_dark_theme_is_applied_to_dialogs(app):
    """Check newly opened settings use the current dark theme colors."""
    app.theme_name.set("Halloween")
    app.apply_theme()
    app.show_new_game_dialog()
    dialog = app.settings_window
    assert dialog.cget("background") == app.theme["card"]
    content = dialog.winfo_children()[0]
    assert content.cget("background") == app.theme["card"]
