import io
import csv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS, SUPPORT_HANDLE
import database as db
from keyboards import admin_submission_actions_keyboard, admin_dashboard_keyboard, admin_settings_keyboard, main_menu_keyboard

WAIT_ADMIN_SEARCH = 301
WAIT_ADMIN_SETTING_VALUE = 304

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def format_admin_submission_card(sub: dict, queue_info: dict = None) -> str:
    status_emoji_map = {
        "PENDING": "⏳ PENDING",
        "IN_REVIEW": "🔍 IN REVIEW",
        "ACCEPTED": "✅ ACCEPTED",
        "DISAPPROVED": "❌ DISAPPROVED",
        "CAN_RESUBMIT": "🔄 CAN RESUBMIT"
    }
    status_str = status_emoji_map.get(sub["status"], sub["status"])
    pass_val = sub.get("pass_code") or sub.get("full_name") or "N/A"
    key_val = sub.get("key_code") or sub.get("unique_code") or "N/A"
    text = (
        f"📋 <b>Recyclable Submission #{sub['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>Telegram:</b> @{sub.get('username') or 'None'} (ID: <code>{sub['user_id']}</code>)\n"
        f"📧 <b>Email:</b> <code>{sub['email']}</code>\n"
        f"🔒 <b>PASS:</b> <code>{pass_val}</code>\n"
        f"🔑 <b>Key:</b> <code>{key_val}</code>\n"
        f"📅 <b>Submitted Date:</b> {sub['created_at']}\n"
        f"📊 <b>Status:</b> <b>{status_str}</b>\n"
    )
    if sub.get("is_resubmission"):
        text += f"🔄 <b>Resubmitted At:</b> {sub.get('resubmitted_at') or sub.get('updated_at')}\n"

    if sub.get("admin_notes"):
        text += f"📝 <b>Admin Notes:</b> {sub['admin_notes']}\n"

    if sub["status"] == "PENDING" and queue_info:
        text += (
            f"🔢 <b>Queue Pos:</b> #{queue_info['position']} "
            f"({queue_info['ahead_count']} ahead | {queue_info['total_pending']} total)\n"
        )
    text += "━━━━━━━━━━━━━━━━━━━"
    return text

async def admin_dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        if update.callback_query:
            await update.callback_query.answer("⛔ Access Denied.")
        else:
            await update.message.reply_text("⛔ Access Denied. Admin only.")
        return

    stats = await db.get_admin_stats()
    text = (
        f"⚙️ <b>Admin Control Dashboard</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>INVENTORY & STOCK OVERVIEW:</b>\n"
        f"• 🆕 <b>New Accounts:</b> {stats['new_total']} (⏳ {stats['new_pending']} pending)\n"
        f"• 🔄 <b>Resubmitted Accounts:</b> {stats['resubmitted_total']} (⏳ {stats['resubmitted_pending']} pending)\n"
        f"• 📦 <b>Total Accounts in Pool:</b> {stats['total']}\n\n"
        f"📊 <b>STATUS BREAKDOWN:</b>\n"
        f"• ⏳ <b>Pending Queue:</b> {stats['pending']}\n"
        f"• 🔍 <b>In Review:</b> {stats['in_review']}\n"
        f"• ✅ <b>Accepted (Paid):</b> {stats['accepted']}\n"
        f"• ❌ <b>Disapproved:</b> {stats['disapproved']}\n"
        f"• 🔓 <b>Unlocked for Resubmit:</b> {stats['can_resubmit']}\n"
        f"• ⚖️ <b>Pending Appeals:</b> {stats['appeals_pending']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Select an action below:"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=admin_dashboard_keyboard()
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=admin_dashboard_keyboard()
        )
    return ConversationHandler.END

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    stats = await db.get_admin_stats()
    text = (
        f"⚙️ <b>Investor & Stock Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>INVENTORY:</b>\n"
        f"• 🆕 <b>New Accounts:</b> {stats['new_total']} (⏳ {stats['new_pending']} pending)\n"
        f"• 🔄 <b>Resubmitted Accounts:</b> {stats['resubmitted_total']} (⏳ {stats['resubmitted_pending']} pending)\n"
        f"• 📦 <b>Total Database Accounts:</b> {stats['total']}\n\n"
        f"📊 <b>STATUS COUNTS:</b>\n"
        f"• ⏳ <b>Pending in Queue:</b> {stats['pending']}\n"
        f"• 🔍 <b>In Review:</b> {stats['in_review']}\n"
        f"• ✅ <b>Accepted:</b> {stats['accepted']}\n"
        f"• ❌ <b>Disapproved:</b> {stats['disapproved']}\n"
        f"• 🔓 <b>Unlocked for Resubmit:</b> {stats['can_resubmit']}\n"
        f"• ⚖️ <b>Pending Appeals:</b> {stats['appeals_pending']}\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=admin_dashboard_keyboard()
    )

