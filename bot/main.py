"""Telegram bot entry point — long polling."""
from __future__ import annotations

import logging
import re
import traceback

from telegram import Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

from bot import config
from bot.handlers import actions as h_actions
from bot.handlers import start as h_start
from bot.services.browser_manager import manager
from bot.utils.keyboards import main_menu

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.INFO)


# ════════════════════════════════════════════════════════════════════
# Lifecycle
# ════════════════════════════════════════════════════════════════════
async def _post_init(app: Application) -> None:
    await manager.start()
    await app.bot.delete_webhook(drop_pending_updates=True)
    me = await app.bot.get_me()
    log.info("Bot connected: @%s", me.username)


async def _post_shutdown(app: Application) -> None:
    await manager.stop()


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Unhandled error: %s", ctx.error)
    log.error("%s", "".join(
        traceback.format_exception(None, ctx.error, ctx.error.__traceback__)
    ))
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "حدث خطأ مؤقت — جرّب /start مرة ثانية.",
            )
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
# Callback router
# ════════════════════════════════════════════════════════════════════
GRID_PRESET_RE = re.compile(r"^grid_set_(\d+)_(\d+)$")
PROXY_PICK_RE = re.compile(r"^proxy_pick_([A-Z]{2})$")


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    await q.answer()
    data = q.data or ""

    # ── menu navigation ─────────────────────────────────────────
    if data == "session_start":
        await h_actions.session_start(update, ctx); return
    if data == "how_it_works":
        await q.message.reply_markdown(h_start.HOW_IT_WORKS); return
    if data == "help":
        await q.message.reply_markdown(h_start.HELP); return
    if data == "engine_info":
        await h_actions.engine_info(update, ctx); return
    if data == "back_to_main":
        await q.message.reply_text(
            "القائمة الرئيسية:",
            reply_markup=main_menu(
                ctx.user_data.get("proxy_label", ""), manager.engine,
            ),
        )
        ctx.user_data.pop("awaiting", None)
        ctx.user_data.pop("await_meta", None)
        return
    if data == "back_to_panel":
        sess = manager.get(update.effective_user.id)
        if sess:
            from bot.utils.keyboards import control_panel
            await q.message.reply_text(
                "↩️ لوحة التحكم:",
                reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
            )
        else:
            await q.message.reply_text(
                "القائمة الرئيسية:",
                reply_markup=main_menu(
                    ctx.user_data.get("proxy_label", ""), manager.engine,
                ),
            )
        ctx.user_data.pop("awaiting", None)
        ctx.user_data.pop("await_meta", None)
        return
    if data == "cancel_input":
        ctx.user_data.pop("awaiting", None)
        ctx.user_data.pop("await_meta", None)
        sess = manager.get(update.effective_user.id)
        if sess:
            from bot.utils.keyboards import control_panel
            await q.message.reply_text(
                "✖️ ألغيت الإدخال.",
                reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
            )
        else:
            await q.message.reply_text(
                "✖️ ألغيت الإدخال.",
                reply_markup=main_menu(
                    ctx.user_data.get("proxy_label", ""), manager.engine,
                ),
            )
        return

    # ── proxy menu ──────────────────────────────────────────────
    if data == "proxy_menu":
        await h_actions.proxy_show_menu(update, ctx); return
    if data == "proxy_direct":
        await h_actions.proxy_set_direct(update, ctx); return
    if data == "proxy_custom":
        await h_actions.proxy_custom_input(update, ctx); return
    m_proxy = PROXY_PICK_RE.match(data)
    if m_proxy:
        await h_actions.proxy_pick_preset(update, ctx, m_proxy.group(1))
        return

    # ── action buttons ──────────────────────────────────────────
    table = {
        "act_open_url":      h_actions.act_open_url,
        "act_screenshot":    h_actions.act_screenshot,
        "act_back":          h_actions.act_back,
        "act_reload":        h_actions.act_reload,
        "act_enter":         h_actions.act_enter,
        "act_type":          h_actions.act_type,
        "act_clear":         h_actions.act_clear,
        "act_scroll_up":     h_actions.act_scroll_up,
        "act_scroll_down":   h_actions.act_scroll_down,
        "act_scroll_top":    h_actions.act_scroll_top,
        "act_scroll_bottom": h_actions.act_scroll_bottom,
        "act_grid_show":     h_actions.act_grid_show,
        "act_grid_settings": h_actions.act_grid_settings,
        "act_find_click":    h_actions.act_find_click,
        "act_find_clear":    h_actions.act_find_clear,
        "act_detect_code":   h_actions.act_detect_code,
        "act_log_time":      h_actions.act_log_time,
        "act_save_end":      h_actions.session_end_confirm,
        "end_confirm":       h_actions.session_end_now,
        "grid_set_custom":   h_actions.act_grid_custom,
    }
    if data in table:
        await table[data](update, ctx); return

    m = GRID_PRESET_RE.match(data)
    if m:
        rows, cols = int(m.group(1)), int(m.group(2))
        await h_actions.act_grid_preset(update, ctx, rows, cols); return

    # Fallback
    await q.message.reply_text("لم أفهم هذا الأمر.")


# ════════════════════════════════════════════════════════════════════
# Build & run
# ════════════════════════════════════════════════════════════════════
def build_app() -> Application:
    config.validate()
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .concurrent_updates(True)
        .build()
    )

    app.add_handler(CommandHandler("start",  h_start.cmd_start))
    app.add_handler(CommandHandler("help",   h_start.cmd_help))
    app.add_handler(CommandHandler("cancel", h_start.cmd_cancel))
    app.add_handler(CommandHandler("end",    h_actions.session_end_now))

    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                   h_actions.on_text))

    app.add_error_handler(on_error)
    return app


def main() -> None:
    _setup_logging()
    app = build_app()
    log.info("Starting polling…")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
