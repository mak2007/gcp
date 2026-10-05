from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS
import database as db
from keyboards import cancel_keyboard, main_menu_keyboard, appeal_admin_keyboard

WAIT_APPEAL_TEXT = 201

async def start_appeal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS

    sub = await db.get_submission_by_user(user_id)
    if not sub:
        await update.message.reply_text(
            "ℹ️ <b>No Submission Found</b>\n"
            "You do not have any submissions on record to appeal.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(is_admin)
        )
        return ConversationHandler.END

    if sub["status"] == "ACCEPTED":
        await update.message.reply_text(
            "✅ <b>Already Accepted</b>\n"
            "Your submission has already been accepted! Payment is queued.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(is_admin)
        )
        return ConversationHandler.END

    if sub["status"] in ["PENDING", "IN_REVIEW"]:
        await update.message.reply_text(
            f"⏳ <b>Submission Still Active</b>\n\n"
            f"Your submission is currently <b>{sub['status']}</b>.\n"
            f"Appeals are only applicable if your submission was disapproved.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(is_admin)
        )
        return ConversationHandler.END

    context.user_data["appeal_sub_id"] = sub["id"]
    await update.message.reply_text(
        f"⚖️ <b>Submit Appeal for Submission #{sub['id']}</b>\n\n"
        f"Please explain why your submission should be reconsidered.\n"
        f"Include any clarifications or details that can help our admin team:\n\n"
        f"<i>(Type your appeal or press ❌ Cancel to return)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )
    return WAIT_APPEAL_TEXT

async def receive_appeal_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    is_admin = user.id in ADMIN_IDS

    if text == "❌ Cancel":
        await update.message.reply_text("Appeal cancelled.", reply_markup=main_menu_keyboard(is_admin))
        return ConversationHandler.END

    if len(text) < 5:
        await update.message.reply_text(
            "⚠️ Please provide a more detailed explanation for your appeal:",
            reply_markup=cancel_keyboard()
        )
        return WAIT_APPEAL_TEXT

    sub_id = context.user_data.get("appeal_sub_id")
    appeal_id = await db.create_appeal(sub_id, user.id, text)
    sub = await db.get_submission_by_id(sub_id)

    # Notify admins
    admin_alert = (
        f"⚖️ <b>NEW APPEAL RECEIVED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Appeal ID:</b> #{appeal_id}\n"
        f"👤 <b>User:</b> @{user.username or 'NoUsername'} (ID: <code>{user.id}</code>)\n"
        f"📧 <b>Email:</b> <code>{sub['email']}</code>\n"
        f"🔒 <b>PASS:</b> <code>{sub.get('pass_code') or sub.get('full_name')}</code>\n"
        f"🔑 <b>Key:</b> <code>{sub.get('key_code') or sub.get('unique_code')}</code>\n"
        f"📅 <b>Original Submission Date:</b> {sub['created_at']}\n"
        f"💬 <b>User's Appeal Message:</b>\n"
        f"<i>{text}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_alert,
                parse_mode=ParseMode.HTML,
                reply_markup=appeal_admin_keyboard(appeal_id)
            )
        except Exception:
            pass

    context.user_data.clear()
    await update.message.reply_text(
        "✅ <b>Appeal Submitted Successfully!</b>\n\n"
        "Our administration team has received your appeal. "
        "You will be notified here as soon as a decision is made.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(is_admin)
    )
    return ConversationHandler.END