async def admin_list_submissions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    # Callback format: adm_list:<STATUS>:<OFFSET>
    parts = query.data.split(":")
    status = parts[1]
    offset = int(parts[2])
    limit = 5

    items = await db.get_submissions_by_status(status, limit=limit, offset=offset)

    status_titles = {
        "PENDING": "⏳ Pending Queue",
        "IN_REVIEW": "🔍 In Review",
        "ACCEPTED": "✅ Approved Submissions",
        "DISAPPROVED": "❌ Disapproved Submissions",
        "CAN_RESUBMIT": "🔄 Can Resubmit"
    }
    title = status_titles.get(status, status)

    if not items:
        await query.edit_message_text(
            f"ℹ️ No submissions found under <b>{title}</b> (page {offset // limit + 1}).",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")
            ]])
        )
        return

    text = f"📋 <b>Submissions: {title}</b> (Page {offset // limit + 1})\n━━━━━━━━━━━━━━━━━━━\n"
    keyboard_buttons = []

    for item in items:
        note_str = f" | Note: <i>{item['admin_notes']}</i>" if item.get('admin_notes') else ""
        text += (
            f"• <b>#{item['id']}</b> | <code>{item['email']}</code>\n"
            f"  PASS: <code>{item.get('pass_code') or item.get('full_name')}</code> | Key: <code>{item.get('key_code') or item.get('unique_code')}</code>\n"
            f"  📅 {item['created_at']}{note_str}\n\n"
        )
        keyboard_buttons.append([
            InlineKeyboardButton(f"👉 Manage #{item['id']} ({item['email'][:16]})", callback_data=f"adm_view:{item['id']}")
        ])

    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"adm_list:{status}:{max(0, offset - limit)}"))
    if len(items) == limit:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"adm_list:{status}:{offset + limit}"))
    if nav_row:
        keyboard_buttons.append(nav_row)

    keyboard_buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")])

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard_buttons)
    )

async def admin_list_resubmitted_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    # Callback format: adm_resub_list:<OFFSET>
    parts = query.data.split(":")
    offset = int(parts[1]) if len(parts) > 1 else 0
    limit = 5

    items = await db.get_resubmitted_submissions(limit=limit, offset=offset)
    total_count = await db.get_resubmitted_count()

    if not items:
        await query.edit_message_text(
            "ℹ️ <b>No Resubmitted Emails Found</b>\n"
            "There are currently no resubmitted entries in the database.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")
            ]])
        )
        return

    text = f"🔄 <b>Resubmitted Emails List</b> (Page {offset // limit + 1} | Total: {total_count})\n━━━━━━━━━━━━━━━━━━━\n"
    keyboard_buttons = []

    for item in items:
        status_emoji_map = {
            "PENDING": "⏳ PENDING",
            "IN_REVIEW": "🔍 IN REVIEW",
            "ACCEPTED": "✅ ACCEPTED",
            "DISAPPROVED": "❌ DISAPPROVED",
            "CAN_RESUBMIT": "🔄 CAN RESUBMIT"
        }
        st_text = status_emoji_map.get(item["status"], item["status"])
        resub_date = item.get("resubmitted_at") or item.get("updated_at")
        text += (
            f"• <b>#{item['id']}</b> | <code>{item['email']}</code>\n"
            f"  🔒 PASS: <code>{item.get('pass_code') or item.get('full_name')}</code>\n"
            f"  🔑 Key: <code>{item.get('key_code') or item.get('unique_code')}</code>\n"
            f"  📊 Status: <b>{st_text}</b>\n"
            f"  🔄 Resubmitted: {resub_date}\n"
            f"  📅 Original: {item['created_at']}\n\n"
        )
        keyboard_buttons.append([
            InlineKeyboardButton(f"👉 Manage #{item['id']} ({item['email'][:16]})", callback_data=f"adm_view:{item['id']}")
        ])

    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"adm_resub_list:{max(0, offset - limit)}"))
    if offset + limit < total_count:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"adm_resub_list:{offset + limit}"))
    if nav_row:
        keyboard_buttons.append(nav_row)

    keyboard_buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")])

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard_buttons)
    )

