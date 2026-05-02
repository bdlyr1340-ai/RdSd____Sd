"""Inline keyboards for the browser-control bot."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    """Main menu shown on /start."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 بدء جلسة جديدة", callback_data="session_start")],
        [InlineKeyboardButton("ℹ️ كيف يعمل البوت", callback_data="how_it_works")],
        [InlineKeyboardButton("📖 المساعدة", callback_data="help")],
    ])


def control_panel(grid_rows: int, grid_cols: int) -> InlineKeyboardMarkup:
    """The main control panel shown during an active browser session."""
    total_cells = grid_rows * grid_cols
    return InlineKeyboardMarkup([
        # Row 1 — open URL + screenshot
        [
            InlineKeyboardButton("🌐 افتح رابط", callback_data="act_open_url"),
            InlineKeyboardButton("📸 لقطة شاشة", callback_data="act_screenshot"),
        ],
        # Row 2 — back / refresh
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
        # Row 5 — small scroll
        [
            InlineKeyboardButton("⬆️ صعود بسيط", callback_data="act_scroll_up"),
            InlineKeyboardButton("⬇️ نزول بسيط", callback_data="act_scroll_down"),
        ],
        # Row 6 — full scroll
        [
            InlineKeyboardButton("⏫ صعود نهاية", callback_data="act_scroll_top"),
            InlineKeyboardButton("⏬ نزول نهاية", callback_data="act_scroll_bottom"),
        ],
        # Row 7 — text search
        [
            InlineKeyboardButton("🔍 بحث + ضغط", callback_data="act_find_click"),
            InlineKeyboardButton("🔎 بحث + ضغط + مسح", callback_data="act_find_clear"),
        ],
        # Row 8 — code detect + time log
        [
            InlineKeyboardButton("🛡️ كود التحقق", callback_data="act_detect_code"),
            InlineKeyboardButton("🕒 تسجيل الوقت", callback_data="act_log_time"),
        ],
        # Row 9 — settings + save
        [
            InlineKeyboardButton("⚙️ إعدادات الشبكة", callback_data="act_grid_settings"),
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
