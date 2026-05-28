"""Tests for BLOCKER-7 (auth + JWT)."""

import datetime

import jwt
import pytest


class TestJwtToken:
    """Test JWT token creation and verification."""

    def test_create_and_decode_token(self):
        from studio_api.auth import create_access_token, decode_access_token

        user_id = "user_test"
        token = create_access_token(user_id, expires_minutes=60)
        payload = decode_access_token(token)
        assert payload["sub"] == user_id

    def test_expired_token_raises(self):
        from studio_api.auth import JWT_ALGORITHM, JWT_SECRET

        # Create an already-expired token
        exp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        token = jwt.encode({"sub": "user_test", "exp": exp}, JWT_SECRET, algorithm=JWT_ALGORITHM)

        from studio_api.auth import decode_access_token

        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_invalid_token_raises(self):
        from studio_api.auth import decode_access_token

        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token("invalid.token.here")


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_and_verify(self):
        from studio_api.auth import hash_password, verify_password

        plain = "my_secure_password"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)

    def test_wrong_password_fails(self):
        from studio_api.auth import hash_password, verify_password

        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        from studio_api.auth import hash_password

        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        # bcrypt includes random salt, so hashes should differ
        assert h1 != h2


class TestAuthEndpoints:
    """Test the /auth endpoints using httpx + FastAPI TestClient."""

    @pytest.fixture
    async def client(self, tmp_path):
        """Create a test client with a fresh SQLite DB in tmp_path."""
        from httpx import ASGITransport, AsyncClient

        import studio_api.config as cfg
        import studio_api.db as db_mod
        from studio_api.models import Base

        tmp_db = f"sqlite+aiosqlite:///{tmp_path}/test_auth.sqlite3"
        cfg.settings.database_url = tmp_db

        # Recreate engine for the new DB
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

    @pytest.mark.asyncio
    async def test_register_returns_token(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "password": "secret123",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_login_with_correct_credentials(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "loginuser",
                "password": "secret456",
            },
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "loginuser",
                "password": "secret456",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_login_with_wrong_password(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "wronguser",
                "password": "correct",
            },
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "wronguser",
                "password": "wrong",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "dup_user",
                "password": "pass1",
            },
        )
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "dup_user",
                "password": "pass2",
            },
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_me_endpoint(self, client):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "meuser",
                "password": "passme",
            },
        )
        token = reg.json()["access_token"]
        resp = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "meuser"
