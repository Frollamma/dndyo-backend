from functools import lru_cache
from pathlib import Path

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
    
    # Image storage configuration
    images_dir: str = "images"  # Directory to store generated images
    
    @property
    def images_path(self) -> Path:
        """Get the images directory path, creating it if needed."""
        path = Path(self.images_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
