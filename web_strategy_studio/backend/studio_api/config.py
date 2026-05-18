from __future__ import annotations

from pathlib import Path
from typing import List, Optional

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
    # S11: Always resolve artifact_dir to absolute path so subprocess CWD
    # (a temp directory) doesn't break file lookups in backtest_executor.
    artifact_dir: Path = _default_repo_root() / "artifacts"
    public_base_url: str = ""  # optional absolute prefix for generated URLs
    run_timeout_sec: int = 900
    max_memory_mb: int = 2048
    enable_network: bool = False  # documented; subprocess does not enforce firejail in MVP
    repo_root: Path = _default_repo_root()
    api_host: str = "127.0.0.1"
    api_port: int = 8080
    # S1: CORS — restrict to localhost by default; override via env for staging/production.
    # Do NOT use ["*"] together with allow_credentials=True (browser spec disallows it).
    cors_allowed_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]
    # S6: idempotency key TTL in seconds (default 24 h)
    idempotency_ttl_sec: int = 86400
    # B17/B18: concurrency cap (max simultaneous backtest subprocesses)
    max_concurrent_runs: int = 2
    # B18: per-IP rate limit for POST /runs.
    # HIGH-17: these counters are stored in-memory in a single Python dict.
    # They are NOT shared across multiple workers or pods.
    # Multi-worker (e.g. gunicorn --workers N) or multi-pod deployments need a
    # shared backend such as Redis; that is currently NOT implemented.
    rate_limit_runs_per_window: int = 10
    rate_limit_window_sec: int = 300  # 5 minutes
    # B6: SSE ring buffer retention (seconds) after a run reaches terminal state
    sse_buffer_ttl_sec: int = 1800  # 30 minutes
    # B4: coalescing window — edits within this many seconds reuse the current version row
    version_coalesce_sec: int = 60  # 1 minute
    # BLOCKER-8: runner backend — "local" (subprocess, no sandbox) or "docker"
    # (container with --network none --read-only --memory --pids-limit)
    runner: str = "local"


settings = Settings()