async def admin_view_submission_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    sub_id = int(query.data.split(":")[1])
    sub = await db.get_submission_by_id(sub_id)
    if not sub:
        await query.edit_message_text("⚠️ Submission not found.")
        return

    q_info = await db.get_queue_info(sub_id) if sub["status"] == "PENDING" else None
    card_text = format_admin_submission_card(sub, q_info)
    kb = admin_submission_actions_keyboard(sub_id, sub["status"])

    await query.edit_message_text(card_text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def admin_change_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    # Callback format: adm_st:<SUB_ID>:<NEW_STATUS>
    parts = query.data.split(":")
    sub_id = int(parts[1])
    new_status = parts[2]

    sub = await db.get_submission_by_id(sub_id)
    if not sub:
        await query.edit_message_text("⚠️ Submission not found.")
        return

    updated_sub = await db.update_submission_status(sub_id, new_status)
    user_id = sub["user_id"]

    if new_status == "PENDING":
        updated_sub = await db.update_submission_status(sub_id, "PENDING", admin_notes=None)
        user_msg = (
            f"ℹ️ <b>Status Update: Submission #{sub_id}</b>\n\n"
            f"Your submission status has been reset back to <b>Pending Review</b>."
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=user_msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

        q_info = await db.get_queue_info(sub_id)
        card_text = format_admin_submission_card(updated_sub, q_info)
        kb = admin_submission_actions_keyboard(sub_id, "PENDING")
        await query.edit_message_text(
            f"↩️ <b>ACTION UNDONE: Submission #{sub_id} reverted back to PENDING!</b>\n\n" + card_text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
        return

    updated_sub = await db.update_submission_status(sub_id, new_status)
    user_id = sub["user_id"]

    # Notify User based on status
    if new_status == "IN_REVIEW":
        user_msg = (
            f"🔍 <b>Status Update</b>\n\n"
            f"Your submission (ID: #{sub_id}) status has changed to <b>In Review</b>!\n"
            f"Our team is currently reviewing and verifying your details.\n\n"
            f"📅 <b>Submitted Date:</b> {sub['created_at']}"
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=user_msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    elif new_status == "ACCEPTED":
        current_handle = await db.get_support_handle()
        tg_contact = current_handle if current_handle.startswith("@") else f"@{current_handle}"
        clean_handle = tg_contact.lstrip("@")
        user_msg = (
            f"🎉 <b>Status Update: Submission Approved!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Your submission (ID: #{sub_id}) has been APPROVED!</b>\n\n"
            f"📧 <b>Email:</b> <code>{sub['email']}</code>\n"
            f"📅 <b>Submitted Date:</b> {sub['created_at']}\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>CLAIM YOUR PAYMENT:</b>\n"
            f"Please message admin directly on Telegram to receive your payment for this account:\n\n"
            f"👉 <b>Telegram ID:</b> {tg_contact}\n\n"
            f"<i>Send a message to {tg_contact} quoting Submission ID #{sub_id} with your payment details to receive your payout!</i>"
        )
        pay_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💬 Message {tg_contact} for Payment", url=f"https://t.me/{clean_handle}")]
        ])
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=user_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=pay_kb
            )
        except Exception:
            pass

        # Remove from chat and maintain in category buttons
        await query.answer(f"✅ Approved #{sub_id} & removed from chat! Maintained in 'Approved Submissions' category.", show_alert=False)
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_text(
                f"✅ <b>Submission #{sub_id} Approved!</b>\n<i>(Maintained under '✅ Approved Submissions' in Dashboard)</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")]])
            )
        return

    # Update admin message for other statuses (e.g. IN_REVIEW)
    q_info = await db.get_queue_info(sub_id) if new_status == "PENDING" else None
    card_text = format_admin_submission_card(updated_sub, q_info)
    kb = admin_submission_actions_keyboard(sub_id, new_status)

    await query.edit_message_text(
        f"✅ <b>Status updated to {new_status}!</b>\n\n" + card_text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )

async def admin_disapprove_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    sub_id = int(query.data.split(":")[1])
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Invalid Unique Code", callback_data=f"adm_dis_do:{sub_id}:Invalid unique code")],
        [InlineKeyboardButton("❌ Duplicate / Multiple Account", callback_data=f"adm_dis_do:{sub_id}:Duplicate / Multi-accounting prohibited")],
        [InlineKeyboardButton("❌ Information Mismatch", callback_data=f"adm_dis_do:{sub_id}:Information mismatch on website")],
        [InlineKeyboardButton("❌ General Disapproval", callback_data=f"adm_dis_do:{sub_id}:Verification requirements not met")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"adm_view:{sub_id}")]
    ])
    await query.edit_message_text(
        f"Select a reason for disapproving Submission #{sub_id}:",
        reply_markup=kb
    )

async def admin_disapprove_do_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    # Callback format: adm_dis_do:<SUB_ID>:<REASON>
    parts = query.data.split(":", 2)
    sub_id = int(parts[1])
    reason = parts[2]

    sub = await db.get_submission_by_id(sub_id)
    if not sub:
        await query.edit_message_text("⚠️ Submission not found.")
        return

    updated_sub = await db.update_submission_status(sub_id, "DISAPPROVED", admin_notes=reason)

    # Notify User
    user_msg = (
        f"❌ <b>Status Update: Submission Disapproved</b>\n\n"
        f"Your submission (ID: #{sub_id}) was <b>Disapproved</b>.\n"
        f"📝 <b>Reason:</b> {reason}\n"
        f"📅 <b>Submitted Date:</b> {sub['created_at']}\n\n"
        f"If you believe this was in error, you can submit an appeal by pressing <b>⚖️ Submit Appeal</b> in the bot menu."
    )
    try:
        await context.bot.send_message(chat_id=sub["user_id"], text=user_msg, parse_mode=ParseMode.HTML)
    except Exception:
        pass

    # Remove from chat and maintain in category buttons
    await query.answer(f"❌ Disapproved #{sub_id} & removed from chat! Maintained in 'Disapproved Submissions' category.", show_alert=False)
    try:
        await query.message.delete()
    except Exception:
        await query.edit_message_text(
            f"❌ <b>Submission #{sub_id} Disapproved!</b>\n<i>(Maintained under '❌ Disapproved Submissions' in Dashboard)</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")]])
        )

async def admin_resubmit_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    sub_id = int(query.data.split(":")[1])
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Re-enter Key", callback_data=f"adm_res_do:{sub_id}:Please provide a valid Key")],
        [InlineKeyboardButton("🔄 Re-enter Email/PASS", callback_data=f"adm_res_do:{sub_id}:Please re-enter correct email and PASS")],
        [InlineKeyboardButton("🔄 General Resubmission", callback_data=f"adm_res_do:{sub_id}:Please check and re-submit your details")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"adm_view:{sub_id}")]
    ])
    await query.edit_message_text(
        f"Select a reason to allow resubmission for #{sub_id}:",
        reply_markup=kb
    )

