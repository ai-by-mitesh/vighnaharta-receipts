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
5. Show success + download link
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import streamlit as st

from auth import (
    ensure_active_session,
    render_login_page,
    render_session_bar,
)
from pdf_generator import DEFAULT_NOTES
from receipt_service import generate_donation_receipt
from sheets_logger import append_donation, connect_to_sheet, get_next_receipt_number
from utils import format_currency, format_receipt_number, normalize_phone

PAYMENT_MODES = ("Cash", "UPI", "Other")
PAYMENT_ICONS = {"Cash": "💵", "UPI": "📱", "Other": "💳"}

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

/* —— Hero —— */
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

.vr-hero::after {
    content: "";
    position: absolute;
    right: -40px;
    top: -40px;
    width: 180px;
    height: 180px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.14);
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

/* Success receipt card */
.vr-success {
    border-radius: 20px;
    border: 1px solid rgba(34, 160, 90, 0.18);
    background:
        linear-gradient(180deg, #f3fff8 0%, #ffffff 55%);
    padding: 1.35rem 1.4rem 1.2rem;
    margin: 0.5rem 0 1rem;
    box-shadow: 0 12px 28px rgba(28, 28, 28, 0.05);
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

/* Our emoji toggle sits in a column (not inside stTextInput) */
div[data-testid="stHorizontalBlock"] > div:last-child button {
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
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


def _render_hero() -> None:
    st.markdown(
        """
        <div class="vr-hero">
            <div class="vr-kicker">दादरचा विघ्नहर्ता</div>
            <h1>Paperless Receipts</h1>
            <p>
                Issue paperless donation e-receipts in seconds,
                PDF ready to download, records saved for accounting automatically.
            </p>
            </br>
            <div class="vr-hero-meta">
                <span class="vr-chip">⚡ Instant PDF</span>
                <span class="vr-chip">📤 Google Sheets sync</span>
                <span class="vr-chip">🧡 Mandal ready</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _init_page() -> None:
    """Must run before any other Streamlit body output."""
    st.set_page_config(
        page_title="Vighnaharta Receipts",
        page_icon="🙏",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    _inject_styles()


def _validate(
    name: str,
    whatsapp: str,
    amount: float | None,
) -> list[str]:
    """Return a list of validation error messages (empty if OK)."""
    errors: list[str] = []
    if not name.strip():
        errors.append("Full name is required.")

    digits = normalize_phone(whatsapp)
    if not digits:
        errors.append("WhatsApp number is required.")
    elif len(digits) < 10:
        errors.append("WhatsApp number should have at least 10 digits.")

    if amount is None:
        errors.append("Amount is required.")
    elif amount <= 0:
        errors.append("Amount must be greater than zero.")

    return errors


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
            f"Could not reach Google Sheets for receipt numbering ({exc}). "
            "Using a temporary local number — row will not be logged until Sheets is configured."
        )
        if "local_receipt_seq" not in st.session_state:
            st.session_state.local_receipt_seq = 0
        st.session_state.local_receipt_seq += 1
        receipt_no = format_receipt_number(st.session_state.local_receipt_seq)
        return receipt_no, None


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
) -> None:
    """Polished post-submit summary card."""
    icon = PAYMENT_ICONS.get(payment_mode, "💳")
    safe_name = html.escape(name.strip())
    safe_receipt = html.escape(receipt_no)
    safe_phone = html.escape(phone)
    safe_mode = html.escape(payment_mode)
    safe_date = html.escape(date_display)
    safe_amount = html.escape(format_currency(amount))

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
        <div class="vr-success">
            <div class="vr-success-badge">✓ Receipt issued</div>
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
        </div>
        """,
        unsafe_allow_html=True,
    )


def _process_donation(
    name: str,
    whatsapp: str,
    amount: float,
    payment_mode: str,
    notes: str,
) -> None:
    """Generate receipt number, PDF, log to sheet, and show success UI."""
    receipt_no, worksheet = _allocate_receipt_number()
    now = datetime.now()
    date_display = now.strftime("%d %B %Y")
    date_log = now.strftime("%Y-%m-%d %H:%M:%S")
    phone = normalize_phone(whatsapp)
    # Default note when the form field is left blank
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
        # Backend selected via RECEIPT_METHOD env or st.secrets [receipt].method
        # ("fpdf" default landscape | "template" e-pawati overlay).
        pdf_path = generate_donation_receipt(donation)
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

    st.balloons()
    _render_success_card(
        receipt_no=receipt_no,
        name=name,
        amount=amount,
        payment_mode=payment_mode,
        phone=phone,
        date_display=date_display,
        notes=notes_final,
        sheet_ok=sheet_ok,
    )

    pdf_bytes = Path(pdf_path).read_bytes()
    st.download_button(
        label="⬇️  Download PDF receipt",
        data=pdf_bytes,
        file_name=Path(pdf_path).name,
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )


def _render_donation_app() -> None:
    """Main donation UI — only reached after a successful login."""
    # Session bar first (user, login time, idle expiry, logout)
    render_session_bar()
    _render_hero()

    st.markdown(
        """
        <div class="vr-card-label">
            <h2>New donation</h2>
            <span>Required fields marked *</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("donation_form", clear_on_submit=True):
        name = st.text_input(
            "Full name *",
            placeholder="e.g. Rajesh Sharma",
            help="Name as it should appear on the e-receipt.",
        )

        col_phone, col_amount = st.columns(2)
        with col_phone:
            whatsapp = st.text_input(
                "WhatsApp number *",
                placeholder="10-digit mobile",
                help="Used later for WhatsApp e-receipt delivery.",
            )
        with col_amount:
            amount = st.number_input(
                "Amount (₹) *",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                help="Donation amount in Indian Rupees.",
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
            "✨  Generate e-receipt",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        errors = _validate(name, whatsapp, amount)
        if errors:
            for msg in errors:
                st.error(msg)
            return

        with st.spinner("Creating receipt & syncing to Sheets…"):
            _process_donation(
                name=name,
                whatsapp=whatsapp,
                amount=float(amount),
                payment_mode=payment_mode,
                notes=notes or "",
            )

    st.markdown(
        '<p class="vr-footnote">Navayuvak Mitra Mandal · E-Receipts</p>',
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
