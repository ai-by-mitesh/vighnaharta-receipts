"""
Main Streamlit application for Vighnaharta Receipts.

Entry point for the paperless donation e-receipt system used by
Dadar Cha Vighnaharta Ganpati Mandal.

Responsibilities (to be implemented):
- Donor detail form (name, phone, amount, payment mode, etc.)
- Trigger PDF receipt generation
- Log donations to Google Sheets
- Send e-receipts via WhatsApp (Wappfly)
"""

import streamlit as st


def main() -> None:
    """Render the Streamlit UI and wire up receipt workflows."""
    st.set_page_config(
        page_title="Vighnaharta Receipts",
        page_icon="🙏",
        layout="centered",
    )

    st.title("Vighnaharta Receipts")
    st.caption("Dadar Cha Vighnaharta · Donation e-receipts")

    # TODO: donor form, generate PDF, log to sheets, send via WhatsApp
    st.info("App scaffold ready. Implement the donation flow here.")


if __name__ == "__main__":
    main()
