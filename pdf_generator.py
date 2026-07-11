"""
PDF e-receipt generation for Vighnaharta Receipts.

Landscape (horizontal) donation receipt for Dadar Cha Vighnaharta Ganpati Mandal.

Layout:
  ┌─────────────────┬──────────────────────────┐
  │  ganpati art    │  brand + donation details  │
  │  (left panel)   │  amount + thank-you      │
  └─────────────────┴──────────────────────────┘
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

# ── Brand palette ────────────────────────────────────────────────────────────
ORANGE = (245, 140, 30)       # #F58C1E
ORANGE_DEEP = (232, 93, 4)    # #E85D04
ORANGE_SOFT = (255, 244, 232) # #FFF4E8
CREAM = (255, 251, 247)
INK = (32, 28, 26)
MUTED = (120, 105, 92)
LINE = (232, 216, 198)
WHITE = (255, 255, 255)
ROW_ALT = (255, 248, 241)

PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
FONTS_DIR = ASSETS_DIR / "fonts"

DEFAULT_LOGO_PATH = IMAGES_DIR / "profile_image.png"
DEFAULT_ART_PATH = IMAGES_DIR / "ganpati_vector.jpg"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "receipts"
LOGO_CACHE_PATH = PROJECT_ROOT / ".cache" / "profile_logo_tight.png"
ART_CACHE_PATH = PROJECT_ROOT / ".cache" / "ganpati_vector_clean.jpg"

MANDAL_NAME = "दादरचा विघ्नहर्ता"
MANDAL_SUBTITLE = "Navayuvak Mitra Mandal"
DOC_TITLE = "Donation E-Receipt"
DEFAULT_NOTES = "Ganeshotsav Seva"
THANK_YOU = (
    "Thank you for your generous donation. "
    "May Bappa bless you and your family with health, happiness, and prosperity. "
    "Ganpati Bappa Morya!"
)

# Landscape geometry (A4 landscape = 297 x 210 mm)
LEFT_PANEL_W = 112  # mm — art column
CONTENT_PAD = 12    # padding inside the right content column
LOGO_DIAM_MM = 22   # small brand mark on the right header

# Same typeface as the Streamlit UI (bundled under assets/fonts/)
FONT_FAMILY = "Poppins"
POPPINS_REGULAR = FONTS_DIR / "Poppins-Regular.ttf"
POPPINS_BOLD = FONTS_DIR / "Poppins-Bold.ttf"


def _pdf_amount(amount: float | int) -> str:
    """Format amount for PDF display."""
    if float(amount).is_integer():
        return f"Rs. {amount:,.0f}"
    return f"Rs. {amount:,.2f}"


def _clip_text(value: str, max_len: int = 90) -> str:
    """Trim long strings for single-line cells."""
    value = str(value)
    if len(value) > max_len:
        return value[: max_len - 1] + "..."
    return value


def _set_font(pdf: FPDF, style: str = "", size: float = 10) -> None:
    """Set the receipt font (Poppins when registered, else Helvetica)."""
    family = getattr(pdf, "_receipt_font_family", "Helvetica")
    if family == "Helvetica" and style not in ("", "B", "I", "BI"):
        style = ""
    if style not in ("", "B"):
        style = "B" if "B" in style else ""
    pdf.set_font(family, style, size)


def prepare_logo(
    source: Path = DEFAULT_LOGO_PATH,
    dest: Path = LOGO_CACHE_PATH,
) -> Path | None:
    """
    Tight-crop the mandal logo and drop empty light padding.

    ``profile_image.png`` has a large pale border; only the central artwork is kept.
    Result is cached under ``.cache/`` and refreshed when the source changes.
    """
    if not source.is_file():
        return None

    try:
        from PIL import Image
    except ImportError:
        return source

    dest.parent.mkdir(parents=True, exist_ok=True)
    if (
        dest.is_file()
        and dest.stat().st_mtime >= source.stat().st_mtime
        and dest.stat().st_size > 0
    ):
        return dest

    im = Image.open(source).convert("RGBA")
    w, h = im.size

    cleaned: list[tuple[int, int, int, int]] = []
    for r, g, b, a in im.getdata():
        if a < 12:
            cleaned.append((0, 0, 0, 0))
        elif r >= 242 and g >= 242 and b >= 242:
            cleaned.append((0, 0, 0, 0))
        elif min(r, g, b) > 225 and (max(r, g, b) - min(r, g, b)) < 22:
            cleaned.append((0, 0, 0, 0))
        else:
            cleaned.append((r, g, b, a))
    im.putdata(cleaned)

    bbox = im.getbbox()
    if not bbox:
        im.save(dest, "PNG")
        return dest

    pad = 12
    l, t, r, b = bbox
    l, t = max(0, l - pad), max(0, t - pad)
    r, b = min(w, r + pad), min(h, b + pad)
    cropped = im.crop((l, t, r, b))

    side = max(cropped.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ox = (side - cropped.size[0]) // 2
    oy = (side - cropped.size[1]) // 2
    square.paste(cropped, (ox, oy), cropped)
    square = square.resize((700, 700), Image.Resampling.LANCZOS)
    square.save(dest, "PNG", optimize=True)
    return dest


def prepare_art(
    source: Path = DEFAULT_ART_PATH,
    dest: Path = ART_CACHE_PATH,
    min_crop_px: int = 4,
    max_edge_scan: int = 24,
    white_mean: float = 245.0,
) -> Path | None:
    """
    Strip thin dark/grey borders from the Vecteezy art (top/bottom/sides).

    ``ganpati_vector.jpg`` has ~1px grey edge lines that show up against the
    white panel. Crops those (plus a small safety margin) and caches the result.
    """
    if not source.is_file():
        return None

    try:
        from PIL import Image
    except ImportError:
        return source

    dest.parent.mkdir(parents=True, exist_ok=True)
    if (
        dest.is_file()
        and dest.stat().st_mtime >= source.stat().st_mtime
        and dest.stat().st_size > 0
    ):
        return dest

    im = Image.open(source).convert("RGB")
    w, h = im.size
    px = im.load()

    def _row_mean(y: int) -> float:
        total = 0
        for x in range(w):
            r, g, b = px[x, y]
            total += r + g + b
        return total / (3 * w)

    def _col_mean(x: int) -> float:
        total = 0
        for y in range(h):
            r, g, b = px[x, y]
            total += r + g + b
        return total / (3 * h)

    def _edge_inset(mean_fn, length: int) -> int:
        """How many edge rows/cols are not near-white (border lines)."""
        inset = 0
        scan = min(max_edge_scan, length)
        for i in range(scan):
            if mean_fn(i) < white_mean:
                inset = i + 1
            else:
                break
        # +1 safety so the grey line is fully gone; always crop a few px
        return max(min_crop_px, inset + 1)

    top = _edge_inset(_row_mean, h)
    bottom = _edge_inset(lambda i: _row_mean(h - 1 - i), h)
    left = _edge_inset(_col_mean, w)
    right = _edge_inset(lambda i: _col_mean(w - 1 - i), w)

    # Never eat more than ~5% per side
    top = min(top, h // 20)
    bottom = min(bottom, h // 20)
    left = min(left, w // 20)
    right = min(right, w // 20)

    cropped = im.crop((left, top, w - right, h - bottom))
    cropped.save(dest, "JPEG", quality=95, optimize=True)
    return dest


class ReceiptPDF(FPDF):
    """Landscape single-page donation receipt."""

    def __init__(self) -> None:
        super().__init__(orientation="L", unit="mm", format="A4")
        self.set_auto_page_break(auto=False)
        self.set_margins(left=0, top=0, right=0)
        self._receipt_font_family = self._register_fonts()
        self._enable_text_shaping()

    def _register_fonts(self) -> str:
        """
        Register Poppins (matches the Streamlit form).

        Includes Latin + Devanagari so Marathi labels render correctly.
        Falls back to Helvetica only if the bundled TTFs are missing.
        """
        if POPPINS_REGULAR.is_file() and POPPINS_BOLD.is_file():
            try:
                self.add_font(FONT_FAMILY, "", str(POPPINS_REGULAR))
                self.add_font(FONT_FAMILY, "B", str(POPPINS_BOLD))
                return FONT_FAMILY
            except Exception:
                pass
        return "Helvetica"

    def _enable_text_shaping(self) -> None:
        """
        Enable HarfBuzz shaping so Devanagari conjuncts/matras match the source text.

        Without this, fpdf2 draws raw codepoints and Marathi can look rearranged.
        Requires the ``uharfbuzz`` package.
        """
        try:
            self.set_text_shaping(
                True,
                script="deva",
                language="mar",
            )
        except Exception:
            # Package missing or engine unavailable — Latin still works; Marathi may look off
            pass


def _contain_image(
    pdf: FPDF,
    path: Path,
    x: float,
    y: float,
    w: float,
    h: float,
    pad: float = 0,
    zoom: float = 1.0,
) -> None:
    """
    Draw the image inside a box, centred (CSS object-fit: contain + optional zoom).

    ``zoom`` > 1 enlarges past pure-contain so built-in white margins on the
    asset can be used as real estate (edges clip; figure looks larger).
    Clipped to the box so nothing spills outside.
    """
    box_x = x + pad
    box_y = y + pad
    box_w = max(1.0, w - 2 * pad)
    box_h = max(1.0, h - 2 * pad)

    try:
        from PIL import Image

        with Image.open(path) as im:
            iw, ih = im.size
    except Exception:
        pdf.image(str(path), x=box_x, y=box_y, w=box_w, h=box_h)
        return

    img_aspect = iw / ih if ih else 1.0
    box_aspect = box_w / box_h if box_h else 1.0

    if img_aspect > box_aspect:
        # Wider than box → fit to width
        draw_w = box_w
        draw_h = box_w / img_aspect
    else:
        # Taller / square → fit to height
        draw_h = box_h
        draw_w = box_h * img_aspect

    # Enlarge to reclaim the asset's empty white padding
    zoom = max(1.0, zoom)
    draw_w *= zoom
    draw_h *= zoom

    draw_x = box_x + (box_w - draw_w) / 2
    draw_y = box_y + (box_h - draw_h) / 2

    with pdf.rect_clip(box_x, box_y, box_w, box_h):
        pdf.image(str(path), x=draw_x, y=draw_y, w=draw_w, h=draw_h)


def _draw_left_art(pdf: FPDF, art_path: Path | None) -> None:
    """Full-height left panel with Ganpati artwork (centred, white backdrop)."""
    w, h = LEFT_PANEL_W, pdf.h
    veil_h = 26

    # White base so the vector's white margins blend into one seamless field
    pdf.set_fill_color(*WHITE)
    pdf.rect(0, 0, w, h, style="F")

    # Art sits above the bottom blessing strip; slight zoom uses in-image whitespace
    art_h = h - veil_h
    if art_path and art_path.is_file():
        try:
            _contain_image(pdf, art_path, 0, 0, w, art_h, pad=2, zoom=1.28)
        except Exception:
            pass
    else:
        pdf.set_fill_color(*ORANGE)
        pdf.rect(0, 0, w, art_h, style="F")
        pdf.set_xy(0, art_h / 2 - 6)
        _set_font(pdf, "B", 14)
        pdf.set_text_color(*WHITE)
        pdf.cell(w, 12, "ॐ श्री गणेशाय नमः", align="C")

    # Bottom blessing strip
    pdf.set_fill_color(28, 18, 10)
    pdf.rect(0, h - veil_h, w, veil_h, style="F")

    pdf.set_xy(8, h - veil_h + 6)
    _set_font(pdf, "B", 11)
    pdf.set_text_color(*WHITE)
    pdf.cell(w - 16, 6, "ॐ श्री गणेशाय नमः", align="C")

    pdf.set_xy(8, h - veil_h + 14)
    _set_font(pdf, "", 8)
    pdf.set_text_color(255, 220, 180)
    pdf.cell(w - 16, 5, MANDAL_NAME, align="C")

    # Slim accent edge between art and content
    pdf.set_fill_color(*ORANGE_DEEP)
    pdf.rect(w - 1.2, 0, 1.2, h, style="F")


def _draw_logo_mark(pdf: FPDF, logo_path: Path | None, x: float, y: float, d: float) -> None:
    """Small circular brand mark (no coloured ring)."""
    if logo_path and logo_path.is_file():
        try:
            with pdf.elliptic_clip(x, y, d, d):
                pdf.image(str(logo_path), x=x, y=y, w=d, h=d)
            return
        except Exception:
            pass

    pdf.set_fill_color(*ORANGE_SOFT)
    pdf.ellipse(x, y, d, d, style="F")
    pdf.set_xy(x, y + d / 2 - 3.5)
    _set_font(pdf, "B", 9)
    pdf.set_text_color(*ORANGE_DEEP)
    pdf.cell(d, 7, "DV", align="C")


def _content_left() -> float:
    return LEFT_PANEL_W + CONTENT_PAD


def _content_width(pdf: FPDF) -> float:
    return pdf.w - _content_left() - CONTENT_PAD


def _draw_right_header(
    pdf: FPDF,
    logo_path: Path | None,
    receipt_no: str,
    date_str: str,
) -> float:
    """Brand row + receipt meta on the right column. Returns next Y."""
    x0 = _content_left()
    y = 12
    d = LOGO_DIAM_MM

    _draw_logo_mark(pdf, logo_path, x0, y, d)

    tx = x0 + d + 6
    tw = _content_width(pdf) - d - 6

    pdf.set_xy(tx, y + 1)
    _set_font(pdf, "B", 7.5)
    pdf.set_text_color(*ORANGE_DEEP)
    pdf.cell(tw, 3.5, MANDAL_SUBTITLE.upper())

    pdf.set_xy(tx, y + 6)
    _set_font(pdf, "B", 15)
    pdf.set_text_color(*INK)
    pdf.cell(tw, 7, MANDAL_NAME)

    pdf.set_xy(tx, y + 14)
    _set_font(pdf, "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(tw, 4, DOC_TITLE)

    # Meta strip: receipt no + date
    y = y + d + 8
    cw = _content_width(pdf)
    strip_h = 14
    pdf.set_fill_color(*ORANGE_SOFT)
    pdf.rect(x0, y, cw, strip_h, style="F", round_corners=True, corner_radius=2.5)

    half = cw / 2
    pdf.set_xy(x0 + 5, y + 2)
    _set_font(pdf, "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(half - 8, 3, "RECEIPT NO.")

    pdf.set_xy(x0 + 5, y + 6.5)
    _set_font(pdf, "B", 10)
    pdf.set_text_color(*ORANGE_DEEP)
    pdf.cell(half - 8, 5, _clip_text(receipt_no, 24))

    pdf.set_xy(x0 + half + 2, y + 2)
    _set_font(pdf, "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(half - 8, 3, "DATE")

    pdf.set_xy(x0 + half + 2, y + 6.5)
    _set_font(pdf, "B", 10)
    pdf.set_text_color(*INK)
    pdf.cell(half - 8, 5, _clip_text(date_str, 24))

    return y + strip_h + 7


def _draw_amount(pdf: FPDF, y: float, amount_text: str) -> float:
    x0 = _content_left()
    cw = _content_width(pdf)
    h = 22

    pdf.set_fill_color(*ORANGE)
    pdf.rect(x0, y, cw, h, style="F", round_corners=True, corner_radius=3)

    pdf.set_xy(x0 + 7, y + 4)
    _set_font(pdf, "B", 7.5)
    pdf.set_text_color(255, 240, 220)
    pdf.cell(cw - 14, 4, "TOTAL DONATION RECEIVED")

    pdf.set_xy(x0 + 7, y + 9.5)
    _set_font(pdf, "B", 18)
    pdf.set_text_color(*WHITE)
    pdf.cell(cw - 14, 9, amount_text)

    return y + h + 7


def _draw_fields(pdf: FPDF, y: float, rows: list[tuple[str, str]]) -> float:
    x0 = _content_left()
    cw = _content_width(pdf)
    label_w = 38
    row_h = 10

    pdf.set_xy(x0, y)
    _set_font(pdf, "B", 7.5)
    pdf.set_text_color(*ORANGE_DEEP)
    pdf.cell(cw, 4, "DONOR DETAILS")
    y += 6

    for i, (label, value) in enumerate(rows):
        pdf.set_fill_color(*(ROW_ALT if i % 2 == 0 else WHITE))
        pdf.rect(x0, y, cw, row_h, style="F")

        pdf.set_fill_color(*ORANGE)
        pdf.rect(x0, y + 2.2, 1.1, row_h - 4.4, style="F")

        pdf.set_xy(x0 + 5, y + 2.5)
        _set_font(pdf, "", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(label_w, 5, _clip_text(label.upper(), 22))

        pdf.set_xy(x0 + 5 + label_w, y + 2.3)
        _set_font(pdf, "B", 9.5)
        pdf.set_text_color(*INK)
        pdf.cell(cw - label_w - 10, 5.5, _clip_text(value, 48))

        pdf.set_draw_color(*LINE)
        pdf.set_line_width(0.2)
        pdf.line(x0, y + row_h, x0 + cw, y + row_h)
        y += row_h

    return y + 6


def _draw_thank_you(pdf: FPDF, y: float, message: str) -> float:
    """
    Compact gratitude panel sized to the text only (no large empty bottom).

    Returns the Y position under the panel.
    """
    x0 = _content_left()
    cw = _content_width(pdf)
    text = _clip_text(message, 280)
    line_h = 3.8
    pad_top = 3.0
    pad_mid = 1.5
    pad_bottom = 3.5
    title_h = 4.5

    # Measure how many lines the body needs at this width
    _set_font(pdf, "", 8)
    lines = pdf.multi_cell(
        cw - 10,
        line_h,
        text,
        dry_run=True,
        output="LINES",
    )
    body_h = max(line_h, len(lines) * line_h)
    h = pad_top + title_h + pad_mid + body_h + pad_bottom

    # Stay above the right-column footer
    max_bottom = pdf.h - 14
    if y + h > max_bottom:
        h = max(16.0, max_bottom - y)

    pdf.set_fill_color(*ORANGE_SOFT)
    pdf.set_draw_color(*ORANGE)
    pdf.set_line_width(0.3)
    pdf.rect(x0, y, cw, h, style="FD", round_corners=True, corner_radius=2.5)

    pdf.set_xy(x0 + 5, y + pad_top)
    _set_font(pdf, "B", 9)
    pdf.set_text_color(*ORANGE_DEEP)
    pdf.cell(cw - 10, title_h, "With gratitude")

    pdf.set_xy(x0 + 5, y + pad_top + title_h + pad_mid)
    _set_font(pdf, "", 8)
    pdf.set_text_color(*INK)
    pdf.multi_cell(cw - 10, line_h, text)

    return y + h


def _draw_right_footer(pdf: FPDF) -> None:
    """Right-column footer with vector attribution."""
    x0 = _content_left()
    cw = _content_width(pdf)
    y = pdf.h - 11

    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.25)
    pdf.line(x0, y, x0 + cw, y)

    pdf.set_xy(x0, y + 2)
    _set_font(pdf, "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(
        cw,
        3.5,
        "Vector artwork courtesy of Vecteezy.com  ·  www.vecteezy.com",
        align="C",
    )


def generate_receipt(
    donation: dict[str, Any],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    logo_path: str | Path | None = None,
    art_path: str | Path | None = None,
) -> Path:
    """
    Generate a landscape PDF donation receipt.

    Expected ``donation`` keys:
        receipt_no, donor_name, amount, payment_mode, date (optional),
        notes (optional), thank_you (optional), whatsapp (optional).

    Args:
        donation: Donor and payment fields.
        output_dir: Directory for the PDF.
        logo_path: Optional brand mark override (defaults to assets/images/profile_image.png).
        art_path: Optional left-panel art (defaults to assets/images/ganpati_vector.jpg).
    """
    receipt_no = str(donation["receipt_no"])
    donor_name = str(donation["donor_name"]).strip()
    amount = donation["amount"]
    payment_mode = str(donation.get("payment_mode", "")).strip() or "-"
    whatsapp = str(donation.get("whatsapp", "")).strip()
    date_str = str(donation.get("date") or datetime.now().strftime("%d %B %Y"))
    thank_you = str(donation.get("thank_you") or THANK_YOU)
    notes = str(donation.get("notes") or "").strip() or DEFAULT_NOTES

    source_logo = Path(logo_path) if logo_path else DEFAULT_LOGO_PATH
    prepared_logo = prepare_logo(source_logo)
    source_art = Path(art_path) if art_path else DEFAULT_ART_PATH
    prepared_art = prepare_art(source_art) if source_art == DEFAULT_ART_PATH else prepare_art(source_art)
    resolved_art = prepared_art or source_art

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = receipt_no.replace("/", "-")
    pdf_path = out_dir / f"receipt_{safe_name}.pdf"

    pdf = ReceiptPDF()
    pdf.set_title(f"Receipt {receipt_no}")
    pdf.set_author(MANDAL_NAME)
    pdf.add_page()

    # Right column cream background
    pdf.set_fill_color(*CREAM)
    pdf.rect(LEFT_PANEL_W, 0, pdf.w - LEFT_PANEL_W, pdf.h, style="F")

    _draw_left_art(pdf, resolved_art if resolved_art.is_file() else None)

    y = _draw_right_header(pdf, prepared_logo, receipt_no, date_str)
    y = _draw_amount(pdf, y, _pdf_amount(amount))

    rows: list[tuple[str, str]] = [
        ("Donor name", donor_name),
        ("Payment mode", payment_mode),
    ]
    if whatsapp:
        rows.append(("WhatsApp", whatsapp))
    rows.append(("Notes", notes))

    y = _draw_fields(pdf, y, rows)
    _draw_thank_you(pdf, y, thank_you)
    _draw_right_footer(pdf)

    pdf.output(str(pdf_path))
    return pdf_path
