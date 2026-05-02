"""All control-panel button handlers + free-text awaiting-input dispatcher."""
from __future__ import annotations

import logging
import os
from typing import Optional

from telegram import InputFile, Update
from telegram.ext import ContextTypes

from bot import config
from bot.services.browser_manager import manager
from bot.services.browser_session import BrowserSession
from bot.utils.keyboards import (
    back_to_panel, confirm_end_menu, control_panel,
    grid_settings_menu, main_menu,
)

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════
async def _send_screenshot(
    update: Update,
    sess: BrowserSession,
    path: Optional[str],
    caption: str,
) -> None:
    """Send a screenshot to the user, with a fallback message if missing."""
    panel = control_panel(sess.grid_rows, sess.grid_cols)
    chat_id = update.effective_chat.id
    bot = update.get_bot()
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as f:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=InputFile(f, filename=os.path.basename(path)),
                    caption=caption,
                    reply_markup=panel,
                )
            return
        except Exception as exc:
            log.warning("send_photo failed: %s", exc)
    await bot.send_message(
        chat_id=chat_id,
        text=caption,
        reply_markup=panel,
    )


async def _ensure_session(update: Update) -> Optional[BrowserSession]:
    user = update.effective_user
    sess = manager.get(user.id)
    if sess is None:
        await update.effective_message.reply_text(
            "⚠️ لا توجد جلسة نشطة. اضغط /start ثم *🚀 بدء جلسة جديدة*.",
        )
    return sess


def _set_awaiting(ctx: ContextTypes.DEFAULT_TYPE,
                  kind: str, **meta) -> None:
    ctx.user_data["awaiting"] = kind
    ctx.user_data["await_meta"] = meta


