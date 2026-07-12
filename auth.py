"""
Authentication for Vighnaharta Receipts.

Login is validated against ``st.secrets``::

    [credentials]
    usernames = ["admin", "navayuvak"]

    [passwords]
    admin = "..."
    navayuvak = "..."

Session state tracks authentication, login time, and last activity.
Idle sessions expire after ``SESSION_TIMEOUT_MINUTES``.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

import streamlit as st

# Idle timeout (30 minutes of no user interaction)
SESSION_TIMEOUT_MINUTES = 60
# How often the background watchdog re-checks idle expiry without a button click
IDLE_CHECK_INTERVAL_SECONDS = 15

# session_state keys
_KEY_AUTH = "authenticated"
_KEY_USER = "username"
_KEY_ACTIVITY = "last_activity"
_KEY_LOGIN_AT = "login_at"
_KEY_FLASH = "auth_flash"  # one-shot message (e.g. session expired)
_KEY_FLASH_KIND = "auth_flash_kind"  # "success" | "error" | "warning" | "info"
_KEY_SHOW_PW = "login_show_password"


def _as_dict(value: Any) -> dict[str, Any]:
    """Normalize Streamlit AttrDict / Mapping to a plain dict."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def init_auth_state() -> None:
    """Ensure auth-related session_state keys exist."""
    if _KEY_AUTH not in st.session_state:
        st.session_state[_KEY_AUTH] = False
    if _KEY_USER not in st.session_state:
        st.session_state[_KEY_USER] = None
    if _KEY_ACTIVITY not in st.session_state:
        st.session_state[_KEY_ACTIVITY] = None
    if _KEY_LOGIN_AT not in st.session_state:
        st.session_state[_KEY_LOGIN_AT] = None
    if _KEY_SHOW_PW not in st.session_state:
        st.session_state[_KEY_SHOW_PW] = False


def _set_flash(message: str, kind: str = "info") -> None:
    """Store a one-shot message shown on the next render."""
    st.session_state[_KEY_FLASH] = message
    st.session_state[_KEY_FLASH_KIND] = kind


def consume_flash() -> None:
    """Display and clear any pending flash message (e.g. session expired)."""
    msg = st.session_state.pop(_KEY_FLASH, None)
    kind = st.session_state.pop(_KEY_FLASH_KIND, "info")
    if not msg:
        return
    if kind == "success":
        st.success(msg)
    elif kind == "error":
        st.error(msg)
    elif kind == "warning":
        st.warning(msg)
    else:
        st.info(msg)


def load_password_map() -> dict[str, str]:
    """
    Build username → password map from ``st.secrets``.

    Uses ``[credentials].usernames`` as the allow-list and ``[passwords]``
    for the secret values.
    """
    try:
        secrets = _as_dict(st.secrets)
    except Exception as exc:
        raise ValueError(
            "Could not load st.secrets. Ensure .streamlit/secrets.toml exists."
        ) from exc

    creds = _as_dict(secrets.get("credentials"))
    passwords = _as_dict(secrets.get("passwords"))

    usernames = creds.get("usernames") or []
    if isinstance(usernames, str):
        usernames = [usernames]

    password_map: dict[str, str] = {}
    for raw in usernames:
        user = str(raw).strip()
        if not user:
            continue
        if user not in passwords:
            continue
        password_map[user] = str(passwords[user])

    if not password_map and passwords:
        password_map = {str(k): str(v) for k, v in passwords.items()}

    return password_map


def validate_login(username: str, password: str) -> bool:
    """Return True if username/password match secrets."""
    username = (username or "").strip()
    password = password or ""
    if not username or not password:
        return False

    password_map = load_password_map()
    expected = password_map.get(username)
    if expected is None:
        return False
    return password == expected


