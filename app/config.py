from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str
    admin_username: str

    database_url: str  # e.g. postgresql+asyncpg://user:pass@host:5432/dbname

    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"

    webhook_domain: str = "tg-assistant.f-f.dev"
    webhook_path: str = "/webhook"
    webhook_secret: str = ""

    host: str = "0.0.0.0"
    port: int = 8080

    @property
    def webhook_url(self) -> str:
        return f"https://{self.webhook_domain}{self.webhook_path}"

    model_config = {"env_prefix": "BOT_"}