async def admin_resubmit_do_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    parts = query.data.split(":", 2)
    sub_id = int(parts[1])
    reason = parts[2]

    sub = await db.get_submission_by_id(sub_id)
    if not sub:
        await query.edit_message_text("⚠️ Submission not found.")
        return

    updated_sub = await db.update_submission_status(sub_id, "CAN_RESUBMIT", admin_notes=reason)

    # Notify User
    user_msg = (
        f"⚠️ <b>Status Update: Resubmission Unlocked by Admin</b>\n\n"
        f"Your submission (ID: #{sub_id}) was unlocked for resubmission.\n"
        f"📝 <b>Note:</b> {reason}\n"
        f"📅 <b>Original Submission Date:</b> {sub['created_at']}\n\n"
        f"<i>(Note: An 8-hour cooldown applies from the time of this approval before the account can be resubmitted.)</i>\n\n"
        f"You can check eligibility or resubmit anytime via <b>⚖️ Submit Appeal / Resubmit</b>."
    )
    try:
        await context.bot.send_message(chat_id=sub["user_id"], text=user_msg, parse_mode=ParseMode.HTML)
    except Exception:
        pass

    card_text = format_admin_submission_card(updated_sub)
    kb = admin_submission_actions_keyboard(sub_id, "CAN_RESUBMIT")
    await query.edit_message_text(
        f"🔄 <b>Submission #{sub_id} marked as CAN_RESUBMIT!</b>\n\n" + card_text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )

async def admin_appeals_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    appeals = await db.get_pending_appeals(limit=5)
    if not appeals:
        await query.edit_message_text(
            "ℹ️ <b>No Pending Appeals</b>\nThere are currently no unresolved appeals.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")
            ]])
        )
        return

    text = "⚖️ <b>Pending Appeals:</b>\n━━━━━━━━━━━━━━━━━━━\n"
    kb = []
    for app in appeals:
        text += (
            f"• <b>Appeal #{app['id']}</b> (Submission #{app['submission_id']})\n"
            f"  Date: {app['created_at']}\n"
            f"  Reason: <i>{app['appeal_text'][:80]}...</i>\n\n"
        )
        kb.append([
            InlineKeyboardButton(f"👉 Review Appeal #{app['id']}", callback_data=f"adm_app_view:{app['id']}")
        ])

    kb.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def admin_view_appeal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    appeal_id = int(query.data.split(":")[1])
    appeal = await db.get_appeal_by_id(appeal_id)
    if not appeal:
        await query.edit_message_text("⚠️ Appeal not found.")
        return

    sub = await db.get_submission_by_id(appeal["submission_id"])
    pass_val = sub.get("pass_code") or sub.get("full_name") if sub else "N/A"
    key_val = sub.get("key_code") or sub.get("unique_code") if sub else "N/A"
    text = (
        f"⚖️ <b>Appeal #{appeal['id']} Details</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Submission ID:</b> #{appeal['submission_id']}\n"
        f"📧 <b>Email:</b> <code>{sub['email'] if sub else 'Unknown'}</code>\n"
        f"🔒 <b>PASS:</b> <code>{pass_val}</code>\n"
        f"🔑 <b>Key:</b> <code>{key_val}</code>\n"
        f"💬 <b>Appeal Reason:</b>\n<i>{appeal['appeal_text']}</i>\n"
        f"📅 <b>Appeal Date:</b> {appeal['created_at']}\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    from keyboards import appeal_admin_keyboard
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=appeal_admin_keyboard(appeal_id)
    )

async def admin_appeal_decision_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    # Callback format: app_dec:<APPEAL_ID>:<DECISION>
    parts = query.data.split(":")
    appeal_id = int(parts[1])
    decision = parts[2]

    appeal = await db.get_appeal_by_id(appeal_id)
    if not appeal:
        await query.edit_message_text("⚠️ Appeal not found.")
        return

    sub_id = appeal["submission_id"]
    sub = await db.get_submission_by_id(sub_id)
    user_id = appeal["user_id"]

    if decision == "ACCEPT":
        await db.update_appeal_status(appeal_id, "APPROVED", "Accepted by admin")
        await db.update_submission_status(sub_id, "ACCEPTED", admin_notes="Accepted via appeal")
        current_handle = await db.get_support_handle()
        tg_contact = current_handle if current_handle.startswith("@") else f"@{current_handle}"
        clean_handle = tg_contact.lstrip("@")
        user_msg = (
            f"🎉 <b>Appeal Approved!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Your submission (ID: #{sub_id}) has been APPROVED!</b>\n\n"
            f"📧 <b>Email:</b> <code>{sub['email']}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>CLAIM YOUR PAYMENT:</b>\n"
            f"Please message admin directly on Telegram to receive your payment for this account:\n\n"
            f"👉 <b>Telegram ID:</b> {tg_contact}\n\n"
            f"<i>Send a message to {tg_contact} quoting Submission ID #{sub_id} with your payment details to receive your payout!</i>"
        )
        pay_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💬 Message {tg_contact} for Payment", url=f"https://t.me/{clean_handle}")]
        ])
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=user_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=pay_kb
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"✅ <b>Appeal #{appeal_id} APPROVED & Submission #{sub_id} marked as ACCEPTED!</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")
            ]])
        )

    elif decision == "RESUBMIT":
        await db.update_appeal_status(appeal_id, "APPROVED", "Resubmission granted")
        await db.update_submission_status(sub_id, "CAN_RESUBMIT", admin_notes="Resubmission granted via appeal")
        user_msg = (
            f"⚠️ <b>Appeal Decision: Resubmission Granted</b>\n\n"
            f"Your appeal was reviewed and approved for resubmission.\n"
            f"<i>(Note: An 8-hour cooldown applies from the time of this approval before the account can be resubmitted.)</i>\n\n"
            f"You can track status or resubmit in <b>⚖️ Submit Appeal / Resubmit</b>."
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=user_msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

        await query.edit_message_text(
            f"🔄 <b>Appeal #{appeal_id} processed: Submission #{sub_id} unlocked for resubmission!</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")
            ]])
        )

    elif decision == "REJECT":
        await db.update_appeal_status(appeal_id, "REJECTED", "Rejected by admin")
        user_msg = (
            f"❌ <b>Appeal Decision</b>\n\n"
            f"Your appeal for Submission #{sub_id} was reviewed and <b>Disapproved</b> by the administration team."
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=user_msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

        await query.edit_message_text(
            f"❌ <b>Appeal #{appeal_id} REJECTED.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")
            ]])
        )

