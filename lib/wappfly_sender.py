"""
WhatsApp delivery via Wappfly for Vighnaharta Receipts.

Sends donation e-receipts (and optional confirmation messages) to donors
using the Wappfly API over HTTP (requests).

Expected flow (to be implemented):
1. Load API credentials from environment
2. Build message / media payload (PDF attachment when supported)
3. POST to Wappfly and handle response / errors
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def send_receipt(
    phone: str,
    message: str,
    pdf_path: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Send a WhatsApp message (and optional PDF) to the donor.

    Args:
        phone: Recipient phone number (E.164 or local format as required by Wappfly).
        message: Text body of the message.
        pdf_path: Optional path to the receipt PDF to attach.
        **kwargs: Extra API options (template name, media URL, etc.).

    Returns:
        Parsed API response payload.
    """
    # TODO: implement Wappfly API call with requests
    raise NotImplementedError("Wappfly WhatsApp sender is not implemented yet.")
