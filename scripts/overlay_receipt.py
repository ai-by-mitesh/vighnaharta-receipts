"""
Overlay dummy receipt text onto the e-pawati PDF template.

Usage:
    python overlay_receipt.py

Coordinates below match find_pdf_coords.py (top-left origin, Y grows downward).
ReportLab uses bottom-left origin, so Y is converted automatically when drawing.

Font styling matches ``lib/template_receipt.py`` (Poppins + field sizes).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import black, white
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
# True Devanagari face for Marathi digits (Poppins only has partial/fallback glyphs).
NOTO_DEVANAGARI = FONTS_DIR / "NotoSansDevanagari-Regular.ttf"

# India Standard Time — same idea as lib/utils.now_ist (year for ganpati count).
IST = timezone(timedelta(hours=5, minutes=30), name="IST")
FOUNDING_YEAR = 1968  # Navayuvak Mitra Mandal / Dadar Cha Vighnaharta

# Western digits → Devanagari (Marathi) digits for the year-count badge.
_DEVANAGARI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")

# ── Dummy data (swap for real values later) ──────────────────────────────────
DATA = {
    "receipt_no": "DCV-2026-0042",
    "date": "28/07/2026",
    "donor_name": "Mandy Ramalingam Swamy",
    "amount_words": "Eleven Thousand One Hundred Eleven Only",
    "amount_figures": "98909/-",
}

# ── Text placement ───────────────────────────────────────────────────────────
# Paste values from find_pdf_coords.py here: X = left edge, Y = top of text area.
# Format: (x, y) in PDF points. (vertical e-pawati template)
COORDS = {
    "receipt_no": (155.5, 697.5),
    "date": (438.5, 697.5),
    "donor_name": (139.5, 733.5),
    "amount_words": (89.5, 814.5),
    "amount_figures": (427.5, 860.5),
    # White Marathi year-count badge near top (current_year - 1968 + 1).
    "ganpati_years": (440.0, 61.5),
}

# Same typeface / sizes as lib/template_receipt.py
FONT_NAME = "Poppins"
FONT_SIZE = 16.0
# Amount-in-words is long; start smaller and shrink further to stay in the blank.
AMOUNT_WORDS_FONT_SIZE = 15.0
AMOUNT_WORDS_MIN_SIZE = 11.0
# Right margin so text does not run into the decorative panel / page edge.
AMOUNT_WORDS_RIGHT_PAD = 30
# Year-count badge (white Marathi digits via Noto Sans Devanagari).
GANPATI_YEARS_FONT_NAME = "NotoSansDevanagari"
GANPATI_YEARS_FONT_SIZE = 13.0


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


def _ensure_devanagari() -> str:
    """
    Register Noto Sans Devanagari for Marathi digits.

    Falls back to Poppins only if the TTF is missing (glyphs may look wrong).
    """
    if GANPATI_YEARS_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return GANPATI_YEARS_FONT_NAME
    if NOTO_DEVANAGARI.is_file():
        pdfmetrics.registerFont(
            TTFont(GANPATI_YEARS_FONT_NAME, str(NOTO_DEVANAGARI))
        )
        return GANPATI_YEARS_FONT_NAME
    return _ensure_poppins()


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


def ganpati_year_count(year: int | None = None) -> int:
    """
    Years of celebration: ``current_year - founding_year + 1``.

    Example (2026): 2026 - 1968 + 1 = 59.
    """
    y = year if year is not None else datetime.now(IST).year
    return y - FOUNDING_YEAR + 1


def to_marathi_digits(n: int | str) -> str:
    """Convert Western digits to Devanagari (Marathi) digits, e.g. 59 → ५९."""
    return str(n).translate(_DEVANAGARI_DIGITS)


def _draw_overlay(page_width: float, page_height: float) -> BytesIO:
    """Build a single-page transparent PDF with the text fields only."""
    font_name = _ensure_poppins()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    # Body fields in black (default).
    c.setFillColor(black)
    for key, (x, y_top) in COORDS.items():
        if key == "ganpati_years":
            continue
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

    # Year-count badge: white Marathi digits in a Devanagari face (e.g. ५९).
    years_key = "ganpati_years"
    if years_key in COORDS:
        x, y_top = COORDS[years_key]
        years_text = to_marathi_digits(ganpati_year_count())
        size = GANPATI_YEARS_FONT_SIZE
        dev_font = _ensure_devanagari()
        c.setFillColor(white)
        c.setFont(dev_font, size)
        y = page_height - y_top - size * 0.8
        c.drawString(x, y, years_text)

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

    years = ganpati_year_count()
    print(f"Saved: {out_path} (body={_ensure_poppins()}, years={_ensure_devanagari()})")
    print(
        f"Ganpati years: {years} → {to_marathi_digits(years)} "
        f"@ {COORDS['ganpati_years']} size={GANPATI_YEARS_FONT_SIZE}"
    )


if __name__ == "__main__":
    main()