async def admin_export_csv_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating CSV...")
    if not is_admin(query.from_user.id):
        return

    submissions = await db.get_all_submissions()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "User ID", "Username", "Email", "PASS", "Key", "Status", "Admin Notes", "Created At", "Updated At"])

    for s in submissions:
        writer.writerow([
            s["id"],
            s["user_id"],
            s.get("username") or "",
            s["email"],
            s.get("pass_code") or s.get("full_name") or "",
            s.get("key_code") or s.get("unique_code") or "",
            s["status"],
            s.get("admin_notes") or "",
            s["created_at"],
            s["updated_at"]
        ])

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
    csv_bytes.name = "submissions_export.csv"

    await query.message.reply_document(
        document=InputFile(csv_bytes, filename="submissions_export.csv"),
        caption=f"📊 <b>Submissions Export (CSV)</b>\nTotal records: {len(submissions)}",
        parse_mode=ParseMode.HTML
    )

async def generate_txt_file(submissions: list) -> io.BytesIO:
    lines = [
        "=" * 60,
        "MADCORN BOT - SUBMISSIONS DATA EXPORT (TEXT FORMAT)",
        f"Total Records: {len(submissions)}",
        "=" * 60,
        ""
    ]
    for s in submissions:
        pass_val = s.get("pass_code") or s.get("full_name") or "N/A"
        key_val = s.get("key_code") or s.get("unique_code") or "N/A"
        lines.append(f"[Submission #{s['id']}] Date: {s['created_at']}")
        lines.append(f"  • Email:    {s['email']}")
        lines.append(f"  • PASS:     {pass_val}")
        lines.append(f"  • Key:      {key_val}")
        lines.append(f"  • Status:   {s['status']}")
        lines.append(f"  • User:     @{s.get('username') or 'None'} (ID: {s['user_id']})")
        if s.get("admin_notes"):
            lines.append(f"  • Notes:    {s['admin_notes']}")
        lines.append("-" * 60)
        lines.append("")

    txt_content = "\n".join(lines)
    txt_bytes = io.BytesIO(txt_content.encode("utf-8"))
    txt_bytes.name = "submissions_export.txt"
    return txt_bytes

async def generate_batch_txt_file(submissions: list, count: int) -> io.BytesIO:
    lines = [
        "=" * 60,
        f"MADCORN BOT - BATCH ACCOUNTS EXPORT ({len(submissions)} ACCOUNTS)",
        f"Generated: {db.now_iso()}",
        "=" * 60,
        "",
        "--- DETAILED ACCOUNTS LIST ---"
    ]
    for idx, s in enumerate(submissions, 1):
        pass_val = s.get("pass_code") or s.get("full_name") or "N/A"
        key_val = s.get("key_code") or s.get("unique_code") or "N/A"
        resub_flag = "Yes" if s.get("is_resubmission") else "No"
        lines.append(f"[{idx}] ID: #{s['id']}")
        lines.append(f"  • Email:        {s['email']}")
        lines.append(f"  • PASS:         {pass_val}")
        lines.append(f"  • Key:          {key_val}")
        lines.append(f"  • Status:       {s['status']}")
        lines.append(f"  • Resubmission: {resub_flag}")
        lines.append(f"  • Date:         {s['created_at']}")
        lines.append("-" * 60)

    lines.append("")
    lines.append("--- QUICK FORMAT (EMAIL:PASS:KEY) ---")
    for s in submissions:
        pass_val = s.get("pass_code") or s.get("full_name") or ""
        key_val = s.get("key_code") or s.get("unique_code") or ""
        lines.append(f"{s['email']}:{pass_val}:{key_val}")

    lines.append("=" * 60)

    txt_content = "\n".join(lines)
    txt_bytes = io.BytesIO(txt_content.encode("utf-8"))
    txt_bytes.name = f"submissions_batch_{count}.txt"
    return txt_bytes

