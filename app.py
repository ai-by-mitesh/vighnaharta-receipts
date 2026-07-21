"""
Main Streamlit application for Vighnaharta Receipts.

Paperless donation e-receipt system for Dadar Cha Vighnaharta Ganpati Mandal.

Auth:
- Login via auth.py + st.secrets ([credentials] / [passwords])
- Session idle timeout (30 minutes)

Donation flow (after login):
1. Validate the form
2. Fetch next receipt number from Google Sheets (fallback if offline)
3. Generate PDF receipt
4. Log the donation row to Google Sheets
5. Show success UI and auto-download the PDF in the browser
"""

from __future__ import annotations

import base64
import html
import time
from datetime import timedelta
from typing import Any

import streamlit as st

from lib.auth import (
    ensure_active_session,
    render_login_page,
    # render_session_bar,  # re-enable with the session bar call below
)
from lib.pdf_generator import DEFAULT_NOTES
from lib.receipt_service import generate_donation_receipt
from lib.sheets_logger import append_donation, connect_to_sheet, get_next_receipt_number
from lib.upi_qr import generate_upi_qr_for_note
from lib.utils import format_currency, format_receipt_number, normalize_phone, now_ist

PAYMENT_MODES = ("Cash", "UPI", "Other")
PAYMENT_ICONS = {"Cash": "💵", "UPI": "📱", "Other": "💳"}

# Success overlay lives in session_state (survives download rerun), then auto-hides.
SUCCESS_CARD_SECONDS = 5
_SESSION_SUCCESS_KEY = "receipt_success"
_SESSION_DOWNLOAD_PENDING_KEY = "receipt_success_download_pending"
_SESSION_UPI_QR_KEY = "upi_qr_popup"

# QR icon as CSS data-URI (white stroke) painted on the Streamlit button
_HERO_QR_ICON_CSS = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
    "stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E"
    "%3Crect x='3' y='3' width='7' height='7' rx='1'/%3E"
    "%3Crect x='14' y='3' width='7' height='7' rx='1'/%3E"
    "%3Crect x='3' y='14' width='7' height='7' rx='1'/%3E"
    "%3Cpath d='M14 14h.01'/%3E%3Cpath d='M17 14h.01'/%3E%3Cpath d='M14 17h.01'/%3E"
    "%3Cpath d='M17 17h.01'/%3E%3Cpath d='M14 20h.01'/%3E%3Cpath d='M17 20h.01'/%3E"
    "%3Cpath d='M20 14h.01'/%3E%3Cpath d='M20 17h.01'/%3E%3Cpath d='M20 20h.01'/%3E"
    "%3C/svg%3E"
)

# Injected once per run — modern card UI without extra frontend deps.
_CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap');

html, body, [class*="css"],
.stApp, .stApp *,
.stMarkdown, .stTextInput, .stNumberInput, .stSelectbox, .stTextArea, .stRadio,
.stButton, .stForm, div[data-testid="stForm"],
button, input, textarea, label, p, h1, h2, h3, h4, h5, h6, span {
    font-family: "Poppins", sans-serif !important;
}

