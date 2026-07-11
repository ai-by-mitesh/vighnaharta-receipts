"""
Shared helpers for Vighnaharta Receipts.

Utility functions used across the Streamlit app, PDF generator,
Sheets logger, and Wappfly sender (formatting, validation, IDs, etc.).
"""

from __future__ import annotations

from datetime import datetime


def format_currency(amount: float | int, currency: str = "INR") -> str:
    """
    Format a donation amount for display on receipts and in the UI.

    Args:
        amount: Numeric donation amount.
        currency: Currency code (default INR).

    Returns:
        Human-readable amount string (e.g. "₹1,000").
    """
    # TODO: refine formatting / locale rules as needed
    if currency == "INR":
        return f"₹{amount:,.0f}" if float(amount).is_integer() else f"₹{amount:,.2f}"
    return f"{currency} {amount:,.2f}"


def generate_receipt_id(prefix: str = "DCV") -> str:
    """
    Generate a simple receipt identifier.

    Args:
        prefix: Short prefix for the mandal (default DCV).

    Returns:
        Receipt ID string, e.g. DCV-20260711-143052.
    """
    # TODO: replace with a more robust sequence if required
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}"


def normalize_phone(phone: str) -> str:
    """
    Normalize a phone number for storage and WhatsApp delivery.

    Args:
        phone: Raw phone input from the form.

    Returns:
        Digits-only (or E.164) phone string.
    """
    # TODO: enforce country code / validation rules
    return "".join(ch for ch in phone if ch.isdigit())
