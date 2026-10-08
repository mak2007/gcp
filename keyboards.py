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

def admin_approve_tier_keyboard(submission_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 1 - Normal", callback_data=f"adm_appr_do:{submission_id}:NORMAL"),
            InlineKeyboardButton("⭐ 2 - Premium", callback_data=f"adm_appr_do:{submission_id}:PREMIUM")
        ],
        [
            InlineKeyboardButton("🔙 Back to Review", callback_data=f"adm_view:{submission_id}")
        ]
    ])

def admin_submission_actions_keyboard(submission_id: int, current_status: str) -> InlineKeyboardMarkup:
    buttons = []
    
    # Verdict buttons: Accept routes to 2-tier approval menu
    buttons.append([
        InlineKeyboardButton("✅ Accept / Approve", callback_data=f"adm_appr_menu:{submission_id}"),
        InlineKeyboardButton("❌ Disapprove", callback_data=f"adm_dis:{submission_id}")
    ])

    buttons.append([
        InlineKeyboardButton("🔄 Can Resubmit", callback_data=f"adm_res:{submission_id}"),
        InlineKeyboardButton("🔍 In Review", callback_data=f"adm_st:{submission_id}:IN_REVIEW")
    ])

    # Undo / Revert to Pending button
    if current_status != "PENDING":
        buttons.append([InlineKeyboardButton("↩️ Undo / Revert to Pending", callback_data=f"adm_st:{submission_id}:PENDING")])

    buttons.append([
        InlineKeyboardButton("⏳ In Queue", callback_data="adm_list:PENDING:0"),
        InlineKeyboardButton("🔙 Dashboard", callback_data="adm_dashboard_nav")
    ])
    return InlineKeyboardMarkup(buttons)

def admin_dashboard_keyboard(stats: Optional[dict] = None) -> InlineKeyboardMarkup:
    if stats:
        pend_c = stats.get('pending', 0)
        norm_c = stats.get('accepted_normal', 0)
        prem_c = stats.get('accepted_premium', 0)
        dis_c = stats.get('disapproved', 0)
        resub_c = stats.get('can_resubmit', 0)
        app_c = stats.get('appeals_pending', 0)
        row1_txt = f"⏳ In Queue ({pend_c})"
        row2_norm = f"🟢 Normal Gmails ({norm_c})"
        row2_prem = f"⭐ Premium Gmails ({prem_c})"
        row3_dis = f"❌ Rejected Accs ({dis_c})"
        row3_res = f"🔄 Resubmit-Clicked ({resub_c})"
        row4_app = f"⚖️ Appeals ({app_c})"
    else:
        row1_txt = "⏳ In Queue"
        row2_norm = "🟢 Normal Gmails"
        row2_prem = "⭐ Premium Gmails"
        row3_dis = "❌ Rejected Accs"
        row3_res = "🔄 Resubmit-Clicked"
        row4_app = "⚖️ Appeals"

    return InlineKeyboardMarkup([
        # 1. Main Queue (highest priority)
        [InlineKeyboardButton(row1_txt, callback_data="adm_list:PENDING:0")],
        # 2. Approved Gmails (Normal & Premium separated)
        [
            InlineKeyboardButton(row2_norm, callback_data="adm_tier_list:NORMAL:0"),
            InlineKeyboardButton(row2_prem, callback_data="adm_tier_list:PREMIUM:0")
        ],
        # 3. Rejected Accounts & Resubmit-Clicked
        [
            InlineKeyboardButton(row3_dis, callback_data="adm_list:DISAPPROVED:0"),
            InlineKeyboardButton(row3_res, callback_data="adm_list:CAN_RESUBMIT:0")
        ],
        # 4. Appeals
        [InlineKeyboardButton(row4_app, callback_data="adm_appeals:0")],
        # 5. Fast Exports (Normal & Premium TXT)
        [
            InlineKeyboardButton("📄 Export Normal TXT", callback_data="adm_export_txt:NORMAL"),
            InlineKeyboardButton("⭐ Export Premium TXT", callback_data="adm_export_txt:PREMIUM")
        ],
        # 6. General TXT & Custom Batch
        [
            InlineKeyboardButton("📄 Export All TXT", callback_data="adm_export_txt:ALL"),
            InlineKeyboardButton("📦 Custom TXT Batch", callback_data="adm_req_txt_prompt")
        ],
        # 7. Broadcast & Search
        [
            InlineKeyboardButton("📢 Announcement", callback_data="adm_broadcast_prompt"),
            InlineKeyboardButton("🔎 Search Submission", callback_data="adm_search_prompt")
        ],
        # 8. Settings & Stats
        [
            InlineKeyboardButton("📊 Stats & Inventory", callback_data="adm_stats"),
            InlineKeyboardButton("⚙️ Bot Settings", callback_data="adm_settings_menu")
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
