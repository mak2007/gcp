from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional

def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("📝 Submit Information"), KeyboardButton("📊 Check Status & Queue")],
        [KeyboardButton("⚖️ Submit Appeal"), KeyboardButton("💬 Support")]
    ]
    if is_admin:
        buttons.append([KeyboardButton("⚙️ Admin Dashboard")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True, one_time_keyboard=True)

def admin_submission_actions_keyboard(submission_id: int, current_status: str) -> InlineKeyboardMarkup:
    buttons = []
    
    # First row: In Review & Accept
    row1 = []
    if current_status != "IN_REVIEW":
        row1.append(InlineKeyboardButton("🔍 In Review", callback_data=f"adm_st:{submission_id}:IN_REVIEW"))
    if current_status != "ACCEPTED":
        row1.append(InlineKeyboardButton("✅ Accept (Pay)", callback_data=f"adm_st:{submission_id}:ACCEPTED"))
    if row1:
        buttons.append(row1)

    # Second row: Disapprove & Resubmit
    row2 = []
    if current_status != "DISAPPROVED":
        row2.append(InlineKeyboardButton("❌ Disapprove", callback_data=f"adm_dis:{submission_id}"))
    if current_status != "CAN_RESUBMIT":
        row2.append(InlineKeyboardButton("🔄 Can Resubmit", callback_data=f"adm_res:{submission_id}"))
    if row2:
        buttons.append(row2)

    # Undo / Revert to Pending button
    if current_status != "PENDING":
        buttons.append([InlineKeyboardButton("↩️ Undo / Revert to Pending", callback_data=f"adm_st:{submission_id}:PENDING")])

    buttons.append([
        InlineKeyboardButton("🔄 Refresh Details", callback_data=f"adm_view:{submission_id}"),
        InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")
    ])
    return InlineKeyboardMarkup(buttons)

def admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏳ Pending Queue", callback_data="adm_list:PENDING:0"),
            InlineKeyboardButton("🔍 In Review", callback_data="adm_list:IN_REVIEW:0")
        ],
        [
            InlineKeyboardButton("✅ Approved Submissions", callback_data="adm_list:ACCEPTED:0"),
            InlineKeyboardButton("❌ Disapproved Submissions", callback_data="adm_list:DISAPPROVED:0")
        ],
        [
            InlineKeyboardButton("🔄 Resubmitted Emails", callback_data="adm_resub_list:0"),
            InlineKeyboardButton("⚖️ Pending Appeals", callback_data="adm_appeals:0")
        ],
        [
            InlineKeyboardButton("📊 Inventory / Stock Stats", callback_data="adm_stats"),
            InlineKeyboardButton("📢 Make Announcement", callback_data="adm_broadcast_prompt")
        ],
        [
            InlineKeyboardButton("📥 Export CSV", callback_data="adm_export_csv"),
            InlineKeyboardButton("📄 Export All TXT", callback_data="adm_export_txt")
        ],
        [
            InlineKeyboardButton("📄 Request Custom TXT Batch", callback_data="adm_req_txt_prompt"),
            InlineKeyboardButton("🔎 Search Submission", callback_data="adm_search_prompt")
        ],
        [
            InlineKeyboardButton("🔗 Bot Links & Settings", callback_data="adm_settings_menu")
        ]
    ])

def admin_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Change Channel Link", callback_data="adm_set:channel_url")],
        [InlineKeyboardButton("🎥 Change Tutorial Video Link", callback_data="adm_set:video_url")],
        [InlineKeyboardButton("💬 Change Admin / Payout TG Handle", callback_data="adm_set:support_handle")],
        [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_dashboard_nav")]
    ])

def appeal_admin_keyboard(appeal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept & Approve", callback_data=f"app_dec:{appeal_id}:ACCEPT"),
            InlineKeyboardButton("🔄 Allow Resubmit", callback_data=f"app_dec:{appeal_id}:RESUBMIT")
        ],
        [
            InlineKeyboardButton("❌ Reject Appeal", callback_data=f"app_dec:{appeal_id}:REJECT")
        ]
    ])

def user_status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Status", callback_data="usr_refresh_status")]
    ])
