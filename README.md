# Vighnaharta Receipts

Paperless donation **e-pawati** system for **दादरचा विघ्नहर्ता** (Dadar Cha Vighnaharta) · Navayuvak Mitra Mandal.

Staff-facing web app to issue donation receipts: enter donor details, generate a vertical e-pawati PDF, store it online, log the entry to a spreadsheet, and deliver the receipt on WhatsApp.

Built with **[Grok Build](https://x.ai)** by xAI.

## What it does

- Staff login (session-based)
- Donation form — name, WhatsApp number, amount, payment mode, notes
- In-app UPI QR (payee note uses the next receipt number)
- Vertical e-pawati PDF generation (template overlay; Marathi year badge)
- Cloud storage of the PDF (public URL for WhatsApp delivery)
- Google Sheets logging (receipt sequence + donation row + PDF link)
- WhatsApp send: e-pawati document, then a short follow-up message
- Mobile-friendly UI with loading and success overlays
- Optional local browser download of the PDF (off by default)

## Issue flow (high level)

1. Next receipt number from the sheet (with a local fallback if needed)
2. Generate PDF
3. Upload PDF to storage
4. Log donation (including PDF URL when available)
5. Send WhatsApp messages
6. Show success status

Later steps are soft-fail where possible so an issued receipt is not blocked by a temporary storage or WhatsApp outage.

## Stack

[Streamlit](https://streamlit.io/) · ReportLab / pypdf · Supabase Storage · Google Sheets · WasenderAPI · Poppins / Noto Sans Devanagari

## Layout

```
app.py              # Streamlit entrypoint
lib/                # auth, PDF, sheets, storage, WhatsApp, UPI QR, utils
assets/
  pdf/              # e-pawati templates
  fonts/            # UI + PDF fonts
  images/
scripts/            # local PDF coord / overlay tools, SQL helper
.github/workflows/  # scheduled keep-alive for free-tier storage project
.streamlit/         # local config + secrets (not committed)
```

## Run locally

Python 3.13+:

```bash
pip install -r requirements.txt
# or: uv sync && uv run streamlit run app.py
streamlit run app.py
```

### Configuration

All credentials and service settings live in **Streamlit secrets** (local `.streamlit/secrets.toml` or Streamlit Cloud app secrets). That file is **gitignored** and must never be committed.

Operators need access to login credentials, Google Sheets, cloud storage, UPI payee details, and WhatsApp delivery — configured the same way in Cloud as locally. Developers can see which env/secret **names** a module expects by reading the corresponding file under `lib/` (no secret values belong in the repo).

## Deploy

- **App:** [Streamlit Community Cloud](https://share.streamlit.io) — entrypoint `app.py`; add secrets in the Cloud UI.
- **Integrations:** spreadsheet service account, storage project, and WhatsApp API as used by the app.

### Free-tier storage keep-alive

A GitHub Action pings the storage project on a fixed schedule so a free plan is less likely to pause after inactivity. Setup is documented in the workflow file under `.github/workflows/` (repo Actions secrets only — not Streamlit secrets). One-time SQL for the heartbeat table is in `scripts/supabase_keepalive.sql`.

## Local PDF layout tools

```bash
python scripts/find_pdf_coords.py    # click template for coordinates
python scripts/overlay_receipt.py    # preview dummy overlay PDF under receipts/
```

Settled layout values are promoted into `lib/template_receipt.py` for production.

## License

Private project for Dadarcha Vighnaharta Ganpati Mandal · Navayuvak Mitra Mandal.
