"""
Overlay dummy receipt text onto the e-pawati PDF template.

Usage:
    python overlay_receipt.py

Coordinates below match find_pdf_coords.py (top-left origin, Y grows downward).
ReportLab uses bottom-left origin, so Y is converted automatically when drawing.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATE_PDF = PROJECT_ROOT / "assets" / "pdfs" / "e-pawati.pdf"
OUTPUT_DIR = PROJECT_ROOT / "receipts"

# ── Dummy data (swap for real values later) ──────────────────────────────────
DATA = {
    "receipt_no": "DCV-2026-0042",
    "date": "13/07/2026",
    "donor_name": "Mandar Pawar",
    "amount_words": "Five Hundred One Only",
    "amount_figures": "501/-",
}

# ── Text placement ───────────────────────────────────────────────────────────
# Paste values from find_pdf_coords.py here: X = left edge, Y = top of text area.
# Format: (x, y) in PDF points.
COORDS = {
    "receipt_no": (353.5, 152.5),
    "date": (515.0, 152.5),
    "donor_name": (344.5, 174.5),
    "amount_words": (312.0, 221.5),
    "amount_figures": (508.5, 250.0),
}

# Font settings (tweak if text looks too big/small)
FONT_NAME = "Helvetica"
FONT_SIZE = 10


def _draw_overlay(page_width: float, page_height: float) -> BytesIO:
    """Build a single-page transparent PDF with the text fields only."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))
    c.setFont(FONT_NAME, FONT_SIZE)

    for key, (x, y_top) in COORDS.items():
        # Convert top-left Y (find_pdf_coords) → ReportLab bottom-left baseline Y.
        # Subtract a bit of font size so the click point sits near the text top.
        y = page_height - y_top - FONT_SIZE * 0.8
        c.drawString(x, y, DATA[key])

    c.save()
    buf.seek(0)
    return buf


def main() -> None:
    if not TEMPLATE_PDF.is_file():
        raise SystemExit(f"Template not found: {TEMPLATE_PDF}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    template = PdfReader(str(TEMPLATE_PDF))
    page = template.pages[0]
    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)

    overlay = PdfReader(_draw_overlay(page_width, page_height))
    page.merge_page(overlay.pages[0])

    out_path = OUTPUT_DIR / f"receipt_{DATA['receipt_no']}.pdf"
    writer = PdfWriter()
    writer.add_page(page)
    with out_path.open("wb") as f:
        writer.write(f)

    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
