"""Shared test configuration for studio backend tests."""

import os

import pytest

# A-REG4: Enable test-mode fallback for ensure_admin_user so tests that
# create the FastAPI app don't need EQ_ADMIN_PASSWORD set explicitly.
os.environ.setdefault("EQ_STUDIO_TESTING", "1")


@pytest.fixture(autouse=True, scope="session")
def _enable_registration_globally():
    """Enable registration for all tests (Module E default is disabled)."""
    import studio_api.config as cfg

    original = cfg.settings.allow_registration
    cfg.settings.allow_registration = True
    yield
    cfg.settings.allow_registration = original


@pytest.fixture
async def auth_client(tmp_path):
    """Shared test client with a fresh SQLite DB.

    Also enables registration by default (most auth tests expect it).
    """
    from httpx import ASGITransport, AsyncClient

    import studio_api.config as cfg
    import studio_api.db as db_mod
    from studio_api.models import Base

    # Enable registration and a known invite code for tests
    cfg.settings.allow_registration = True
    cfg.settings.require_invite_code = False
    cfg.settings.valid_invite_codes = ["TESTCODE"]
    cfg.settings.max_login_attempts = 5
    cfg.settings.lockout_duration_sec = 2  # short for tests
    cfg.settings.max_sessions_per_user = 10  # high default to avoid interference
    cfg.settings.auto_revoke_oldest_session = True

    tmp_db = f"sqlite+aiosqlite:///{tmp_path}/test_auth.sqlite3"
    cfg.settings.database_url = tmp_db

    new_engine = db_mod.create_async_engine(tmp_db, echo=False)
    db_mod.engine = new_engine
    db_mod.SessionLocal = db_mod.async_sessionmaker(
        new_engine, class_=db_mod.AsyncSession, expire_on_commit=False
    )

    async with new_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from studio_api.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await new_engine.dispose()
