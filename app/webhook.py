"""Litestar-based webhook server for the Telegram bot."""

import logging

from litestar import Litestar, Request, post, get
from litestar.response import Response
from telegram import Update

logger = logging.getLogger(__name__)

# These will be set by main.py before the app starts
_application = None
_webhook_secret = ""


def set_bot_application(application, webhook_secret: str) -> None:
    global _application, _webhook_secret
    _application = application
    _webhook_secret = webhook_secret


@get("/health")
async def health() -> dict:
    return {"status": "ok"}


@post("/webhook")
async def webhook_handler(request: Request) -> Response:
    if _application is None:
        return Response(content={"error": "Bot not initialized"}, status_code=503)

    # Verify webhook secret if configured
    if _webhook_secret:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != _webhook_secret:
            return Response(content={"error": "Unauthorized"}, status_code=403)

    data = await request.json()
    update = Update.de_json(data=data, bot=_application.bot)
    await _application.process_update(update)
    return Response(content=None, status_code=200)


def create_litestar_app() -> Litestar:
    return Litestar(
        route_handlers=[health, webhook_handler],
        debug=False,
    )
