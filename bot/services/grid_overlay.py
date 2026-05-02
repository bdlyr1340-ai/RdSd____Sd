"""Mouse-grid overlay — draws a numbered grid on top of a screenshot
so the user can pick a cell number on Telegram to click it in the browser."""
from __future__ import annotations

import logging
import os
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)


def _try_load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a TTF font that supports digits cleanly. Fallback to default."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def overlay_numbered_grid(
    image_path: str,
    output_path: str,
    rows: int,
    cols: int,
) -> Dict[int, Tuple[float, float]]:
    """Overlay a numbered grid on an image and save the result.

    Args:
        image_path: source PNG/JPEG screenshot.
        output_path: where to save the annotated image.
        rows, cols: grid dimensions. Numbers are filled left→right, top→bottom.

    Returns:
        A dict {cell_number: (x_center, y_center)} in *image* pixel coordinates.
    """
    if rows < 1 or cols < 1:
        raise ValueError("rows and cols must be >= 1")

    img = Image.open(image_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    w, h = img.size
    cell_w = w / cols
    cell_h = h / rows

    # Pick a font size that comfortably fits inside a cell.
    raw = min(cell_w, cell_h) * 0.45
    font_size = max(9, int(raw))
    if font_size > 28:
        font_size = 28
    font = _try_load_font(font_size)

    cells: Dict[int, Tuple[float, float]] = {}
    n = 1

    # 1. Translucent grid lines first.
    line_color = (255, 60, 60, 170)
    for c in range(cols + 1):
        x = c * cell_w
        draw.line([(x, 0), (x, h)], fill=line_color, width=1)
    for r in range(rows + 1):
        y = r * cell_h
        draw.line([(0, y), (w, y)], fill=line_color, width=1)

    # 2. Numbers in each cell with a dark pill behind them.
    for r in range(rows):
        for c in range(cols):
            x0 = c * cell_w
            y0 = r * cell_h
            cx = x0 + cell_w / 2
            cy = y0 + cell_h / 2

            text = str(n)
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
            except Exception:
                tw = font_size * 0.6 * len(text)
                th = font_size

            pad = 2
            draw.rectangle(
                [cx - tw / 2 - pad, cy - th / 2 - pad,
                 cx + tw / 2 + pad, cy + th / 2 + pad],
                fill=(0, 0, 0, 180),
            )
            draw.text((cx - tw / 2, cy - th / 2 - 1), text,
                      fill=(255, 230, 0, 255), font=font)

            cells[n] = (cx, cy)
            n += 1

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(output_path, "PNG", optimize=True)
    return cells


def cell_center(rows: int, cols: int, n: int,
                width: int, height: int) -> Tuple[float, float]:
    """Compute the center of cell ``n`` for a given image size — used when we
    don't want to re-draw the grid (e.g. recreating coordinates server-side).
    """
    if n < 1 or n > rows * cols:
        raise ValueError(f"cell number {n} out of range 1..{rows * cols}")
    idx = n - 1
    r = idx // cols
    c = idx % cols
    cell_w = width / cols
    cell_h = height / rows
    return (c * cell_w + cell_w / 2, r * cell_h + cell_h / 2)