/* Soft page backdrop */
.stApp {
    background:
        radial-gradient(1200px 500px at 10% -10%, #ffe0c2 0%, transparent 55%),
        radial-gradient(900px 420px at 100% 0%, #ffd6a8 0%, transparent 50%),
        linear-gradient(180deg, #fffaf5 0%, #ffffff 42%, #fff8f1 100%);
}

/* Hide default Streamlit chrome noise */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

.block-container {
    padding-top: 1.4rem;
    padding-bottom: 3rem;
    max-width: 760px;
}

/* —— Hero (login + form: same main-branch card) —— */
.vr-hero {
    position: relative;
    overflow: hidden;
    border-radius: 22px;
    padding: 1.6rem 1.7rem 1.45rem;
    margin-bottom: 1.25rem;
    color: #fff;
    background: linear-gradient(135deg, #e85d04 0%, #f48c06 48%, #ffba08 120%);
    box-shadow:
        0 18px 40px rgba(232, 93, 4, 0.28),
        0 2px 0 rgba(255, 255, 255, 0.25) inset;
}

/*
 * Form page: wrap pure .vr-hero + st.button so height matches main,
 * and pin the QR control to the right edge (not a left-shifted column).
 */
div.st-key-form_hero_wrap {
    position: relative !important;
    margin-bottom: 1.25rem;
}

div.st-key-form_hero_wrap .vr-hero {
    margin-bottom: 0;
    /* room on the right so title never sits under the QR tile */
    padding-right: 5.25rem;
}

/* Pin QR button to the right-middle of the hero card (slightly below center) */
div.st-key-form_hero_wrap div.st-key-hero_upi_qr {
    position: absolute !important;
    right: 1.35rem;
    top: calc(50% + 5px);
    transform: translateY(-50%);
    z-index: 5;
    width: auto !important;
    margin: 0 !important;
    height: auto !important;
}

div.st-key-form_hero_wrap div.st-key-hero_upi_qr [data-testid="stTooltipHoverTarget"],
div.st-key-form_hero_wrap div.st-key-hero_upi_qr .stButton,
div.st-key-form_hero_wrap div.st-key-hero_upi_qr button {
    width: 3.25rem !important;
    height: 3.25rem !important;
    min-width: 3.25rem !important;
    min-height: 3.25rem !important;
}

div.st-key-form_hero_wrap div.st-key-hero_upi_qr button {
    padding: 0 !important;
    border-radius: 14px !important;
    border: 1px solid rgba(255, 255, 255, 0.45) !important;
    background:
        url("__HERO_QR_ICON__") center / 1.95rem 1.95rem no-repeat,
        rgba(255, 255, 255, 0.22) !important;
    box-shadow:
        0 8px 18px rgba(0, 0, 0, 0.12),
        0 1px 0 rgba(255, 255, 255, 0.30) inset !important;
    color: transparent !important;
    transition: background 0.12s ease, box-shadow 0.12s ease;
}

div.st-key-form_hero_wrap div.st-key-hero_upi_qr button:hover {
    background:
        url("__HERO_QR_ICON__") center / 1.95rem 1.95rem no-repeat,
        rgba(255, 255, 255, 0.34) !important;
    box-shadow:
        0 12px 22px rgba(0, 0, 0, 0.16),
        0 1px 0 rgba(255, 255, 255, 0.34) inset !important;
}

div.st-key-form_hero_wrap div.st-key-hero_upi_qr button p,
div.st-key-form_hero_wrap div.st-key-hero_upi_qr button span {
    color: transparent !important;
    font-size: 0 !important;
    line-height: 0 !important;
}

/*
 * UPI QR popup — same fixed full-screen pattern as receipt success.
 * Backdrop is a full-screen Streamlit button (click outside closes).
 * Card sits above it; no X control.
 */
div.st-key-upi_qr_dismiss {
    position: fixed !important;
    inset: 0 !important;
    z-index: 2147483000 !important;
    width: 100vw !important;
    height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
}

div.st-key-upi_qr_dismiss [data-testid="stTooltipHoverTarget"],
div.st-key-upi_qr_dismiss .stButton {
    width: 100% !important;
    height: 100% !important;
}

div.st-key-upi_qr_dismiss button {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    min-width: 100vw !important;
    min-height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    border-radius: 0 !important;
    background: rgba(20, 18, 16, 0.48) !important;
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    box-shadow: none !important;
    color: transparent !important;
    cursor: default !important;
}

div.st-key-upi_qr_dismiss button p,
div.st-key-upi_qr_dismiss button span {
    color: transparent !important;
    font-size: 0 !important;
    line-height: 0 !important;
}

.vr-qr-overlay {
    position: fixed;
    inset: 0;
    z-index: 2147483001;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.25rem;
    background: transparent;
    pointer-events: none; /* clicks outside the card fall through to the backdrop button */
}

.vr-qr-card {
    pointer-events: auto;
    width: min(300px, 100%);
    border-radius: 20px;
    border: 1px solid rgba(232, 93, 4, 0.14);
    background: linear-gradient(180deg, #fff8f1 0%, #ffffff 55%);
    padding: 1.4rem 1.35rem 1.25rem;
    margin: 0;
    text-align: center;
    box-shadow:
        0 28px 64px rgba(20, 18, 16, 0.28),
        0 2px 0 rgba(255, 255, 255, 0.85) inset;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
}

.vr-qr-title {
    font-family: "Poppins", sans-serif !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    color: #1c1c1c !important;
    letter-spacing: -0.01em;
    margin: 0 0 0.15rem 0 !important;
    text-align: center !important;
}

.vr-qr-card img {
    display: block;
    width: 200px;
    height: 200px;
    margin: 0 auto;
    border-radius: 12px;
    border: 1px solid rgba(232, 93, 4, 0.10);
    background: #fff;
}

.vr-qr-note {
    font-family: "Poppins", sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    color: #e85d04 !important;
    letter-spacing: 0.02em;
    text-align: center !important;
    margin: 0 !important;
    word-break: break-all;
}

.vr-hero::after {
    content: "";
    position: absolute;
    right: -40px;
    top: -40px;
    width: 180px;
    height: 180px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.14);
    pointer-events: none;
}

.vr-hero::before {
    content: "";
    position: absolute;
    left: -30px;
    bottom: -50px;
    width: 140px;
    height: 140px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.10);
    pointer-events: none;
}

.vr-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    opacity: 0.92;
    background: rgba(255, 255, 255, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.28);
    border-radius: 999px;
    padding: 0.28rem 0.7rem;
    margin-bottom: 0.75rem;
}

.vr-hero h1 {
    font-family: "Poppins", sans-serif !important;
    font-size: 1.85rem;
    font-weight: 700;
    line-height: 1.15;
    margin: 0 0 0.4rem 0;
    letter-spacing: -0.02em;
}

.vr-hero p {
    margin: 0;
    font-size: 0.98rem;
    opacity: 0.95;
    max-width: 34rem;
    line-height: 1.45;
}

.vr-hero-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 1.05rem;
}

.vr-chip {
    font-size: 0.78rem;
    font-weight: 600;
    background: rgba(255, 255, 255, 0.16);
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 999px;
    padding: 0.32rem 0.72rem;
}

/* —— Form card —— */
.vr-card-label {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin: 0.25rem 0 0.85rem;
}

.vr-card-label h2 {
    font-family: "Poppins", sans-serif !important;
    font-size: 1.2rem;
    font-weight: 700;
    color: #1c1c1c;
    margin: 0;
    letter-spacing: -0.01em;
}

.vr-card-label span {
    font-size: 0.78rem;
    font-weight: 600;
    color: #e85d04;
    background: #fff4e8;
    border: 1px solid #ffd7b0;
    border-radius: 999px;
    padding: 0.28rem 0.65rem;
    white-space: nowrap;
}

div[data-testid="stForm"] {
    background: rgba(255, 255, 255, 0.88);
    border: 1px solid rgba(232, 93, 4, 0.12);
    border-radius: 20px;
    padding: 1.35rem 1.35rem 1.15rem;
    box-shadow:
        0 10px 30px rgba(28, 28, 28, 0.05),
        0 1px 0 rgba(255, 255, 255, 0.8) inset;
    backdrop-filter: blur(8px);
}

/* Inputs */
.stTextInput label,
.stNumberInput label,
.stSelectbox label,
.stTextArea label,
.stRadio label {
    font-weight: 600 !important;
    color: #2b2b2b !important;
    font-size: 0.9rem !important;
}

.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    border-radius: 12px !important;
    border: 1px solid #eadfd3 !important;
    background: #fffdfb !important;
    min-height: 2.7rem;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.stTextInput input:focus,
.stNumberInput input:focus,
.stTextArea textarea:focus {
    border-color: #e85d04 !important;
    box-shadow: 0 0 0 3px rgba(232, 93, 4, 0.15) !important;
}

div[data-baseweb="select"] > div {
    border-radius: 12px !important;
    border-color: #eadfd3 !important;
    background: #fffdfb !important;
}

/* Radio as modern mode picker */
div[role="radiogroup"] {
    gap: 0.5rem !important;
    flex-wrap: wrap !important;
}

div[role="radiogroup"] label {
    background: #fff8f1 !important;
    border: 1px solid #f0e0d0 !important;
    border-radius: 12px !important;
    padding: 0.55rem 0.9rem !important;
    margin: 0 !important;
    transition: all 0.15s ease;
}

div[role="radiogroup"] label:hover {
    border-color: #e85d04 !important;
    background: #fff1e3 !important;
}

/* Primary CTA */
div[data-testid="stForm"] .stButton > button[kind="primary"],
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #e85d04 0%, #f48c06 100%) !important;
    border: none !important;
    border-radius: 14px !important;
    font-weight: 700 !important;
    letter-spacing: 0.01em;
    min-height: 3rem;
    box-shadow: 0 10px 22px rgba(232, 93, 4, 0.28) !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease;
}

