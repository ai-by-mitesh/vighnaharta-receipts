"""
Receipt PDF dispatcher: choose fpdf (legacy) vs e-pawati template overlay.

Toggle via (first match wins):
  1. Environment variable ``RECEIPT_METHOD``
  2. Streamlit secrets: ``[receipt] method = "..."``
  3. Default: ``fpdf`` (existing landscape generator)

Accepted values:
  - ``fpdf`` / ``generated`` / ``legacy``  → pdf_generator.generate_receipt
  - ``template`` / ``overlay`` / ``e-pawati`` → template_receipt.generate_template_receipt
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pdf_generator import generate_receipt
from template_receipt import generate_template_receipt

# Canonical method names used after normalization.
METHOD_FPDF = "fpdf"
METHOD_TEMPLATE = "template"

_FPDF_ALIASES = frozenset({METHOD_FPDF, "generated", "legacy", "old"})
_TEMPLATE_ALIASES = frozenset({METHOD_TEMPLATE, "overlay", "e-pawati", "epawati"})


def _from_secrets() -> str | None:
    """Read ``st.secrets['receipt']['method']`` when Streamlit is available."""
    try:
        import streamlit as st

        section = st.secrets.get("receipt")
        if section is None:
            return None
        # AttrDict / dict
        if hasattr(section, "get"):
            value = section.get("method")
        else:
            value = section["method"] if "method" in section else None
        return str(value) if value is not None else None
    except Exception:
        return None


def get_receipt_method() -> str:
    """
    Resolve which PDF backend to use.

    Returns:
        ``fpdf`` or ``template``.
    """
    raw = (os.environ.get("RECEIPT_METHOD") or _from_secrets() or METHOD_FPDF)
    key = str(raw).strip().lower()
    if key in _TEMPLATE_ALIASES:
        return METHOD_TEMPLATE
    if key in _FPDF_ALIASES:
        return METHOD_FPDF
    # Unknown value → safe default (do not break production).
    return METHOD_FPDF


def generate_donation_receipt(
    donation: dict[str, Any],
    output_dir: str | Path | None = None,
) -> Path:
    """
    Generate a receipt PDF using the configured method.

    Same ``donation`` contract as ``pdf_generator.generate_receipt``:
    receipt_no, donor_name, amount, plus optional payment_mode/date/notes/etc.
    """
    method = get_receipt_method()
    kwargs: dict[str, Any] = {}
    if output_dir is not None:
        kwargs["output_dir"] = output_dir

    if method == METHOD_TEMPLATE:
        return generate_template_receipt(donation, **kwargs)
    return generate_receipt(donation, **kwargs)
