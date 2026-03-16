from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from app.models.database import get_session_factory
from app.services.access import (
    add_to_whitelist,
    get_whitelist,
    is_admin,
    remove_from_whitelist,
)
from app.services.i18n import t

WAITING_USERNAME = 1


def _admin_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    settings = context.bot_data["settings"]
    username = update.effective_user.username if update.effective_user else None
    return is_admin(username, settings)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _admin_check(update, context):
        return
    lang = update.effective_user.language_code if update.effective_user else None
    keyboard = [
        [InlineKeyboardButton(t("admin-add-user", lang), callback_data="admin_add")],
        [InlineKeyboardButton(t("admin-remove-user", lang), callback_data="admin_remove")],
    ]
    await update.message.reply_text(
        t("admin-manage-whitelist", lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def admin_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not _admin_check(update, context):
        return ConversationHandler.END
    await query.answer()
    lang = update.effective_user.language_code if update.effective_user else None
    await query.edit_message_text(t("admin-send-username", lang))
    return WAITING_USERNAME


async def admin_add_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return ConversationHandler.END
    if not _admin_check(update, context):
        return ConversationHandler.END

    lang = update.effective_user.language_code
    username = update.message.text.strip().lstrip("@")

    if not username:
        return ConversationHandler.END

    # We don't know telegram_id from username, store 0 as placeholder.
    # The bot will resolve the ID when the user first interacts.
    async with get_session_factory()() as session:
        added = await add_to_whitelist(0, username, session)
    if added:
        await update.message.reply_text(
            t("admin-user-added", lang, username=username, user_id="pending")
        )
    else:
        await update.message.reply_text(t("admin-user-already-exists", lang))
    return ConversationHandler.END


async def admin_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not _admin_check(update, context):
        return
    await query.answer()
    lang = update.effective_user.language_code if update.effective_user else None

    async with get_session_factory()() as session:
        users = await get_whitelist(session)

    if not users:
        await query.edit_message_text(t("admin-whitelist-empty", lang))
        return

    keyboard = [
        [InlineKeyboardButton(
            f"@{u.username}" if u.username else f"ID: {u.telegram_id}",
            callback_data=f"admin_rm_{u.telegram_id}",
        )]
        for u in users
    ]
    await query.edit_message_text(
        t("admin-whitelist-title", lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def admin_remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not _admin_check(update, context):
        return
    await query.answer()
    lang = update.effective_user.language_code if update.effective_user else None
    telegram_id = int(query.data.replace("admin_rm_", ""))

    async with get_session_factory()() as session:
        await remove_from_whitelist(telegram_id, session)

    await query.edit_message_text(t("admin-user-removed", lang))


def get_admin_handlers() -> list:
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_add_callback, pattern="^admin_add$"),
        ],
        states={
            WAITING_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_username),
            ],
        },
        fallbacks=[],
    )
    return [
        CommandHandler("admin", admin_command),
        conv_handler,
        CallbackQueryHandler(admin_remove_callback, pattern="^admin_remove$"),
        CallbackQueryHandler(admin_remove_user, pattern="^admin_rm_"),
    ]
