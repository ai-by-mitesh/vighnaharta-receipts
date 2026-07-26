"""
Supabase Storage uploads for Vighnaharta Receipt PDFs.

Uploads generated e-receipt PDFs to a public bucket so the object URL can be
reused later (e.g. WasenderAPI document messages).

Config lives in ``.streamlit/secrets.toml``::

    [supabase]
    url = "https://xxxx.supabase.co"
    secret_key = "sb_secret_..."            # preferred (server uploads)
    publishable_key = "sb_publishable_..."  # optional fallback
    bucket = "receipts"
    path_style = "{current_year}/{receipt_no}.pdf"

Path placeholders: ``{current_year}`` / ``{year}``, ``{receipt_no}`` / ``{receipt_number}``.

Upload failures are raised to the caller — the app treats them as soft-fail
so browser download + Sheets logging still succeed.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import requests

from lib.utils import now_ist

# Default object key when secrets omit path_style.
_DEFAULT_PATH_STYLE = "{current_year}/{receipt_no}.pdf"
_UPLOAD_TIMEOUT_S = 30


def _as_dict(value: Any) -> dict[str, Any]:
    """Normalize Streamlit secrets / mappings to a plain dict."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _try_streamlit_secrets() -> dict[str, Any]:
    """Return Streamlit secrets as a dict, or {} if unavailable."""
    try:
        import streamlit as st

        return _as_dict(st.secrets)
    except Exception:
        return {}


def load_supabase_config() -> dict[str, str]:
    """
    Load Supabase storage settings from secrets or environment.

    Secrets keys (preferred)::

        [supabase]
        url / publishable_key (or key / secret_key) / bucket / path_style

    Env fallbacks: ``SUPABASE_URL``, ``SUPABASE_KEY`` / ``SUPABASE_PUBLISHABLE_KEY``,
    ``SUPABASE_BUCKET``, ``SUPABASE_PATH_STYLE``.

    Returns:
        Dict with ``url``, ``key``, ``bucket``, ``path_style``.

    Raises:
        ValueError: If url, key, or bucket is missing.
    """
    secrets = _try_streamlit_secrets()
    section = _as_dict(secrets.get("supabase"))

    url = (
        section.get("url")
        or os.getenv("SUPABASE_URL")
        or secrets.get("SUPABASE_URL")
        or ""
    )
    # Prefer secret/service role for server uploads (bypasses Storage RLS).
    # Fall back to publishable only if no secret is configured.
    key = (
        section.get("secret_key")
        or section.get("service_role_key")
        or section.get("key")
        or os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or section.get("publishable_key")
        or os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or secrets.get("SUPABASE_KEY")
        or ""
    )
    bucket = (
        section.get("bucket")
        or os.getenv("SUPABASE_BUCKET")
        or secrets.get("SUPABASE_BUCKET")
        or ""
    )
    path_style = (
        section.get("path_style")
        or os.getenv("SUPABASE_PATH_STYLE")
        or secrets.get("SUPABASE_PATH_STYLE")
        or _DEFAULT_PATH_STYLE
    )

    url = str(url).strip().rstrip("/")
    key = str(key).strip()
    bucket = str(bucket).strip()
    path_style = str(path_style).strip() or _DEFAULT_PATH_STYLE

    missing = [name for name, val in (("url", url), ("key", key), ("bucket", bucket)) if not val]
    if missing:
        raise ValueError(
            "Supabase storage is not configured. Missing: "
            + ", ".join(missing)
            + ". Set [supabase] url, secret_key (or publishable_key), and bucket in secrets.toml."
        )
    return {
        "url": url,
        "key": key,
        "bucket": bucket,
        "path_style": path_style,
    }


def build_object_path(
    receipt_no: str,
    *,
    path_style: str | None = None,
    year: int | None = None,
) -> str:
    """
    Build the storage object key from ``path_style`` and receipt metadata.

    Args:
        receipt_no: e.g. ``DCV-2026-0001``.
        path_style: Template with placeholders; defaults from config / default style.
        year: Calendar year for ``{current_year}``; defaults to IST year.

    Returns:
        Object path without a leading slash, e.g. ``2026/DCV-2026-0001.pdf``.
    """
    style = (path_style or _DEFAULT_PATH_STYLE).strip()
    y = year if year is not None else now_ist().year
    receipt = str(receipt_no).strip()
    path = (
        style.replace("{current_year}", str(y))
        .replace("{year}", str(y))
        .replace("{receipt_no}", receipt)
        .replace("{receipt_number}", receipt)
    )
    return path.lstrip("/")


def public_object_url(base_url: str, bucket: str, object_path: str) -> str:
    """
    Build the public object URL for a file in a public Supabase bucket.

    Path segments are URL-encoded so spaces/special chars in keys stay valid.
    """
    base = base_url.rstrip("/")
    # Encode each path segment; keep slashes as separators.
    encoded = "/".join(quote(seg, safe="") for seg in object_path.lstrip("/").split("/"))
    return f"{base}/storage/v1/object/public/{bucket}/{encoded}"


def upload_receipt_pdf(
    pdf_bytes: bytes,
    *,
    receipt_no: str,
    content_type: str = "application/pdf",
    upsert: bool = True,
) -> str:
    """
    Upload receipt PDF bytes to the configured Supabase bucket.

    Args:
        pdf_bytes: Raw PDF content.
        receipt_no: Used in the object path template.
        content_type: MIME type (default application/pdf).
        upsert: When True, overwrite an existing object at the same path.

    Returns:
        Public URL of the uploaded object.

    Raises:
        ValueError: Missing config or empty payload.
        RuntimeError: HTTP / network failure from Storage API.
    """
    if not pdf_bytes:
        raise ValueError("Cannot upload empty PDF bytes.")

    cfg = load_supabase_config()
    object_path = build_object_path(receipt_no, path_style=cfg["path_style"])
    endpoint = (
        f"{cfg['url']}/storage/v1/object/{cfg['bucket']}/{object_path}"
    )

    headers = {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}",
        "Content-Type": content_type,
        "x-upsert": "true" if upsert else "false",
    }

    try:
        response = requests.post(
            endpoint,
            data=pdf_bytes,
            headers=headers,
            timeout=_UPLOAD_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Supabase storage upload request failed: {exc}") from exc

    if response.status_code not in (200, 201):
        # Keep body short — may include policy / auth hints.
        detail = (response.text or "").strip()
        if len(detail) > 400:
            detail = detail[:400] + "…"
        raise RuntimeError(
            f"Supabase storage upload failed (HTTP {response.status_code}): {detail or 'no body'}"
        )

    return public_object_url(cfg["url"], cfg["bucket"], object_path)


def _self_check() -> None:
    """Minimal offline checks for path + public URL builders (no network)."""
    path = build_object_path("DCV-2026-0042", path_style="{current_year}/{receipt_no}.pdf", year=2026)
    assert path == "2026/DCV-2026-0042.pdf", path

    path2 = build_object_path("DCV-2026-0001", path_style="{receipt_no}.pdf", year=2026)
    assert path2 == "DCV-2026-0001.pdf", path2

    url = public_object_url(
        "https://example.supabase.co",
        "receipts",
        "2026/DCV-2026-0042.pdf",
    )
    assert url == (
        "https://example.supabase.co/storage/v1/object/public/receipts/2026/DCV-2026-0042.pdf"
    ), url

    print("supabase_storage self-check OK")


if __name__ == "__main__":
    _self_check()