div[data-testid="stForm"] .stButton > button[kind="primary"]:hover,
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 14px 28px rgba(232, 93, 4, 0.34) !important;
}

/* Success receipt — fixed overlay on top of everything */
.vr-success-overlay {
    position: fixed;
    inset: 0;
    z-index: 2147483000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.25rem;
    background: rgba(20, 18, 16, 0.48);
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    /* No enter animation: fragment re-renders every 1s and would re-trigger it. */
}

.vr-success {
    width: min(440px, 100%);
    border-radius: 20px;
    border: 1px solid rgba(34, 160, 90, 0.18);
    background:
        linear-gradient(180deg, #f3fff8 0%, #ffffff 55%);
    padding: 1.35rem 1.4rem 1.2rem;
    margin: 0;
    box-shadow:
        0 28px 64px rgba(20, 18, 16, 0.28),
        0 2px 0 rgba(255, 255, 255, 0.85) inset;
}

.vr-success-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #178a4b;
    background: #e5f8ed;
    border-radius: 999px;
    padding: 0.28rem 0.65rem;
    margin-bottom: 0.7rem;
}

.vr-success h3 {
    font-family: "Poppins", sans-serif !important;
    font-size: 1.35rem;
    margin: 0 0 0.25rem 0;
    color: #14261b;
}