def _clear_awaiting(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data.pop("awaiting", None)
    ctx.user_data.pop("await_meta", None)


# ════════════════════════════════════════════════════════════════════
# Session lifecycle
# ════════════════════════════════════════════════════════════════════
async def session_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not config.is_authorized(user.id):
        await update.effective_message.reply_text("🚫 غير مسموح.")
        return
    # Close any leftover session.
    await manager.end_session(user.id)
    sess = await manager.get_or_create(user.id)
    await update.effective_message.reply_text(
        "✅ *تم تشغيل المتصفح.*\n"
        "اضغط *🌐 افتح رابط* للبدء، ثم استخدم لوحة التحكم.",
        parse_mode="Markdown",
        reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
    )


async def session_end_confirm(update: Update,
                              ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    await update.callback_query.message.reply_text(
        f"⚠️ هل تريد *حفظ وإنهاء الجلسة*؟\n"
        f"عدد الإجراءات المسجَّلة: {len(sess.recorder.actions)}",
        parse_mode="Markdown",
        reply_markup=confirm_end_menu(),
    )


async def session_end_now(update: Update,
                          ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    sess = manager.get(user.id)
    if sess is None:
        await update.effective_message.reply_text(
            "لا توجد جلسة لإنهائها.",
            reply_markup=main_menu(),
        )
        return
    msg_target = update.effective_message
    await msg_target.reply_text("💾 جاري إنهاء الجلسة وكتابة الملفات…")
    artifacts = await manager.end_session(user.id)
    if not artifacts:
        await msg_target.reply_text(
            "❌ تعذّر حفظ الملفات.",
            reply_markup=main_menu(),
        )
        return
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    for label, path in artifacts.items():
        if not (path and os.path.exists(path)):
            continue
        try:
            with open(path, "rb") as f:
                await bot.send_document(
                    chat_id=chat_id,
                    document=InputFile(f, filename=os.path.basename(path)),
                    caption=f"📄 {label}",
                )
        except Exception as exc:
            log.warning("send_document(%s) failed: %s", label, exc)
    await bot.send_message(
        chat_id=chat_id,
        text="✅ انتهت الجلسة. اضغط /start لبدء جلسة جديدة.",
        reply_markup=main_menu(),
    )


# ════════════════════════════════════════════════════════════════════
# Action handlers
# ════════════════════════════════════════════════════════════════════
async def act_screenshot(update: Update,
                         ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    p = await sess.screenshot()
    url = await sess.current_url()
    await _send_screenshot(update, sess, p, f"📸 لقطة شاشة\n🔗 {url or '—'}")


async def act_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    p = await sess.back()
    await _send_screenshot(update, sess, p, "⬅️ تم الرجوع")


async def act_reload(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    p = await sess.reload()
    await _send_screenshot(update, sess, p, "🔄 تم التحديث")


async def act_enter(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    p = await sess.press_enter()
    await _send_screenshot(update, sess, p, "↩️ Enter")


async def act_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    p = await sess.clear_text()
    await _send_screenshot(update, sess, p, "❌ تم مسح النص")


async def act_scroll_up(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    p = await sess.scroll("up")
    await _send_screenshot(update, sess, p, "⬆️ تمرير لأعلى")


async def act_scroll_down(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    p = await sess.scroll("down")
    await _send_screenshot(update, sess, p, "⬇️ تمرير لأسفل")


async def act_scroll_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    p = await sess.scroll("top")
    await _send_screenshot(update, sess, p, "⏫ بداية الصفحة")


async def act_scroll_bottom(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    p = await sess.scroll("bottom")
    await _send_screenshot(update, sess, p, "⏬ نهاية الصفحة")


async def act_grid_show(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    msg = update.effective_message
    await msg.reply_text(
        "🔢 جاري إنشاء شبكة الموس… أرسل رقم المربع بعد ظهور اللقطة."
    )
    p = await sess.grid_screenshot()
    _set_awaiting(ctx, "grid_click")
    total = sess.grid_total
    caption = (
        f"🔢 *شبكة الموس* — {sess.grid_rows}×{sess.grid_cols} = *{total}* مربع\n"
        f"أرسل الآن رقم المربع (1..{total}) للضغط في مركزه."
    )
    await _send_screenshot(update, sess, p, caption)


async def act_grid_settings(update: Update,
                            ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    await update.effective_message.reply_markdown(
        f"⚙️ *إعدادات شبكة الموس*\n\n"
        f"الإعداد الحالي: `{sess.grid_rows}×{sess.grid_cols}` "
        f"= *{sess.grid_total}* مربع.\n"
        f"الحد الأقصى: *{config.MAX_GRID_CELLS}* مربع.\n\n"
        f"اختر إعداداً جاهزاً، أو *مخصص* لإدخال أبعاد يدوية.",
        reply_markup=grid_settings_menu(),
    )


async def act_open_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    _set_awaiting(ctx, "url")
    await update.effective_message.reply_text(
        "🌐 أرسل الرابط الذي تريد فتحه (مثال: https://google.com).",
        reply_markup=back_to_panel(),
    )


async def act_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    _set_awaiting(ctx, "type_text")
    await update.effective_message.reply_text(
        "⌨️ أرسل النص الذي تريد كتابته في الحقل المُركَّز.\n"
        "تلميح: اضغط أولاً على الحقل عبر شبكة الموس أو البحث.",
        reply_markup=back_to_panel(),
    )


async def act_find_click(update: Update,
                         ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    _set_awaiting(ctx, "find_click")
    await update.effective_message.reply_text(
        "🔍 أرسل النص الذي تريد البحث عنه والضغط عليه.",
        reply_markup=back_to_panel(),
    )


async def act_find_clear(update: Update,
                         ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    _set_awaiting(ctx, "find_clear")
    await update.effective_message.reply_text(
        "🔎 أرسل النص الذي تريد البحث عنه، الضغط عليه، ثم مسحه.",
        reply_markup=back_to_panel(),
    )


async def act_detect_code(update: Update,
                          ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    codes = await sess.detect_codes()
    if codes:
        body = "🛡️ *أكواد محتملة على الصفحة:*\n" + "\n".join(
            f"• `{c}`" for c in codes
        )
    else:
        body = "🛡️ لم أعثر على أيّ كود تحقق على الصفحة الحالية."
    await update.effective_message.reply_markdown(
        body, reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
    )


async def act_log_time(update: Update,
                       ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    ts = sess.log_time(note="manual")
    await update.effective_message.reply_text(
        f"🕒 تم تسجيل الوقت: `{ts}`",
        parse_mode="Markdown",
        reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
    )


# ════════════════════════════════════════════════════════════════════
# Grid preset buttons
# ════════════════════════════════════════════════════════════════════
async def act_grid_preset(update: Update,
                          ctx: ContextTypes.DEFAULT_TYPE,
                          rows: int, cols: int) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    try:
        sess.set_grid(rows, cols)
    except ValueError as exc:
        await update.effective_message.reply_text(f"⚠️ {exc}")
        return
    await update.effective_message.reply_text(
        f"✅ تم ضبط الشبكة إلى *{rows}×{cols}* = {rows * cols} مربع.",
        parse_mode="Markdown",
        reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
    )


async def act_grid_custom(update: Update,
                          ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sess = await _ensure_session(update)
    if not sess:
        return
    _set_awaiting(ctx, "grid_custom")
    await update.effective_message.reply_text(
        f"✏️ أرسل أبعاد الشبكة بصيغة `الصفوف x الأعمدة` "
        f"(مثال: `30x40`).\nالحد الأقصى: {config.MAX_GRID_CELLS} مربع.",
        parse_mode="Markdown",
        reply_markup=back_to_panel(),
    )


# ════════════════════════════════════════════════════════════════════
# Free-text dispatcher (fed by main.py text handler)
# ════════════════════════════════════════════════════════════════════
async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.is_authorized(update.effective_user.id):
        return
    awaiting = ctx.user_data.get("awaiting")
    if not awaiting:
        # No pending input — give a friendly hint.
        await update.effective_message.reply_text(
            "ℹ️ استخدم /start ثم اضغط على أزرار لوحة التحكم.",
        )
        return

    text = (update.effective_message.text or "").strip()
    sess = await _ensure_session(update)
    if not sess:
        _clear_awaiting(ctx)
        return

    try:
        if awaiting == "url":
            url = text
            if not (url.startswith("http://") or url.startswith("https://")):
                url = "https://" + url
            _clear_awaiting(ctx)
            p = await sess.open_url(url)
            await _send_screenshot(update, sess, p, f"🌐 فُتح: {url}")

        elif awaiting == "type_text":
            _clear_awaiting(ctx)
            p = await sess.type_text(text)
            preview = text if len(text) <= 80 else text[:77] + "…"
            await _send_screenshot(update, sess, p, f"⌨️ تمت الكتابة: `{preview}`")

        elif awaiting == "find_click":
            _clear_awaiting(ctx)
            try:
                p = await sess.find_click(text)
                await _send_screenshot(
                    update, sess, p, f"🔍 ضُغط على: «{text}»"
                )
            except RuntimeError as exc:
                await update.effective_message.reply_text(
                    f"⚠️ {exc}",
                    reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
                )

        elif awaiting == "find_clear":
            _clear_awaiting(ctx)
            try:
                p = await sess.find_click_clear(text)
                await _send_screenshot(
                    update, sess, p,
                    f"🔎 ضُغط ومُسح: «{text}»",
                )
            except RuntimeError as exc:
                await update.effective_message.reply_text(
                    f"⚠️ {exc}",
                    reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
                )

        elif awaiting == "grid_click":
            _clear_awaiting(ctx)
            if not text.isdigit():
                await update.effective_message.reply_text(
                    "⚠️ أرسل رقماً صحيحاً يمثّل المربع.",
                    reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
                )
                return
            n = int(text)
            try:
                p = await sess.click_cell(n)
                await _send_screenshot(
                    update, sess, p,
                    f"🔢 تم الضغط على المربع #{n}",
                )
            except ValueError as exc:
                await update.effective_message.reply_text(
                    f"⚠️ {exc}",
                    reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
                )

        elif awaiting == "grid_custom":
            _clear_awaiting(ctx)
            cleaned = text.lower().replace("×", "x").replace(" ", "")
            parts = cleaned.split("x")
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                await update.effective_message.reply_text(
                    "⚠️ صيغة غير صحيحة. استخدم: `30x40`.",
                    parse_mode="Markdown",
                )
                return
            r, c = int(parts[0]), int(parts[1])
            try:
                sess.set_grid(r, c)
                await update.effective_message.reply_text(
                    f"✅ تم ضبط الشبكة إلى {r}×{c} = {r * c} مربع.",
                    reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
                )
            except ValueError as exc:
                await update.effective_message.reply_text(
                    f"⚠️ {exc}",
                    reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
                )

        else:
            _clear_awaiting(ctx)
            await update.effective_message.reply_text(
                "ℹ️ تم تجاهل النص — لا يوجد إدخال معلَّق.",
                reply_markup=control_panel(sess.grid_rows, sess.grid_cols),
            )

    except Exception as exc:
        log.exception("on_text failed: %s", exc)
        _clear_awaiting(ctx)
        await update.effective_message.reply_text(
            f"❌ خطأ غير متوقع: {exc}",
        )