async def send_batch_txt(chat_id: int, bot, count: int):
    submissions = await db.get_submissions_batch(limit=count, status="PENDING")
    if not submissions:
        await bot.send_message(chat_id=chat_id, text="⚠️ No accounts found in pool.")
        return

    txt_bytes = await generate_batch_txt_file(submissions, count)
    await bot.send_document(
        chat_id=chat_id,
        document=InputFile(txt_bytes, filename=f"submissions_batch_{len(submissions)}.txt"),
        caption=(
            f"📄 <b>Custom Batch Export ({len(submissions)} Accounts)</b>\n"
            f"• <b>Requested:</b> {count}\n"
            f"• <b>Delivered:</b> {len(submissions)} accounts\n"
            f"• <b>Format:</b> Detailed list + Quick Copy (EMAIL:PASS:KEY)"
        ),
        parse_mode=ParseMode.HTML
    )

async def admin_export_txt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating TXT file...")
    if not is_admin(query.from_user.id):
        return

    submissions = await db.get_all_submissions()
    txt_bytes = await generate_txt_file(submissions)

    await query.message.reply_document(
        document=InputFile(txt_bytes, filename="submissions_export.txt"),
        caption=f"📄 <b>Submissions Data (TXT Format)</b>\nTotal records: {len(submissions)}",
        parse_mode=ParseMode.HTML
    )

async def admin_export_txt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if context.args and context.args[0].isdigit():
        count = int(context.args[0])
        await send_batch_txt(update.effective_chat.id, context.bot, count)
        return

    # Default: export all submissions
    submissions = await db.get_all_submissions()
    txt_bytes = await generate_txt_file(submissions)

    await update.message.reply_document(
        document=InputFile(txt_bytes, filename="submissions_export.txt"),
        caption=(
            f"📄 <b>Submissions Data (TXT Format)</b>\nTotal records: {len(submissions)}\n\n"
            f"<i>💡 Tip: To export a custom batch count, use: <code>/txt 5</code> or <code>/txt 10</code></i>"
        ),
        parse_mode=ParseMode.HTML
    )

WAIT_ADMIN_BATCH_COUNT = 303

async def admin_req_txt_prompt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    stats = await db.get_admin_stats()
    text = (
        f"📄 <b>Request Custom Batch TXT Export</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Pool Availability:</b>\n"
        f"• ⏳ <b>Pending Accounts:</b> {stats['pending']}\n"
        f"• 🆕 <b>New Accounts:</b> {stats['new_total']}\n"
        f"• 🔄 <b>Resubmitted Accounts:</b> {stats['resubmitted_total']}\n"
        f"• 📦 <b>Total Database Accounts:</b> {stats['total']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Please reply with the <b>number of accounts</b> you want in the TXT file (e.g. <code>5</code>, <code>10</code>, <code>25</code>):\n\n"
        f"<i>(Or send ❌ Cancel to abort)</i>"
    )
    await query.message.reply_text(text, parse_mode=ParseMode.HTML)
    return WAIT_ADMIN_BATCH_COUNT

async def receive_admin_batch_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    msg_text = update.message.text.strip()
    from handlers.submission import check_menu_intercept
    intercept_state = await check_menu_intercept(update, context, msg_text)
    if intercept_state is not None:
        return ConversationHandler.END

    if not msg_text.isdigit() or int(msg_text) <= 0:
        await update.message.reply_text(
            "⚠️ Please enter a valid positive number (e.g. <code>5</code>, <code>10</code>) or send ❌ Cancel:",
            parse_mode=ParseMode.HTML
        )
        return WAIT_ADMIN_BATCH_COUNT

    count = int(msg_text)
    await send_batch_txt(update.effective_chat.id, context.bot, count)
    return ConversationHandler.END

async def admin_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "🔎 <b>Search Usage:</b>\n<code>/search &lt;email, name, or code&gt;</code>",
            parse_mode=ParseMode.HTML
        )
        return

    query_str = " ".join(context.args)
    results = await db.search_submissions(query_str)
    if not results:
        await update.message.reply_text(f"No results found for '<code>{query_str}</code>'.", parse_mode=ParseMode.HTML)
        return

    text = f"🔎 <b>Search Results for '{query_str}':</b>\n━━━━━━━━━━━━━━━━━━━\n"
    kb = []
    for item in results:
        text += (
            f"• <b>#{item['id']}</b> | {item['full_name']} | <code>{item['email']}</code>\n"
            f"  Status: {item['status']} | Code: <code>{item['unique_code']}</code>\n\n"
        )
        kb.append([
            InlineKeyboardButton(f"👉 Manage #{item['id']}", callback_data=f"adm_view:{item['id']}")
        ])

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def admin_search_prompt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    await query.message.reply_text(
        "🔎 <b>Search Submissions</b>\n\n"
        "Please enter an <b>Email</b>, <b>PASS</b>, or <b>Key</b> to search:\n\n"
        "<i>(Or send ❌ Cancel to abort)</i>",
        parse_mode=ParseMode.HTML
    )
    return WAIT_ADMIN_SEARCH