.vr-success .vr-receipt-id {
    font-size: 1.05rem;
    font-weight: 700;
    color: #e85d04;
    margin-bottom: 1rem;
}

.vr-success-foot {
    margin-top: 0.95rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: #6b7c70;
    text-align: center;
}

/* Loading overlay (same shell as success; orange card) */
.vr-loading {
    width: min(360px, 100%);
    border-radius: 20px;
    border: 1px solid rgba(232, 93, 4, 0.18);
    background: linear-gradient(180deg, #fff8f1 0%, #ffffff 55%);
    padding: 1.6rem 1.5rem 1.45rem;
    margin: 0 auto;
    text-align: center !important;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow:
        0 28px 64px rgba(20, 18, 16, 0.28),
        0 2px 0 rgba(255, 255, 255, 0.85) inset;
}

.vr-loading-spinner {
    width: 2.4rem;
    height: 2.4rem;
    margin: 0 auto 1rem;
    border-radius: 50%;
    border: 3px solid #ffe0c2;
    border-top-color: #e85d04;
    animation: vr-spin 0.75s linear infinite;
    flex-shrink: 0;
}

.vr-loading h3 {
    font-family: "Poppins", sans-serif !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    line-height: 1.3 !important;
    margin: 0 0 0.35rem 0 !important;
    padding: 0 !important;
    color: #1c1c1c !important;
    text-align: center !important;
    width: 100%;
    /* Optical nudge — title reads slightly left of the spinner otherwise */
    transform: translateX(12px);
}

.vr-loading p {
    margin: 0 !important;
    padding: 0 !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    line-height: 1.4 !important;
    color: #8a7460 !important;
    text-align: center !important;
    width: 100%;
}

@keyframes vr-spin {
    to { transform: rotate(360deg); }
}

.vr-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem 1rem;
}

.vr-field {
    background: #fffaf5;
    border: 1px solid #f0e4d7;
    border-radius: 12px;
    padding: 0.7rem 0.85rem;
}

.vr-field .lbl {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #8a7460;
    margin-bottom: 0.2rem;
}

.vr-field .val {
    font-size: 0.98rem;
    font-weight: 600;
    color: #1c1c1c;
    word-break: break-word;
}

.vr-field.full {
    grid-column: 1 / -1;
}

