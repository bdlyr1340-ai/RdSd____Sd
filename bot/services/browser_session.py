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
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from bot import config
from bot.services.grid_overlay import overlay_numbered_grid
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
    """Wraps one Playwright page + a SessionRecorder."""

    def __init__(self, user_id: int, ctx: Any, page: Any) -> None:
        self.user_id = user_id
        self.ctx = ctx
        self.page = page
        self.recorder = SessionRecorder(
            user_id=user_id,
            viewport=(config.VIEWPORT_W, config.VIEWPORT_H),
        )
        self.grid_rows = config.DEFAULT_GRID_ROWS
        self.grid_cols = config.DEFAULT_GRID_COLS
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

    async def _safe_screenshot(self, path: str) -> Optional[str]:
        try:
            await self.page.screenshot(
                path=path,
                full_page=False,           # only viewport — needed for grid alignment
                timeout=15_000,
            )
            return path
        except Exception as exc:
            log.warning("screenshot failed: %s", exc)
            return None

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
                # Use a small per-char delay so JS validators see human typing.
                await self.page.keyboard.type(text, delay=80)
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
        """direction ∈ {up, down, top, bottom}."""
        async with self._lock:
            try:
                if direction == "up":
                    await self.page.mouse.wheel(0, -300)
                    self.recorder.log("scroll", dy=-300)
                elif direction == "down":
                    await self.page.mouse.wheel(0, 300)
                    self.recorder.log("scroll", dy=300)
                elif direction == "top":
                    await self.page.evaluate("window.scrollTo(0, 0)")
                    self.recorder.log("scroll_top")
                elif direction == "bottom":
                    await self.page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight)"
                    )
                    self.recorder.log("scroll_bottom")
            except Exception as exc:
                log.warning("scroll(%s) failed: %s", direction, exc)
            await asyncio.sleep(0.3)
            return await self._safe_screenshot(self._shot_path(f"scroll_{direction}"))

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
                # Fallback: infer from viewport.
                from bot.services.grid_overlay import cell_center
                img_w, img_h = config.VIEWPORT_W, config.VIEWPORT_H
                ix, iy = cell_center(self.grid_rows, self.grid_cols, n,
                                     img_w, img_h)
            # Convert image px → CSS px (viewport coords) via the device-pixel ratio.
            sx = config.VIEWPORT_W / img_w
            sy = config.VIEWPORT_H / img_h
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
        try:
            await self.ctx.close()
        except Exception:
            pass
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
