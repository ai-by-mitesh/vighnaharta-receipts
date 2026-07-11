"""
Shared helpers for Vighnaharta Receipts.

Formatting, phone normalization, and receipt-number utilities used by the
Streamlit app, PDF generator, and Google Sheets logger.
"""

from __future__ import annotations

import re
from datetime import datetime

# Receipt format: VIGH-YYYY-NNNN  (e.g. VIGH-2026-0001)
RECEIPT_PREFIX = "VIGH"
RECEIPT_PATTERN = re.compile(r"^VIGH-(\d{4})-(\d{4})$")


def format_currency(amount: float | int, currency: str = "INR") -> str:
    """
    Format a donation amount for display on receipts and in the UI.

    Args:
        amount: Numeric donation amount.
        currency: Currency code (default INR).

    Returns:
        Human-readable amount string (e.g. "₹1,000").
    """
    if currency == "INR":
        if float(amount).is_integer():
            return f"₹{amount:,.0f}"
        return f"₹{amount:,.2f}"
    return f"{currency} {amount:,.2f}"


def normalize_phone(phone: str) -> str:
    """
    Keep digits only from a phone / WhatsApp number input.

    Args:
        phone: Raw phone input from the form.

    Returns:
        Digits-only phone string.
    """
    return "".join(ch for ch in phone if ch.isdigit())


def format_receipt_number(sequence: int, year: int | None = None) -> str:
    """
    Build a receipt number in the form VIGH-YYYY-NNNN.

    The sequence is zero-padded to 4 digits. Year defaults to the current
    calendar year. Incrementing against existing sheet rows is handled by
    sheets_logger.get_next_receipt_number().

    Args:
        sequence: 1-based sequence number for the year (e.g. 1 → 0001).
        year: Calendar year; defaults to today.

    Returns:
        Receipt number string, e.g. ``VIGH-2026-0001``.

    Raises:
        ValueError: If sequence is less than 1.
    """
    if sequence < 1:
        raise ValueError("Receipt sequence must be >= 1")

    year = year if year is not None else datetime.now().year
    return f"{RECEIPT_PREFIX}-{year}-{sequence:04d}"


def parse_receipt_number(receipt_no: str) -> tuple[int, int] | None:
    """
    Parse a receipt number into (year, sequence).

    Args:
        receipt_no: Value like ``VIGH-2026-0001``.

    Returns:
        ``(year, sequence)`` or ``None`` if the format is invalid.
    """
    match = RECEIPT_PATTERN.match((receipt_no or "").strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def next_sequence_from_last(last_receipt_no: str | None, year: int | None = None) -> int:
    """
    Decide the next sequence number from the last stored receipt.

    - Empty / invalid last receipt → start at 1 for the target year.
    - Same year → last sequence + 1.
    - Different year → reset to 1.

    Args:
        last_receipt_no: Most recent receipt number from the sheet (or None).
        year: Target year; defaults to current year.

    Returns:
        Next sequence integer (not yet formatted).
    """
    year = year if year is not None else datetime.now().year
    parsed = parse_receipt_number(last_receipt_no) if last_receipt_no else None

    if parsed is None:
        return 1

    last_year, last_seq = parsed
    if last_year != year:
        return 1
    return last_seq + 1
