"""
Shared helpers for Vighnaharta Receipts.

Formatting, phone normalization, and receipt-number utilities used by the
Streamlit app, PDF generator, and Google Sheets logger.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

# Receipt format: DCV-YYYY-NNNN  (e.g. DCV-2026-0001)
RECEIPT_PREFIX = "DCV"
RECEIPT_PATTERN = re.compile(rf"^{re.escape(RECEIPT_PREFIX)}-(\d{{4}})-(\d{{4}})$")

# India Standard Time — Streamlit Cloud runs in UTC; use this for all "today" dates.
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_ist() -> datetime:
    """Current datetime in India Standard Time (UTC+05:30)."""
    return datetime.now(IST)


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
    Build a receipt number in the form DCV-YYYY-NNNN.

    The sequence is zero-padded to 4 digits. Year defaults to the current
    calendar year. Incrementing against existing sheet rows is handled by
    sheets_logger.get_next_receipt_number().

    Args:
        sequence: 1-based sequence number for the year (e.g. 1 → 0001).
        year: Calendar year; defaults to today.

    Returns:
        Receipt number string, e.g. ``DCV-2026-0001``.

    Raises:
        ValueError: If sequence is less than 1.
    """
    if sequence < 1:
        raise ValueError("Receipt sequence must be >= 1")

    year = year if year is not None else now_ist().year
    return f"{RECEIPT_PREFIX}-{year}-{sequence:04d}"


def parse_receipt_number(receipt_no: str) -> tuple[int, int] | None:
    """
    Parse a receipt number into (year, sequence).

    Args:
        receipt_no: Value like ``DCV-2026-0001``.

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
    year = year if year is not None else now_ist().year
    parsed = parse_receipt_number(last_receipt_no) if last_receipt_no else None

    if parsed is None:
        return 1

    last_year, last_seq = parsed
    if last_year != year:
        return 1
    return last_seq + 1


# ── Amount in words (English, Indian numbering) ──────────────────────────────
_ONES = (
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
)
_TENS = (
    "",
    "",
    "Twenty",
    "Thirty",
    "Forty",
    "Fifty",
    "Sixty",
    "Seventy",
    "Eighty",
    "Ninety",
)


def _words_under_100(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    if ones == 0:
        return _TENS[tens]
    return f"{_TENS[tens]} {_ONES[ones]}"


def _words_under_1000(n: int) -> str:
    if n < 100:
        return _words_under_100(n)
    hundreds, rest = divmod(n, 100)
    head = f"{_ONES[hundreds]} Hundred"
    if rest == 0:
        return head
    return f"{head} {_words_under_100(rest)}"


def amount_to_words(amount: float | int) -> str:
    """
    Convert a rupee amount to English words (Indian scale).

    Examples:
        501 → ``Five Hundred One Only``
        25000 → ``Twenty Five Thousand Only``
        1_50_000 → ``One Lakh Fifty Thousand Only``

    Whole rupees only (fractional paise are rounded to the nearest rupee).
    Supports 0 through 999 crore (exclusive).
    """
    if amount is None:
        raise ValueError("Amount is required")

    n = int(round(float(amount)))
    if n < 0:
        raise ValueError("Amount must be non-negative")
    if n == 0:
        return "Zero Only"
    if n >= 100_00_00_000:  # 100 crore
        raise ValueError("Amount too large for amount-in-words conversion")

    crore, n = divmod(n, 1_00_00_000)
    lakh, n = divmod(n, 1_00_000)
    thousand, rest = divmod(n, 1_000)

    parts: list[str] = []
    if crore:
        parts.append(f"{_words_under_100(crore)} Crore")
    if lakh:
        parts.append(f"{_words_under_100(lakh)} Lakh")
    if thousand:
        parts.append(f"{_words_under_1000(thousand)} Thousand")
    if rest:
        parts.append(_words_under_1000(rest))

    return f"{' '.join(parts)} Only"


if __name__ == "__main__":
    # Smallest checks that fail if amount-in-words logic breaks.
    assert amount_to_words(0) == "Zero Only"
    assert amount_to_words(501) == "Five Hundred One Only"
    assert amount_to_words(25_000) == "Twenty Five Thousand Only"
    assert amount_to_words(1_50_000) == "One Lakh Fifty Thousand Only"
    assert format_receipt_number(1, 2026) == "DCV-2026-0001"
    print("utils self-check OK")
