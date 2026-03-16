import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.database import get_session_factory
from app.models.user import TranslateWhitelistUser, TranslationSettings
from app.services.access import is_admin
from app.services.gemini import translate_disclaimer, translate_text, transcribe_and_translate
from app.services.i18n import get_disclaimer, t

logger = logging.getLogger(__name__)

WAITING_TRANSLATE_USERNAME = 10


# ── DB helpers ───────────────────────────────────────────────────────────────

async def _get_translate_users(
    session: AsyncSession, admin_chat_id: int
) -> list[TranslateWhitelistUser]:
    result = await session.exec(
        select(TranslateWhitelistUser).where(
            TranslateWhitelistUser.admin_chat_id == admin_chat_id
        )
    )
    return list(result.all())


async def _add_translate_user(
    session: AsyncSession, username: str, admin_chat_id: int
) -> bool:
    existing = await session.exec(
        select(TranslateWhitelistUser).where(
            TranslateWhitelistUser.username == username.lower(),
            TranslateWhitelistUser.admin_chat_id == admin_chat_id,
        )
    )
    if existing.first():
        return False
    user = TranslateWhitelistUser(
        username=username.lower(), admin_chat_id=admin_chat_id
    )
    session.add(user)
    await session.commit()
    return True


async def _remove_translate_user(session: AsyncSession, user_id: int) -> str | None:
    result = await session.exec(
        select(TranslateWhitelistUser).where(TranslateWhitelistUser.id == user_id)
    )
    user = result.first()
    if not user:
        return None
    username = user.username
    await session.delete(user)
    await session.commit()
    return username


async def _is_user_in_translate_list(
    session: AsyncSession, username: str, admin_chat_id: int
) -> bool:
    result = await session.exec(
        select(TranslateWhitelistUser).where(
            TranslateWhitelistUser.username == username.lower(),
            TranslateWhitelistUser.admin_chat_id == admin_chat_id,
        )
    )
    return result.first() is not None


async def _get_translation_settings(
    session: AsyncSession, admin_chat_id: int
) -> TranslationSettings:
    result = await session.exec(
        select(TranslationSettings).where(
            TranslationSettings.admin_chat_id == admin_chat_id
        )
    )
    settings = result.first()
    if not settings:
        settings = TranslationSettings(admin_chat_id=admin_chat_id, enabled=True)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


async def _toggle_translation(session: AsyncSession, admin_chat_id: int) -> bool:
    ts = await _get_translation_settings(session, admin_chat_id)
    ts.enabled = not ts.enabled
    session.add(ts)
    await session.commit()
    return ts.enabled


# ── Inline menu ──────────────────────────────────────────────────────────────

