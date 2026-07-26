"""
Overlay dummy receipt text onto the e-pawati PDF template.

Usage:
    python overlay_receipt.py

Coordinates below match find_pdf_coords.py (top-left origin, Y grows downward).
ReportLab uses bottom-left origin, so Y is converted automatically when drawing.

Font styling matches ``lib/template_receipt.py`` (Poppins + field sizes).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PDF = PROJECT_ROOT / "assets" / "pdf" / "e-pawati-vertical.pdf"
OUTPUT_DIR = PROJECT_ROOT / "receipts"
FONTS_DIR = PROJECT_ROOT / "assets" / "fonts"
POPPINS_REGULAR = FONTS_DIR / "Poppins-Regular.ttf"
POPPINS_BOLD = FONTS_DIR / "Poppins-Bold.ttf"

# ── Dummy data (swap for real values later) ──────────────────────────────────
DATA = {
    "receipt_no": "DCV-2026-0042",
    "date": "13/07/2026",
    "donor_name": "Mandy Ramalingam Swamy",
    "amount_words": "Eleven Thousand One Hundred Eleven Only",
    "amount_figures": "98909/-",
}

# ── Text placement ───────────────────────────────────────────────────────────
# Paste values from find_pdf_coords.py here: X = left edge, Y = top of text area.
# Format: (x, y) in PDF points. (vertical e-pawati template)
COORDS = {
    "receipt_no": (155.5, 697.5),
    "date": (439.5, 697.5),
    "donor_name": (139.5, 733.5),
    "amount_words": (89.5, 814.5),
    "amount_figures": (427.5, 860.5),
}

# Same typeface / sizes as lib/template_receipt.py
FONT_NAME = "Poppins"
FONT_SIZE = 15.5
# Amount-in-words is long; start smaller and shrink further to stay in the blank.
AMOUNT_WORDS_FONT_SIZE = 13.5
AMOUNT_WORDS_MIN_SIZE = 11.5
# Right margin so text does not run into the decorative panel / page edge.
AMOUNT_WORDS_RIGHT_PAD = 30


def _ensure_poppins() -> str:
    """Register Poppins once; fall back to Helvetica if the TTF is missing."""
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return FONT_NAME
    if POPPINS_REGULAR.is_file():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(POPPINS_REGULAR)))
        if POPPINS_BOLD.is_file():
            pdfmetrics.registerFont(TTFont(f"{FONT_NAME}-Bold", str(POPPINS_BOLD)))
        return FONT_NAME
    return "Helvetica"


def _fit_font_size(
    text: str,
    font_name: str,
    max_width: float,
    max_size: float,
    min_size: float,
) -> float:
    """Shrink font until ``text`` fits in ``max_width`` (or hit min_size)."""
    size = max_size
    while size > min_size and pdfmetrics.stringWidth(text, font_name, size) > max_width:
        size -= 0.5
    return size


def _draw_overlay(page_width: float, page_height: float) -> BytesIO:
    """Build a single-page transparent PDF with the text fields only."""
    font_name = _ensure_poppins()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    for key, (x, y_top) in COORDS.items():
        text = DATA[key]
        if key == "amount_words":
            max_width = max(40.0, page_width - x - AMOUNT_WORDS_RIGHT_PAD)
            size = _fit_font_size(
                text,
                font_name,
                max_width=max_width,
                max_size=AMOUNT_WORDS_FONT_SIZE,
                min_size=AMOUNT_WORDS_MIN_SIZE,
            )
        else:
            size = FONT_SIZE
        c.setFont(font_name, size)
        # Convert top-left Y (find_pdf_coords) → ReportLab bottom-left baseline Y.
        y = page_height - y_top - size * 0.8
        c.drawString(x, y, text)

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

    out_path = OUTPUT_DIR / f"{DATA['receipt_no']}.pdf"
    writer = PdfWriter()
    writer.add_page(page)
    with out_path.open("wb") as f:
        writer.write(f)

    print(f"Saved: {out_path} (font={_ensure_poppins()})")


if __name__ == "__main__":
    main()
