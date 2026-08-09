"""
WhatsApp delivery via WasenderAPI for Vighnaharta Receipts.

After a receipt is stored on Supabase, sends:
  1. Document message — e-pawati PDF (public URL) + short thank-you text
  2. Follow-up text — mandal story / social links

Config (``.streamlit/secrets.toml``)::

    [wasenderapi]
    ws_api_key = "..."
    plan = "trial"   # trial → 60s gap; paid/other → 5s (Wasender rate limits)
    # optional:
    # endpoint = "https://www.wasenderapi.com/api/send-message"
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any

import requests

DEFAULT_ENDPOINT = "https://www.wasenderapi.com/api/send-message"
_REQUEST_TIMEOUT_S = 45
# Wasender rate limits between the document + follow-up sends.
_TRIAL_INTER_MESSAGE_DELAY_S = 60  # trial: 1 msg/min
_PAID_INTER_MESSAGE_DELAY_S = 5  # paid: 1 msg / 5s

# Receipt document caption (shared for every donor; only phone/url/filename vary).
DOCUMENT_TEXT = (
    "E-Vargani Pawati : The paper collected through your contribution is being "
    "used to create our eco-friendly Ganesh Murti. Thank you for your valuable "
    "support! 🌱"
)

# Follow-up brand message (phone only varies).
FOLLOWUP_TEXT = (
    "🕉️ Dadar Cha Vighnaharta\n"
    "Navyuvak Mitra Mandal | Est. 1968\n"
    "Celebrating our 59th Year 🎉\n"
    "\n"
    "📸 Instagram: https://py.md/ddBAU\n"
    "\n"
    "From a small home festival to a grand 11-day celebration loved by the entire city.\n"
    "\n"
    "🌟 Our journey:\n"
    "Thermocol idols → Pure cotton Ganesh (Silver Jubilee) → "
    "Eco-friendly Tissue Paper idols (last 4 years) 🌱\n"
    "\n"
    "Through Atulya Charitable Trust, we serve our community with school supplies, "
    "health & eye camps, toppers’ felicitation, drawing competitions… and even "
    "distributed 1,000 cotton masks during COVID.\n"
    "\n"
    "More than a festival — we are tradition, devotion, social service & "
    "environmental care.\n"
    "\n"
    "📍 Maps: https://py.md/FeFMw"
)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _try_streamlit_secrets() -> dict[str, Any]:
    try:
        import streamlit as st

        return _as_dict(st.secrets)
    except Exception:
        return {}


def load_wasender_config() -> dict[str, str]:
    """
    Load WasenderAPI endpoint, bearer token, and plan.

    Secrets: ``[wasenderapi] ws_api_key``, optional ``plan`` (``trial`` | ``paid`` | …).
    Env: ``WASENDER_API_KEY``, ``WASENDER_ENDPOINT``, ``WASENDER_PLAN``.
    """
    secrets = _try_streamlit_secrets()
    section = _as_dict(secrets.get("wasenderapi"))

    api_key = (
        section.get("ws_api_key")
        or section.get("api_key")
        or section.get("token")
        or os.getenv("WASENDER_API_KEY")
        or secrets.get("WASENDER_API_KEY")
        or ""
    )
    endpoint = (
        section.get("endpoint")
        or section.get("base_url")
        or os.getenv("WASENDER_ENDPOINT")
        or DEFAULT_ENDPOINT
    )
    plan = (
        section.get("plan")
        or os.getenv("WASENDER_PLAN")
        or secrets.get("WASENDER_PLAN")
        or ""
    )

    api_key = str(api_key).strip()
    endpoint = str(endpoint).strip() or DEFAULT_ENDPOINT
    plan = str(plan).strip().lower()
    if not api_key:
        raise ValueError(
            "WasenderAPI is not configured. "
            "Set [wasenderapi] ws_api_key in secrets.toml."
        )
    return {"api_key": api_key, "endpoint": endpoint, "plan": plan}


def inter_message_delay_seconds(plan: str | None = None) -> int:
    """
    Seconds to wait after a successful first send before the follow-up.

    - ``trial`` → 60 (1 msg/min)
    - any other plan (``paid``, ``pro``, unset, …) → 5 (1 msg / 5s)
    """
    if plan is None:
        plan = load_wasender_config().get("plan", "")
    key = str(plan or "").strip().lower()
    if key == "trial":
        return _TRIAL_INTER_MESSAGE_DELAY_S
    return _PAID_INTER_MESSAGE_DELAY_S


def format_whatsapp_e164(phone: str, *, default_region: str = "91") -> str:
    """
    Normalize a phone to E.164 for Wasender (``+91xxxxxxxxxx``).

    Accepts digits-only, ``+91…``, or leading ``0`` local numbers.
    Default region India (91) when a 10-digit mobile is given.
    """
    raw = str(phone or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise ValueError("Phone number is empty.")

    # Strip leading 0 from local numbers (09876… → 9876…).
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == 10:
        digits = f"{default_region}{digits}"
    elif digits.startswith(default_region) and len(digits) >= 12:
        pass
    elif len(digits) < 10:
        raise ValueError(f"Phone number too short: {phone!r}")

    return f"+{digits}"


def _post_message(payload: dict[str, Any], *, cfg: dict[str, str] | None = None) -> dict[str, Any]:
    """POST one JSON message to WasenderAPI; return parsed body (or {})."""
    cfg = cfg or load_wasender_config()
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            cfg["endpoint"],
            json=payload,
            headers=headers,
            timeout=_REQUEST_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"WasenderAPI request failed: {exc}") from exc

    body: dict[str, Any] = {}
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            body = parsed
    except Exception:
        body = {"raw": (response.text or "")[:400]}

    if response.status_code >= 400:
        detail = body.get("message") or body.get("error") or body or response.text
        if isinstance(detail, str) and len(detail) > 400:
            detail = detail[:400] + "…"
        raise RuntimeError(
            f"WasenderAPI error (HTTP {response.status_code}): {detail}"
        )
    return body


def send_document_message(
    *,
    to: str,
    document_url: str,
    file_name: str,
    text: str = DOCUMENT_TEXT,
) -> dict[str, Any]:
    """Send PDF document message (public Supabase URL)."""
    payload = {
        "to": format_whatsapp_e164(to),
        "text": text,
        "documentUrl": document_url,
        "fileName": file_name,
    }
    return _post_message(payload)


def send_text_message(*, to: str, text: str = FOLLOWUP_TEXT) -> dict[str, Any]:
    """Send plain follow-up text message."""
    payload = {
        "to": format_whatsapp_e164(to),
        "text": text,
    }
    return _post_message(payload)


def send_receipt_whatsapp(
    *,
    phone: str,
    document_url: str,
    file_name: str,
) -> dict[str, Any]:
    """
    Full donor delivery: document (e-pawati) then follow-up text.

    Args:
        phone: Donor WhatsApp (10-digit or E.164).
        document_url: Public Supabase PDF URL.
        file_name: Attachment name, e.g. ``DCV-2026-0032.pdf``.

    Returns:
        ``{"document": {...}, "followup": {...}, "to": "+91…"}``.
    """
    url = str(document_url or "").strip()
    if not url:
        raise ValueError("document_url is required to send the e-pawati PDF.")
    name = str(file_name or "").strip() or "pawati.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"

    to = format_whatsapp_e164(phone)
    cfg = load_wasender_config()
    doc_resp = send_document_message(
        to=to, document_url=url, file_name=name, text=DOCUMENT_TEXT
    )
    # Only wait after a successful document send (send_document_message raises otherwise).
    delay = inter_message_delay_seconds(cfg.get("plan"))
    if delay > 0:
        time.sleep(delay)
    follow_resp = send_text_message(to=to, text=FOLLOWUP_TEXT)
    return {
        "to": to,
        "document": doc_resp,
        "followup": follow_resp,
        "inter_message_delay_s": delay,
        "plan": cfg.get("plan") or "",
    }


def _self_check() -> None:
    assert format_whatsapp_e164("9876543210") == "+919876543210"
    assert format_whatsapp_e164("919876543210") == "+919876543210"
    assert format_whatsapp_e164("+91 98765 43210") == "+919876543210"
    assert format_whatsapp_e164("09876543210") == "+919876543210"
    assert inter_message_delay_seconds("trial") == 60
    assert inter_message_delay_seconds("TRIAL") == 60
    assert inter_message_delay_seconds("pro") == 5
    assert inter_message_delay_seconds("paid") == 5
    assert inter_message_delay_seconds("") == 5
    print("wasender_sender self-check OK")


if __name__ == "__main__":
    _self_check()
