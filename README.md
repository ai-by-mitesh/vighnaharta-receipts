# Vighnaharta Receipts

Paperless donation e-receipt system for **Dadar Cha Vighnaharta** Ganpati Mandal.

Collect donor details, generate PDF e-receipts, log entries to Google Sheets, and send receipts over WhatsApp — all from a simple Streamlit interface.

## Tech Stack

| Layer | Technology |
| --- | --- |
| UI | [Streamlit](https://streamlit.io/) |
| PDF generation | [fpdf2](https://py-pdf.github.io/fpdf2/) |
| Spreadsheet logging | [gspread](https://docs.gspread.org/) + Google Auth |
| WhatsApp delivery | Wappfly API (`requests`) |
| Config | `python-dotenv` |

## Project Structure

```
vighnaharta-receipts/
├── app.py                 # Main Streamlit application
├── pdf_generator.py       # PDF e-receipt generation
├── sheets_logger.py       # Google Sheets logging
├── wappfly_sender.py      # WhatsApp message sender
├── utils.py               # Shared helpers
├── src/                   # Package root (future modules)
├── .streamlit/config.toml # Streamlit theme & settings
├── pyproject.toml
└── README.md
```

## How to Run

1. **Create and activate a virtual environment** (if not already set up):

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS / Linux
   ```

2. **Install dependencies**:

   ```bash
   pip install -e .
   # or: uv sync
   ```

3. **Configure secrets** (Google service account, Wappfly API keys, etc.):

   - Copy credentials into `.env` (never commit this file)
   - Place `service_account.json` in the project root (gitignored)
   - Optionally add Streamlit secrets under `.streamlit/secrets.toml`

4. **Launch the app**:

   ```bash
   streamlit run app.py
   ```

5. Open the local URL shown in the terminal (typically `http://localhost:8501`).

## License

Private project for Dadar Cha Vighnaharta Ganpati Mandal.
