import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS, SUPPORT_HANDLE, REQUIRED_CHANNEL, TUTORIAL_VIDEO_URL
import database as db
from keyboards import main_menu_keyboard, user_status_keyboard, cancel_keyboard

WAIT_SUPPORT_MSG = 101

async def format_user_overview(user_id: int) -> str:
    subs = await db.get_all_submissions_by_user(user_id)
    if not subs:
        return (
            "ℹ️ <b>No Submissions Found</b>\n\n"
            "You have not submitted any details yet.\n"
            "Tap <b>📝 Submit Information</b> below to get started!"
        )

    display_subs = subs[:12]
    note = f"<i>(Showing latest {len(display_subs)} submissions)</i>\n\n" if len(subs) > 12 else ""
    text = f"📊 <b>Your Submissions Overview ({len(subs)} Total):</b>\n━━━━━━━━━━━━━━━━━━━\n{note}"

    for i, s in enumerate(display_subs, 1):
        status = s["status"]
        if status == "PENDING":
            q_info = await db.get_queue_info(s["id"])
            status_str = f"⏳ Pending (Queue #{q_info['position']} | {q_info['ahead_count']} ahead)"
        elif status == "IN_REVIEW":
            status_str = "🔍 In Review"
        elif status == "ACCEPTED":
            status_str = "✅ Accepted (Payment soon)"
        elif status == "DISAPPROVED":
            status_str = "❌ Rejected / Disapproved"
        elif status == "CAN_RESUBMIT":
            status_str = "🔄 Can Resubmit"
        else:
            status_str = status

        pass_val = s.get("pass_code") or s.get("full_name") or "N/A"
        key_val = s.get("key_code") or s.get("unique_code") or "N/A"

        text += (
            f"<b>{i}.</b> 📧 <code>{s['email']}</code>\n"
            f"   • 🔒 <b>PASS:</b> <code>{pass_val}</code>\n"
            f"   • 🔑 <b>Key:</b> <code>{key_val}</code>\n"
            f"   • 📊 <b>Status:</b> <b>{status_str}</b>\n"
            f"   • 📅 <b>Date:</b> {s['created_at']}\n\n"
        )

    text += "━━━━━━━━━━━━━━━━━━━"
    return text

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS

    # Register user in database
    await db.register_user(user.id, user.username, user.first_name)

    channel_url = await db.get_channel_url()
    video_url = await db.get_video_url()

    welcome_text = (
        f"👋 <b>Welcome to Madcorn Bot!</b>\n\n"
        f"🎥 <b>Tutorial Video:</b> <a href=\"{video_url}\">Watch Here</a>\n\n"
        f"📢 <b>Please join our updates channel first:</b>\n"
        f"👉 <a href=\"{channel_url}\">Click to Join Channel</a>"
    )

    join_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=channel_url)],
        [InlineKeyboardButton("🎥 Tutorial Video", url=video_url)],
        [InlineKeyboardButton("✅ I Have Joined / Continue", callback_data="usr_continue_main")]
    ])

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=join_keyboard,
        disable_web_page_preview=True
    )
    return ConversationHandler.END

async def continue_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_admin = update.effective_user.id in ADMIN_IDS

    await query.message.reply_text(
        "✅ <b>Welcome to Madcorn Bot!</b>\nSelect an option below:",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(is_admin)
    )

async def check_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    overview_text = await format_user_overview(user_id)

    await update.message.reply_text(
        overview_text,
        parse_mode=ParseMode.HTML,
        reply_markup=user_status_keyboard()
    )
    return ConversationHandler.END

async def refresh_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Status refreshed!")
    user_id = update.effective_user.id
    overview_text = await format_user_overview(user_id)

    try:
        await query.edit_message_text(
            overview_text,
            parse_mode=ParseMode.HTML,
            reply_markup=user_status_keyboard()
        )
    except Exception:
        pass

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    support_handle = await db.get_support_handle()
    support_text = (
        f"💬 <b>Support</b>\n\n"
        f"Contact Admin: {support_handle}\n\n"
        f"Or type your question below (or send ❌ Cancel):"
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

    from handlers.submission import check_menu_intercept
    intercept_state = await check_menu_intercept(update, context, msg_text)
    if intercept_state is not None:
        return intercept_state

    await db.save_support_message(user.id, user.username, msg_text)

    alert = (
        f"📩 <b>Support Inquiry</b>\n"
        f"From: @{user.username or 'NoUsername'} (ID: <code>{user.id}</code>)\n\n"
        f"{msg_text}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=alert, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    await update.message.reply_text(
        "✅ Message sent to support!",
        reply_markup=main_menu_keyboard(is_admin)
    )
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_id = update.effective_user.id if update.effective_user else 0
    is_admin = user_id in ADMIN_IDS
    if update.callback_query:
        await update.callback_query.answer()
        await update.effective_message.reply_text("Action cancelled.", reply_markup=main_menu_keyboard(is_admin))
    elif update.message:
        await update.message.reply_text("Action cancelled.", reply_markup=main_menu_keyboard(is_admin))
    return ConversationHandler.END