def login_user(username: str) -> None:
    """Mark the session as authenticated; stamp login + activity times."""
    now = datetime.now()
    st.session_state[_KEY_AUTH] = True
    st.session_state[_KEY_USER] = username.strip()
    st.session_state[_KEY_LOGIN_AT] = now
    st.session_state[_KEY_ACTIVITY] = now
    st.session_state[_KEY_SHOW_PW] = False
    # No success flash — landing on the form is enough confirmation.


def logout_user(*, reason: str | None = None, kind: str = "info") -> None:
    """
    Clear auth session state.

    Args:
        reason: Optional flash message (e.g. session expired).
        kind: Flash style — success | error | warning | info.
    """
    st.session_state[_KEY_AUTH] = False
    st.session_state[_KEY_USER] = None
    st.session_state[_KEY_ACTIVITY] = None
    st.session_state[_KEY_LOGIN_AT] = None
    st.session_state[_KEY_SHOW_PW] = False
    if reason:
        _set_flash(reason, kind)


def touch_activity() -> None:
    """
    Record real user activity (widget interaction / form submit / navigation).

    Do **not** call this from the idle watchdog — only from paths that mean the
    user did something in the UI.
    """
    if st.session_state.get(_KEY_AUTH):
        st.session_state[_KEY_ACTIVITY] = datetime.now()


def is_authenticated() -> bool:
    """True if the session is currently marked logged-in (before timeout check)."""
    return bool(st.session_state.get(_KEY_AUTH))


def current_username() -> str | None:
    """Logged-in username, or None."""
    user = st.session_state.get(_KEY_USER)
    return str(user) if user else None


def login_timestamp() -> datetime | None:
    """When the current session started, or None."""
    value = st.session_state.get(_KEY_LOGIN_AT)
    return value if isinstance(value, datetime) else None


def last_activity_timestamp() -> datetime | None:
    """Last activity time, or None."""
    value = st.session_state.get(_KEY_ACTIVITY)
    return value if isinstance(value, datetime) else None


def session_expires_at() -> datetime | None:
    """Idle deadline: last activity + timeout window."""
    last = last_activity_timestamp()
    if last is None:
        return None
    return last + timedelta(minutes=SESSION_TIMEOUT_MINUTES)


def is_session_expired() -> bool:
    """True when idle longer than SESSION_TIMEOUT_MINUTES."""
    if not st.session_state.get(_KEY_AUTH):
        return False
    last = last_activity_timestamp()
    if last is None:
        return True
    return datetime.now() - last > timedelta(minutes=SESSION_TIMEOUT_MINUTES)


def check_session_timeout() -> bool:
    """
    Pure timeout check — does **not** extend the idle clock.

    Returns:
        True if the session is still valid (logged in and not expired).
        False if logged out or just expired (logout applied + flash set).
    """
    init_auth_state()

    if not is_authenticated():
        return False

    if is_session_expired():
        logout_user(
            reason="Session expired. Please login again.",
            kind="warning",
        )
        return False

    return True


def ensure_active_session() -> bool:
    """
    Gate for the main app script run (user-driven rerun).

    1. If not logged in → False
    2. If idle past timeout → logout, flash message, False
    3. Else treat this rerun as activity (extend idle clock) → True

    Call once at the top of ``main()`` on every script run. Combined with
    ``session_idle_watchdog``, expiry is also detected while the user is idle.
    """
    if not check_session_timeout():
        return False

    # User-driven script run (widget change, button, etc.) counts as activity
    touch_activity()
    return True


@st.fragment(run_every=timedelta(seconds=IDLE_CHECK_INTERVAL_SECONDS))
def session_idle_watchdog() -> None:
    """
    Background idle monitor.

    Streamlit only reruns the full script on interaction. Without this fragment,
    an idle tab would never hit the timeout check until the next button click.
    Runs every ``IDLE_CHECK_INTERVAL_SECONDS`` and forces a full rerun to the
    login page when the session has expired.
    """
    if not is_authenticated():
        return

    if is_session_expired():
        logout_user(
            reason="Session expired. Please login again.",
            kind="warning",
        )
        # Full-app rerun so main() shows the login page
        st.rerun()