.vr-status-ok { color: #178a4b; }
.vr-status-warn { color: #b45309; }

.vr-footnote {
    text-align: center;
    color: #9a8572;
    font-size: 0.82rem;
    margin-top: 1.5rem;
}

/* Hide sidebar entirely — session controls live in the main form flow */
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}

/* Hide Streamlit's built-in password show/hide control ("visibility" text) */
div[data-testid="stTextInput"] button,
div[data-testid="stTextInputRootElement"] button,
div[data-baseweb="base-input"] button,
/* Material icon / visibility adornment inside password inputs */
[data-testid="stTextInput"] [data-testid="stBaseButton-secondary"],
[data-testid="stTextInput"] [kind="secondary"] {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    min-width: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    overflow: hidden !important;
}

/* Login password emoji toggle only (not the form-hero QR tertiary button) */
div[data-testid="stHorizontalBlock"] > div:last-child button[data-testid="stBaseButton-secondary"] {
    display: inline-flex !important;
    visibility: visible !important;
    width: 100% !important;
    min-width: 2.7rem !important;
    padding: 0.4rem !important;
    border-radius: 12px !important;
    min-height: 2.7rem;
    border: 1px solid #eadfd3 !important;
    background: #fffdfb !important;
    font-size: 1.15rem !important;
}

/* —— Session bar (above donation form) —— */
.vr-session-bar {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(232, 93, 4, 0.14);
    border-radius: 16px;
    padding: 0.85rem 1.05rem;
    box-shadow: 0 8px 22px rgba(28, 28, 28, 0.04);
    margin-bottom: 0;
}

/* Space between session bar block and hero / form below */
.vr-session-gap {
    height: 1.15rem;
}

.vr-session-main {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem 0.5rem;
    margin-bottom: 0.3rem;
}

.vr-session-user {
    font-weight: 700;
    color: #e85d04;
    font-size: 0.98rem;
}

.vr-session-dot {
    color: #c4b0a0;
}

.vr-session-meta {
    font-size: 0.86rem;
    color: #5c4f44;
    font-weight: 500;
}

.vr-session-idle {
    font-size: 0.8rem;
    color: #8a7460;
    line-height: 1.4;
}

.vr-session-idle strong {
    color: #1c1c1c;
    font-weight: 600;
}

.vr-session-idle-note {
    color: #b09a88;
    margin-left: 0.2rem;
}

@media (max-width: 640px) {
    .vr-hero h1 { font-size: 1.5rem; }
    .vr-grid { grid-template-columns: 1fr; }
    div[data-testid="stForm"] { padding: 1rem; }
}
</style>
"""


def _inject_styles() -> None:
    st.markdown(
        _CUSTOM_CSS.replace("__HERO_QR_ICON__", _HERO_QR_ICON_CSS),
        unsafe_allow_html=True,
    )


def _clear_upi_qr_popup() -> None:
    st.session_state.pop(_SESSION_UPI_QR_KEY, None)


def _peek_next_receipt_number() -> str:
    """
    Next receipt number for the UPI note (read-only peek).

    Does not burn the offline local sequence counter.
    """
    try:
        return get_next_receipt_number()
    except Exception:
        seq = int(st.session_state.get("local_receipt_seq", 0)) + 1
        return format_receipt_number(seq)


def _open_upi_qr_popup() -> None:
    """Build QR from next sheet receipt number and stash for the overlay."""
    try:
        note = _peek_next_receipt_number()
        png, _uri = generate_upi_qr_for_note(note)
        st.session_state[_SESSION_UPI_QR_KEY] = {"note": note, "png": png}
    except Exception as exc:
        st.session_state.pop(_SESSION_UPI_QR_KEY, None)
        st.error(f"Could not generate UPI QR ({exc}).")


def _render_upi_qr_popup_if_any() -> None:
    """
    Center-screen QR overlay (same shell as receipt success).

    No X button. Click the dimmed area outside the card to close.
    """
    payload = st.session_state.get(_SESSION_UPI_QR_KEY)
    if not payload:
        return

    # Full-screen backdrop button under the card — click = dismiss
    if st.button(
        "Close",
        key="upi_qr_dismiss",
        help="Click outside the card to close",
        type="tertiary",
        width="stretch",
    ):
        _clear_upi_qr_popup()
        st.rerun()

    qr_b64 = base64.b64encode(bytes(payload["png"])).decode("ascii")
    note_safe = html.escape(str(payload["note"]))
    st.markdown(
        f"""
        <div class="vr-qr-overlay" role="dialog" aria-modal="true" aria-label="Scan to Pay">
            <div class="vr-qr-card">
                <p class="vr-qr-title">Scan to Pay</p>
                <img src="data:image/png;base64,{qr_b64}" width="200" height="200" alt="UPI QR code" />
                <p class="vr-qr-note">{note_safe}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_hero() -> None:
    """
    Form hero: same pure HTML ``.vr-hero`` as main (correct height).

    QR is a real ``st.button`` pinned to the right edge of the card via CSS
    (no columns layout, no query-param navigation).
    """
    if "show_upi_qr" in st.query_params:
        try:
            del st.query_params["show_upi_qr"]
        except Exception:
            pass

    with st.container(key="form_hero_wrap"):
        # Exact main-branch markup / padding / h1 margins → original height
        st.markdown(
            """
            <div class="vr-hero">
                <h1>E-Pawati</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "QR",
            key="hero_upi_qr",
            help="Generate UPI payment QR",
            type="tertiary",
            width="content",
        ):
            # Show loader first (same pattern as e-pawati generation), then build QR
            loading_slot = st.empty()
            with loading_slot:
                _render_loading_overlay(
                    title="Generating QR",
                    subtitle="Fetching next pawati number",
                )
            try:
                _open_upi_qr_popup()
            finally:
                loading_slot.empty()


def _init_page() -> None:
    """Must run before any other Streamlit body output."""
    st.set_page_config(
        page_title="दादरचा विघ्नहर्ता ई-पावती",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    _inject_styles()


def _parse_amount(raw: str | float | int | None) -> float | None:
    """
    Parse a typed amount string (no number-input steppers).

    Accepts ``501``, ``501.50``, ``1,000``. Returns None if empty/invalid.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(",", "").replace("₹", "").replace("Rs.", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _validate(
    name: str,
    whatsapp: str,
    amount_raw: str | float | int | None,
) -> tuple[list[str], float | None]:
    """
    Validate form fields.

    Returns:
        (errors, parsed_amount). parsed_amount is set only when amount is valid.
    """
    errors: list[str] = []
    if not name.strip():
        errors.append("Full name is required.")

    digits = normalize_phone(whatsapp)
    if not digits:
        errors.append("WhatsApp number is required.")
    elif len(digits) < 10:
        errors.append("WhatsApp number should have at least 10 digits.")

    amount = _parse_amount(amount_raw)
    if amount_raw is None or (isinstance(amount_raw, str) and not str(amount_raw).strip()):
        errors.append("Amount is required.")
    elif amount is None:
        errors.append("Amount must be a valid number.")
    elif amount <= 0:
        errors.append("Amount must be greater than zero.")

    return errors, amount


def _allocate_receipt_number() -> tuple[str, object | None]:
    """
    Get the next receipt number from Sheets when possible.

    Returns:
        (receipt_no, worksheet_or_None). Worksheet is reused for the append
        so we do not open two connections per submission.
    """
    try:
        worksheet = connect_to_sheet()
        receipt_no = get_next_receipt_number(worksheet)
        return receipt_no, worksheet
    except Exception as exc:
        st.warning(
            f"Could not reach Google Sheets for pawati numbering ({exc}). "
            "Using a temporary local number — row will not be logged until Sheets is configured."
        )
        if "local_receipt_seq" not in st.session_state:
            st.session_state.local_receipt_seq = 0
        st.session_state.local_receipt_seq += 1
        receipt_no = format_receipt_number(st.session_state.local_receipt_seq)
        return receipt_no, None


def _render_loading_overlay(
    title: str = "Creating E-Pawati",
    subtitle: str = "Generating PDF & syncing to Sheets",
) -> None:
    """Fixed overlay while slow work runs (same shell as success / QR popup)."""
    safe_title = html.escape(title)
    safe_sub = html.escape(subtitle)
    st.markdown(
        f"""
        <div class="vr-success-overlay" role="status" aria-live="polite" aria-busy="true">
            <div class="vr-loading">
                <div class="vr-loading-spinner" aria-hidden="true"></div>
                <h3 style="text-align:center;margin:0 0 0.35rem 0;width:100%;transform:translateX(12px);">{safe_title}</h3>
                <p style="text-align:center;margin:0;width:100%;">{safe_sub}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_success_card(
    *,
    receipt_no: str,
    name: str,
    amount: float,
    payment_mode: str,
    phone: str,
    date_display: str,
    notes: str,
    sheet_ok: bool,
    seconds_left: int,
) -> None:
    """Polished post-submit summary card (overlay)."""
    icon = PAYMENT_ICONS.get(payment_mode, "💳")
    safe_name = html.escape(name.strip())
    safe_receipt = html.escape(receipt_no)
    safe_phone = html.escape(phone)
    safe_mode = html.escape(payment_mode)
    safe_date = html.escape(date_display)
    safe_amount = html.escape(format_currency(amount))
    left = max(0, int(seconds_left))
    close_label = "closes in 1s" if left == 1 else f"closes in {left}s"

    sheet_html = (
        '<span class="vr-status-ok">✓ Logged to Google Sheets</span>'
        if sheet_ok
        else '<span class="vr-status-warn">⚠ Not logged to Sheets</span>'
    )
    notes_block = ""
    if notes.strip():
        notes_block = f"""
        <div class="vr-field full">
            <div class="lbl">Notes</div>
            <div class="val">{html.escape(notes.strip())}</div>
        </div>
        """

    st.markdown(
        f"""
        <div class="vr-success-overlay" role="status" aria-live="polite">
            <div class="vr-success">
                <div class="vr-success-badge">✓ Pawati issued</div>
                <h3>Thank you, {safe_name}!</h3>
                <div class="vr-receipt-id">{safe_receipt}</div>
                <div class="vr-grid">
                    <div class="vr-field">
                        <div class="lbl">Amount</div>
                        <div class="val">{safe_amount}</div>
                    </div>
                    <div class="vr-field">
                        <div class="lbl">Payment</div>
                        <div class="val">{icon} {safe_mode}</div>
                    </div>
                    <div class="vr-field">
                        <div class="lbl">WhatsApp</div>
                        <div class="val">{safe_phone}</div>
                    </div>
                    <div class="vr-field">
                        <div class="lbl">Date</div>
                        <div class="val">{safe_date}</div>
                    </div>
                    <div class="vr-field full">
                        <div class="lbl">Sync status</div>
                        <div class="val">{sheet_html}</div>
                    </div>
                    <!-- {notes_block} --!>
                </div>
                <div class="vr-success-foot">Download started · {close_label}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _trigger_pdf_download(
    pdf_bytes: bytes,
    filename: str,
    *,
    key: str,
    auto_click: bool = True,
) -> None:
    """
    Offer a PDF download (hidden button). Optionally auto-click once.

    Streamlit's download button causes a script rerun; callers must keep the
    success card in ``st.session_state`` so it survives that rerun.
    """
    st.markdown(
        """
        <style>
        /* Off-screen so there is no visible download button */
        div[data-testid="stDownloadButton"] {
            position: fixed !important;
            left: -10000px !important;
            top: 0 !important;
            width: 1px !important;
            height: 1px !important;
            opacity: 0 !important;
            overflow: hidden !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.download_button(
        label="Download PDF pawati",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        key=key,
    )
    if not auto_click:
        return

    # st.iframe replaces deprecated st.components.v1.html (raw HTML string).
    st.iframe(
        """
        <script>
        (function () {
            const doc = window.parent.document;
            function tryClick() {
                const nodes = doc.querySelectorAll(
                    'div[data-testid="stDownloadButton"] button'
                );
                if (!nodes.length) return false;
                nodes[nodes.length - 1].click();
                return true;
            }
            if (tryClick()) return;
            let n = 0;
            const id = setInterval(function () {
                n += 1;
                if (tryClick() || n > 40) clearInterval(id);
            }, 100);
        })();
        </script>
        """,
        height=1,
    )


def _process_donation(
    name: str,
    whatsapp: str,
    amount: float,
    payment_mode: str,
    notes: str,
) -> None:
    """Generate receipt number, PDF, log to sheet; stash success UI in session."""
    receipt_no, worksheet = _allocate_receipt_number()
    now = now_ist()
    date_display = now.strftime("%d %B %Y")
    date_log = now.strftime("%Y-%m-%d %H:%M:%S")
    phone = normalize_phone(whatsapp)
    notes_final = notes.strip() or DEFAULT_NOTES

    donation = {
        "receipt_no": receipt_no,
        "donor_name": name.strip(),
        "whatsapp": phone,
        "amount": amount,
        "payment_mode": payment_mode,
        "notes": notes_final,
        "date": date_display,
    }

    try:
        # Backend: RECEIPT_METHOD env or st.secrets [receipt].method
        # template → in-memory only; fpdf → also writes receipts/*.pdf
        pdf_bytes, pdf_name = generate_donation_receipt(donation)
    except Exception as exc:
        st.error(f"Failed to generate PDF: {exc}")
        return

    sheet_ok = False
    if worksheet is not None:
        try:
            append_donation(
                {
                    **donation,
                    "date": date_log,
                },
                worksheet=worksheet,
            )
            sheet_ok = True
        except Exception as exc:
            st.error(f"PDF created, but logging to Google Sheets failed: {exc}")

    # Persist so the success card survives the download-button rerun.
    st.session_state[_SESSION_SUCCESS_KEY] = {
        "receipt_no": receipt_no,
        "name": name.strip(),
        "amount": amount,
        "payment_mode": payment_mode,
        "phone": phone,
        "date_display": date_display,
        "notes": notes_final,
        "sheet_ok": sheet_ok,
        "pdf_bytes": pdf_bytes,
        "pdf_name": pdf_name,
        "shown_at": time.time(),
    }
    st.session_state[_SESSION_DOWNLOAD_PENDING_KEY] = True


@st.fragment(run_every=timedelta(seconds=1))
def _render_receipt_success_if_any() -> None:
    """
    Show the success receipt as a fixed overlay, auto-download once, hide after 10s.

    Fragment ticks every second so the popup can dismiss without freezing the
    page. Data lives in session_state so the download-button rerun keeps it.
    """
    data: dict[str, Any] | None = st.session_state.get(_SESSION_SUCCESS_KEY)
    if not data:
        return

    shown_at = float(data.get("shown_at") or time.time())
    age = time.time() - shown_at
    seconds_left = max(0, int(SUCCESS_CARD_SECONDS - age + 0.999))  # ceil remaining

    # Time is up — clear and stop rendering (next fragment tick stays empty).
    if age >= SUCCESS_CARD_SECONDS:
        st.session_state.pop(_SESSION_SUCCESS_KEY, None)
        st.session_state.pop(_SESSION_DOWNLOAD_PENDING_KEY, None)
        return

    _render_success_card(
        receipt_no=str(data["receipt_no"]),
        name=str(data["name"]),
        amount=float(data["amount"]),
        payment_mode=str(data["payment_mode"]),
        phone=str(data["phone"]),
        date_display=str(data["date_display"]),
        notes=str(data.get("notes") or ""),
        sheet_ok=bool(data.get("sheet_ok")),
        seconds_left=seconds_left,
    )

    pdf_bytes = data.get("pdf_bytes")
    if not isinstance(pdf_bytes, (bytes, bytearray)):
        return

    pending = bool(st.session_state.get(_SESSION_DOWNLOAD_PENDING_KEY))
    # Mark before auto-click so the rerun does not fire a second download loop.
    if pending:
        st.session_state[_SESSION_DOWNLOAD_PENDING_KEY] = False

    pdf_name = str(data.get("pdf_name") or "pawati.pdf")
    _trigger_pdf_download(
        bytes(pdf_bytes),
        pdf_name,
        key=f"auto_dl_{data['receipt_no']}",
        auto_click=pending,
    )



def _render_donation_app() -> None:
    """Main donation UI — only reached after a successful login."""
    # Session bar (user, login time, idle expiry, logout) — re-enable when needed:
    # render_session_bar()
    _render_hero()
    _render_upi_qr_popup_if_any()

    # Section header above the form — cosmetic only; re-enable if useful:
    # st.markdown(
    #     """
    #     <div class="vr-card-label">
    #         <h2>New donation</h2>
    #         <span>Required fields marked *</span>
    #     </div>
    #     """,
    #     unsafe_allow_html=True,
    # )

    with st.form("donation_form", clear_on_submit=True):
        name = st.text_input(
            "Full name *",
            placeholder="e.g. Rajesh Sharma",
            help="Name as it should appear on the e-pawati.",
        )

        col_phone, col_amount = st.columns(2)
        with col_phone:
            whatsapp = st.text_input(
                "WhatsApp number *",
                placeholder="10-digit mobile",
                help="Used later for WhatsApp e-pawati delivery.",
            )
        with col_amount:
            # text_input: real placeholder, full-width field, no +/- steppers
            amount_raw = st.text_input(
                "Amount (₹) *",
                placeholder="e.g. 501",
            )

        payment_mode = st.radio(
            "Payment mode *",
            options=PAYMENT_MODES,
            horizontal=True,
            format_func=lambda m: f"{PAYMENT_ICONS.get(m, '')}  {m}",
            help="How the donation was received.",
        )

        notes = st.text_area(
            "Notes (optional)",
            placeholder="Any remark for the record…",
            height=80,
        )

        st.markdown("")  # small spacer before CTA
        submitted = st.form_submit_button(
            "✨  Generate e-pawati",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        errors, amount = _validate(name, whatsapp, amount_raw)
        if errors:
            for msg in errors:
                st.error(msg)
            return

        # Overlay while work runs; clear before success card paints this same run.
        loading_slot = st.empty()
        with loading_slot:
            _render_loading_overlay()
        try:
            _process_donation(
                name=name,
                whatsapp=whatsapp,
                amount=float(amount or 0),
                payment_mode=payment_mode,
                notes=notes or "",
            )
        finally:
            loading_slot.empty()

    # After form handling so a just-created receipt is shown this run,
    # and again on the download-button rerun (session_state).
    _render_receipt_success_if_any()

    st.markdown(
        '<p class="vr-footnote">Navayuvak Mitra Mandal · E-Pawati</p>',
        unsafe_allow_html=True,
    )


def main() -> None:
    """
    App entry: login gate → donation form.

    Unauthenticated (or expired) users only see the login page.
    """
    _init_page()

    if not ensure_active_session():
        # Session-expired flash (if any) shows on the login page
        render_login_page()
        return

    _render_donation_app()


if __name__ == "__main__":
    main()
