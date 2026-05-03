"""Admin approval helpers for new Telegram users."""
from __future__ import annotations

import logging
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot import config

log = logging.getLogger(__name__)


def _user_label(user) -> str:
    name = " ".join(x for x in [user.first_name, user.last_name] if x) or "بدون اسم"
    username = f"@{user.username}" if user.username else "لا يوجد يوزر"
    return f"{escape(name)} | {escape(username)} | ID: <code>{user.id}</code>"


def admin_decision_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ موافقة دائمة", callback_data=f"access_approve_{user_id}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"access_reject_{user_id}"),
        ]
    ])


async def request_access(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Tell the user access is pending and notify all configured admins."""
    user = update.effective_user
    if not user:
        return

    if not config.approval_required():
        await update.effective_message.reply_text("🚫 غير مسموح لك باستخدام هذا البوت.")
        return

    pending = ctx.application.bot_data.setdefault("pending_access_requests", set())
    first_time_this_run = user.id not in pending
    pending.add(user.id)

    await update.effective_message.reply_text(
        "🔐 تم إرسال طلبك للإدمن.\n"
        "بعد الموافقة تگدر تستخدم البوت دائماً بدون طلب جديد."
    )

    if not first_time_this_run:
        return

    body = (
        "🔐 <b>طلب وصول جديد للبوت</b>\n\n"
        f"المستخدم: {_user_label(user)}\n\n"
        "اضغط موافقة حتى ينضاف للقائمة المسموحة دائماً."
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await ctx.bot.send_message(
                chat_id=admin_id,
                text=body,
                parse_mode="HTML",
                reply_markup=admin_decision_keyboard(user.id),
            )
        except Exception as exc:
            log.warning("failed to notify admin %s about access request: %s", admin_id, exc)
