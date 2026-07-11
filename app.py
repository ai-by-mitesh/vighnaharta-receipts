"""
Main Streamlit application for Vighnaharta Receipts.

Paperless donation e-receipt system for Dadar Cha Vighnaharta Ganpati Mandal.

Flow on submit:
1. Validate the form
2. Fetch next receipt number from Google Sheets (fallback if offline)
3. Generate PDF receipt
4. Log the donation row to Google Sheets
5. Show success + download link
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from pdf_generator import generate_receipt
from sheets_logger import append_donation, connect_to_sheet, get_next_receipt_number
from utils import format_currency, format_receipt_number, normalize_phone

PAYMENT_MODES = ("Cash", "UPI", "Other")


def _init_page() -> None:
    st.set_page_config(
        page_title="Vighnaharta Receipts",
        page_icon="🙏",
        layout="centered",
    )
    st.title("🙏 Vighnaharta Receipts")
    st.caption("Dadar Cha Vighnaharta · Paperless donation e-receipts")


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
        # Local / first-run fallback so the form still works without Sheets
        st.warning(
            f"Could not reach Google Sheets for receipt numbering ({exc}). "
            "Using a temporary local number — row will not be logged until Sheets is configured."
        )
        # Session counter avoids collisions within one browser session
        if "local_receipt_seq" not in st.session_state:
            st.session_state.local_receipt_seq = 0
        st.session_state.local_receipt_seq += 1
        receipt_no = format_receipt_number(st.session_state.local_receipt_seq)
        return receipt_no, None


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

    donation = {
        "receipt_no": receipt_no,
        "donor_name": name.strip(),
        "whatsapp": phone,
        "amount": amount,
        "payment_mode": payment_mode,
        "notes": notes.strip(),
        "date": date_display,
    }

    # 1) PDF
    try:
        pdf_path = generate_receipt(donation)
    except Exception as exc:
        st.error(f"Failed to generate PDF: {exc}")
        return

    # 2) Google Sheets (skip if we already know Sheets is unavailable)
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

    # 3) Success
    st.success(f"Receipt generated successfully · **{receipt_no}**")
    st.balloons()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Receipt No", receipt_no)
        st.write(f"**Donor:** {name.strip()}")
        st.write(f"**Amount:** {format_currency(amount)}")
        st.write(f"**Mode:** {payment_mode}")
    with col2:
        st.write(f"**Date:** {date_display}")
        st.write(f"**WhatsApp:** {phone}")
        if notes.strip():
            st.write(f"**Notes:** {notes.strip()}")
        st.write(f"**Sheet logged:** {'Yes' if sheet_ok else 'No'}")

    pdf_bytes = Path(pdf_path).read_bytes()
    st.download_button(
        label="Download PDF receipt",
        data=pdf_bytes,
        file_name=Path(pdf_path).name,
        mime="application/pdf",
        type="primary",
    )


def main() -> None:
    """Render the donation form and handle submission."""
    _init_page()

    st.markdown(
        "Enter donor details below to issue an e-receipt. "
        "Data is saved to Google Sheets and a PDF is generated for download."
    )

    with st.form("donation_form", clear_on_submit=True):
        name = st.text_input("Full Name *", placeholder="Donor's full name")
        whatsapp = st.text_input(
            "WhatsApp Number *",
            placeholder="10-digit mobile number",
            help="Used later for WhatsApp e-receipt delivery.",
        )
        amount = st.number_input(
            "Amount (₹) *",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            help="Donation amount in Indian Rupees.",
        )
        payment_mode = st.selectbox("Payment Mode *", options=PAYMENT_MODES)
        notes = st.text_area("Notes (optional)", placeholder="Any additional remarks")

        submitted = st.form_submit_button("Generate Receipt", type="primary", use_container_width=True)

    if submitted:
        errors = _validate(name, whatsapp, amount)
        if errors:
            for msg in errors:
                st.error(msg)
            return

        with st.spinner("Generating receipt…"):
            _process_donation(
                name=name,
                whatsapp=whatsapp,
                amount=float(amount),
                payment_mode=payment_mode,
                notes=notes or "",
            )


if __name__ == "__main__":
    main()
