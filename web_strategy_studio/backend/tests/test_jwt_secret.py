"""Tests for Module E1: JWT Secret persistence."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock


def _clear_env():
    return mock.patch.dict(os.environ, {}, clear=False)


def test_env_var_takes_precedence(tmp_path: Path):
    """If EQ_JWT_SECRET is set, it is used directly and no file is written."""
    from studio_api import auth as auth_mod

    fake_file = tmp_path / ".jwt_secret"
    with mock.patch.object(auth_mod, "_JWT_SECRET_FILE", fake_file), _clear_env():
        os.environ["EQ_JWT_SECRET"] = "env-secret-value"
        secret = auth_mod._get_or_create_jwt_secret()
        assert secret == "env-secret-value"
        assert not fake_file.exists()
        del os.environ["EQ_JWT_SECRET"]


def test_reads_from_persisted_file(tmp_path: Path):
    """If the file exists and no env var, return the file contents."""
    from studio_api import auth as auth_mod

    fake_file = tmp_path / ".jwt_secret"
    fake_file.write_text("file-stored-secret\n", encoding="utf-8")
    with mock.patch.object(auth_mod, "_JWT_SECRET_FILE", fake_file), _clear_env():
        os.environ.pop("EQ_JWT_SECRET", None)
        secret = auth_mod._get_or_create_jwt_secret()
        assert secret == "file-stored-secret"


def test_generates_and_persists_when_missing(tmp_path: Path):
    """If neither env nor file, a new secret is generated and written."""
    from studio_api import auth as auth_mod

    fake_file = tmp_path / ".jwt_secret"
    with mock.patch.object(auth_mod, "_JWT_SECRET_FILE", fake_file), _clear_env():
        os.environ.pop("EQ_JWT_SECRET", None)
        secret1 = auth_mod._get_or_create_jwt_secret()

        # 32 bytes → 64-char hex string
        assert len(secret1) == 64
        assert fake_file.is_file()
        assert fake_file.read_text(encoding="utf-8").strip() == secret1

        # Second call returns the SAME persisted secret (stability)
        secret2 = auth_mod._get_or_create_jwt_secret()
        assert secret2 == secret1


def test_empty_file_triggers_regeneration(tmp_path: Path):
    """An empty / whitespace-only file is treated as missing."""
    from studio_api import auth as auth_mod

    fake_file = tmp_path / ".jwt_secret"
    fake_file.write_text("   \n", encoding="utf-8")
    with mock.patch.object(auth_mod, "_JWT_SECRET_FILE", fake_file), _clear_env():
        os.environ.pop("EQ_JWT_SECRET", None)
        secret = auth_mod._get_or_create_jwt_secret()
        assert len(secret) == 64
        # File now contains the new secret (not whitespace)
        assert fake_file.read_text(encoding="utf-8").strip() == secret


def test_jwt_module_secret_is_string():
    """The module-level JWT_SECRET is a non-empty string."""
    from studio_api.auth import JWT_SECRET

    assert isinstance(JWT_SECRET, str)
    assert len(JWT_SECRET) > 0


def test_token_uses_module_secret():
    """Tokens created via create_access_token can be decoded with JWT_SECRET."""
    import jwt as pyjwt

    from studio_api.auth import JWT_ALGORITHM, JWT_SECRET, create_access_token, decode_access_token

    token = create_access_token("user_test", expires_minutes=30)
    payload = decode_access_token(token)
    assert payload["sub"] == "user_test"
    # Also decode with the same secret to prove consistency
    payload2 = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload2["sub"] == "user_test"
