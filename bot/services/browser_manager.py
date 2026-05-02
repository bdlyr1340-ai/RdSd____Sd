"""Global browser manager — one Playwright + Chromium for all users,
isolated browser context per user.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from bot import config
from bot.services.browser_session import BrowserSession

log = logging.getLogger(__name__)


class BrowserManager:
    """Lifecycle holder — start at boot, stop at shutdown."""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._sessions: Dict[int, BrowserSession] = {}
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=config.HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        self._started = True
        log.info("BrowserManager started (headless=%s)", config.HEADLESS)

    async def stop(self) -> None:
        # Close all open sessions first.
        for uid in list(self._sessions.keys()):
            try:
                await self.end_session(uid)
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None
        self._started = False
        log.info("BrowserManager stopped.")

    async def get_or_create(self, user_id: int) -> BrowserSession:
        async with self._lock:
            if user_id in self._sessions:
                return self._sessions[user_id]
            if not self._started:
                await self.start()
            ctx = await self._browser.new_context(
                viewport={"width": config.VIEWPORT_W, "height": config.VIEWPORT_H},
                user_agent=config.USER_AGENT,
                locale="ar-SA",
            )
            page = await ctx.new_page()
            await page.set_viewport_size(
                {"width": config.VIEWPORT_W, "height": config.VIEWPORT_H}
            )
            sess = BrowserSession(user_id, ctx, page)
            self._sessions[user_id] = sess
            log.info("New session for user %s", user_id)
            return sess

    def get(self, user_id: int) -> Optional[BrowserSession]:
        return self._sessions.get(user_id)

    async def end_session(self, user_id: int) -> Optional[Dict[str, str]]:
        async with self._lock:
            sess = self._sessions.pop(user_id, None)
        if sess is None:
            return None
        try:
            return await sess.close()
        except Exception as exc:
            log.warning("Failed to close session for %s: %s", user_id, exc)
            return None


# Singleton — imported by handlers and main.
manager = BrowserManager()
