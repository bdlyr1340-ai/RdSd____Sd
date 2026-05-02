"""Bot configuration — values loaded from environment variables."""
from __future__ import annotations

import os
import sys


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
VIEWPORT_W: int = int(os.environ.get("VIEWPORT_W", "1280"))
VIEWPORT_H: int = int(os.environ.get("VIEWPORT_H", "800"))
USER_AGENT: str = os.environ.get(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
)

# ── Files ──
SHOTS_DIR: str = os.environ.get("SHOTS_DIR", "/tmp/shots")
SCRIPTS_DIR: str = os.environ.get("SCRIPTS_DIR", "/tmp/scripts")

# ── Mouse grid ──
DEFAULT_GRID_ROWS: int = int(os.environ.get("DEFAULT_GRID_ROWS", "20"))
DEFAULT_GRID_COLS: int = int(os.environ.get("DEFAULT_GRID_COLS", "20"))
MAX_GRID_CELLS: int = int(os.environ.get("MAX_GRID_CELLS", "2000"))

# ── Logging ──
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


def is_authorized(user_id: int) -> bool:
    """Return True if a user is allowed to use the bot."""
    if ALLOW_ALL:
        return True
    return user_id in ADMIN_IDS


def validate() -> None:
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if missing:
        print(f"[FATAL] Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(SHOTS_DIR, exist_ok=True)
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
