"""/start, /help and the welcome screen."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot import config
from bot.utils.keyboards import main_menu

log = logging.getLogger(__name__)


WELCOME = (
    "👋 *أهلاً بك في بوت التحكم بالمتصفح*\n\n"
    "هذا البوت يُشغّل لك متصفّحاً سرّياً عن بُعد، وأنت تتحكّم به من تلجرام:\n"
    "• 🦊 *Camoufox* (Firefox مكافح للكشف) — كل ضغطة مفتاح تظهر `isTrusted: true`.\n"
    "• 🌍 ملف دولة كامل (وقت + لغة + GPS) — مع/بدون بروكسي.\n"
    "• ⌨️ *كتابة بشرية* فعلية: توقيت متغيّر، توقّفات تفكير، أخطاء وتصحيح اختياري.\n"
    "• 📸 لقطة شاشة لكل خطوة.\n"
    "• 🔢 شبكة موس مرقّمة (حتى 2000 مربع) للضغط بدقّة.\n"
    "• 🛡️ كشف أكواد التحقق + 🔍 بحث عن النصوص.\n"
    "• 💾 في النهاية تستلم *سكربت Python جاهز* يُعيد كل ما فعلته.\n\n"
    "👇 ابدأ من الزر:"
)

HOW_IT_WORKS = (
    "🛠️ *كيف يعمل البوت*\n\n"
    "1) (اختياري) اضغط *🌍 الدولة* لاختيار ملف دولة (وقت/لغة/GPS) "
    "وبروكسي إن وُجد.\n"
    "2) اضغط *🚀 بدء جلسة جديدة* فيشغّل لك متصفحاً نظيفاً.\n"
    "3) تظهر لوحة التحكم — كل زر يُنفّذ خطوة ويُرسل لك لقطة شاشة.\n"
    "4) لشبكة الموس: غيّر العدد من *إعدادات الشبكة* (حد أقصى 2000 مربع).\n"
    "   ثم اضغط *🔢 شبكة الموس* لرؤية اللقطة مرقّمة، وأرسل رقم المربع للضغط.\n"
    "5) للكتابة: اضغط أولاً مكان الإدخال (شبكة أو بحث)، ثم اختر "
    "*⌨️ كتابة نص* وأرسل النص — يُكتب بمحاكاة بشرية كاملة.\n"
    "6) عند الانتهاء، اضغط *💾 حفظ وإنهاء الجلسة* لتستلم:\n"
    "   • سكربت Python جاهز للتشغيل (يستخدم نفس المتصفح والدولة).\n"
    "   • تقرير Markdown يشرح ما تمّ.\n"
    "   • ملف JSON خام لإعادة الاستخدام برمجياً.\n"
)

HELP = (
    "📖 *الأوامر*\n\n"
    "/start — القائمة الرئيسية.\n"
    "/cancel — إلغاء أي إدخال نصي معلّق.\n"
    "/end — حفظ وإنهاء الجلسة الحالية فوراً.\n"
)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not config.is_authorized(user.id):
        await update.effective_message.reply_text(
            "🚫 غير مسموح لك باستخدام هذا البوت."
        )
        return
    label = ctx.user_data.get("proxy_label", "")
    # Lazy import to avoid a circular dependency at module load time.
    from bot.services.browser_manager import manager
    await update.effective_message.reply_markdown(
        WELCOME, reply_markup=main_menu(label, manager.engine),
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.is_authorized(update.effective_user.id):
        return
    await update.effective_message.reply_markdown(HELP)


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data.pop("awaiting", None)
    ctx.user_data.pop("await_meta", None)
    await update.effective_message.reply_text("✖️ تم الإلغاء.")
