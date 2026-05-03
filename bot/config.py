"""Bot configuration — values loaded from environment variables."""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional
from urllib.parse import urlparse


def _int_list(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",") if x.strip().lstrip("-").isdigit()]


# ── Telegram ──
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")

# Optional: only these user IDs may use the bot.
# Leave empty to allow everyone.
ADMIN_IDS: list[int] = _int_list(os.environ.get("ADMIN_IDS", ""))
ALLOW_ALL: bool = len(ADMIN_IDS) == 0

# ── Browser ──
HEADLESS: bool = os.environ.get("HEADLESS", "1") not in ("0", "false", "False")
# Default desktop/laptop browser size. 1920×1080 shows much more of pages like Canva.
# You can override from Railway Variables if your server memory is low.
VIEWPORT_W: int = int(os.environ.get("VIEWPORT_W", "1920"))
VIEWPORT_H: int = int(os.environ.get("VIEWPORT_H", "1080"))
LAPTOP_VIEWPORT_W: int = int(os.environ.get("LAPTOP_VIEWPORT_W", "1366"))
LAPTOP_VIEWPORT_H: int = int(os.environ.get("LAPTOP_VIEWPORT_H", "768"))
DESKTOP_VIEWPORT_W: int = int(os.environ.get("DESKTOP_VIEWPORT_W", "1920"))
DESKTOP_VIEWPORT_H: int = int(os.environ.get("DESKTOP_VIEWPORT_H", "1080"))
AUTO_PAGE_ZOOM: float = float(os.environ.get("AUTO_PAGE_ZOOM", "0.80"))
MIN_PAGE_ZOOM: float = float(os.environ.get("MIN_PAGE_ZOOM", "0.50"))
MAX_PAGE_ZOOM: float = float(os.environ.get("MAX_PAGE_ZOOM", "1.50"))
USER_AGENT: str = os.environ.get(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
)
SCROLL_STEP_Y: int = int(os.environ.get("SCROLL_STEP_Y", "650"))
SCROLL_STEP_X: int = int(os.environ.get("SCROLL_STEP_X", "800"))


# ── Browser engine ──
# "auto"      → Camoufox if installed, otherwise Playwright Chromium
# "camoufox"  → force Camoufox (anti-detection Firefox; produces isTrusted=true events)
# "playwright"→ force standard Playwright Chromium
BROWSER_ENGINE: str = os.environ.get("BROWSER_ENGINE", "auto").lower()

# ── Human typing ──
# Master switch for the human-typing simulator.
HUMAN_TYPING: bool = os.environ.get("HUMAN_TYPING", "1") not in ("0", "false", "False")
# Probability (0..1) of generating a typo + Backspace correction per character.
# 0.0  = perfect typing.
# 0.02 = ~2 typos per 100 chars (realistic).
# 0.05 = noticeably error-prone.
# Note: typos are skipped automatically inside numeric/email/url-looking text.
HUMAN_TYPO_RATE: float = float(os.environ.get("HUMAN_TYPO_RATE", "0.0"))

# ── Files ──
SHOTS_DIR: str = os.environ.get("SHOTS_DIR", "/tmp/shots")
SCRIPTS_DIR: str = os.environ.get("SCRIPTS_DIR", "/tmp/scripts")

# ── Access approval ──
# When ADMIN_IDS is set, new users request access and an admin approves once.
# Approved users are saved here, so they can use the bot permanently.
ACCESS_APPROVAL_REQUIRED: bool = os.environ.get(
    "ACCESS_APPROVAL_REQUIRED", "1"
) not in ("0", "false", "False")
APPROVED_USERS_FILE: str = os.environ.get(
    "APPROVED_USERS_FILE",
    os.path.join(SCRIPTS_DIR, "approved_users.json"),
)


# ── Mouse grid ──
DEFAULT_GRID_ROWS: int = int(os.environ.get("DEFAULT_GRID_ROWS", "20"))
DEFAULT_GRID_COLS: int = int(os.environ.get("DEFAULT_GRID_COLS", "20"))
MAX_GRID_CELLS: int = int(os.environ.get("MAX_GRID_CELLS", "2000"))

# ── Logging ──
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


