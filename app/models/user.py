from sqlmodel import Field, SQLModel


class WhitelistUser(SQLModel, table=True):
    __tablename__ = "whitelist_users"

    id: int | None = Field(default=None, primary_key=True)
    telegram_id: int = Field(unique=True, index=True)
    username: str = Field(default="")


class TranslateWhitelistUser(SQLModel, table=True):
    __tablename__ = "translate_whitelist_users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    admin_chat_id: int = Field(index=True)


class TranslationSettings(SQLModel, table=True):
    __tablename__ = "translation_settings"

    id: int | None = Field(default=None, primary_key=True)
    admin_chat_id: int = Field(unique=True, index=True)
    enabled: bool = Field(default=True)
