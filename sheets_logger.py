"""
Google Sheets logging for Vighnaharta Receipts.

Connects with a service account, appends donation rows, and derives the next
receipt number from the last logged row.

Credentials resolution (for local + Streamlit Cloud):
1. ``st.secrets["gcp_service_account"]`` dict when available
2. Path from ``st.secrets["gcp"]["service_account_file"]`` if set
3. Local ``service_account.json`` (or ``GOOGLE_SERVICE_ACCOUNT_FILE`` env)
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from utils import format_receipt_number, next_sequence_from_last

# Columns written to the worksheet (header row expected in row 1)
HEADERS = [
    "Receipt No",
    "Date",
    "Full Name",
    "WhatsApp Number",
    "Amount",
    "Payment Mode",
    "Notes",
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DEFAULT_SERVICE_ACCOUNT_FILE = "service_account.json"
# Receipt number lives in column A
RECEIPT_COL_INDEX = 0


def _as_dict(value: Any) -> dict[str, Any]:
    """
    Normalize Streamlit secrets sections to a plain dict.

    Nested ``st.secrets`` values are ``AttrDict``, which is a Mapping but
    **not** a ``dict`` subclass — so ``isinstance(x, dict)`` is False.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _try_streamlit_secrets() -> dict[str, Any] | None:
    """Return Streamlit secrets mapping if available (local secrets.toml or Cloud)."""
    try:
        import streamlit as st

        # Force-load / access secrets; converts top-level AttrDict → dict.
        # Nested sections remain AttrDict until passed through _as_dict().
        return _as_dict(st.secrets)
    except Exception:
        return None


def _resolve_spreadsheet_config(
    spreadsheet_id: str | None = None,
    worksheet_name: str | None = None,
) -> tuple[str, str]:
    """
    Resolve spreadsheet id and worksheet name from args, secrets, or env.

    Expected secrets layout (future deployment)::

        [gcp]
        spreadsheet_id = "..."
        worksheet_name = "Donations"
        service_account_file = "service_account.json"  # optional local path

        [gcp_service_account]
        type = "service_account"
        ...
    """
    secrets = _try_streamlit_secrets() or {}
    gcp = _as_dict(secrets.get("gcp"))

    sid = (
        spreadsheet_id
        or gcp.get("spreadsheet_id")
        or os.getenv("GOOGLE_SPREADSHEET_ID")
        or secrets.get("GOOGLE_SPREADSHEET_ID")
    )
    ws = (
        worksheet_name
        or gcp.get("worksheet_name")
        or os.getenv("GOOGLE_WORKSHEET_NAME")
        or secrets.get("GOOGLE_WORKSHEET_NAME")
        or "Donations"
    )

    if not sid:
        raise ValueError(
            "Google Spreadsheet ID is not configured. "
            "Set st.secrets['gcp']['spreadsheet_id'] or GOOGLE_SPREADSHEET_ID."
        )
    return str(sid), str(ws)


def _build_credentials() -> Credentials:
    """
    Build Google service-account credentials.

    Prefer ``st.secrets['gcp_service_account']`` (dict) for cloud deploy;
    otherwise load a JSON key file from disk.
    """
    secrets = _try_streamlit_secrets() or {}

    # 1) Inline service-account JSON in Streamlit secrets
    sa_info = _as_dict(secrets.get("gcp_service_account"))
    if sa_info:
        return Credentials.from_service_account_info(sa_info, scopes=SCOPES)

    # 2) Path from secrets / env / default filename
    gcp = _as_dict(secrets.get("gcp"))
    path = (
        gcp.get("service_account_file")
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        or DEFAULT_SERVICE_ACCOUNT_FILE
    )
    key_path = Path(path)
    if not key_path.is_file():
        raise FileNotFoundError(
            f"Service account file not found: {key_path}. "
            "Place service_account.json in the project root, or set "
            "st.secrets['gcp_service_account']."
        )
    return Credentials.from_service_account_file(str(key_path), scopes=SCOPES)


def connect_to_sheet(
    spreadsheet_id: str | None = None,
    worksheet_name: str | None = None,
) -> gspread.Worksheet:
    """
    Authenticate and open the donations worksheet.

    Args:
        spreadsheet_id: Optional override; otherwise from secrets / env.
        worksheet_name: Optional override; default ``Donations``.

    Returns:
        Opened ``gspread.Worksheet``.
    """
    sid, ws_name = _resolve_spreadsheet_config(spreadsheet_id, worksheet_name)
    creds = _build_credentials()
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sid)

    try:
        worksheet = spreadsheet.worksheet(ws_name)
    except gspread.WorksheetNotFound:
        # Create worksheet with headers if it does not exist yet
        worksheet = spreadsheet.add_worksheet(title=ws_name, rows=1000, cols=len(HEADERS))
        worksheet.append_row(HEADERS, value_input_option="USER_ENTERED")

    # Ensure header row is present on an empty sheet
    existing = worksheet.row_values(1)
    if not existing:
        worksheet.append_row(HEADERS, value_input_option="USER_ENTERED")

    return worksheet


def get_last_receipt_number(worksheet: gspread.Worksheet) -> str | None:
    """
    Read the receipt number from the last data row (column A).

    Args:
        worksheet: Active donations worksheet.

    Returns:
        Last receipt number string, or None if only headers / empty.
    """
    # col_values includes the header in row 1
    col = worksheet.col_values(RECEIPT_COL_INDEX + 1)
    if len(col) <= 1:
        return None

    last = (col[-1] or "").strip()
    if not last or last == HEADERS[0]:
        return None
    return last


def get_next_receipt_number(
    worksheet: gspread.Worksheet | None = None,
    year: int | None = None,
) -> str:
    """
    Compute the next receipt number by inspecting the last sheet row.

    Format: ``VIGH-YYYY-NNNN`` (resets sequence each calendar year).

    Args:
        worksheet: Open worksheet; opens a new connection if omitted.
        year: Override year (defaults to current).

    Returns:
        Next receipt number, e.g. ``VIGH-2026-0001``.
    """
    ws = worksheet if worksheet is not None else connect_to_sheet()
    year = year if year is not None else datetime.now().year
    last = get_last_receipt_number(ws)
    sequence = next_sequence_from_last(last, year=year)
    return format_receipt_number(sequence, year=year)


def append_donation(
    donation: dict[str, Any],
    worksheet: gspread.Worksheet | None = None,
) -> list[Any]:
    """
    Append one donation row to Google Sheets.

    Expected keys: receipt_no, donor_name, whatsapp, amount, payment_mode,
    notes (optional), date (optional).

    Args:
        donation: Donation field mapping.
        worksheet: Open worksheet; opens a new connection if omitted.

    Returns:
        The row values that were written.
    """
    ws = worksheet if worksheet is not None else connect_to_sheet()

    date_str = str(
        donation.get("date")
        or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    row = [
        str(donation["receipt_no"]),
        date_str,
        str(donation["donor_name"]).strip(),
        str(donation.get("whatsapp", "")).strip(),
        donation["amount"],
        str(donation.get("payment_mode", "")).strip(),
        str(donation.get("notes") or "").strip(),
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")
    return row


def log_donation(donation: dict[str, Any]) -> list[Any]:
    """
    Convenience wrapper: connect and append a donation row.

    Args:
        donation: Donation field mapping (see ``append_donation``).

    Returns:
        The row values that were written.
    """
    worksheet = connect_to_sheet()
    return append_donation(donation, worksheet=worksheet)
