from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_repo_root() -> Path:
    # .../EasyQuant/web_strategy_studio/backend/studio_api/config.py -> parents[3] == EasyQuant
    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EQ_STUDIO_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./studio.sqlite3"
    redis_url: Optional[str] = None  # reserved for future queue split
    artifact_dir: Path = Path("./artifacts")
    public_base_url: str = ""  # optional absolute prefix for generated URLs
    run_timeout_sec: int = 900
    max_memory_mb: int = 2048
    enable_network: bool = False  # documented; subprocess does not enforce firejail in MVP
    repo_root: Path = _default_repo_root()
    api_host: str = "127.0.0.1"
    api_port: int = 8080


settings = Settings()
