"""Check that both local piece image sets are complete and readable."""

import pytest
from PIL import Image

from chess_engine.piece_images import PIECES_PATH


@pytest.mark.parametrize("name", ["chessnut", "skulls"])
def test_all_piece_images_are_readable_and_transparent(name):
    """Check both piece sets contain twelve readable RGBA images with transparent corners."""
    for color in "wb":
        for kind in "KQRBNP":
            with Image.open(PIECES_PATH / name / f"{color}{kind}.png") as image:
                assert image.size == (256, 256)
                assert image.mode == "RGBA"
                assert image.getchannel("A").getbbox() is not None
                assert image.getpixel((0, 0))[3] == 0
