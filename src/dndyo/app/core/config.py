from functools import lru_cache
import os

from pydantic import BaseModel


class Settings(BaseModel):
    mistral_model: str = "mistral-small-latest"
    mistral_api_key: str = "AAA"
    mistral_server_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings(
        mistral_model=os.environ.get("MISTRAL_MODEL", "mistral-small-latest"),
        mistral_api_key=os.environ.get("MISTRAL_API_KEY", "AAA"),
        mistral_server_url=os.environ.get("MISTRAL_SERVER_URL"),
    )