async def receive_admin_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    query_str = update.message.text.strip()
    from handlers.submission import check_menu_intercept
    intercept_state = await check_menu_intercept(update, context, query_str)
    if intercept_state is not None:
        return ConversationHandler.END

    results = await db.search_submissions(query_str)
    if not results:
        await update.message.reply_text(
            f"ℹ️ No submissions found matching '<code>{query_str}</code>'.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")]])
        )
        return ConversationHandler.END

    text = f"🔎 <b>Search Results for '{query_str}' ({len(results)} found):</b>\n━━━━━━━━━━━━━━━━━━━\n"
    kb = []
    for item in results:
        pass_val = item.get("pass_code") or item.get("full_name") or "N/A"
        key_val = item.get("key_code") or item.get("unique_code") or "N/A"
        text += (
            f"• <b>#{item['id']}</b> | <code>{item['email']}</code>\n"
            f"  PASS: <code>{pass_val}</code> | Key: <code>{key_val}</code>\n"
            f"  Status: <b>{item['status']}</b> | Date: {item['created_at']}\n\n"
        )
        kb.append([
            InlineKeyboardButton(f"👉 Manage #{item['id']} ({item['email'][:16]})", callback_data=f"adm_view:{item['id']}")
        ])
    kb.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")])

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

WAIT_ADMIN_BROADCAST = 302

async def admin_broadcast_prompt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    count = await db.get_total_users_count()
    await query.message.reply_text(
        f"📢 <b>Create Announcement</b>\n\n"
        f"There are currently <b>{count}</b> registered users in the database.\n\n"
        f"Please send the message you want to broadcast to everyone.\n"
        f"<i>(You can use bold, italics, links, and emojis)</i>\n\n"
        f"Send <b>❌ Cancel</b> to abort.",
        parse_mode=ParseMode.HTML
    )
    return WAIT_ADMIN_BROADCAST

async def receive_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    msg_text = update.message.text.strip()
    from handlers.submission import check_menu_intercept
    intercept_state = await check_menu_intercept(update, context, msg_text)
    if intercept_state is not None:
        return ConversationHandler.END

    count = await db.get_total_users_count()
    context.user_data["broadcast_content"] = msg_text

    confirm_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Confirm & Send to All", callback_data="adm_bcast_do"),
            InlineKeyboardButton("❌ Cancel", callback_data="adm_bcast_cancel")
        ]
    ])

    await update.message.reply_text(
        f"📢 <b>Announcement Preview:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{msg_text}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Target Audience: <b>{count} users</b>\n"
        f"Are you sure you want to broadcast this message to everyone?",
        parse_mode=ParseMode.HTML,
        reply_markup=confirm_kb
    )
    return ConversationHandler.END

async def execute_broadcast(bot, user_ids: list, message_text: str) -> dict:
    import asyncio
    from telegram.error import Forbidden, BadRequest, RetryAfter

    sent = 0
    failed = 0
    formatted_msg = f"📢 <b>Announcement</b>\n\n{message_text}"

    for uid in user_ids:
        try:
            await bot.send_message(
                chat_id=uid,
                text=formatted_msg,
                parse_mode=ParseMode.HTML
            )
            sent += 1
            await asyncio.sleep(0.04)  # 25 messages per second to respect Telegram rate limits
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(chat_id=uid, text=formatted_msg, parse_mode=ParseMode.HTML)
                sent += 1
            except Exception:
                failed += 1
        except (Forbidden, BadRequest):
            # User blocked bot or chat deleted
            failed += 1
        except Exception:
            failed += 1

    return {"total": len(user_ids), "sent": sent, "failed": failed}

async def admin_broadcast_do_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Broadcasting announcement...")
    if not is_admin(query.from_user.id):
        return

    text = context.user_data.get("broadcast_content")
    if not text:
        await query.edit_message_text("⚠️ No broadcast content found. Please start over.")
        return

    await query.edit_message_text("⏳ <b>Broadcasting announcement to all users...</b>\nPlease wait.", parse_mode=ParseMode.HTML)

    user_ids = await db.get_all_user_ids()
    res = await execute_broadcast(context.bot, user_ids, text)
    context.user_data.pop("broadcast_content", None)

    await query.edit_message_text(
        f"✅ <b>Announcement Broadcast Completed!</b>\n\n"
        f"• 👥 <b>Total Targets:</b> {res['total']}\n"
        f"• 🚀 <b>Successfully Sent:</b> {res['sent']}\n"
        f"• ⚠️ <b>Failed / Blocked:</b> {res['failed']}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")
        ]])
    )

async def admin_broadcast_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Cancelled.")
    context.user_data.pop("broadcast_content", None)
    await query.edit_message_text("❌ Broadcast cancelled.")

async def admin_quick_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "📢 <b>Broadcast Command Usage:</b>\n"
            "<code>/broadcast Your message text here</code>\n\n"
            "Or use <b>⚙️ Admin Dashboard ➔ 📢 Make Announcement</b> for an interactive preview.",
            parse_mode=ParseMode.HTML
        )
        return

    msg_text = " ".join(context.args)
    user_ids = await db.get_all_user_ids()
    status_msg = await update.message.reply_text(
        f"⏳ Broadcasting to {len(user_ids)} users...",
        parse_mode=ParseMode.HTML
    )

    res = await execute_broadcast(context.bot, user_ids, msg_text)
    await status_msg.edit_text(
        f"✅ <b>Broadcast Completed!</b>\n\n"
        f"• 👥 <b>Total Targets:</b> {res['total']}\n"
        f"• 🚀 <b>Delivered:</b> {res['sent']}\n"
        f"• ⚠️ <b>Failed / Blocked:</b> {res['failed']}",
        parse_mode=ParseMode.HTML
    )

