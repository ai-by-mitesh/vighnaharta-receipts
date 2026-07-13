# Vighnaharta Receipts

Paperless donation **e-receipt** system for **दादरचा विघ्नहर्ता** (Dadarcha Vighnaharta) · Navayuvak Mitra Mandal.

A simple staff-facing web app to issue donation receipts: enter donor details, generate a PDF e-receipt, save the entry to a sheet, and download the receipt in the browser.

## What it does

- Staff login (session-based)
- Donation form — name, WhatsApp number, amount, payment mode, notes
- PDF e-receipt generation
- Logging to Google Sheets
- Clean mobile-friendly UI with loading and success overlays

## Stack

[Streamlit](https://streamlit.io/) · PDF generation · Google Sheets · Poppins UI

Built entirely with **[Grok Build](https://x.ai)** by xAI — yes, the whole thing.

## Run locally

Python 3.13+, then:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Configuration (login credentials, Google Sheets, etc.) lives in Streamlit secrets and is not committed to the repo.

## Deploy

Built to run on [Streamlit Community Cloud](https://share.streamlit.io) from this repository (`app.py` as the entrypoint). Add secrets in the Cloud app settings.

## License

Private project for Dadarcha Vighnaharta Ganpati Mandal · Navayuvak Mitra Mandal.
