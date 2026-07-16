"""
Barebones Dynamic UPI QR generator.

Usage:
    python scripts/dynamic_upi_qr.py
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from urllib.parse import quote

import qrcode
from PIL import ImageTk

# --- Hardcoded payee details ---
UPI_ID = "your-upi-id"
PAYEE_NAME = "your-name"


def new_note() -> str:
    """Short unique note: DON + ddmmyyyy + hhmmss."""
    return datetime.now().strftime("DON%d%m%Y%H%M%S")


def build_upi_uri(note: str) -> str:
    return (
        f"upi://pay?pa={UPI_ID}"
        f"&pn={quote(PAYEE_NAME)}"
        f"&tn={quote(note)}"
        f"&cu=INR"
    )


def make_qr_image(uri: str):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def main() -> None:
    root = tk.Tk()
    root.title("Dynamic UPI QR")
    root.resizable(False, False)

    photo_holder: dict[str, ImageTk.PhotoImage | None] = {"img": None}

    qr_label = tk.Label(root)
    qr_label.pack(padx=16, pady=(16, 8))

    ref_label = tk.Label(root, text="Click Generate to create a QR", font=("Helvetica", 12))
    ref_label.pack(pady=(0, 12))

    def generate() -> None:
        note = new_note()
        uri = build_upi_uri(note)
        img = make_qr_image(uri)
        photo = ImageTk.PhotoImage(img)
        photo_holder["img"] = photo  # keep a reference so the image is not GC'd
        qr_label.configure(image=photo)
        ref_label.configure(text=note)



    tk.Button(root, text="Generate New QR", command=generate, font=("Helvetica", 12)).pack(
        pady=(0, 16)
    )

    root.mainloop()


if __name__ == "__main__":
    main()