async def admin_settings_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    channel_url = await db.get_channel_url()
    video_url = await db.get_video_url()
    support_handle = await db.get_support_handle()

    text = (
        "⚙️ <b>Bot Links & Telegram Handles Settings</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📢 <b>Channel Link:</b>\n👉 <code>{channel_url}</code>\n\n"
        f"🎥 <b>Tutorial Video Link:</b>\n👉 <code>{video_url}</code>\n\n"
        f"💬 <b>Support & Payout Handle:</b>\n👉 <code>{support_handle}</code>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "<i>Select which link or handle you want to update:</i>"
    )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=admin_settings_keyboard(),
        disable_web_page_preview=True
    )

async def admin_set_prompt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    setting_key = query.data.split(":")[1]
    context.user_data["admin_setting_target"] = setting_key

    prompts = {
        "channel_url": "📢 <b>Update Channel Link</b>\n\nPlease enter the new Telegram channel link (e.g. <code>https://t.me/yourchannel</code>)\n\n<i>Or send ❌ Cancel to abort:</i>",
        "video_url": "🎥 <b>Update Tutorial Video Link</b>\n\nPlease enter the new video URL (e.g. <code>https://t.me/yourvideo</code> or YouTube link)\n\n<i>Or send ❌ Cancel to abort:</i>",
        "support_handle": "💬 <b>Update Support / Payout Telegram Handle</b>\n\nPlease enter the Telegram username (e.g. <code>@MyAdminHandle</code>)\n\n<i>Or send ❌ Cancel to abort:</i>"
    }

    msg = prompts.get(setting_key, "Please enter the new value:\n\n<i>Or send ❌ Cancel to abort:</i>")
    await query.edit_message_text(msg, parse_mode=ParseMode.HTML)
    return WAIT_ADMIN_SETTING_VALUE

async def receive_admin_setting_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    raw_val = update.message.text.strip()
    from handlers.submission import check_menu_intercept
    intercept_state = await check_menu_intercept(update, context, raw_val)
    if intercept_state is not None:
        return ConversationHandler.END

    target_key = context.user_data.get("admin_setting_target")
    if not target_key:
        await update.message.reply_text("⚠️ No active setting update found.")
        return ConversationHandler.END

    if target_key == "support_handle":
        val = raw_val if raw_val.startswith("@") else f"@{raw_val}"
    else:
        val = raw_val

    await db.set_setting(target_key, val)
    context.user_data.pop("admin_setting_target", None)

    names = {
        "channel_url": "Channel Link",
        "video_url": "Tutorial Video Link",
        "support_handle": "Support / Payout Handle"
    }
    label = names.get(target_key, target_key)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Back to Settings", callback_data="adm_settings_menu")],
        [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")]
    ])

    await update.message.reply_text(
        f"✅ <b>{label} Updated Successfully!</b>\n\n"
        f"New value:\n👉 <code>{val}</code>\n\n"
        f"<i>This update takes effect immediately for all users across the bot!</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
        disable_web_page_preview=True
    )
    return ConversationHandler.END

async def admin_setchannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        curr = await db.get_channel_url()
        await update.message.reply_text(
            f"📢 <b>Current Channel Link:</b> <code>{curr}</code>\n\n"
            f"<b>Usage:</b> <code>/setchannel https://t.me/yourchannel</code>",
            parse_mode=ParseMode.HTML
        )
        return
    new_url = context.args[0].strip()
    await db.set_setting("channel_url", new_url)
    await update.message.reply_text(
        f"✅ Channel link updated to: <code>{new_url}</code>",
        parse_mode=ParseMode.HTML
    )

async def admin_setvideo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        curr = await db.get_video_url()
        await update.message.reply_text(
            f"🎥 <b>Current Video Link:</b> <code>{curr}</code>\n\n"
            f"<b>Usage:</b> <code>/setvideo https://t.me/yourvideo</code>",
            parse_mode=ParseMode.HTML
        )
        return
    new_url = context.args[0].strip()
    await db.set_setting("video_url", new_url)
    await update.message.reply_text(
        f"✅ Video link updated to: <code>{new_url}</code>",
        parse_mode=ParseMode.HTML
    )

async def admin_setsupport_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        curr = await db.get_support_handle()
        await update.message.reply_text(
            f"💬 <b>Current Support Handle:</b> <code>{curr}</code>\n\n"
            f"<b>Usage:</b> <code>/setsupport @YourHandle</code>",
            parse_mode=ParseMode.HTML
        )
        return
    raw_handle = context.args[0].strip()
    new_handle = raw_handle if raw_handle.startswith("@") else f"@{raw_handle}"
    await db.set_setting("support_handle", new_handle)
    await update.message.reply_text(
        f"✅ Support / Payout handle updated to: <code>{new_handle}</code>",
        parse_mode=ParseMode.HTML
    )


