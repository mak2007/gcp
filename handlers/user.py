import re
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS, SUPPORT_HANDLE
import database as db
from keyboards import main_menu_keyboard, user_status_keyboard, cancel_keyboard

WAIT_SUPPORT_MSG = 101

def format_status_text(submission: dict, queue_info: dict = None) -> str:
    status = submission["status"]
    status_emoji_map = {
        "PENDING": "⏳ Pending in Queue",
        "IN_REVIEW": "🔍 In Review",
        "ACCEPTED": "✅ Accepted",
        "DISAPPROVED": "❌ Disapproved",
        "CAN_RESUBMIT": "🔄 Can Be Resubmitted"
    }
    status_str = status_emoji_map.get(status, status)
    
    text = (
        f"📋 <b>Your Submission Details</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Submission ID:</b> #{submission['id']}\n"
        f"👤 <b>Name:</b> {submission['full_name']}\n"
        f"📧 <b>Email:</b> <code>{submission['email']}</code>\n"
        f"🔑 <b>Unique Code:</b> <code>{submission['unique_code']}</code>\n"
        f"📅 <b>Submitted Date:</b> {submission['created_at']}\n"
        f"📊 <b>Current Status:</b> <b>{status_str}</b>\n"
    )

    if submission.get("admin_notes"):
        text += f"📝 <b>Admin Note:</b> {submission['admin_notes']}\n"

    text += "━━━━━━━━━━━━━━━━━━━\n"

    if status == "PENDING":
        pos = queue_info["position"] if queue_info else "?"
        ahead = queue_info["ahead_count"] if queue_info else "?"
        total = queue_info["total_pending"] if queue_info else "?"
        text += (
            f"🔢 <b>Queue Information:</b>\n"
            f"• <b>Your Queue Position:</b> #{pos}\n"
            f"• <b>Submissions Ahead of You:</b> {ahead}\n"
            f"• <b>Total Pending Submissions:</b> {total}\n\n"
            f"<i>Your submission is waiting in line. Once an admin starts processing your submission, "
            f"you will receive a notification that your status changed to 'In Review'.</i>"
        )
    elif status == "IN_REVIEW":
        text += (
            "🔍 <b>Status Update:</b>\n"
            "An administrator is currently reviewing your submission details. "
            "Please wait for final approval."
        )
    elif status == "ACCEPTED":
        text += (
            "🎉 <b>Congratulations!</b>\n"
            "Your status changed to <b>Accepted</b>. Your payment will be made soon! 💳✨"
        )
    elif status == "DISAPPROVED":
        text += (
            "⚠️ <b>Submission Disapproved:</b>\n"
            "Your submission was rejected by the admin.\n"
            "If you believe this was in error, tap <b>⚖️ Submit Appeal</b> in the menu."
        )
    elif status == "CAN_RESUBMIT":
        text += (
            "⚠️ <b>Resubmission Allowed:</b>\n"
            "The admin has permitted you to resubmit or correct your details.\n"
            "Tap <b>📝 Submit Information</b> to enter your updated information."
        )

    return text

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS

    # Register user in database for announcements and records
    await db.register_user(user.id, user.username, user.first_name)

    welcome_text = (
        f"👋 Hello <b>{user.first_name}</b>, welcome to the Submission & Verification Bot!\n\n"
        f"Here you can submit your details, track your position in line in real-time, and get updates.\n\n"
        f"📌 <b>Available Options:</b>\n"
        f"• <b>📝 Submit Information:</b> Enter your Name, Email, and Unique Code.\n"
        f"• <b>📊 Check Status & Queue:</b> View your submission date, current status, and queue number.\n"
        f"• <b>⚖️ Submit Appeal:</b> Submit an appeal if your submission was disapproved.\n"
        f"• <b>💬 Support:</b> Contact administrative support for any inquiries."
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(is_admin)
    )

async def check_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sub = await db.get_submission_by_user(user_id)

    if not sub:
        await update.message.reply_text(
            "ℹ️ <b>No Submission Found</b>\n\n"
            "You have not submitted your details yet.\n"
            "Tap <b>📝 Submit Information</b> below to get started!",
            parse_mode=ParseMode.HTML
        )
        return

    queue_info = None
    if sub["status"] == "PENDING":
        queue_info = await db.get_queue_info(sub["id"])

    text = format_status_text(sub, queue_info)
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=user_status_keyboard()
    )

async def refresh_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Status refreshed!")
    user_id = update.effective_user.id
    sub = await db.get_submission_by_user(user_id)

    if not sub:
        await query.edit_message_text("No submission found.")
        return

    queue_info = None
    if sub["status"] == "PENDING":
        queue_info = await db.get_queue_info(sub["id"])

    text = format_status_text(sub, queue_info)
    try:
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=user_status_keyboard()
        )
    except Exception:
        # Message content identical
        pass

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    support_text = (
        f"💬 <b>Support & Assistance</b>\n\n"
        f"If you have any questions or encounter issues, we're here to help:\n\n"
        f"• <b>Direct Admin Contact:</b> {SUPPORT_HANDLE}\n\n"
        f"You can also send a direct message to our support staff right now. "
        f"Type your message below or press <b>❌ Cancel</b> to return."
    )
    await update.message.reply_text(
        support_text,
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )
    return WAIT_SUPPORT_MSG

async def receive_support_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg_text = update.message.text.strip()
    is_admin = user.id in ADMIN_IDS

    if msg_text == "❌ Cancel":
        await update.message.reply_text("Support inquiry cancelled.", reply_markup=main_menu_keyboard(is_admin))
        return ConversationHandler.END

    await db.save_support_message(user.id, user.username, msg_text)

    # Forward support request to all admins
    alert = (
        f"📩 <b>New Support Message</b>\n"
        f"From: <b>{user.full_name}</b> (@{user.username or 'NoUsername'} | ID: <code>{user.id}</code>)\n\n"
        f"<b>Message:</b>\n{msg_text}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=alert, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    await update.message.reply_text(
        "✅ <b>Your message has been forwarded to support!</b>\nAn admin will review it shortly.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(is_admin)
    )
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id in ADMIN_IDS
    await update.message.reply_text("Action cancelled.", reply_markup=main_menu_keyboard(is_admin))
    return ConversationHandler.END
