from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS
import database as db
from keyboards import cancel_keyboard, main_menu_keyboard, appeal_admin_keyboard

WAIT_APPEAL_TEXT = 201

async def start_appeal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS

    unlocked_subs = await db.get_user_eligible_resubmissions(user_id)
    disapproved_subs = await db.get_user_disapproved_submissions(user_id)

    if not unlocked_subs and not disapproved_subs:
        await update.message.reply_text(
            "ℹ️ <b>No Eligible Submissions Found</b>\n\n"
            "You do not have any submissions currently eligible for appeal or resubmission.\n\n"
            "• <b>Appeals:</b> Only available if your submission was Disapproved.\n"
            "• <b>Resubmissions:</b> Only available after an admin clicks 'Can Resubmit' on their side and the 8-hour cooldown has elapsed.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(is_admin)
        )
        return ConversationHandler.END

    text = "⚖️ <b>Appeals & Resubmission Center</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []

    if unlocked_subs:
        text += "🔄 <b>Admin-Unlocked Emails (Resubmissions):</b>\n"
        for s in unlocked_subs:
            can_resub, reason, rem_h, rem_m = db.check_resubmit_eligibility(s)
            email_abbr = s["email"][:20]
            if can_resub:
                text += f"• <code>{s['email']}</code>: ✅ <b>Ready to Resubmit</b> (Admin unlocked & 8h passed)\n"
                buttons.append([
                    InlineKeyboardButton(f"🔄 Resubmit: {email_abbr}", callback_data=f"usr_start_resub:{s['id']}")
                ])
            else:
                text += f"• <code>{s['email']}</code>: ⏱️ <b>Cooldown Active</b> ({rem_h}h {rem_m}m remaining)\n"
                buttons.append([
                    InlineKeyboardButton(f"⏱️ Cooldown ({rem_h}h {rem_m}m): {email_abbr}", callback_data=f"usr_cooldown_alert:{s['id']}")
                ])
        text += "\n"

    if disapproved_subs:
        text += "❌ <b>Disapproved Submissions (Eligible for Appeal):</b>\n"
        for s in disapproved_subs:
            reason_str = s.get("admin_notes") or "Disapproved"
            email_abbr = s["email"][:20]
            text += f"• <code>{s['email']}</code> (ID: #{s['id']}): <i>{reason_str}</i>\n"
            buttons.append([
                InlineKeyboardButton(f"⚖️ Submit Appeal #{s['id']} ({email_abbr})", callback_data=f"usr_start_appeal:{s['id']}")
            ])
        text += "\n"

    text += "━━━━━━━━━━━━━━━━━━━\n<i>Select an account above to proceed:</i>"

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return ConversationHandler.END

async def appeal_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.split(":")[1])
    sub = await db.get_submission_by_id(sub_id)
    if not sub:
        await query.edit_message_text("⚠️ Submission not found.")
        return ConversationHandler.END

    context.user_data["appeal_sub_id"] = sub_id
    await query.edit_message_text(
        f"⚖️ <b>Submit Appeal for Submission #{sub_id}</b> (<code>{sub['email']}</code>)\n\n"
        f"Please explain why your submission should be reconsidered.\n"
        f"Include any clarifications or details that can help our admin team:\n\n"
        f"<i>(Type your appeal below or send ❌ Cancel to return)</i>",
        parse_mode=ParseMode.HTML
    )
    return WAIT_APPEAL_TEXT

async def cooldown_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sub_id = int(query.data.split(":")[1])
    sub = await db.get_submission_by_id(sub_id)
    if not sub:
        await query.answer("Submission not found.", show_alert=True)
        return

    can_resub, reason, rem_h, rem_m = db.check_resubmit_eligibility(sub)
    if not can_resub and reason == "COOLDOWN_ACTIVE":
        await query.answer(
            f"⏱️ 8-Hour Cooldown Active!\n\nAdmin unlocked this email, but you must wait 8 hours from approval.\nTime remaining: {rem_h}h {rem_m}m.",
            show_alert=True
        )
    elif can_resub:
        await query.answer("✅ 8-hour cooldown passed! You can resubmit now.", show_alert=True)
    else:
        await query.answer("Resubmission not eligible.", show_alert=True)

async def receive_appeal_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    is_admin = user.id in ADMIN_IDS

    from handlers.submission import check_menu_intercept
    intercept_state = await check_menu_intercept(update, context, text)
    if intercept_state is not None:
        return intercept_state

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
