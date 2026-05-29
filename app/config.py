from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./payment_compass.db"
    timezone: str = "Europe/Moscow"
    reminders_enabled: bool = True
    im_back_always_visible: bool = False
    dev_mode: bool = False
    planning_horizon_days: int = 90

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
