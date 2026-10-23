"""Load and resize local PNG files without any chess rules."""

from pathlib import Path
import sys

from PIL import Image, ImageTk


PIECES_PATH = Path(__file__).resolve().parent.parent / "assets" / "pieces"


class PieceImages:
    """Cache original PNG files and keep Tkinter references to resized images."""
    def __init__(self, master, directory=PIECES_PATH):
        """Store the Tk parent and image directory, and create empty image caches."""
        self.master = master
        self.directory = Path(directory)
        self.originals = {}
        self.images = {}
        self.current = None

    def prepare(self, name: str, size: int) -> None:
        """Load and resize a piece set when its name or requested size changes.

        Keep decoded originals for reuse. Clear resized images and report file
        errors so that the board can fall back to text symbols.
        """
        if self.current == (name, size):
            return
        self.current = (name, size)
        self.images = {}
        try:
            for color in "wb":
                for kind in "KQRBNP":
                    code = color + kind
                    key = (name, code)
                    if key not in self.originals:
                        with Image.open(self.directory / name / f"{code}.png") as image:
                            self.originals[key] = image.convert("RGBA")
                    resized = self.originals[key].resize((size, size), Image.Resampling.LANCZOS)
                    piece = kind if color == "w" else kind.lower()
                    # Tk needs these Python references to keep the images visible.
                    self.images[piece] = ImageTk.PhotoImage(resized, master=self.master)
        except OSError as error:
            self.images = {}
            print(f"Could not load piece images: {error}. Using symbols instead.", file=sys.stderr)

    def get(self, piece: str):
        """Return the prepared Tkinter image for a piece, or None if unavailable."""
        return self.images.get(piece)
