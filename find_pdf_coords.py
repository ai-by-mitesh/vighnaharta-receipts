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

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_PDF = PROJECT_ROOT / "assets" / "pdfs" / "e-pawati.pdf"
ZOOM = 2.0  # higher = sharper preview; click coords are scaled back to PDF points


def main() -> None:
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = fitz.Matrix(ZOOM, ZOOM)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    root = tk.Tk()
    root.title(f"Click for coordinates — {pdf_path.name}")
    photo = ImageTk.PhotoImage(img)
    label = tk.Label(root, image=photo, cursor="crosshair")
    label.pack()
    label.image = photo  # keep a reference so the image is not GC'd

    def on_click(event: tk.Event) -> None:
        x = event.x / ZOOM
        y = event.y / ZOOM
        print(f"X = {x:.1f}, Y = {y:.1f}", flush=True)

    label.bind("<Button-1>", on_click)

    print(f"Opened: {pdf_path}")
    print(f"Page size: {page.rect.width:.1f} x {page.rect.height:.1f} pts (top-left origin)")
    print("Click anywhere on the PDF. Close the window to exit.")
    root.mainloop()
    doc.close()


if __name__ == "__main__":
    main()
