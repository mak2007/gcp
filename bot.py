import sys
import logging
import asyncio

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

from config import BOT_TOKEN, ADMIN_IDS
import database as db

from handlers.user import (
    start_handler,
    check_status_handler,
    refresh_status_callback,
    support_handler,
    receive_support_msg,
    cancel_conversation,
    WAIT_SUPPORT_MSG
)
from handlers.submission import (
    start_submission,
    receive_email,
    receive_pass,
    receive_key,
    WAIT_EMAIL,
    WAIT_PASS,
    WAIT_KEY
)
from handlers.appeal import (
    start_appeal,
    receive_appeal_text,
    WAIT_APPEAL_TEXT
)
from handlers.admin import (
    admin_dashboard_command,
    admin_stats_callback,
    admin_list_submissions_callback,
    admin_view_submission_callback,
    admin_change_status_callback,
    admin_disapprove_menu_callback,
    admin_disapprove_do_callback,
    admin_resubmit_menu_callback,
    admin_resubmit_do_callback,
    admin_appeals_list_callback,
    admin_view_appeal_callback,
    admin_appeal_decision_callback,
    admin_export_csv_callback,
    admin_search_command,
    admin_broadcast_prompt_callback,
    receive_broadcast_text,
    admin_broadcast_do_callback,
    admin_broadcast_cancel_callback,
    admin_quick_broadcast_command,
    WAIT_ADMIN_BROADCAST
)

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

async def post_init(application):
    await db.init_db()
    logger.info("Database initialized successfully.")
    bot_info = await application.bot.get_me()
    logger.info(f"Bot connected as @{bot_info.username} (ID: {bot_info.id})")
    if ADMIN_IDS:
        logger.info(f"Configured Admins: {ADMIN_IDS}")
    else:
        logger.warning("No ADMIN_IDS configured in .env! Admin commands won't be accessible.")

def main():
    import os
    if not BOT_TOKEN:
        print("\n" + "=" * 60)
        print("❌ ERROR: BOT_TOKEN is not configured!")
        print("Available environment variable keys found in container:")
        print([k for k in os.environ.keys() if not k.startswith("RAILWAY_SYSTEM_")])
        print("Please ensure BOT_TOKEN is saved in Railway Variables.")
        print("=" * 60 + "\n")
        sys.exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # 1. Submission Conversation Handler
    submission_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📝 Submit Information$"), start_submission),
            CommandHandler("submit", start_submission)
        ],
        states={
            WAIT_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email)],
            WAIT_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pass)],
            WAIT_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_key)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Cancel$"), cancel_conversation),
            CommandHandler("cancel", cancel_conversation)
        ],
        allow_reentry=True
    )
    app.add_handler(submission_conv)

    # 2. Appeal Conversation Handler
    appeal_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^⚖️ Submit Appeal$"), start_appeal),
            CommandHandler("appeal", start_appeal)
        ],
        states={
            WAIT_APPEAL_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_appeal_text)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Cancel$"), cancel_conversation),
            CommandHandler("cancel", cancel_conversation)
        ],
        allow_reentry=True
    )
    app.add_handler(appeal_conv)

    # 3. Support Conversation Handler
    support_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💬 Support$"), support_handler),
            CommandHandler("support", support_handler)
        ],
        states={
            WAIT_SUPPORT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_support_msg)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Cancel$"), cancel_conversation),
            CommandHandler("cancel", cancel_conversation)
        ],
        allow_reentry=True
    )
    app.add_handler(support_conv)

    # 4. Admin Broadcast Conversation Handler
    broadcast_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_broadcast_prompt_callback, pattern=r"^adm_broadcast_prompt$")
        ],
        states={
            WAIT_ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast_text)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Cancel$"), cancel_conversation),
            CommandHandler("cancel", cancel_conversation)
        ],
        allow_reentry=True
    )
    app.add_handler(broadcast_conv)

    # 5. Standard Commands & Buttons
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", check_status_handler))
    app.add_handler(MessageHandler(filters.Regex("^📊 Check Status & Queue$"), check_status_handler))

    # User Callbacks
    app.add_handler(CallbackQueryHandler(refresh_status_callback, pattern=r"^usr_refresh_status$"))

    # 6. Admin Commands & Handlers
    app.add_handler(CommandHandler("admin", admin_dashboard_command))
    app.add_handler(CommandHandler("search", admin_search_command))
    app.add_handler(CommandHandler("broadcast", admin_quick_broadcast_command))
    app.add_handler(CommandHandler("announce", admin_quick_broadcast_command))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Admin Dashboard$"), admin_dashboard_command))

    # Admin Callback Queries
    app.add_handler(CallbackQueryHandler(admin_dashboard_command, pattern=r"^adm_dashboard_nav$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback, pattern=r"^adm_stats$"))
    app.add_handler(CallbackQueryHandler(admin_list_submissions_callback, pattern=r"^adm_list:"))
    app.add_handler(CallbackQueryHandler(admin_view_submission_callback, pattern=r"^adm_view:"))
    app.add_handler(CallbackQueryHandler(admin_change_status_callback, pattern=r"^adm_st:"))
    app.add_handler(CallbackQueryHandler(admin_disapprove_menu_callback, pattern=r"^adm_dis:\d+$"))
    app.add_handler(CallbackQueryHandler(admin_disapprove_do_callback, pattern=r"^adm_dis_do:"))
    app.add_handler(CallbackQueryHandler(admin_resubmit_menu_callback, pattern=r"^adm_res:\d+$"))
    app.add_handler(CallbackQueryHandler(admin_resubmit_do_callback, pattern=r"^adm_res_do:"))
    app.add_handler(CallbackQueryHandler(admin_appeals_list_callback, pattern=r"^adm_appeals:"))
    app.add_handler(CallbackQueryHandler(admin_view_appeal_callback, pattern=r"^adm_app_view:"))
    app.add_handler(CallbackQueryHandler(admin_appeal_decision_callback, pattern=r"^app_dec:"))
    app.add_handler(CallbackQueryHandler(admin_export_csv_callback, pattern=r"^adm_export_csv$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_do_callback, pattern=r"^adm_bcast_do$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_cancel_callback, pattern=r"^adm_bcast_cancel$"))

    # Global Error Handler
    app.add_error_handler(error_handler)

    print("🚀 Starting Telegram Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
