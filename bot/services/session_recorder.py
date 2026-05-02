"""Session recorder.

Every action the user performs during a session is logged here. When the user
ends the session, this module exports:

  • A standalone Playwright Python script that reproduces the entire session.
  • A Markdown narrative that explains step-by-step what was done.

The generated script is meant to be the foundation of a custom Telegram bot or
a stand-alone automation — exactly what the user asked for.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Action:
    type: str
    timestamp: str            # HH:MM:SS local
    elapsed_sec: int          # seconds since session start
    details: Dict[str, Any] = field(default_factory=dict)


class SessionRecorder:
    """Lightweight in-memory recorder, one instance per Telegram user."""

    def __init__(self, user_id: int, viewport: tuple[int, int]) -> None:
        self.user_id = user_id
        self.viewport_w, self.viewport_h = viewport
        self.start_ts = time.time()
        self.start_iso = time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime(self.start_ts))
        self.actions: List[Action] = []

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def log(self, action_type: str, **details: Any) -> None:
        self.actions.append(Action(
            type=action_type,
            timestamp=time.strftime("%H:%M:%S"),
            elapsed_sec=int(time.time() - self.start_ts),
            details=details,
        ))

    # ------------------------------------------------------------------
    # Exports
    # ------------------------------------------------------------------
    def to_python_script(self) -> str:
        """Generate a runnable Playwright Python script."""
        lines: List[str] = []
        lines.append('"""')
        lines.append("Auto-generated browser-automation script.")
        lines.append(f"User ID    : {self.user_id}")
        lines.append(f"Started at : {self.start_iso}")
        lines.append(f"Actions    : {len(self.actions)}")
        lines.append("")
        lines.append("Run with:")
        lines.append("    pip install playwright")
        lines.append("    playwright install chromium")
        lines.append("    python session_script.py")
        lines.append('"""')
        lines.append("from __future__ import annotations")
        lines.append("")
        lines.append("import asyncio")
        lines.append("from playwright.async_api import async_playwright")
        lines.append("")
        lines.append("")
        lines.append("async def run() -> None:")
        lines.append("    async with async_playwright() as pw:")
        lines.append("        browser = await pw.chromium.launch(headless=False)")
        lines.append(f"        ctx = await browser.new_context("
                     f"viewport={{'width': {self.viewport_w}, "
                     f"'height': {self.viewport_h}}})")
        lines.append("        page = await ctx.new_page()")
        lines.append("")

        for i, act in enumerate(self.actions, 1):
            comment = f"        # [{act.timestamp} | +{act.elapsed_sec}s] " \
                      f"#{i} {act.type}"
            lines.append(comment)
            for code_line in self._code_for(act):
                lines.append(f"        {code_line}")
            lines.append("")

        lines.append("        await asyncio.sleep(2)")
        lines.append("        await browser.close()")
        lines.append("")
        lines.append("")
        lines.append('if __name__ == "__main__":')
        lines.append("    asyncio.run(run())")
        lines.append("")
        return "\n".join(lines)

    def to_markdown_narrative(self) -> str:
        """Generate a human-readable Markdown report (Arabic + English)."""
        out: List[str] = []
        out.append("# 📋 تقرير الجلسة | Session Report")
        out.append("")
        out.append(f"- **User ID:** `{self.user_id}`")
        out.append(f"- **Started:** {self.start_iso}")
        out.append(f"- **Total actions:** {len(self.actions)}")
        out.append(f"- **Viewport:** {self.viewport_w}×{self.viewport_h}")
        out.append("")
        out.append("---")
        out.append("")
        out.append("## الخطوات | Steps")
        out.append("")
        if not self.actions:
            out.append("_(no actions recorded)_")
        for i, act in enumerate(self.actions, 1):
            out.append(f"### {i}. {self._human_label(act)}")
            out.append(f"- ⏱️ `{act.timestamp}` (+{act.elapsed_sec}s)")
            if act.details:
                # Print details on a single line, JSON-encoded for clarity.
                pretty = json.dumps(act.details, ensure_ascii=False)
                out.append(f"- 📦 `{pretty}`")
            out.append("")
        return "\n".join(out)

    def to_json(self) -> str:
        """Raw JSON dump — useful if you want to programmatically replay."""
        return json.dumps(
            {
                "user_id": self.user_id,
                "started": self.start_iso,
                "viewport": [self.viewport_w, self.viewport_h],
                "actions": [
                    {
                        "type": a.type,
                        "timestamp": a.timestamp,
                        "elapsed_sec": a.elapsed_sec,
                        "details": a.details,
                    }
                    for a in self.actions
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

    def write_all(self, output_dir: str) -> Dict[str, str]:
        """Write all three artifacts to disk and return their paths."""
        os.makedirs(output_dir, exist_ok=True)
        ts = int(self.start_ts)
        prefix = os.path.join(output_dir, f"session_{self.user_id}_{ts}")

        py_path = f"{prefix}.py"
        md_path = f"{prefix}.md"
        json_path = f"{prefix}.json"

        with open(py_path, "w", encoding="utf-8") as f:
            f.write(self.to_python_script())
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.to_markdown_narrative())
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

        return {"script": py_path, "narrative": md_path, "json": json_path}

    # ------------------------------------------------------------------
    # Internal — mapping action → Python source lines
    # ------------------------------------------------------------------
    @staticmethod
    def _q(s: str) -> str:
        """Repr a string for safe inlining in generated source."""
        return json.dumps(s, ensure_ascii=False)

    def _code_for(self, act: Action) -> List[str]:
        d = act.details
        t = act.type

        if t == "open_url":
            return [
                f"await page.goto({self._q(d.get('url', ''))}, timeout=60_000)",
                "await page.wait_for_load_state('domcontentloaded')",
            ]
        if t == "screenshot":
            return ["# (screenshot taken — non-essential for replay)"]
        if t == "back":
            return ["await page.go_back()",
                    "await page.wait_for_load_state('domcontentloaded')"]
        if t == "reload":
            return ["await page.reload()",
                    "await page.wait_for_load_state('domcontentloaded')"]
        if t == "press_enter":
            return ["await page.keyboard.press('Enter')",
                    "await asyncio.sleep(0.4)"]
        if t == "type_text":
            text = d.get("text", "")
            return [f"await page.keyboard.type({self._q(text)}, delay=80)"]
        if t == "clear_text":
            return [
                "await page.keyboard.press('Control+A')",
                "await page.keyboard.press('Delete')",
            ]
        if t == "scroll":
            dy = int(d.get("dy", 0))
            return [f"await page.mouse.wheel(0, {dy})",
                    "await asyncio.sleep(0.2)"]
        if t == "scroll_top":
            return ["await page.evaluate('window.scrollTo(0, 0)')",
                    "await asyncio.sleep(0.2)"]
        if t == "scroll_bottom":
            return ["await page.evaluate("
                    "'window.scrollTo(0, document.body.scrollHeight)')",
                    "await asyncio.sleep(0.2)"]
        if t == "grid_click":
            x = float(d.get("x", 0))
            y = float(d.get("y", 0))
            cell = d.get("cell")
            rows = d.get("rows")
            cols = d.get("cols")
            return [
                f"# grid cell {cell} of {rows}x{cols}",
                f"await page.mouse.click({x:.1f}, {y:.1f})",
                "await asyncio.sleep(0.4)",
            ]
        if t == "find_click":
            text = d.get("text", "")
            return [
                f"await page.get_by_text({self._q(text)}, "
                f"exact=False).first.click(timeout=10_000)",
                "await asyncio.sleep(0.4)",
            ]
        if t == "find_clear":
            text = d.get("text", "")
            return [
                f"_loc = page.get_by_text({self._q(text)}, exact=False).first",
                "await _loc.click(timeout=10_000)",
                "await page.keyboard.press('Control+A')",
                "await page.keyboard.press('Delete')",
                "await asyncio.sleep(0.3)",
            ]
        if t == "detect_code":
            return ["# verification code detection — informational only"]
        if t == "log_time":
            return [f"# manual time marker: {d.get('note', '')}"]
        if t == "grid_settings":
            rows = d.get("rows")
            cols = d.get("cols")
            return [f"# grid resolution changed → {rows}x{cols}"]

        return [f"# unknown action: {t} {d}"]

    @staticmethod
    def _human_label(act: Action) -> str:
        d = act.details
        t = act.type
        if t == "open_url":
            return f"🌐 افتح رابط — `{d.get('url', '')}`"
        if t == "screenshot":
            return "📸 لقطة شاشة"
        if t == "back":
            return "⬅️ رجوع"
        if t == "reload":
            return "🔄 تحديث"
        if t == "press_enter":
            return "↩️ Enter"
        if t == "type_text":
            txt = d.get("text", "")
            preview = txt if len(txt) <= 40 else txt[:37] + "…"
            return f"⌨️ كتابة نص — `{preview}`"
        if t == "clear_text":
            return "❌ مسح النص"
        if t == "scroll":
            dy = d.get("dy", 0)
            return f"🖱️ سحب ({dy:+d}px)"
        if t == "scroll_top":
            return "⏫ صعود لأعلى الصفحة"
        if t == "scroll_bottom":
            return "⏬ نزول لأسفل الصفحة"
        if t == "grid_click":
            return f"🔢 ضغط على خلية الشبكة #{d.get('cell')}"
        if t == "find_click":
            return f"🔍 بحث + ضغط — `{d.get('text', '')}`"
        if t == "find_clear":
            return f"🔎 بحث + ضغط + مسح — `{d.get('text', '')}`"
        if t == "detect_code":
            codes = d.get("codes", [])
            return f"🛡️ اكتشاف كود التحقق — {codes}"
        if t == "log_time":
            return f"🕒 تسجيل الوقت — {d.get('note', '')}"
        if t == "grid_settings":
            return f"⚙️ تغيير شبكة الموس → {d.get('rows')}×{d.get('cols')}"
        return f"• {t}"
