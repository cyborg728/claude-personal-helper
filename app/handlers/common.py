from telegram import Update
from telegram.ext import ContextTypes

from app.models.database import get_session_factory
from app.services.access import is_allowed
from app.services.i18n import t


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    settings = context.bot_data["settings"]
    async with get_session_factory()() as session:
        if not await is_allowed(
            update.effective_user.id,
            update.effective_user.username,
            settings,
            session,
        ):
            await update.message.reply_text(
                t("no-permission", update.effective_user.language_code)
            )
            return
    lang = update.effective_user.language_code
    await update.message.reply_text(t("start-welcome", lang))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    settings = context.bot_data["settings"]
    async with get_session_factory()() as session:
        if not await is_allowed(
            update.effective_user.id,
            update.effective_user.username,
            settings,
            session,
        ):
            await update.message.reply_text(
                t("no-permission", update.effective_user.language_code)
            )
            return
    lang = update.effective_user.language_code
    await update.message.reply_text(t("help-text", lang))
