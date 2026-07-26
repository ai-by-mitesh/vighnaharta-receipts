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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from lib.utils import amount_to_words, now_ist

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PDF = PROJECT_ROOT / "assets" / "pdf" / "e-pawati-vertical.pdf"
FONTS_DIR = PROJECT_ROOT / "assets" / "fonts"
POPPINS_REGULAR = FONTS_DIR / "Poppins-Regular.ttf"
POPPINS_BOLD = FONTS_DIR / "Poppins-Bold.ttf"

# Vertical e-pawati: paste from find_pdf_coords.py (x, y) top-left origin, PDF points.
# Tuned in scripts/overlay_receipt.py before promotion to production.
COORDS: dict[str, tuple[float, float]] = {
    "receipt_no": (155.5, 697.5),
    "date": (439.5, 697.5),
    "donor_name": (139.5, 733.5),
    "amount_words": (89.5, 814.5),
    "amount_figures": (427.5, 860.5),
}

# Same typeface as the Streamlit UI (bundled under assets/fonts/).
# Sizes match the vertical layout tuned in scripts/overlay_receipt.py.
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
            # Optional bold face (same family name + "-Bold" if ever needed).
            pdfmetrics.registerFont(TTFont(f"{FONT_NAME}-Bold", str(POPPINS_BOLD)))
        return FONT_NAME
    return "Helvetica"


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
    """
    amount = donation["amount"]
    return {
        "receipt_no": str(donation["receipt_no"]),
        "date": now_ist().strftime("%d/%m/%Y"),
        "donor_name": str(donation["donor_name"]).strip(),
        "amount_words": amount_to_words(amount),
        "amount_figures": _format_amount_figures(amount),
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

    for key, (x, y_top) in COORDS.items():
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
    # Smallest checks: Poppins registers, amount-in-words fits on the vertical blank.
    font = _ensure_poppins()
    assert font == "Poppins", font
    assert TEMPLATE_PDF.is_file(), TEMPLATE_PDF
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
    print(f"ok: {font} size={size} width={width:.1f}/{max_w:.1f} text={long!r}")
    print(f"ok: generated {name} ({len(pdf_bytes)} bytes) from {TEMPLATE_PDF.name}")