def _fmt_time(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%d %b %Y, %I:%M %p")


def render_login_page() -> None:
    """
    Render the branded login form.

    Password visibility uses an emoji toggle (not Streamlit's default label).
    """
    init_auth_state()
    consume_flash()

    st.markdown(
        """
        <div class="vr-hero">
            <div class="vr-kicker">🙏 दादरचा विघ्नहर्ता</div>
            <h1>Staff login</h1>
            <p>
                Sign in to issue paperless donation e-receipts for
                Dadar Cha Vighnaharta · Navayuvak Mitra Mandal.
            </p>
            <div class="vr-hero-meta">
                <span class="vr-chip">🔒 Secure access</span>
                <span class="vr-chip">⏱ 30 min idle timeout</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="vr-card-label">
            <h2>Welcome back</h2>
            <span>Use your mandal credentials</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # No open/close HTML wrappers around widgets — those leave empty white bars.
    username = st.text_input(
        "Username",
        placeholder="e.g. admin",
        autocomplete="username",
        key="login_username",
    )

    show_pw = bool(st.session_state.get(_KEY_SHOW_PW))
    pw_type = "default" if show_pw else "password"
    toggle_emoji = "🙈" if show_pw else "👁️"
    toggle_help = "Hide password" if show_pw else "Show password"

    # Password + emoji toggle (Streamlit's built-in "visibility" control is CSS-hidden)
    pw_col, toggle_col = st.columns([10, 1], vertical_alignment="bottom")
    with pw_col:
        password = st.text_input(
            "Password",
            type=pw_type,
            placeholder="Enter password",
            autocomplete="current-password",
            key="login_password",
        )
    with toggle_col:
        if st.button(
            toggle_emoji,
            key="login_pw_toggle",
            help=toggle_help,
            use_container_width=True,
        ):
            st.session_state[_KEY_SHOW_PW] = not show_pw
            st.rerun()

    submitted = st.button(
        "🔓  Sign in",
        type="primary",
        use_container_width=True,
        key="login_submit",
    )

    if submitted:
        if not username.strip() or not password:
            st.error("Invalid username or password")
        elif validate_login(username, password):
            login_user(username)
            st.rerun()
        else:
            st.error("Invalid username or password")

    st.markdown(
        '<p class="vr-footnote">Navayuvak Mitra Mandal · Authorized users only</p>',
        unsafe_allow_html=True,
    )


def render_session_bar() -> None:
    """
    Top bar on the donation form: user, login time, idle expiry, logout.

    Also mounts the idle watchdog fragment so timeout is enforced without
    waiting for Generate PDF / other buttons.
    """
    # Periodic idle check (does not extend last_activity)
    session_idle_watchdog()

    user = current_username() or "User"
    login_at = login_timestamp()
    expires_at = session_expires_at()

    safe_user = html.escape(user)
    safe_login = html.escape(_fmt_time(login_at))
    safe_expires = html.escape(_fmt_time(expires_at))

    left, right = st.columns([5, 1], vertical_alignment="center")
    with left:
        st.markdown(
            f"""
            <div class="vr-session-bar">
                <div class="vr-session-main">
                    <span class="vr-session-user">👤 {safe_user}</span>
                    <span class="vr-session-dot">·</span>
                    <span class="vr-session-meta">Logged in {safe_login}</span>
                </div>
                <div class="vr-session-idle">
                    ⏱ Session ends without activity at <strong>{safe_expires}</strong>
                    <span class="vr-session-idle-note">({SESSION_TIMEOUT_MINUTES} min idle)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        if st.button("Logout", use_container_width=True, type="secondary", key="session_logout"):
            logout_user(reason=None)
            st.rerun()

    # Breathing room before hero / donation form
    st.markdown('<div class="vr-session-gap"></div>', unsafe_allow_html=True)
