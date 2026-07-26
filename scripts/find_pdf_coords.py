"""
Click on a PDF page to print exact PyMuPDF coordinates (points, top-left origin).

Usage:
    python find_pdf_coords.py
    python find_pdf_coords.py path/to/other.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz
import tkinter as tk
from PIL import Image, ImageTk

# scripts/ → project root (same layout as lib/template_receipt.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF = PROJECT_ROOT / "assets" / "pdf" / "e-pawati-vertical.pdf"

# Leave room for window chrome / menu bar so the page is not clipped.
_SCREEN_MARGIN_X = 40
_SCREEN_MARGIN_Y = 100
# Never upscale beyond this (preview quality vs size).
_MAX_ZOOM = 2.5


def _fit_zoom(page_w: float, page_h: float, avail_w: int, avail_h: int) -> float:
    """Scale so the full page fits in the available pixel area."""
    if page_w <= 0 or page_h <= 0 or avail_w <= 0 or avail_h <= 0:
        return 1.0
    zoom = min(avail_w / page_w, avail_h / page_h)
    return max(0.1, min(zoom, _MAX_ZOOM))


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    page = doc[0]
    page_w = float(page.rect.width)
    page_h = float(page.rect.height)

    # Need a root before reading screen size.
    root = tk.Tk()
    root.title(f"Click for coordinates — {pdf_path.name}")
    root.update_idletasks()

    avail_w = max(200, root.winfo_screenwidth() - _SCREEN_MARGIN_X)
    avail_h = max(200, root.winfo_screenheight() - _SCREEN_MARGIN_Y)
    zoom = _fit_zoom(page_w, page_h, avail_w, avail_h)

    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    # If pixmap still slightly overshoots (HiDPI / rounding), shrink to fit.
    if img.width > avail_w or img.height > avail_h:
        img.thumbnail((avail_w, avail_h), Image.Resampling.LANCZOS)
        # Display scale vs PDF points (uniform; thumbnail keeps aspect).
        scale_x = img.width / page_w
        scale_y = img.height / page_h
    else:
        scale_x = zoom
        scale_y = zoom

    photo = ImageTk.PhotoImage(img)
    label = tk.Label(root, image=photo, cursor="crosshair")
    label.pack()
    label.image = photo  # keep a reference so the image is not GC'd

    def on_click(event: tk.Event) -> None:
        x = event.x / scale_x
        y = event.y / scale_y
        print(f"X = {x:.1f}, Y = {y:.1f}", flush=True)

    label.bind("<Button-1>", on_click)

    print(f"Opened: {pdf_path}")
    print(f"Page size: {page_w:.1f} x {page_h:.1f} pts (top-left origin)")
    print(f"Preview zoom: {zoom:.3f}x → {img.width}×{img.height} px (fits screen)")
    print("Click anywhere on the PDF. Close the window to exit.")
    root.mainloop()
    doc.close()


if __name__ == "__main__":
    main()
