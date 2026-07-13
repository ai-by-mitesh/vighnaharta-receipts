"""
Template-overlay PDF receipts (e-pawati background).

Stamps donor fields onto ``assets/pdf/e-pawati.pdf`` using ReportLab + pypdf.
Coordinates match ``scripts/find_pdf_coords.py`` (top-left origin); Y is
converted to ReportLab's bottom-left system when drawing.

This module does not allocate receipt numbers — callers pass a filled
``donation`` dict (same shape as ``pdf_generator.generate_receipt``).
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from utils import amount_to_words

PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATE_PDF = PROJECT_ROOT / "assets" / "pdf" / "e-pawati.pdf"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "receipts"

# Paste values from find_pdf_coords.py: (x, y) top-left origin, PDF points.
COORDS: dict[str, tuple[float, float]] = {
    "receipt_no": (353.5, 152.5),
    "date": (515.0, 152.5),
    "donor_name": (344.5, 174.5),
    "amount_words": (312.0, 221.5),
    "amount_figures": (508.5, 250.0),
}

FONT_NAME = "Helvetica"
FONT_SIZE = 10


def _format_amount_figures(amount: float | int) -> str:
    """Figures for the template amount box, e.g. ``501/-``."""
    if float(amount).is_integer():
        return f"{int(amount)}/-"
    return f"{float(amount):.2f}/-"


def build_overlay_fields(donation: dict[str, Any]) -> dict[str, str]:
    """
    Map a donation dict to template text fields.

    Expected keys: ``receipt_no``, ``donor_name``, ``amount``.
    Date is always today's date as DD/MM/YYYY. Amount in words is computed.
    """
    amount = donation["amount"]
    return {
        "receipt_no": str(donation["receipt_no"]),
        "date": datetime.now().strftime("%d/%m/%Y"),
        "donor_name": str(donation["donor_name"]).strip(),
        "amount_words": amount_to_words(amount),
        "amount_figures": _format_amount_figures(amount),
    }


def _draw_overlay(
    page_width: float,
    page_height: float,
    fields: dict[str, str],
) -> BytesIO:
    """Build a single-page PDF containing only the stamped text."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))
    c.setFont(FONT_NAME, FONT_SIZE)

    for key, (x, y_top) in COORDS.items():
        # Top-left click coords → ReportLab baseline Y.
        y = page_height - y_top - FONT_SIZE * 0.8
        c.drawString(x, y, fields[key])

    c.save()
    buf.seek(0)
    return buf


def generate_template_receipt(
    donation: dict[str, Any],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    template_path: str | Path | None = None,
) -> Path:
    """
    Stamp donation fields onto the e-pawati template and write a PDF.

    Args:
        donation: Must include receipt_no, donor_name, amount.
        output_dir: Directory for the finished PDF.
        template_path: Optional override for the background PDF.

    Returns:
        Path to the written receipt PDF.
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

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = fields["receipt_no"].replace("/", "-")
    out_path = out_dir / f"receipt_{safe_name}.pdf"

    writer = PdfWriter()
    writer.add_page(page)
    with out_path.open("wb") as f:
        writer.write(f)

    return out_path
