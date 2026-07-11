"""
Google Sheets logging for Vighnaharta Receipts.

Uses gspread + Google service-account auth to append donation rows
for record-keeping and audits.

Expected flow (to be implemented):
1. Authenticate with service_account.json
2. Open the configured spreadsheet / worksheet
3. Append a new donation row
"""

from __future__ import annotations

from typing import Any


def log_donation(donation: dict[str, Any]) -> None:
    """
    Append a donation record to Google Sheets.

    Args:
        donation: Fields to log (receipt id, name, phone, amount, timestamp, etc.).
    """
    # TODO: authenticate with gspread / google-auth and append row
    raise NotImplementedError("Google Sheets logging is not implemented yet.")
