"""
PDF e-receipt generation for Vighnaharta Receipts.

Builds a clean, branded donation receipt (orange / white / black) with fpdf2
for Dadar Cha Vighnaharta Ganpati Mandal.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

# Brand colours (RGB) — matches Streamlit orange theme
ORANGE = (232, 93, 4)       # #E85D04
DARK = (28, 28, 28)         # near-black body text
MUTED = (90, 90, 90)        # secondary labels
LIGHT_ORANGE = (255, 244, 232)  # #FFF4E8 soft panel
WHITE = (255, 255, 255)
BORDER = (220, 220, 220)

DEFAULT_OUTPUT_DIR = Path("receipts")
MANDAL_NAME = "Dadar Cha Vighnaharta"
MANDAL_SUBTITLE = "Ganpati Mandal"
THANK_YOU = (
    "Thank you for your generous donation. "
    "May Bappa bless you and your family with health, happiness, and prosperity. "
    "Ganpati Bappa Morya!"
)


def _pdf_amount(amount: float | int) -> str:
    """
    Format amount for core PDF fonts (Helvetica has no rupee glyph).

    Streamlit UI can still show ₹ via utils.format_currency.
    """
    if float(amount).is_integer():
        return f"Rs. {amount:,.0f}"
    return f"Rs. {amount:,.2f}"



class ReceiptPDF(FPDF):
    """Single-page donation receipt with header bar and detail rows."""

    def header(self) -> None:
        # Top accent bar
        self.set_fill_color(*ORANGE)
        self.rect(0, 0, self.w, 28, "F")

        self.set_y(8)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 8, MANDAL_NAME, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, MANDAL_SUBTITLE, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(12)

    def footer(self) -> None:
        self.set_y(-18)
        self.set_draw_color(*ORANGE)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, "Vighnaharta Receipts · Paperless donation e-receipt", align="C")


def _detail_row(pdf: FPDF, label: str, value: str, y: float) -> float:
    """Draw one label / value pair and return the next Y position."""
    left = pdf.l_margin
    label_w = 45
    value_w = pdf.epw - label_w

    pdf.set_xy(left, y)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(label_w, 8, label)

    pdf.set_xy(left + label_w, y)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*DARK)
    pdf.cell(value_w, 8, value)

    # Light separator under the row
    line_y = y + 9
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.2)
    pdf.line(left, line_y, left + pdf.epw, line_y)
    return line_y + 4


def generate_receipt(
    donation: dict[str, Any],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """
    Generate a professional PDF donation receipt.

    Expected ``donation`` keys:
        receipt_no, donor_name, amount, payment_mode, date (optional),
        notes (optional), thank_you (optional).

    Args:
        donation: Donor and payment fields.
        output_dir: Directory where the PDF will be written.

    Returns:
        Path to the generated PDF file.
    """
    receipt_no = str(donation["receipt_no"])
    donor_name = str(donation["donor_name"]).strip()
    amount = donation["amount"]
    payment_mode = str(donation.get("payment_mode", "")).strip()
    date_str = str(
        donation.get("date")
        or datetime.now().strftime("%d %B %Y")
    )
    thank_you = str(donation.get("thank_you") or THANK_YOU)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Safe filename from receipt number
    safe_name = receipt_no.replace("/", "-")
    pdf_path = out_dir / f"receipt_{safe_name}.pdf"

    pdf = ReceiptPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(left=18, top=20, right=18)
    pdf.add_page()

    # Title ribbon
    pdf.set_fill_color(*LIGHT_ORANGE)
    pdf.set_text_color(*ORANGE)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, "DONATION RECEIPT", align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # Detail block
    y = pdf.get_y()
    amount_text = _pdf_amount(amount)
    y = _detail_row(pdf, "Receipt No", receipt_no, y)
    y = _detail_row(pdf, "Date", date_str, y)
    y = _detail_row(pdf, "Donor Name", donor_name, y)
    y = _detail_row(pdf, "Amount", amount_text, y)
    y = _detail_row(pdf, "Payment Mode", payment_mode or "-", y)

    notes = str(donation.get("notes") or "").strip()
    if notes:
        y = _detail_row(pdf, "Notes", notes, y)

    # Amount highlight box
    pdf.set_y(y + 6)
    pdf.set_fill_color(*ORANGE)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(
        0,
        12,
        f"  Total Received: {amount_text}",
        fill=True,
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(10)

    # Thank-you message
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 7, "Thank You", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 6, thank_you)

    pdf.ln(14)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, "This is a computer-generated e-receipt.", align="C")

    pdf.output(str(pdf_path))
    return pdf_path