# ─────────────────────────────────────────────────────────────────────
# Country profiles — applied to the browser context (timezone, locale,
# Accept-Language header, geolocation coordinates).
#
# These work *without any proxy* and trick websites that rely on:
#   - JavaScript Date()/Intl APIs
#   - navigator.language / Accept-Language header
#   - navigator.geolocation API
#
# They DO NOT change your IP — sites that check IP geolocation (banks,
# Netflix, government sites) still see your real country. For full
# geographic disguise, also configure ``PROXY_<CODE>`` below.
# ─────────────────────────────────────────────────────────────────────
COUNTRY_PROFILES: Dict[str, Dict[str, Any]] = {
    "IQ": {
        "label": "🇮🇶 العراق",
        "timezone": "Asia/Baghdad",
        "locale": "ar-IQ",
        "accept_language": "ar-IQ,ar;q=0.9,en;q=0.8",
        "geolocation": {"latitude": 33.3152, "longitude": 44.3661},  # Baghdad
    },
    "EG": {
        "label": "🇪🇬 مصر",
        "timezone": "Africa/Cairo",
        "locale": "ar-EG",
        "accept_language": "ar-EG,ar;q=0.9,en;q=0.8",
        "geolocation": {"latitude": 30.0444, "longitude": 31.2357},  # Cairo
    },
    "SA": {
        "label": "🇸🇦 السعودية",
        "timezone": "Asia/Riyadh",
        "locale": "ar-SA",
        "accept_language": "ar-SA,ar;q=0.9,en;q=0.8",
        "geolocation": {"latitude": 24.7136, "longitude": 46.6753},  # Riyadh
    },
    "AE": {
        "label": "🇦🇪 الإمارات",
        "timezone": "Asia/Dubai",
        "locale": "ar-AE",
        "accept_language": "ar-AE,ar;q=0.9,en;q=0.8",
        "geolocation": {"latitude": 25.2048, "longitude": 55.2708},  # Dubai
    },
    "US": {
        "label": "🇺🇸 الولايات المتحدة",
        "timezone": "America/New_York",
        "locale": "en-US",
        "accept_language": "en-US,en;q=0.9",
        "geolocation": {"latitude": 40.7128, "longitude": -74.0060},  # New York
    },
    "GB": {
        "label": "🇬🇧 بريطانيا",
        "timezone": "Europe/London",
        "locale": "en-GB",
        "accept_language": "en-GB,en;q=0.9",
        "geolocation": {"latitude": 51.5074, "longitude": -0.1278},   # London
    },
    "DE": {
        "label": "🇩🇪 ألمانيا",
        "timezone": "Europe/Berlin",
        "locale": "de-DE",
        "accept_language": "de-DE,de;q=0.9,en;q=0.8",
        "geolocation": {"latitude": 52.5200, "longitude": 13.4050},   # Berlin
    },
    "TR": {
        "label": "🇹🇷 تركيا",
        "timezone": "Europe/Istanbul",
        "locale": "tr-TR",
        "accept_language": "tr-TR,tr;q=0.9,en;q=0.8",
        "geolocation": {"latitude": 41.0082, "longitude": 28.9784},   # Istanbul
    },
}


# ─────────────────────────────────────────────────────────────────────
# Proxy presets (OPTIONAL). Same country codes as above.
#   PROXY_IQ=http://user:pass@iraq-proxy.example.com:8080
#   PROXY_US=socks5://us.proxy.com:1080
# Leave blank → that country still works with browser-level spoofing,
# but the IP remains unchanged.
# ─────────────────────────────────────────────────────────────────────
PROXY_URLS: Dict[str, str] = {
    code: os.environ.get(f"PROXY_{code}", "")
    for code in COUNTRY_PROFILES.keys()
}


def _read_approved_users() -> dict:
    """Read the persistent approval file safely."""
    try:
        with open(APPROVED_USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("approved_user_ids", [])
            return data
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return {"approved_user_ids": []}


def _write_approved_users(data: dict) -> None:
    os.makedirs(os.path.dirname(APPROVED_USERS_FILE) or ".", exist_ok=True)
    ids = sorted({int(x) for x in data.get("approved_user_ids", [])})
    payload = {"approved_user_ids": ids}
    with open(APPROVED_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def approval_required() -> bool:
    # If no admin is configured, keep the old safe behaviour: allow everyone.
    return ACCESS_APPROVAL_REQUIRED and bool(ADMIN_IDS)


def is_approved_user(user_id: int) -> bool:
    data = _read_approved_users()
    return int(user_id) in {int(x) for x in data.get("approved_user_ids", [])}


def approve_user(user_id: int) -> None:
    data = _read_approved_users()
    ids = {int(x) for x in data.get("approved_user_ids", [])}
    ids.add(int(user_id))
    data["approved_user_ids"] = sorted(ids)
    _write_approved_users(data)


def reject_user(user_id: int) -> None:
    data = _read_approved_users()
    ids = {int(x) for x in data.get("approved_user_ids", [])}
    ids.discard(int(user_id))
    data["approved_user_ids"] = sorted(ids)
    _write_approved_users(data)


def is_authorized(user_id: int) -> bool:
    """Return True if a user is allowed to use the bot."""
    if is_admin(user_id):
        return True
    if approval_required():
        return is_approved_user(user_id)
    if ALLOW_ALL:
        return True
    return False


def parse_proxy_url(url: str) -> Optional[dict]:
    """Convert a proxy URL into the dict shape Playwright expects.

    Accepted formats:
        http://host:port
        http://user:pass@host:port
        https://user:pass@host:port
        socks5://host:port
        socks5://user:pass@host:port

    Returns None when ``url`` is empty. Raises ValueError on bad input.
    """
    if not url or not url.strip():
        return None
    p = urlparse(url.strip())
    if not p.scheme or not p.hostname:
        raise ValueError(f"رابط بروكسي غير صالح: {url}")
    if p.scheme not in ("http", "https", "socks5", "socks4"):
        raise ValueError(
            f"بروتوكول غير مدعوم ({p.scheme}). استخدم http/https/socks5."
        )
    server = f"{p.scheme}://{p.hostname}"
    if p.port:
        server += f":{p.port}"
    out: dict = {"server": server}
    if p.username:
        out["username"] = p.username
    if p.password:
        out["password"] = p.password
    return out


def validate() -> None:
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if missing:
        print(f"[FATAL] Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(SHOTS_DIR, exist_ok=True)
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(APPROVED_USERS_FILE) or ".", exist_ok=True)
