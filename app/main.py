"""Entry point for the Telegram bot with Litestar webhook server."""

import asyncio
import logging

import uvicorn
from telegram.ext import ApplicationBuilder, MessageHandler, filters

from app.config import Settings
from app.handlers.admin import get_admin_handlers
from app.handlers.common import help_command, start
from app.handlers.translator import (
    get_translator_handlers,
    handle_business_message,
    handle_business_message_reply,
)
from app.models.database import close_db, init_db
from app.services.gemini import init_gemini
from app.services.i18n import init_localization
from app.webhook import create_litestar_app, set_bot_application

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings()

    # Initialize services
    init_localization()
    init_gemini(settings.gemini_api_key, settings.gemini_model)
    await init_db(settings)

    # Build telegram application
    application = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .updater(None)  # We handle updates via webhook
        .build()
    )
    application.bot_data["settings"] = settings

    # Register handlers — order matters
    from telegram.ext import CommandHandler

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    for handler in get_admin_handlers():
        application.add_handler(handler)

    for handler in get_translator_handlers():
        application.add_handler(handler)

    # Business message handlers (must come after command/callback handlers)
    # Reply detection: admin replies have reply_to_message set and sender == admin
    application.add_handler(
        MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_business_message_reply),
        group=1,
    )
    application.add_handler(
        MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_business_message),
        group=2,
    )

    # Initialize the application
    await application.initialize()
    await application.start()

    # Set webhook
    await application.bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.webhook_secret or None,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info("Webhook set to %s", settings.webhook_url)

    # Configure Litestar app
    set_bot_application(application, settings.webhook_secret)
    litestar_app = create_litestar_app()

    # Run Litestar
    config = uvicorn.Config(
        app=litestar_app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        logger.info("Shutting down...")
        await application.stop()
        await application.shutdown()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
