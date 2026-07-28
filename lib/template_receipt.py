"""
Template-overlay PDF receipts (e-pawati background).

Stamps donor fields onto ``assets/pdf/e-pawati-vertical.pdf`` using ReportLab +
pypdf. Coordinates match ``scripts/find_pdf_coords.py`` / ``overlay_receipt.py``
(top-left origin); Y is converted to ReportLab's bottom-left system when drawing.

This module does not allocate receipt numbers — callers pass a filled
``donation`` dict (same shape as ``pdf_generator.generate_receipt``).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import black, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from lib.utils import amount_to_words, now_ist

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PDF = PROJECT_ROOT / "assets" / "pdf" / "e-pawati-vertical.pdf"
FONTS_DIR = PROJECT_ROOT / "assets" / "fonts"
POPPINS_REGULAR = FONTS_DIR / "Poppins-Regular.ttf"
POPPINS_BOLD = FONTS_DIR / "Poppins-Bold.ttf"
# True Devanagari face for Marathi digits (Poppins only has partial/fallback glyphs).
NOTO_DEVANAGARI = FONTS_DIR / "NotoSansDevanagari-Regular.ttf"

FOUNDING_YEAR = 1968  # Navayuvak Mitra Mandal / Dadar Cha Vighnaharta
# Western digits → Devanagari (Marathi) digits for the year-count badge.
_DEVANAGARI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")

# Vertical e-pawati: paste from find_pdf_coords.py (x, y) top-left origin, PDF points.
# Tuned in scripts/overlay_receipt.py before promotion to production.
COORDS: dict[str, tuple[float, float]] = {
    "receipt_no": (155.5, 697.5),
    "date": (438.5, 697.5),
    "donor_name": (139.5, 733.5),
    "amount_words": (89.5, 814.5),
    "amount_figures": (427.5, 860.5),
    # White Marathi year-count badge near top (current_year - 1968 + 1).
    "ganpati_years": (440.0, 61.5),
}

# Same typeface as the Streamlit UI (bundled under assets/fonts/).
# Sizes match the vertical layout tuned in scripts/overlay_receipt.py.
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
            # Optional bold face (same family name + "-Bold" if ever needed).
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


def ganpati_year_count(year: int | None = None) -> int:
    """
    Years of celebration: ``current_year - founding_year + 1``.

    Example (2026): 2026 - 1968 + 1 = 59.
    """
    y = year if year is not None else now_ist().year
    return y - FOUNDING_YEAR + 1


def to_marathi_digits(n: int | str) -> str:
    """Convert Western digits to Devanagari (Marathi) digits, e.g. 59 → ५९."""
    return str(n).translate(_DEVANAGARI_DIGITS)


def _format_amount_figures(amount: float | int) -> str:
    """Figures for the template amount box, e.g. ``501/-``."""
    if float(amount).is_integer():
        return f"{int(amount)}/-"
    return f"{float(amount):.2f}/-"


def build_overlay_fields(donation: dict[str, Any]) -> dict[str, str]:
    """
    Map a donation dict to template text fields.

    Expected keys: ``receipt_no``, ``donor_name``, ``amount``.
    Date is always today's date as DD/MM/YYYY in IST. Amount in words is computed.
    ``ganpati_years`` is derived (Marathi digits) from the calendar year.
    """
    amount = donation["amount"]
    return {
        "receipt_no": str(donation["receipt_no"]),
        "date": now_ist().strftime("%d/%m/%Y"),
        "donor_name": str(donation["donor_name"]).strip(),
        "amount_words": amount_to_words(amount),
        "amount_figures": _format_amount_figures(amount),
        "ganpati_years": to_marathi_digits(ganpati_year_count()),
    }


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


def _draw_overlay(
    page_width: float,
    page_height: float,
    fields: dict[str, str],
) -> BytesIO:
    """Build a single-page PDF containing only the stamped text."""
    font_name = _ensure_poppins()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    # Body fields in black (default).
    c.setFillColor(black)
    for key, (x, y_top) in COORDS.items():
        if key == "ganpati_years":
            continue
        text = fields[key]
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
        # Top-left click coords → ReportLab baseline Y.
        y = page_height - y_top - size * 0.8
        c.drawString(x, y, text)

    # Year-count badge: white Marathi digits in a Devanagari face (e.g. ५९).
    years_key = "ganpati_years"
    if years_key in COORDS:
        x, y_top = COORDS[years_key]
        years_text = fields.get(years_key) or to_marathi_digits(ganpati_year_count())
        size = GANPATI_YEARS_FONT_SIZE
        dev_font = _ensure_devanagari()
        c.setFillColor(white)
        c.setFont(dev_font, size)
        y = page_height - y_top - size * 0.8
        c.drawString(x, y, years_text)

    c.save()
    buf.seek(0)
    return buf


def generate_template_receipt(
    donation: dict[str, Any],
    template_path: str | Path | None = None,
) -> tuple[bytes, str]:
    """
    Stamp donation fields onto the e-pawati template (in memory only).

    Unlike the fpdf landscape generator, this never writes a file under
    ``receipts/`` — the browser download is the only copy.

    Args:
        donation: Must include receipt_no, donor_name, amount.
        template_path: Optional override for the background PDF.

    Returns:
        ``(pdf_bytes, filename)`` e.g. ``(..., "DCV-2026-0001.pdf")``.
    """
    template = Path(template_path) if template_path else TEMPLATE_PDF
    if not template.is_file():
        raise FileNotFoundError(f"Receipt template not found: {template}")

    fields = build_overlay_fields(donation)

    reader = PdfReader(str(template))
    page = reader.pages[0]
    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)

    overlay = PdfReader(_draw_overlay(page_width, page_height, fields))
    page.merge_page(overlay.pages[0])

    buf = BytesIO()
    writer = PdfWriter()
    writer.add_page(page)
    writer.write(buf)

    safe_name = fields["receipt_no"].replace("/", "-")
    return buf.getvalue(), f"{safe_name}.pdf"


if __name__ == "__main__":
    # Smallest checks: fonts register, amount-in-words fits, year badge is Marathi.
    font = _ensure_poppins()
    dev = _ensure_devanagari()
    assert font == "Poppins", font
    assert dev == GANPATI_YEARS_FONT_NAME, dev
    assert TEMPLATE_PDF.is_file(), TEMPLATE_PDF
    assert NOTO_DEVANAGARI.is_file(), NOTO_DEVANAGARI

    years = ganpati_year_count(2026)
    assert years == 59, years
    assert to_marathi_digits(years) == "५९", to_marathi_digits(years)

    long = amount_to_words(73_373)  # longest wording at/under 1 lakh in practice
    page_w = float(PdfReader(str(TEMPLATE_PDF)).pages[0].mediabox.width)
    x = COORDS["amount_words"][0]
    max_w = page_w - x - AMOUNT_WORDS_RIGHT_PAD
    size = _fit_font_size(
        long, font, max_width=max_w, max_size=AMOUNT_WORDS_FONT_SIZE, min_size=AMOUNT_WORDS_MIN_SIZE
    )
    width = pdfmetrics.stringWidth(long, font, size)
    assert width <= max_w + 0.5, (width, max_w, size, long)
    assert size <= AMOUNT_WORDS_FONT_SIZE

    # End-to-end stamp once (in-memory only).
    pdf_bytes, name = generate_template_receipt(
        {
            "receipt_no": "DCV-2026-0042",
            "donor_name": "Mandy Ramalingam Swamy",
            "amount": 98909,
        }
    )
    assert name == "DCV-2026-0042.pdf"
    assert pdf_bytes.startswith(b"%PDF")
    fields = build_overlay_fields(
        {"receipt_no": "DCV-2026-0042", "donor_name": "Test", "amount": 501}
    )
    assert fields["ganpati_years"] == to_marathi_digits(ganpati_year_count())
    print(f"ok: {font} size={size} width={width:.1f}/{max_w:.1f} text={long!r}")
    print(f"ok: years={fields['ganpati_years']} font={dev} size={GANPATI_YEARS_FONT_SIZE}")
    print(f"ok: generated {name} ({len(pdf_bytes)} bytes) from {TEMPLATE_PDF.name}")
