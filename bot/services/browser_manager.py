"""Global browser manager — supports two engines:

  • **Camoufox** (preferred): an anti-detection Firefox build that produces
    ``isTrusted: true`` events, has GeoIP-based timezone/locale/WebGL spoofing,
    and patches the standard fingerprinting JS surface. Each user gets their
    own Camoufox browser instance because fingerprint options are set at
    *launch* time, not per-context.

  • **Playwright Chromium** (fallback): one shared Chromium with isolated
    contexts per user. Fast, low memory, but anti-bot scripts can still tell
    the events are synthetic.

The engine is auto-detected at startup based on whether the ``camoufox``
package is importable, and can be forced via the ``BROWSER_ENGINE`` env var.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from bot import config
from bot.services.browser_session import BrowserSession

log = logging.getLogger(__name__)


def _detect_engine(requested: str) -> str:
    """Pick the actual engine to use based on the requested setting + what's installed."""
    requested = (requested or "auto").lower()
    if requested == "playwright":
        return "playwright"
    if requested == "camoufox":
        return "camoufox"
    # auto — prefer Camoufox if installed.
    try:
        import camoufox  # noqa: F401
        return "camoufox"
    except ImportError:
        return "playwright"


class BrowserManager:
    """Lifecycle holder + per-user session factory."""

    def __init__(self) -> None:
        self.engine: str = _detect_engine(config.BROWSER_ENGINE)
        self._pw = None                      # Playwright server (when engine=playwright)
        self._browser = None                 # Shared Chromium (when engine=playwright)
        self._sessions: Dict[int, BrowserSession] = {}
        self._lock = asyncio.Lock()
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self._started:
            return
        if self.engine == "playwright":
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
        else:
            # Camoufox: nothing global to start — each session owns its own browser.
            pass
        self._started = True
        log.info("BrowserManager started (engine=%s, headless=%s)",
                 self.engine, config.HEADLESS)

    async def stop(self) -> None:
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

    # ------------------------------------------------------------------
    # Session factory
    # ------------------------------------------------------------------
    async def get_or_create(
        self,
        user_id: int,
        proxy: Optional[dict] = None,
        proxy_label: str = "",
        country_profile: Optional[Dict[str, Any]] = None,
    ) -> BrowserSession:
        async with self._lock:
            if user_id in self._sessions:
                return self._sessions[user_id]
            if not self._started:
                await self.start()

            if self.engine == "camoufox":
                sess = await self._create_camoufox_session(
                    user_id, proxy, proxy_label, country_profile,
                )
            else:
                sess = await self._create_playwright_session(
                    user_id, proxy, proxy_label, country_profile,
                )

            # Forward provenance to the recorder so the generated script
            # reproduces this exact setup.
            sess.recorder.proxy_dict = proxy
            sess.recorder.proxy_label = proxy_label
            sess.recorder.country_profile = country_profile
            sess.recorder.engine = self.engine
            self._sessions[user_id] = sess
            log.info(
                "New session — user=%s engine=%s country=%s proxy=%s",
                user_id, self.engine,
                (country_profile or {}).get("label", "default"),
                proxy_label or "direct",
            )
            return sess

    # ----- Camoufox path ----------------------------------------------
    async def _create_camoufox_session(
        self,
        user_id: int,
        proxy: Optional[dict],
        proxy_label: str,
        country_profile: Optional[Dict[str, Any]],
    ) -> BrowserSession:
        from camoufox.async_api import AsyncCamoufox

        cam_kwargs: Dict[str, Any] = {
            "headless": config.HEADLESS,
            # Camoufox's built-in cursor humanizer (mouse movement, not typing).
            "humanize": True,
        }
        if proxy:
            cam_kwargs["proxy"] = proxy
            # When using a proxy, let Camoufox's GeoIP figure out timezone/locale
            # from the proxy IP. This is more authentic than spoofing manually.
            cam_kwargs["geoip"] = True
        if country_profile:
            # Locale is always safe to set explicitly.
            cam_kwargs["locale"] = [country_profile["locale"], "en"]
            if not proxy:
                # No proxy — feed the geographic coordinates manually so
                # navigator.geolocation reports the chosen country.
                cam_kwargs["geoip"] = country_profile["geolocation"]

        cam = AsyncCamoufox(**cam_kwargs)
        browser = await cam.start()
        page = await browser.new_page()
        try:
            await page.set_viewport_size(
                {"width": config.VIEWPORT_W, "height": config.VIEWPORT_H}
            )
        except Exception:
            pass

        async def _cleanup() -> None:
            # AsyncCamoufox.__aexit__ closes the browser; we mirror that.
            try:
                await browser.close()
            except Exception:
                pass
            try:
                stop = getattr(cam, "__aexit__", None)
                if stop:
                    await stop(None, None, None)
            except Exception:
                pass

        sess = BrowserSession(user_id, owner=browser, page=page,
                              cleanup=_cleanup)
        sess.proxy_label = proxy_label
        sess.proxy_used = bool(proxy)
        sess.country_profile = country_profile
        sess.engine = "camoufox"
        return sess

    # ----- Playwright path --------------------------------------------
    async def _create_playwright_session(
        self,
        user_id: int,
        proxy: Optional[dict],
        proxy_label: str,
        country_profile: Optional[Dict[str, Any]],
    ) -> BrowserSession:
        ctx_kwargs: Dict[str, Any] = {
            "viewport": {"width": config.VIEWPORT_W,
                         "height": config.VIEWPORT_H},
            "user_agent": config.USER_AGENT,
        }
        if country_profile:
            ctx_kwargs["locale"] = country_profile["locale"]
            ctx_kwargs["timezone_id"] = country_profile["timezone"]
            ctx_kwargs["geolocation"] = country_profile["geolocation"]
            ctx_kwargs["permissions"] = ["geolocation"]
            ctx_kwargs["extra_http_headers"] = {
                "Accept-Language": country_profile["accept_language"],
            }
        else:
            ctx_kwargs["locale"] = "ar-SA"
        if proxy:
            ctx_kwargs["proxy"] = proxy

        ctx = await self._browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        await page.set_viewport_size(
            {"width": config.VIEWPORT_W, "height": config.VIEWPORT_H}
        )

        async def _cleanup() -> None:
            try:
                await ctx.close()
            except Exception:
                pass

        sess = BrowserSession(user_id, owner=ctx, page=page, cleanup=_cleanup)
        sess.proxy_label = proxy_label
        sess.proxy_used = bool(proxy)
        sess.country_profile = country_profile
        sess.engine = "playwright"
        return sess

    # ------------------------------------------------------------------
    # Lookup / shutdown
    # ------------------------------------------------------------------
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
