"""Inline keyboards for the browser-control bot."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot import config


def main_menu(country_label: str = "", engine: str = "") -> InlineKeyboardMarkup:
    """Main menu shown on /start.

    Args:
        country_label: Currently selected country profile label (e.g.
            "🇮🇶 العراق") or empty string. Reflected on the country button.
        engine: "camoufox" or "playwright" — shown as an info row.
    """
    country_btn = (
        f"🌍 الدولة: {country_label}"
        if country_label
        else "🌍 الدولة/السرفر — افتراضي"
    )
    engine_btn = (
        f"🦊 المتصفح: {engine}" if engine else "🦊 المتصفح"
    )
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 بدء جلسة جديدة", callback_data="session_start")],
        [InlineKeyboardButton(country_btn, callback_data="proxy_menu")],
        [InlineKeyboardButton(engine_btn, callback_data="engine_info")],
        [InlineKeyboardButton("ℹ️ كيف يعمل البوت", callback_data="how_it_works")],
        [InlineKeyboardButton("📖 المساعدة", callback_data="help")],
    ])


def proxy_menu() -> InlineKeyboardMarkup:
    """Country picker. Items show ⚪ when no proxy is configured for that
    country (the country profile still works — only the IP stays unchanged)."""
    rows = []
    pairs = list(config.COUNTRY_PROFILES.items())
    # 2 buttons per row.
    for i in range(0, len(pairs), 2):
        row = []
        for code, prof in pairs[i:i + 2]:
            label = prof["label"]
            has_proxy = bool(config.PROXY_URLS.get(code, ""))
            mark = "" if has_proxy else " ⚪"   # ⚪ = profile only, no proxy
            row.append(InlineKeyboardButton(
                label + mark,
                callback_data=f"proxy_pick_{code}",
            ))
        rows.append(row)
    rows.append([
        InlineKeyboardButton("✏️ بروكسي مخصص", callback_data="proxy_custom"),
        InlineKeyboardButton("🔌 افتراضي", callback_data="proxy_direct"),
    ])
    rows.append([
        InlineKeyboardButton("⬅️ رجوع للقائمة", callback_data="back_to_main"),
    ])
    return InlineKeyboardMarkup(rows)


def control_panel(grid_rows: int, grid_cols: int) -> InlineKeyboardMarkup:
    """The main control panel shown during an active browser session."""
    total_cells = grid_rows * grid_cols
    return InlineKeyboardMarkup([
        # Row 1 — open URL + screenshot
        [
            InlineKeyboardButton("🌐 افتح رابط", callback_data="act_open_url"),
            InlineKeyboardButton("📸 لقطة شاشة", callback_data="act_screenshot"),
        ],
        # Row 2 — HD/full screenshots, useful when Telegram preview looks unclear
        [
            InlineKeyboardButton("📸 لقطة HD", callback_data="act_screenshot_hd"),
            InlineKeyboardButton("🖼️ صفحة كاملة", callback_data="act_screenshot_full"),
        ],
        # Row 3 — screen/zoom controls
        [
            InlineKeyboardButton("🧩 ضبط الشاشة", callback_data="act_fit_screen"),
            InlineKeyboardButton("🖥️ شاشة واسعة", callback_data="act_view_desktop"),
        ],
        [
            InlineKeyboardButton("💻 شاشة لابتوب", callback_data="act_view_laptop"),
            InlineKeyboardButton("🔍 تصغير", callback_data="act_zoom_out"),
            InlineKeyboardButton("🔎 تكبير", callback_data="act_zoom_in"),
        ],
        # Row 4 — back / refresh
        [
            InlineKeyboardButton("⬅️ رجوع", callback_data="act_back"),
            InlineKeyboardButton("🔄 تحديث", callback_data="act_reload"),
        ],
        # Row 3 — typing
        [
            InlineKeyboardButton("⌨️ كتابة نص", callback_data="act_type"),
            InlineKeyboardButton("❌ حذف النص", callback_data="act_clear"),
        ],
        # Row 4 — Enter + Grid
        [
            InlineKeyboardButton("↩️ Enter", callback_data="act_enter"),
            InlineKeyboardButton(f"🔢 شبكة الموس ({total_cells})",
                                 callback_data="act_grid_show"),
        ],
        # Row 5 — vertical scroll
        [
            InlineKeyboardButton("⬆️ صعود بسيط", callback_data="act_scroll_up"),
            InlineKeyboardButton("⬇️ نزول بسيط", callback_data="act_scroll_down"),
        ],
        # Row 6 — full vertical scroll
        [
            InlineKeyboardButton("⏫ صعود نهاية", callback_data="act_scroll_top"),
            InlineKeyboardButton("⏬ نزول نهاية", callback_data="act_scroll_bottom"),
        ],
        # Row 7 — horizontal movement for pages wider than the viewport
        [
            InlineKeyboardButton("⬅️ تحريك يسار", callback_data="act_scroll_left"),
            InlineKeyboardButton("➡️ تحريك يمين", callback_data="act_scroll_right"),
        ],
        # Row 8 — horizontal edges
        [
            InlineKeyboardButton("⇤ أقصى يسار", callback_data="act_scroll_left_end"),
            InlineKeyboardButton("أقصى يمين ⇥", callback_data="act_scroll_right_end"),
        ],
        # Row 9 — text search
        [
            InlineKeyboardButton("🔍 بحث + ضغط", callback_data="act_find_click"),
            InlineKeyboardButton("🔎 بحث + ضغط + مسح", callback_data="act_find_clear"),
        ],
        # Row 10 — code detect + status
        [
            InlineKeyboardButton("🛡️ كود التحقق", callback_data="act_detect_code"),
            InlineKeyboardButton("🧭 حالة الصفحة", callback_data="act_page_status"),
        ],
        # Row 11 — settings + time log
        [
            InlineKeyboardButton("⚙️ إعدادات الشبكة", callback_data="act_grid_settings"),
            InlineKeyboardButton("🕒 تسجيل الوقت", callback_data="act_log_time"),
        ],
        [
            InlineKeyboardButton("💾 حفظ وإنهاء الجلسة", callback_data="act_save_end"),
        ],
    ])


def back_to_panel(grid_rows: int = 20, grid_cols: int = 20) -> InlineKeyboardMarkup:
    """Used while waiting for free-text input — lets user cancel back to the panel."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✖️ إلغاء", callback_data="cancel_input")],
    ])


def grid_settings_menu() -> InlineKeyboardMarkup:
    """Quick presets for the mouse-grid resolution."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("10×10 (100)", callback_data="grid_set_10_10"),
            InlineKeyboardButton("15×15 (225)", callback_data="grid_set_15_15"),
        ],
        [
            InlineKeyboardButton("20×20 (400)", callback_data="grid_set_20_20"),
            InlineKeyboardButton("25×25 (625)", callback_data="grid_set_25_25"),
        ],
        [
            InlineKeyboardButton("30×30 (900)", callback_data="grid_set_30_30"),
            InlineKeyboardButton("40×40 (1600)", callback_data="grid_set_40_40"),
        ],
        [
            InlineKeyboardButton("44×45 (1980)", callback_data="grid_set_44_45"),
            InlineKeyboardButton("✏️ مخصص", callback_data="grid_set_custom"),
        ],
        [
            InlineKeyboardButton("⬅️ رجوع للوحة التحكم", callback_data="back_to_panel"),
        ],
    ])


def confirm_end_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ نعم، احفظ وأغلق", callback_data="end_confirm"),
            InlineKeyboardButton("✖️ تراجع", callback_data="back_to_panel"),
        ],
    ])
