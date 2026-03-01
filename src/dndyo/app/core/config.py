from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mistral_model: str = "mistral-small-latest"
    mistral_api_key: str = "AAA"
    mistral_server_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