async def translator_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message or not update.effective_user:
        return
    settings = context.bot_data["settings"]
    if not is_admin(update.effective_user.username, settings):
        lang = update.effective_user.language_code
        await update.message.reply_text(t("no-permission", lang))
        return

    lang = update.effective_user.language_code
    admin_chat_id = update.effective_chat.id

    async with get_session_factory()() as session:
        ts = await _get_translation_settings(session, admin_chat_id)

    status = (
        t("translator-status-enabled", lang)
        if ts.enabled
        else t("translator-status-disabled", lang)
    )
    toggle_label = (
        t("translator-disable", lang)
        if ts.enabled
        else t("translator-enable", lang)
    )

    keyboard = [
        [InlineKeyboardButton(t("translator-add-user", lang), callback_data="tr_add")],
        [InlineKeyboardButton(t("translator-remove-user", lang), callback_data="tr_remove")],
        [InlineKeyboardButton(toggle_label, callback_data="tr_toggle")],
    ]
    await update.message.reply_text(
        f"{t('translator-title', lang)}\n{status}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def tr_add_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    settings = context.bot_data["settings"]
    if not is_admin(update.effective_user.username if update.effective_user else None, settings):
        await query.answer()
        return ConversationHandler.END
    await query.answer()
    lang = update.effective_user.language_code if update.effective_user else None
    await query.edit_message_text(t("translator-send-username", lang))
    return WAITING_TRANSLATE_USERNAME


async def tr_add_username(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not update.message or not update.effective_user:
        return ConversationHandler.END
    settings = context.bot_data["settings"]
    if not is_admin(update.effective_user.username, settings):
        return ConversationHandler.END

    lang = update.effective_user.language_code
    username = update.message.text.strip().lstrip("@").lower()
    admin_chat_id = update.effective_chat.id

    async with get_session_factory()() as session:
        added = await _add_translate_user(session, username, admin_chat_id)

    if added:
        await update.message.reply_text(
            t("translator-user-added", lang, username=username)
        )
    else:
        await update.message.reply_text(
            t("translator-user-already-exists", lang, username=username)
        )
    return ConversationHandler.END


async def tr_remove_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    settings = context.bot_data["settings"]
    if not is_admin(update.effective_user.username if update.effective_user else None, settings):
        await query.answer()
        return
    await query.answer()
    lang = update.effective_user.language_code if update.effective_user else None
    admin_chat_id = update.effective_chat.id

    async with get_session_factory()() as session:
        users = await _get_translate_users(session, admin_chat_id)

    if not users:
        await query.edit_message_text(t("translator-list-empty", lang))
        return

    keyboard = [
        [InlineKeyboardButton(f"@{u.username}", callback_data=f"tr_rm_{u.id}")]
        for u in users
    ]
    await query.edit_message_text(
        t("translator-list-title", lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def tr_remove_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    settings = context.bot_data["settings"]
    if not is_admin(update.effective_user.username if update.effective_user else None, settings):
        await query.answer()
        return
    await query.answer()
    lang = update.effective_user.language_code if update.effective_user else None
    user_id = int(query.data.replace("tr_rm_", ""))

    async with get_session_factory()() as session:
        username = await _remove_translate_user(session, user_id)

    if username:
        await query.edit_message_text(
            t("translator-user-removed", lang, username=username)
        )


async def tr_toggle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    settings = context.bot_data["settings"]
    if not is_admin(update.effective_user.username if update.effective_user else None, settings):
        await query.answer()
        return
    await query.answer()
    lang = update.effective_user.language_code if update.effective_user else None
    admin_chat_id = update.effective_chat.id

    async with get_session_factory()() as session:
        enabled = await _toggle_translation(session, admin_chat_id)

    if enabled:
        await query.edit_message_text(t("translator-enabled", lang))
    else:
        await query.edit_message_text(t("translator-disabled", lang))


# ── Business message handling ────────────────────────────────────────────────

async def _get_disclaimer_text(user_language: str | None) -> str:
    """Get the disclaimer in the user's language."""
    text, from_locale = get_disclaimer(user_language)
    if from_locale:
        return text
    # Need to translate via AI
    lang_name = user_language or "English"
    translated = await translate_disclaimer(text, lang_name)
    return translated


async def handle_business_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle incoming business messages — translate text/voice from user to admin."""
    if not update.business_message:
        return

    msg = update.business_message
    settings = context.bot_data["settings"]
    business_connection_id = msg.business_connection_id

    # Get the business connection to determine admin chat
    connection = await context.bot.get_business_connection(business_connection_id)
    admin_user = connection.user
    admin_chat_id = admin_user.id

    # Check if translation is enabled
    async with get_session_factory()() as session:
        ts = await _get_translation_settings(session, admin_chat_id)
        if not ts.enabled:
            return

    # Determine if the message is from a user (not the admin replying)
    # In business mode, messages from the external user have from_user != admin
    sender = msg.from_user
    if not sender or sender.id == admin_user.id:
        return

    sender_username = (sender.username or "").lower()

    # Check if sender is in translate whitelist
    async with get_session_factory()() as session:
        if not await _is_user_in_translate_list(session, sender_username, admin_chat_id):
            return

    admin_lang = admin_user.language_code or "en"

    # Handle voice messages
    if msg.voice:
        try:
            voice_file = await context.bot.get_file(msg.voice.file_id)
            voice_bytes = await voice_file.download_as_bytearray()
            result = await transcribe_and_translate(bytes(voice_bytes), admin_lang)
            header = f"🎤 Voice from @{sender_username}:"
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=f"{header}\n\n{result}",
                business_connection_id=business_connection_id,
                reply_to_message_id=msg.message_id,
            )
        except Exception:
            logger.exception("Failed to transcribe/translate voice message")
        return

    # Handle text messages
    if msg.text:
        try:
            translated = await translate_text(msg.text, admin_lang)
            header = f"💬 @{sender_username}:"
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=f"{header}\n\n{translated}",
                business_connection_id=business_connection_id,
                reply_to_message_id=msg.message_id,
            )
        except Exception:
            logger.exception("Failed to translate text message")


async def handle_business_message_reply(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle admin replying to a translated message — translate back and send to user."""
    if not update.business_message:
        return

    msg = update.business_message
    settings = context.bot_data["settings"]
    business_connection_id = msg.business_connection_id

    connection = await context.bot.get_business_connection(business_connection_id)
    admin_user = connection.user
    admin_chat_id = admin_user.id

    # Only process messages from admin that are replies
    sender = msg.from_user
    if not sender or sender.id != admin_user.id:
        return

    if not msg.reply_to_message or not msg.text:
        return

    # Check translation is enabled
    async with get_session_factory()() as session:
        ts = await _get_translation_settings(session, admin_chat_id)
        if not ts.enabled:
            return

    # Determine the original sender from the reply chain
    original_msg = msg.reply_to_message
    chat = msg.chat

    # The chat in business mode is the user's chat
    # We need to determine the user's language
    user_language = chat.first_name  # We don't have language_code from chat
    # Use the chat id to identify the target user
    target_chat_id = chat.id

    # Detect target user's language from the original message or default
    # We'll ask Gemini to detect and translate
    try:
        original_text = original_msg.text or ""
        # Translate admin's reply to the user's language
        # Use the original message language as a hint
        translated = await translate_text(
            msg.text,
            f"the same language as this text: '{original_text[:200]}'" if original_text
            else "the language that would be most appropriate for the recipient",
        )

        disclaimer = await _get_disclaimer_text(None)

        full_message = f"{translated}\n\n_{disclaimer}_"

        await context.bot.send_message(
            chat_id=target_chat_id,
            text=full_message,
            business_connection_id=business_connection_id,
            parse_mode="Markdown",
        )

        # Mark the original message as read
        try:
            await context.bot.read_business_message(
                business_connection_id=business_connection_id,
                chat_id=target_chat_id,
                message_id=original_msg.message_id,
            )
        except Exception:
            logger.debug("Could not mark message as read", exc_info=True)

    except Exception:
        logger.exception("Failed to translate admin reply")


# ── Handler registration ────────────────────────────────────────────────────

def get_translator_handlers() -> list:
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(tr_add_callback, pattern="^tr_add$"),
        ],
        states={
            WAITING_TRANSLATE_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tr_add_username),
            ],
        },
        fallbacks=[],
    )
    return [
        CommandHandler("translator", translator_command),
        conv_handler,
        CallbackQueryHandler(tr_remove_callback, pattern="^tr_remove$"),
        CallbackQueryHandler(tr_remove_user, pattern="^tr_rm_"),
        CallbackQueryHandler(tr_toggle_callback, pattern="^tr_toggle$"),
    ]
