"""
PDF e-receipt generation for Vighnaharta Receipts.

Uses fpdf2 to produce donation receipts for Dadar Cha Vighnaharta
Ganpati Mandal.

Expected flow (to be implemented):
1. Accept donor and donation details
2. Render a branded PDF receipt
3. Return the file path or bytes for download / WhatsApp delivery
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def generate_receipt(donation: dict[str, Any], output_dir: str | Path = ".") -> Path:
    """
    Generate a PDF donation receipt.

    Args:
        donation: Donor and payment fields (name, phone, amount, etc.).
        output_dir: Directory where the PDF will be written.

    Returns:
        Path to the generated PDF file.
    """
    # TODO: implement with fpdf2
    raise NotImplementedError("PDF receipt generation is not implemented yet.")
