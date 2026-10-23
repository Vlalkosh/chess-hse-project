"""The graphical board. Rules and search live in separate modules."""

from collections import Counter
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import traceback

from chess_engine.bot import MATE_SCORE, SEARCH_DEPTH, analyze
from chess_engine.evaluation import evaluate, material_balance
from chess_engine.game import Game, piece_color
from chess_engine.piece_images import PieceImages
from chess_engine.storage import load_game, save_game
from chess_engine.themes import DEFAULT_THEME, THEMES, recolor_widgets


CELL_SIZE = 64
MARGIN = 26
BOARD_SIZE = 8 * CELL_SIZE + 2 * MARGIN
BG = THEMES[DEFAULT_THEME]["bg"]
CARD = THEMES[DEFAULT_THEME]["card"]
TEXT = THEMES[DEFAULT_THEME]["text"]
MUTED = THEMES[DEFAULT_THEME]["muted"]
SYMBOLS = {"k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}
RESULT_TEXT = {
    "white_wins": "Checkmate. White wins!",
    "black_wins": "Checkmate. Black wins!",
    "stalemate": "Draw: stalemate.",
    "insufficient_material": "Draw: insufficient mating material.",
    "threefold_repetition": "Draw: threefold repetition.",
    "fivefold_repetition": "Draw: fivefold repetition.",
    "fifty_moves": "Draw: the fifty-move rule.",
    "seventy_five_moves": "Draw: the seventy-five-move rule.",
}


def format_score(score):
    """Return display text for a centipawn score, a mate score or a missing score."""
    if score is None:
        return "—"
    if abs(score) >= MATE_SCORE - 1000:
        return "Forced mate for White" if score > 0 else "Forced mate for Black"
    return f"{score / 100:+.2f}"


class ChessApp:
    """Connect the Tkinter board and controls to the game and bot.

    Keep widget updates in the main thread. Background searches send their
    results through a queue and can be cancelled when the position changes.
    """
    def __init__(self, root):
        """Create the game, interface state and widgets, then schedule bot polling."""
        self.root = root
        root.title("Chess")
        width = min(1060, root.winfo_screenwidth() - 60)
        height = min(800, root.winfo_screenheight() - 90)
        root.geometry(f"{width}x{height}")
        root.minsize(880, 660)
        root.configure(bg=BG)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        self.game = Game()
        self.selected = None
        self.bot_color = "black"
        self.flipped = False
        self.busy = False
        self.claim_pending = False
        # Each reset advances this number so old worker replies can be discarded.
        self.generation = 0
        # Worker threads send data here; only the main thread changes Tk widgets.
        self.answers = Queue()
        self.search_cancel = None
        self.legal = []
        self.outcome = None
        self.last_search = None
        self.result_window = None
        self.settings_window = None
        self.cell_size = CELL_SIZE
        self.board_left = MARGIN
        self.board_top = MARGIN
        self.theme = THEMES[DEFAULT_THEME]
        self.theme_name = tk.StringVar(value=DEFAULT_THEME)
        self.piece_images = PieceImages(root)

        self.side = tk.StringVar(value="White")
        self.status = tk.StringVar()
        self.mode_text = tk.StringVar()
        self.material_text = tk.StringVar()
        self.white_captures = tk.StringVar()
        self.black_captures = tk.StringVar()
        self.score_text = tk.StringVar()
        self.search_info = tk.StringVar()
        self.search_detail = tk.StringVar()
        self.hint = tk.StringVar(value="Select a piece, then its destination square.")
        self._create_widgets()
        self.apply_theme()
        self.refresh()
        root.after(80, self.poll_bot)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def _create_widgets(self):
        """Set shared widget fonts and spacing, then build the window sections."""
        style = ttk.Style(self.root)
        self.style = style
        style.theme_use("clam")
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 8),
                        borderwidth=0)
        style.configure("TCombobox", padding=6, font=("Segoe UI", 11))

        self._create_header()
        self._create_body()
        self._create_footer()

    def _create_header(self):
        """Build the title, turn status, theme selector and New game button."""
        header = tk.Frame(self.root, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 10))
        title = tk.Frame(header, bg=BG)
        title.pack(side="left")
        tk.Label(title, text="Chess", font=("Segoe UI", 24, "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(title, textvariable=self.status, font=("Segoe UI", 11),
                 bg=BG, fg=MUTED).pack(anchor="w", pady=(3, 0))
        controls = tk.Frame(header, bg=BG)
        controls.pack(side="right")
        theme_choice = ttk.Combobox(controls, textvariable=self.theme_name,
                                    values=list(THEMES), state="readonly", width=13)
        theme_choice.pack(side="left", padx=(0, 12))
        theme_choice.bind("<<ComboboxSelected>>", self.apply_theme)
        ttk.Button(controls, text="New game", style="Accent.TButton",
                   command=self.show_new_game_dialog).pack(side="left")

    def _create_body(self):
        """Build the resizable board and side panel, and bind board events."""
        body = tk.Frame(self.root, bg=BG)
        body.grid(row=1, column=0, sticky="nsew", padx=18)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, minsize=300)
        body.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(body, width=BOARD_SIZE, height=BOARD_SIZE,
                                bg=BG, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Configure>", self.resize_board)

        self._create_side_panel(body)

    def _create_side_panel(self, body):
        """Build material, search statistics, move history and game action controls."""
        panel = tk.Frame(body, bg=BG, width=300)
        panel.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        panel.grid_propagate(False)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)

        material = tk.Frame(panel, bg=CARD, padx=14, pady=10)
        material.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        tk.Label(material, textvariable=self.material_text, font=("Segoe UI", 13, "bold"),
                 bg=CARD, fg=TEXT, wraplength=270, justify="left").pack(anchor="w")
        tk.Label(material, textvariable=self.white_captures, font=("Segoe UI Symbol", 12),
                 bg=CARD, fg=MUTED).pack(anchor="w", pady=(5, 0))
        tk.Label(material, textvariable=self.black_captures, font=("Segoe UI Symbol", 12),
                 bg=CARD, fg=MUTED).pack(anchor="w", pady=(2, 0))

        stats = tk.Frame(panel, bg=CARD, padx=14, pady=10)
        stats.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        tk.Label(stats, textvariable=self.score_text, font=("Segoe UI", 12, "bold"),
                 bg=CARD, fg=TEXT, wraplength=270, justify="left").pack(anchor="w")
        tk.Label(stats, textvariable=self.search_info, font=("Segoe UI", 10),
                 bg=CARD, fg=MUTED, wraplength=270, justify="left").pack(anchor="w", pady=(5, 0))
        tk.Label(stats, textvariable=self.search_detail, font=("Segoe UI", 10),
                 bg=CARD, fg=MUTED, wraplength=270, justify="left").pack(anchor="w", pady=(2, 0))

        history = tk.Frame(panel, bg=CARD, padx=12, pady=10)
        history.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        tk.Label(history, text="Move history", font=("Segoe UI", 12, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        tk.Label(history, textvariable=self.mode_text, font=("Segoe UI", 9),
                 bg=CARD, fg=MUTED).pack(anchor="w", pady=(1, 6))
        log_frame = tk.Frame(history, bg=CARD)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Listbox(log_frame, width=24, height=4, font=("Consolas", 11),
                              bg=CARD, fg=TEXT, relief="flat", highlightthickness=0,
                              selectbackground=self.theme["last"], activestyle="none")
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scrollbar.set)

        actions = tk.Frame(panel, bg=BG)
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure((0, 1), weight=1)
        ttk.Button(actions, text="Undo move", command=self.undo_move).grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(actions, text="Save...", command=self.save).grid(
            row=1, column=0, sticky="ew", padx=(0, 3), pady=(0, 6))
        ttk.Button(actions, text="Load...", command=self.load).grid(
            row=1, column=1, sticky="ew", padx=(3, 0), pady=(0, 6))
        self.claim_button = ttk.Button(actions, text="Claim draw", command=self.claim_draw)
        self.claim_button.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _create_footer(self):
        """Create the hint label below the board and side panel."""
        self.hint_label = tk.Label(self.root, textvariable=self.hint,
                                   font=("Segoe UI", 10), bg=BG, fg=MUTED,
                                   wraplength=900, justify="left", anchor="w")
        self.hint_label.grid(row=2, column=0, sticky="ew", padx=24, pady=(10, 14))

    def apply_theme(self, event=None):
        """Apply the selected colors to widgets and redraw the board and pieces."""
        old_theme = self.theme
        self.theme = THEMES[self.theme_name.get()]
        recolor_widgets(self.root, old_theme, self.theme)
        colors = self.theme
        self.style.configure("TButton", background=colors["button"], foreground=colors["text"])
        self.style.map("TButton", background=[("active", colors["button_hover"])])
        self.style.configure("Accent.TButton", background=colors["accent"],
                             foreground=colors["accent_text"])
        self.style.map("Accent.TButton", background=[("active", colors["accent_hover"])])
        self.style.configure("TCombobox", fieldbackground=colors["card"],
                             foreground=colors["text"], background=colors["button"],
                             arrowcolor=colors["text"], bordercolor=colors["border"])
        self.style.map("TCombobox", fieldbackground=[("readonly", colors["card"])],
                       foreground=[("readonly", colors["text"])],
                       selectbackground=[("readonly", colors["card"])],
                       selectforeground=[("readonly", colors["text"])])
        self.style.configure("Vertical.TScrollbar", background=colors["button"],
                             troughcolor=colors["card"], arrowcolor=colors["muted"])
        self.root.option_add("*TCombobox*Listbox.background", colors["card"])
        self.root.option_add("*TCombobox*Listbox.foreground", colors["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", colors["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", colors["accent_text"])
        self.draw_board()

    def resize_board(self, event):
        """Fit and center eight square cells inside the available canvas size."""
        self.cell_size = max(1, (min(event.width, event.height) - 2 * MARGIN) // 8)
        self.board_left = (event.width - 8 * self.cell_size) // 2
        self.board_top = (event.height - 8 * self.cell_size) // 2
        self.hint_label.configure(wraplength=max(300, self.root.winfo_width() - 48))
        self.draw_board()

    def board_to_screen(self, square):
        """Return the top left pixel coordinates of a square, respecting rotation."""
        row, column = square
        if self.flipped:
            row, column = 7 - row, 7 - column
        return self.board_left + column * self.cell_size, self.board_top + row * self.cell_size

    def screen_to_board(self, x, y):
        """Return board coordinates for a click, or None outside the board.

        Reverse rows and columns when the player views the board from Black's side.
        """
        column = (x - self.board_left) // self.cell_size
        row = (y - self.board_top) // self.cell_size
        if not (0 <= row < 8 and 0 <= column < 8):
            return None
        if self.flipped:
            row, column = 7 - row, 7 - column
        return row, column

    def draw_board(self):
        """Redraw squares, pieces, coordinates and move highlights on the canvas.

        Use text symbols if images are unavailable. Highlight the last move,
        the selected piece, its legal destinations and the checked king.
        """
        self.canvas.delete("all")
        size = self.cell_size
        colors = self.theme
        self.piece_images.prepare(colors["pieces"], max(8, int(size * 0.96)))
        font_size = max(8, int(size * 0.67))
        last = self.game.moves[-1] if self.game.moves else None
        targets = {move.end for move in self.legal if move.start == self.selected}
        checked_king = "K" if self.game.turn == "white" else "k"
        in_check = self.game.is_in_check(self.game.turn)
        left, top = self.board_left, self.board_top
        self.canvas.create_rectangle(left - 3, top - 3, left + 8 * size + 3,
                                     top + 8 * size + 3, fill=colors["border"], outline="")
        for row in range(8):
            for column in range(8):
                square = (row, column)
                x, y = self.board_to_screen(square)
                color = colors["light"] if (row + column) % 2 == 0 else colors["dark"]
                if last and square in (last.start, last.end):
                    color = colors["last"]
                if square == self.selected:
                    color = colors["selected"]
                piece = self.game.board[row][column]
                if in_check and piece == checked_king:
                    color = colors["check"]
                self.canvas.create_rectangle(x, y, x + size, y + size, fill=color, outline=color)
                cx, cy = x + size / 2, y + size / 2
                image = self.piece_images.get(piece)
                if image is not None:
                    self.canvas.create_image(cx, cy, image=image)
                elif piece != ".":
                    symbol = SYMBOLS[piece.lower()]
                    fill = colors["white_piece"] if piece.isupper() else colors["black_piece"]
                    if piece.isupper():
                        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            self.canvas.create_text(cx + dx, cy + dy, text=symbol,
                                                    font=("Segoe UI Symbol", font_size), fill=colors["black_piece"])
                    self.canvas.create_text(cx, cy, text=symbol,
                                            font=("Segoe UI Symbol", font_size), fill=fill)
                if square in targets:
                    if piece == ".":
                        radius = max(3, size // 11)
                        self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                                fill=colors["dot"], outline="")
                    else:
                        self.canvas.create_rectangle(x + 3, y + 3, x + size - 3,
                                                     y + size - 3, outline=colors["dot"], width=3)
        for index in range(8):
            file_index = 7 - index if self.flipped else index
            rank = index + 1 if self.flipped else 8 - index
            self.canvas.create_text(left + (index + 0.5) * size, top + 8 * size + 15,
                                    text="abcdefgh"[file_index], font=("Segoe UI", 10), fill=colors["muted"])
            self.canvas.create_text(left - 15, top + (index + 0.5) * size,
                                    text=str(rank), font=("Segoe UI", 10), fill=colors["muted"])

    def captured_text(self, by_color):
        """Return symbols and counts of pieces captured by the requested color."""
        captured = Counter(piece.lower() for piece in self.game.captured
                           if piece_color(piece) != by_color)
        parts = []
        for kind in "qrbnp":
            count = captured[kind]
            if count:
                parts.append(SYMBOLS[kind] + (f"×{count}" if count > 1 else ""))
        return " ".join(parts) or "—"

    def update_summary(self):
        """Update material, captured pieces, game mode and evaluation labels.

        Show the last bot search when available, and replace the score with the
        final result when the game is over.
        """
        balance = material_balance(self.game)
        if balance == 0:
            self.material_text.set("Material is equal")
        else:
            side = "White" if balance > 0 else "Black"
            self.material_text.set(f"{side}: +{abs(balance) / 100:g} material")
        self.white_captures.set("White captured: " + self.captured_text("white"))
        self.black_captures.set("Black captured: " + self.captured_text("black"))
        if self.bot_color is None:
            self.mode_text.set("Two players on the same board")
        else:
            side = "White" if self.bot_color == "black" else "Black"
            self.mode_text.set(f"You play {side} · Computer opponent")
        if self.last_search is None:
            score = evaluate(self.game)
            self.score_text.set("White score: ≈ " + format_score(score))
            self.search_info.set("Static position evaluation")
            self.search_detail.set("Computer is thinking..." if self.busy else "Search statistics appear after the bot moves")
        else:
            stats = self.last_search
            if stats.score is not None and abs(stats.score) >= MATE_SCORE - 1000:
                self.score_text.set(format_score(stats.score))
            else:
                self.score_text.set("White score: ≈ " + format_score(stats.score))
            self.search_info.set(f"Search: depth {stats.depth} · {stats.nodes:,} nodes")
            self.search_detail.set(f"Calculation time: {stats.elapsed:.2f} s")
        if self.outcome is not None:
            if self.outcome == "white_wins":
                self.score_text.set("Result: 1–0")
            elif self.outcome == "black_wins":
                self.score_text.set("Result: 0–1")
            else:
                self.score_text.set("Result: ½–½")

    def refresh(self):
        """Recalculate legal moves and the result, then update the displayed game.

        Refresh the board, labels and history; schedule a result dialog when
        the position has just changed from ongoing to finished.
        """
        previous_outcome = self.outcome
        self.legal = self.game.legal_moves()
        self.outcome = self.game.result(self.legal)
        if self.outcome:
            self.status.set(RESULT_TEXT[self.outcome])
        else:
            side = "White" if self.game.turn == "white" else "Black"
            text = f"{side} to move"
            if self.busy:
                text += " · Computer is thinking..."
            if self.game.is_in_check(self.game.turn):
                text += " · Check!"
            self.status.set(text)
        self.claim_button.configure(text="Cancel claim" if self.claim_pending else "Claim draw")
        self.draw_board()
        self.update_summary()
        self.log.delete(0, "end")
        for index in range(0, len(self.game.moves), 2):
            white = self.game.moves[index].notation()
            black = self.game.moves[index + 1].notation() if index + 1 < len(self.game.moves) else ""
            self.log.insert("end", f"{index // 2 + 1:>3}. {white:<6} {black}")
        self.log.see("end")
        if self.outcome is not None and previous_outcome is None:
            self.root.after_idle(self.show_result)

    def make_dialog(self, title, width, height):
        """Return a centered dialog that takes input until it is closed."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=CARD)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        x = self.root.winfo_x() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - height) // 2
        dialog.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        dialog.grab_set()
        return dialog

    def show_new_game_dialog(self):
        """Show side and opponent settings without opening a duplicate dialog."""
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        dialog = self.make_dialog("New game", 400, 350)
        self.settings_window = dialog
        side = tk.StringVar(value=self.side.get())
        content = tk.Frame(dialog, bg=CARD, padx=24, pady=18)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="Game settings", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(0, 14))
        tk.Label(content, text="Side and opponent", bg=CARD, fg=MUTED).pack(anchor="w")
        ttk.Combobox(content, textvariable=side, state="readonly",
                     values=("White", "Black", "Two players")).pack(fill="x", pady=(4, 12))
        tk.Label(content, text=f"Bot depth: {SEARCH_DEPTH} plies", bg=CARD,
                 fg=MUTED).pack(anchor="w")
        tk.Label(content, text="The bot checks its move, your reply and its next move.",
                 wraplength=350, justify="left", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 8))

        def start():
            """Apply the selected side, close the settings dialog and start a new game."""
            self.side.set(side.get())
            dialog.destroy()
            self.new_game()

        ttk.Button(content, text="Start game", style="Accent.TButton",
                   command=start).pack(fill="x", pady=(15, 0))
        recolor_widgets(dialog, THEMES[DEFAULT_THEME], self.theme)

    def choose_promotion(self):
        """Wait for a promotion choice and return q, r, b or n.

        Return None if the player closes the dialog without choosing a piece.
        """
        dialog = self.make_dialog("Pawn promotion", 410, 190)
        choice = tk.StringVar(value="")
        tk.Label(dialog, text="Choose the promotion piece", font=("Segoe UI", 13, "bold"),
                 bg=CARD, fg=TEXT).pack(pady=(16, 8))
        options = tk.Frame(dialog, bg=CARD)
        options.pack()
        dialog.piece_images = PieceImages(dialog)
        dialog.piece_images.prepare(self.theme["pieces"], 68)

        def select(kind):
            """Remember the chosen promotion letter and close the dialog."""
            choice.set(kind)
            dialog.destroy()

        for column, (kind, name) in enumerate((("q", "Queen"), ("r", "Rook"),
                                               ("b", "Bishop"), ("n", "Knight"))):
            piece = kind.upper() if self.game.turn == "white" else kind
            image = dialog.piece_images.get(piece)
            button = tk.Button(options, text=SYMBOLS[kind], font=("Segoe UI Symbol", 34),
                               bg=self.theme["button"], fg=TEXT, relief="flat", cursor="hand2",
                               command=lambda kind=kind: select(kind))
            if image is not None:
                button.configure(image=image, width=72, height=72)
            else:
                button.configure(width=2)
            button.grid(row=0, column=column, padx=6)
            tk.Label(options, text=name, bg=CARD, fg=MUTED).grid(row=1, column=column, pady=4)
        recolor_widgets(dialog, THEMES[DEFAULT_THEME], self.theme)
        self.root.wait_window(dialog)
        return choice.get() or None

    def show_result(self):
        """Show a single result dialog when the game is over and settings are closed."""
        if self.outcome is None:
            return
        if self.settings_window is not None and self.settings_window.winfo_exists():
            return
        if self.result_window is not None and self.result_window.winfo_exists():
            return
        dialog = self.make_dialog("Game over", 400, 220)
        self.result_window = dialog
        tk.Label(dialog, text="Game over", font=("Segoe UI", 19, "bold"),
                 bg=CARD, fg=TEXT).pack(pady=(22, 10))
        tk.Label(dialog, text=RESULT_TEXT[self.outcome], font=("Segoe UI", 12),
                 bg=CARD, fg=MUTED, wraplength=350).pack(padx=20)
        buttons = tk.Frame(dialog, bg=CARD)
        buttons.pack(pady=20)

        def restart():
            """Close the result dialog and open settings for a new game."""
            dialog.destroy()
            self.show_new_game_dialog()

        ttk.Button(buttons, text="View board", command=dialog.destroy).pack(side="left", padx=4)
        ttk.Button(buttons, text="New game", style="Accent.TButton",
                   command=restart).pack(side="left", padx=4)
        recolor_widgets(dialog, THEMES[DEFAULT_THEME], self.theme)

    def on_click(self, event):
        """Select a piece or use its selected legal destination.

        Handle promotion choices and intended draw claims. Ignore board input
        when the bot is moving or the game is over, and display invalid claim errors.
        """
        if self.busy or self.outcome or self.game.turn == self.bot_color:
            return
        square = self.screen_to_board(event.x, event.y)
        if square is None:
            return
        row, column = square
        if self.selected is not None:
            candidates = []
            for move in self.legal:
                if move.start == self.selected and move.end == square:
                    candidates.append(move)
            if candidates:
                move = candidates[0]
                # Promotion creates four legal moves with the same start and end.
                if len(candidates) > 1:
                    promotion = self.choose_promotion()
                    if promotion is None:
                        return
                    for candidate in candidates:
                        if candidate.promotion == promotion:
                            move = candidate
                            break
                try:
                    if self.claim_pending:
                        self.game.claim_draw(move)
                    else:
                        self.game.play(move)
                except ValueError as error:
                    self.hint.set(str(error))
                    return
                self.selected = None
                self.claim_pending = False
                self.last_search = None
                self.hint.set("Select a piece, then its destination square.")
                self.refresh()
                self.root.after(80, self.start_bot)
                return
        if piece_color(self.game.board[row][column]) == self.game.turn:
            self.selected = None if self.selected == square else square
            self.hint.set("Select the destination square." if self.selected else "Select a piece.")
        else:
            self.selected = None
            self.hint.set("Select your own piece. Legal moves are highlighted.")
        self.draw_board()

    def start_bot(self):
        """Start a background search if the bot is due to move.

        Claim an available draw first. Otherwise search an independent position
        and attach the current generation number so obsolete replies can be ignored.
        """
        if self.busy or self.outcome or self.game.turn != self.bot_color:
            return
        if self.game.draw_reason() is not None:
            self.game.claim_draw()
            self.refresh()
            return
        self.busy = True
        self.refresh()
        # Search a snapshot so later interface actions cannot change the worker's board.
        position = self.game.copy()
        generation = self.generation
        stop_event = Event()
        self.search_cancel = stop_event

        def calculate():
            """Search in the worker thread and put either the result or error in the queue."""
            try:
                result = analyze(position, stop_event=stop_event)
                self.answers.put((generation, result, None))
            except Exception as error:
                traceback.print_exc()
                self.answers.put((generation, None, str(error)))

        Thread(target=calculate, daemon=True).start()

    def poll_bot(self):
        """Read queued search replies and apply current results in the main thread.

        Ignore replies from older generations, report search errors and schedule
        the next poll without blocking the window.
        """
        try:
            while True:
                generation, result, error = self.answers.get_nowait()
                # A finished search may still be queued after undo, load or a new game.
                if generation != self.generation:
                    continue
                self.busy = False
                self.search_cancel = None
                if error is not None:
                    self.refresh()
                    messagebox.showerror("Bot error", error, parent=self.root)
                else:
                    self.last_search = result
                    if result.move is not None:
                        self.game.play(result.move)
                    self.refresh()
        except Empty:
            # An empty queue is normal; the next scheduled poll will try again.
            pass
        self.root.after(80, self.poll_bot)

    def reset_view(self):
        """Cancel old work, clear selection and search labels, then refresh the game.

        Advance the generation number so queued replies from earlier positions
        will be ignored, and schedule a bot turn if needed.
        """
        if self.search_cancel is not None:
            self.search_cancel.set()
            self.search_cancel = None
        self.generation += 1
        self.busy = False
        self.selected = None
        self.claim_pending = False
        self.last_search = None
        if self.result_window is not None and self.result_window.winfo_exists():
            self.result_window.destroy()
        self.hint.set("Select a piece, then its destination square.")
        self.refresh()
        self.root.after(80, self.start_bot)

    def close(self):
        """Request cancellation of a running search and destroy the main window."""
        if self.search_cancel is not None:
            self.search_cancel.set()
        self.root.destroy()

    def new_game(self):
        """Create a fresh game and apply the chosen opponent, side and board rotation."""
        self.game = Game()
        if self.side.get() == "Two players":
            self.bot_color = None
        else:
            self.bot_color = "white" if self.side.get() == "Black" else "black"
        self.flipped = self.side.get() == "Black"
        self.reset_view()

    def undo_move(self):
        """Restore the game by replaying the history without its last move.

        Against the bot, also remove its reply when needed to restore the human's turn.
        Reset the view and cancel any search for the discarded position.
        """
        if not self.game.moves:
            return
        moves = self.game.moves[:-1]
        next_turn = "white" if len(moves) % 2 == 0 else "black"
        # Remove another ply if a single undo would leave the bot to move again.
        if self.bot_color == next_turn and moves:
            moves = moves[:-1]
        restored = Game()
        for move in moves:
            restored.play(move)
        self.game = restored
        self.reset_view()

    def claim_draw(self):
        """Claim an available draw or toggle selection of an intended claim move."""
        if self.busy or self.outcome or self.game.turn == self.bot_color:
            return
        if self.claim_pending:
            self.claim_pending = False
            self.hint.set("Draw claim cancelled. You can continue playing.")
        elif self.game.draw_reason() is not None:
            self.game.claim_draw()
            self.hint.set("Draw claimed.")
        else:
            self.claim_pending = True
            self.hint.set("To claim a draw, select a piece and its intended destination. "
                          "Press Cancel claim to continue playing normally.")
        self.refresh()

    def save(self):
        """Ask for a JSON filename and save the current game, reporting file errors."""
        filename = filedialog.asksaveasfilename(
            parent=self.root, title="Save game", defaultextension=".json",
            filetypes=[("JSON game", "*.json")])
        if not filename:
            return
        try:
            save_game(self.game, Path(filename))
        except OSError as error:
            messagebox.showerror("Could not save", str(error), parent=self.root)
            return
        self.hint.set("Game saved.")

    def load(self):
        """Load and validate a selected JSON game before replacing the current one.

        Keep the current game if reading or validation fails; reset the view on success.
        """
        filename = filedialog.askopenfilename(
            parent=self.root, title="Load game", filetypes=[("JSON game", "*.json")])
        if not filename:
            return
        try:
            restored = load_game(Path(filename))
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not load", str(error), parent=self.root)
            return
        self.game = restored
        self.reset_view()


def run() -> None:
    """Create the Tkinter application and run its event loop until the window closes."""
    root = tk.Tk()
    ChessApp(root)
    root.mainloop()
