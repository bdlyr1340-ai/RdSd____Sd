"""Per-user browser session.

Each Telegram user gets one ``BrowserSession`` instance backed by an
isolated Playwright context. The class exposes high-level actions:

  • open_url, screenshot, back, reload, press_enter
  • type_text, clear_text
  • scroll (relative or to top/bottom)
  • grid_screenshot + click_cell
  • find_click, find_click_clear
  • detect_codes
  • close (returns paths of generated artifacts)

Every action is forwarded to the ``SessionRecorder`` so the user can later
download a Python script + Markdown narrative of what they did.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from bot import config
from bot.services.grid_overlay import overlay_numbered_grid
from bot.services.human_typing import human_type
from bot.services.session_recorder import SessionRecorder

log = logging.getLogger(__name__)


# -- regex for verification codes ----------------------------------------
# Common patterns: 4–8 digit codes, possibly with spaces/dashes between.
_CODE_RE = re.compile(r"\b(?:\d[\s-]?){3,7}\d\b")
# Words that hint a code is nearby (Arabic + English).
_CODE_HINTS = (
    "code", "verification", "verify", "otp", "passcode", "pin",
    "كود", "رمز", "تحقق", "تأكيد", "التحقق", "تفعيل",
)


class BrowserSession:
    """Wraps one Playwright/Camoufox page + a SessionRecorder."""

    def __init__(
        self,
        user_id: int,
        owner: Any,
        page: Any,
        cleanup: Any = None,
    ) -> None:
        """
        Args:
            user_id: Telegram user id.
            owner: Either a Playwright BrowserContext (Playwright engine) or
                a Camoufox/Playwright Browser (Camoufox engine). Kept around
                so the cleanup callback has a closure over it.
            page: The Playwright/Camoufox Page we drive.
            cleanup: Async callable that releases the owner's resources
                (closes the context or the camoufox browser).
        """
        self.user_id = user_id
        self.owner = owner
        self.page = page
        self._cleanup = cleanup
        self.recorder = SessionRecorder(
            user_id=user_id,
            viewport=(config.VIEWPORT_W, config.VIEWPORT_H),
        )
        self.grid_rows = config.DEFAULT_GRID_ROWS
        self.grid_cols = config.DEFAULT_GRID_COLS
        # Proxy info (set by BrowserManager on creation).
        self.proxy_label: str = ""   # e.g. "🇮🇶 العراق" or empty for direct
        self.proxy_used: bool = False
        # Country profile (timezone/locale/geo) applied to the context.
        self.country_profile: Optional[Dict[str, Any]] = None
        # Engine: "camoufox" or "playwright"
        self.engine: str = "playwright"
        # Last grid info — used so the user can click cells by number after
        # the grid was rendered.
        self._last_grid_cells: Dict[int, Tuple[float, float]] = {}
        self._last_grid_size: Tuple[int, int] = (
            config.VIEWPORT_W, config.VIEWPORT_H,
        )
        # Async lock to serialise page actions per session.
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _shot_path(self, tag: str, ext: str = "png") -> str:
        ts = int(time.time() * 1000)
        return os.path.join(
            config.SHOTS_DIR,
            f"{self.user_id}_{ts}_{tag}.{ext}",
        )

    async def _safe_screenshot(self, path: str, full_page: bool = False) -> Optional[str]:
        try:
            await self.page.screenshot(
                path=path,
                full_page=full_page,
                timeout=30_000 if full_page else 15_000,
            )
            return path
        except Exception as exc:
            log.warning("screenshot failed: %s", exc)
            return None

    async def _viewport_size(self) -> Tuple[int, int]:
        """Return the live Playwright viewport size instead of assuming config defaults."""
        try:
            vp = self.page.viewport_size or {}
            w = int(vp.get("width") or config.VIEWPORT_W)
            h = int(vp.get("height") or config.VIEWPORT_H)
            return w, h
        except Exception:
            return config.VIEWPORT_W, config.VIEWPORT_H

    async def _apply_page_zoom(self, zoom: float) -> None:
        """Apply a CSS zoom so large pages show more content in screenshots."""
        zoom = max(config.MIN_PAGE_ZOOM, min(config.MAX_PAGE_ZOOM, float(zoom)))
        await self.page.evaluate(
            """
            (zoom) => {
                window.__botPageZoom = zoom;
                const root = document.documentElement;
                const body = document.body;
                if (root) {
                    root.style.zoom = String(zoom);
                    root.style.transformOrigin = '0 0';
                }
                if (body) {
                    body.style.transformOrigin = '0 0';
                }
                return zoom;
            }
            """,
            zoom,
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    async def open_url(self, url: str) -> Optional[str]:
        async with self._lock:
            self.recorder.log("open_url", url=url)
            try:
                await self.page.goto(url, timeout=60_000,
                                     wait_until="domcontentloaded")
            except Exception as exc:
                log.warning("open_url failed: %s", exc)
            await asyncio.sleep(0.5)
            return await self._safe_screenshot(self._shot_path("open_url"))

    async def screenshot(self) -> Optional[str]:
        async with self._lock:
            self.recorder.log("screenshot")
            return await self._safe_screenshot(self._shot_path("manual"))

    async def screenshot_full_page(self) -> Optional[str]:
        """Capture the complete page height as a high-detail image."""
        async with self._lock:
            self.recorder.log("screenshot_full_page")
            return await self._safe_screenshot(
                self._shot_path("full_page"), full_page=True
            )

    async def set_viewport(self, width: int, height: int, zoom: Optional[float] = None) -> Optional[str]:
        """Change the live browser viewport and optionally page zoom."""
        async with self._lock:
            width = max(800, min(2560, int(width)))
            height = max(600, min(1600, int(height)))
            try:
                await self.page.set_viewport_size({"width": width, "height": height})
                if zoom is not None:
                    await self._apply_page_zoom(zoom)
                await asyncio.sleep(0.25)
                self.recorder.log("set_viewport", width=width, height=height, zoom=zoom)
            except Exception as exc:
                log.warning("set_viewport failed: %s", exc)
            return await self._safe_screenshot(self._shot_path("viewport"))

    async def set_zoom(self, zoom: float) -> Optional[str]:
        """Change only page zoom, preserving current scroll position."""
        async with self._lock:
            try:
                await self._apply_page_zoom(zoom)
                self.recorder.log("set_zoom", zoom=zoom)
            except Exception as exc:
                log.warning("set_zoom failed: %s", exc)
            await asyncio.sleep(0.25)
            return await self._safe_screenshot(self._shot_path("zoom"))

    async def fit_screen(self) -> Optional[str]:
        """One button fix: wide desktop viewport + zoom out + preserve visible area."""
        async with self._lock:
            try:
                await self.page.set_viewport_size({
                    "width": config.DESKTOP_VIEWPORT_W,
                    "height": config.DESKTOP_VIEWPORT_H,
                })
                await self._apply_page_zoom(config.AUTO_PAGE_ZOOM)
                await asyncio.sleep(0.35)
                # Keep the current vertical position, but reset horizontal drift.
                await self.page.evaluate(
                    """
                    () => {
                        const doc = document.scrollingElement || document.documentElement || document.body;
                        if (doc) doc.scrollLeft = 0;
                        window.scrollTo({left: 0, top: window.scrollY, behavior: 'instant'});
                        return true;
                    }
                    """
                )
                self.recorder.log(
                    "fit_screen",
                    width=config.DESKTOP_VIEWPORT_W,
                    height=config.DESKTOP_VIEWPORT_H,
                    zoom=config.AUTO_PAGE_ZOOM,
                )
            except Exception as exc:
                log.warning("fit_screen failed: %s", exc)
            await asyncio.sleep(0.25)
            return await self._safe_screenshot(self._shot_path("fit_screen"))

    async def back(self) -> Optional[str]:
        async with self._lock:
            self.recorder.log("back")
            try:
                await self.page.go_back(timeout=15_000,
                                        wait_until="domcontentloaded")
            except Exception as exc:
                log.warning("back failed: %s", exc)
            await asyncio.sleep(0.4)
            return await self._safe_screenshot(self._shot_path("back"))

    async def reload(self) -> Optional[str]:
        async with self._lock:
            self.recorder.log("reload")
            try:
                await self.page.reload(timeout=30_000,
                                       wait_until="domcontentloaded")
            except Exception as exc:
                log.warning("reload failed: %s", exc)
            await asyncio.sleep(0.4)
            return await self._safe_screenshot(self._shot_path("reload"))

    async def press_enter(self) -> Optional[str]:
        async with self._lock:
            self.recorder.log("press_enter")
            try:
                await self.page.keyboard.press("Enter")
            except Exception as exc:
                log.warning("enter failed: %s", exc)
            await asyncio.sleep(0.6)
            return await self._safe_screenshot(self._shot_path("enter"))

    async def type_text(self, text: str) -> Optional[str]:
        async with self._lock:
            self.recorder.log("type_text", text=text)
            try:
                if config.HUMAN_TYPING:
                    await human_type(
                        self.page,
                        text,
                        typo_rate=config.HUMAN_TYPO_RATE,
                    )
                else:
                    # Fallback: simple per-char type without humanization.
                    await self.page.keyboard.type(text, delay=60)
            except Exception as exc:
                log.warning("type_text failed: %s", exc)
            await asyncio.sleep(0.3)
            return await self._safe_screenshot(self._shot_path("type"))

    async def clear_text(self) -> Optional[str]:
        async with self._lock:
            self.recorder.log("clear_text")
            try:
                await self.page.keyboard.press("Control+A")
                await asyncio.sleep(0.05)
                await self.page.keyboard.press("Delete")
            except Exception as exc:
                log.warning("clear_text failed: %s", exc)
            await asyncio.sleep(0.2)
            return await self._safe_screenshot(self._shot_path("clear"))

    async def scroll(self, direction: str) -> Optional[str]:
        """Smart scrolling.

        Supports the page itself and inner scrollable panels.
        direction ∈ {up, down, top, bottom, left, right, left_end, right_end}.
        """
        async with self._lock:
            result: Dict[str, Any] = {}
            try:
                result = await self.page.evaluate(
                    """
                    ({direction, stepX, stepY}) => {
                        const doc = document.scrollingElement || document.documentElement || document.body;
                        const isElement = (el) => el && el.nodeType === 1;
                        const canY = (el) => isElement(el) && el.scrollHeight > el.clientHeight + 2;
                        const canX = (el) => isElement(el) && el.scrollWidth > el.clientWidth + 2;
                        const centre = document.elementFromPoint(Math.floor(innerWidth / 2), Math.floor(innerHeight / 2));
                        const active = document.activeElement;
                        const chain = [];
                        const add = (el) => { if (isElement(el) && !chain.includes(el)) chain.push(el); };
                        let el = centre;
                        while (el) { add(el); el = el.parentElement; }
                        el = active;
                        while (el) { add(el); el = el.parentElement; }
                        add(doc); add(document.documentElement); add(document.body);

                        const before = {x: window.scrollX, y: window.scrollY};
                        let target = doc;
                        let moved = false;
                        const useY = ["up", "down", "top", "bottom"].includes(direction);
                        const useX = ["left", "right", "left_end", "right_end"].includes(direction);

                        for (const item of chain) {
                            if (useY && canY(item)) { target = item; break; }
                            if (useX && canX(item)) { target = item; break; }
                        }

                        const scrollOne = (item) => {
                            const oldX = item === doc ? window.scrollX : item.scrollLeft;
                            const oldY = item === doc ? window.scrollY : item.scrollTop;
                            if (direction === "up") item.scrollBy({top: -stepY, behavior: "instant"});
                            else if (direction === "down") item.scrollBy({top: stepY, behavior: "instant"});
                            else if (direction === "left") item.scrollBy({left: -stepX, behavior: "instant"});
                            else if (direction === "right") item.scrollBy({left: stepX, behavior: "instant"});
                            else if (direction === "top") item.scrollTo({top: 0, behavior: "instant"});
                            else if (direction === "bottom") item.scrollTo({top: item.scrollHeight, behavior: "instant"});
                            else if (direction === "left_end") item.scrollTo({left: 0, behavior: "instant"});
                            else if (direction === "right_end") item.scrollTo({left: item.scrollWidth, behavior: "instant"});
                            const newX = item === doc ? window.scrollX : item.scrollLeft;
                            const newY = item === doc ? window.scrollY : item.scrollTop;
                            return (Math.abs(newX - oldX) + Math.abs(newY - oldY)) > 1;
                        };

                        moved = scrollOne(target);

                        // If the chosen panel did not move, try the document and then every scrollable panel.
                        if (!moved) {
                            const fallbacks = [doc, ...chain].filter((item, i, arr) => arr.indexOf(item) === i);
                            for (const item of fallbacks) {
                                if ((useY && canY(item)) || (useX && canX(item))) {
                                    if (scrollOne(item)) { target = item; moved = true; break; }
                                }
                            }
                        }

                        // For end buttons, make sure both page and panels have a chance to reach the edge.
                        if (["top", "bottom", "left_end", "right_end"].includes(direction)) {
                            for (const item of chain) {
                                if ((useY && canY(item)) || (useX && canX(item))) scrollOne(item);
                            }
                        }

                        return {
                            moved,
                            direction,
                            before,
                            after: {x: window.scrollX, y: window.scrollY},
                            viewport: {w: innerWidth, h: innerHeight},
                            page: {w: doc.scrollWidth, h: doc.scrollHeight},
                            targetTag: target && target.tagName ? target.tagName.toLowerCase() : "page",
                            targetClass: target && target.className ? String(target.className).slice(0, 80) : "",
                        };
                    }
                    """,
                    {
                        "direction": direction,
                        "stepX": config.SCROLL_STEP_X,
                        "stepY": config.SCROLL_STEP_Y,
                    },
                )
                if direction in ("up", "down", "left", "right"):
                    dx = 0
                    dy = 0
                    if direction == "up": dy = -config.SCROLL_STEP_Y
                    elif direction == "down": dy = config.SCROLL_STEP_Y
                    elif direction == "left": dx = -config.SCROLL_STEP_X
                    elif direction == "right": dx = config.SCROLL_STEP_X
                    self.recorder.log("scroll", dx=dx, dy=dy, result=result)
                elif direction == "top":
                    self.recorder.log("scroll_top", result=result)
                elif direction == "bottom":
                    self.recorder.log("scroll_bottom", result=result)
                elif direction == "left_end":
                    self.recorder.log("scroll_left_end", result=result)
                elif direction == "right_end":
                    self.recorder.log("scroll_right_end", result=result)
            except Exception as exc:
                log.warning("scroll(%s) failed: %s", direction, exc)
            await asyncio.sleep(0.35)
            return await self._safe_screenshot(self._shot_path(f"scroll_{direction}"))

    async def page_status(self) -> Dict[str, Any]:
        """Return a small live status object to understand what is visible."""
        try:
            return await self.page.evaluate(
                """
                () => {
                    const doc = document.scrollingElement || document.documentElement || document.body;
                    const centre = document.elementFromPoint(Math.floor(innerWidth / 2), Math.floor(innerHeight / 2));
                    const active = document.activeElement;
                    return {
                        url: location.href,
                        title: document.title || '',
                        x: Math.round(window.scrollX),
                        y: Math.round(window.scrollY),
                        viewportW: Math.round(innerWidth),
                        viewportH: Math.round(innerHeight),
                        pageW: Math.round(doc.scrollWidth),
                        pageH: Math.round(doc.scrollHeight),
                        zoom: Number(window.__botPageZoom || (document.documentElement && document.documentElement.style.zoom) || 1),
                        centreTag: centre ? centre.tagName.toLowerCase() : '',
                        activeTag: active ? active.tagName.toLowerCase() : '',
                        scrollables: Array.from(document.querySelectorAll('*')).filter(el => {
                            const st = getComputedStyle(el);
                            return (el.scrollWidth > el.clientWidth + 10 || el.scrollHeight > el.clientHeight + 10)
                                && /(auto|scroll|overlay)/.test(st.overflow + st.overflowX + st.overflowY);
                        }).slice(0, 5).map(el => ({
                            tag: el.tagName.toLowerCase(),
                            x: Math.round(el.scrollLeft),
                            y: Math.round(el.scrollTop),
                            w: Math.round(el.clientWidth),
                            h: Math.round(el.clientHeight),
                            sw: Math.round(el.scrollWidth),
                            sh: Math.round(el.scrollHeight),
                        })),
                    };
                }
                """
            )
        except Exception as exc:
            log.warning("page_status failed: %s", exc)
            return {}

    # ----- mouse-grid actions -----------------------------------------
    async def grid_screenshot(self) -> Optional[str]:
        """Take a viewport screenshot and overlay the numbered grid."""
        async with self._lock:
            raw = self._shot_path("grid_raw")
            await self._safe_screenshot(raw)
            if not os.path.exists(raw):
                return None
            annotated = self._shot_path("grid")
            try:
                # Use Pillow to inspect actual image size (HiDPI / DPR safe).
                from PIL import Image
                with Image.open(raw) as im:
                    img_w, img_h = im.size
                self._last_grid_size = (img_w, img_h)
                self._last_grid_cells = overlay_numbered_grid(
                    raw, annotated,
                    rows=self.grid_rows,
                    cols=self.grid_cols,
                )
                return annotated
            except Exception as exc:
                log.exception("grid overlay failed: %s", exc)
                return None

    async def click_cell(self, n: int) -> Optional[str]:
        """Click the centre of grid cell ``n``.

        If the user never previewed the grid, we still compute coords from
        the viewport size — but we strongly recommend previewing first.
        """
        async with self._lock:
            total = self.grid_rows * self.grid_cols
            if n < 1 or n > total:
                raise ValueError(
                    f"رقم الخلية يجب أن يكون بين 1 و {total}."
                )
            if self._last_grid_cells and n in self._last_grid_cells:
                ix, iy = self._last_grid_cells[n]
                img_w, img_h = self._last_grid_size
            else:
                # Fallback: infer from the live viewport, not old config defaults.
                from bot.services.grid_overlay import cell_center
                img_w, img_h = await self._viewport_size()
                ix, iy = cell_center(self.grid_rows, self.grid_cols, n,
                                     img_w, img_h)
            # Convert image px → CSS px (viewport coords) via the live viewport.
            viewport_w, viewport_h = await self._viewport_size()
            sx = viewport_w / img_w
            sy = viewport_h / img_h
            cx = ix * sx
            cy = iy * sy
            try:
                await self.page.mouse.click(cx, cy)
            except Exception as exc:
                log.warning("click_cell failed: %s", exc)
            self.recorder.log(
                "grid_click", cell=n,
                rows=self.grid_rows, cols=self.grid_cols,
                x=cx, y=cy,
            )
            await asyncio.sleep(0.5)
            return await self._safe_screenshot(self._shot_path(f"cell_{n}"))

    def set_grid(self, rows: int, cols: int) -> None:
        if rows < 1 or cols < 1:
            raise ValueError("الصفوف والأعمدة يجب أن تكون أكبر من صفر.")
        if rows * cols > config.MAX_GRID_CELLS:
            raise ValueError(
                f"الحد الأقصى {config.MAX_GRID_CELLS} مربع — "
                f"{rows}×{cols} = {rows * cols}."
            )
        self.grid_rows = rows
        self.grid_cols = cols
        self.recorder.log("grid_settings", rows=rows, cols=cols)

    # ----- text search ------------------------------------------------
    async def find_click(self, text: str) -> Optional[str]:
        async with self._lock:
            self.recorder.log("find_click", text=text)
            try:
                loc = self.page.get_by_text(text, exact=False).first
                await loc.scroll_into_view_if_needed(timeout=5_000)
                await loc.click(timeout=10_000)
            except Exception as exc:
                log.warning("find_click failed: %s", exc)
                raise RuntimeError(f"لم أجد العنصر «{text}». ({exc})")
            await asyncio.sleep(0.5)
            return await self._safe_screenshot(self._shot_path("find_click"))

    async def find_click_clear(self, text: str) -> Optional[str]:
        async with self._lock:
            self.recorder.log("find_clear", text=text)
            try:
                loc = self.page.get_by_text(text, exact=False).first
                await loc.scroll_into_view_if_needed(timeout=5_000)
                await loc.click(timeout=10_000)
                await asyncio.sleep(0.2)
                await self.page.keyboard.press("Control+A")
                await asyncio.sleep(0.05)
                await self.page.keyboard.press("Delete")
            except Exception as exc:
                log.warning("find_click_clear failed: %s", exc)
                raise RuntimeError(f"فشل البحث/المسح للنص «{text}». ({exc})")
            await asyncio.sleep(0.4)
            return await self._safe_screenshot(self._shot_path("find_clear"))

    # ----- code detection --------------------------------------------
    async def detect_codes(self) -> List[str]:
        """Scan visible text for verification-code candidates and return them.

        Strategy:
          1. Pull the entire page text via JS.
          2. Find regex matches.
          3. Bias toward matches in the same paragraph as a hint word
             ("code", "verification", "كود", "رمز", "تحقق", …).
        """
        async with self._lock:
            try:
                text: str = await self.page.evaluate(
                    "document.body && document.body.innerText || ''"
                )
            except Exception as exc:
                log.warning("detect_codes innerText failed: %s", exc)
                text = ""
            text = text.replace("\u200f", "").replace("\u200e", "")
            candidates: List[str] = []

            # 1) prioritised: lines with a hint word
            for line in text.splitlines():
                low = line.lower()
                if any(h in low for h in _CODE_HINTS):
                    for m in _CODE_RE.finditer(line):
                        clean = re.sub(r"[\s-]", "", m.group(0))
                        if 4 <= len(clean) <= 8 and clean not in candidates:
                            candidates.append(clean)

            # 2) fallback: any standalone digit-runs of 4–8 digits
            if not candidates:
                for m in _CODE_RE.finditer(text):
                    clean = re.sub(r"[\s-]", "", m.group(0))
                    if 4 <= len(clean) <= 8 and clean not in candidates:
                        candidates.append(clean)

            # Deduplicate & cap.
            candidates = candidates[:10]
            self.recorder.log("detect_code", codes=candidates)
            return candidates

    # ----- time logging ---------------------------------------------
    def log_time(self, note: str = "") -> str:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self.recorder.log("log_time", at=ts, note=note)
        return ts

    # ----- close ----------------------------------------------------
    async def close(self) -> Dict[str, str]:
        """Close the browser context and write the script/narrative.

        Returns a dict {"script": path, "narrative": path, "json": path}.
        """
        artifacts: Dict[str, str] = {}
        try:
            artifacts = self.recorder.write_all(config.SCRIPTS_DIR)
        except Exception as exc:
            log.exception("write artifacts failed: %s", exc)
        try:
            await self.page.close()
        except Exception:
            pass
        if self._cleanup is not None:
            try:
                await self._cleanup()
            except Exception as exc:
                log.warning("cleanup callback failed: %s", exc)
        return artifacts

    # ----- meta -----------------------------------------------------
    @property
    def grid_total(self) -> int:
        return self.grid_rows * self.grid_cols

    async def current_url(self) -> str:
        try:
            return self.page.url or ""
        except Exception:
            return ""

    async def current_title(self) -> str:
        try:
            return await self.page.title()
        except Exception:
            return ""
