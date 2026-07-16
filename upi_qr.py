"""
Dynamic UPI QR helpers for the Streamlit donation app.

Payee details come from ``st.secrets``::

    [upi]
    upi_id = "..."
    payee_name = "..."
"""

from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Any
from urllib.parse import quote

import qrcode


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def load_upi_settings() -> tuple[str, str]:
    """
    Load UPI id and payee name from Streamlit secrets.

    Returns:
        ``(upi_id, payee_name)``.

    Raises:
        ValueError: If secrets are missing or incomplete.
    """
    try:
        import streamlit as st

        section = _as_dict(st.secrets.get("upi"))
    except Exception as exc:
        raise ValueError(
            "Could not load UPI settings from st.secrets. "
            "Add a [upi] section to .streamlit/secrets.toml."
        ) from exc

    upi_id = str(section.get("upi_id") or section.get("UPI_ID") or "").strip()
    payee_name = str(section.get("payee_name") or section.get("PAYEE_NAME") or "").strip()
    if not upi_id or not payee_name:
        raise ValueError(
            "UPI settings incomplete. Set upi_id and payee_name under [upi] in secrets.toml."
        )
    return upi_id, payee_name


def build_upi_uri(note: str, *, upi_id: str, payee_name: str) -> str:
    """Build a standard UPI pay deep link (no amount)."""
    return (
        f"upi://pay?pa={upi_id}"
        f"&pn={quote(payee_name)}"
        f"&tn={quote(note)}"
        f"&cu=INR"
    )


def qr_png_bytes(uri: str, *, box_size: int = 8, border: int = 2) -> bytes:
    """Encode ``uri`` as a PNG QR image (bytes)."""
    qr = qrcode.QRCode(box_size=box_size, border=border)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_upi_qr_for_note(note: str) -> tuple[bytes, str]:
    """
    Load secrets, build UPI URI for ``note``, return (png_bytes, uri).

    ``note`` is typically the next receipt number (e.g. DCV-2026-0001).
    """
    upi_id, payee_name = load_upi_settings()
    uri = build_upi_uri(note, upi_id=upi_id, payee_name=payee_name)
    return qr_png_bytes(uri), uri
