import logging

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import Settings
from app.models.user import WhitelistUser

logger = logging.getLogger(__name__)


def is_admin(username: str | None, settings: Settings) -> bool:
    if not username:
        return False
    return username.lower() == settings.admin_username.lower()


async def is_allowed(
    telegram_id: int,
    username: str | None,
    settings: Settings,
    session: AsyncSession,
) -> bool:
    if is_admin(username, settings):
        return True
    result = await session.exec(
        select(WhitelistUser).where(WhitelistUser.telegram_id == telegram_id)
    )
    return result.first() is not None


async def add_to_whitelist(
    telegram_id: int, username: str, session: AsyncSession
) -> bool:
    existing = await session.exec(
        select(WhitelistUser).where(WhitelistUser.telegram_id == telegram_id)
    )
    if existing.first():
        return False
    user = WhitelistUser(telegram_id=telegram_id, username=username)
    session.add(user)
    await session.commit()
    return True


async def remove_from_whitelist(
    telegram_id: int, session: AsyncSession
) -> bool:
    result = await session.exec(
        select(WhitelistUser).where(WhitelistUser.telegram_id == telegram_id)
    )
    user = result.first()
    if not user:
        return False
    await session.delete(user)
    await session.commit()
    return True


async def get_whitelist(session: AsyncSession) -> list[WhitelistUser]:
    result = await session.exec(select(WhitelistUser))
    return list(result.all())
