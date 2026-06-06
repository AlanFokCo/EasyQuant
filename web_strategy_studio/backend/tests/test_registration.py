"""Tests for Module E2/E3: registration control and password strength."""

from __future__ import annotations

import pytest

from studio_api.auth import validate_password_strength


# ── Password strength unit tests ─────────────────────────────────────────────
class TestPasswordStrength:
    """Test password strength validation (bypasses test mode)."""

    def setup_method(self):
        import os
        self._orig = os.environ.get("EQ_STUDIO_TESTING")
        os.environ["EQ_STUDIO_TESTING"] = "0"

    def teardown_method(self):
        import os
        if self._orig is None:
            os.environ.pop("EQ_STUDIO_TESTING", None)
        else:
            os.environ["EQ_STUDIO_TESTING"] = self._orig

    def test_valid_strong_password(self):
        assert validate_password_strength("Strong1!") == []

    def test_valid_long_password(self):
        assert validate_password_strength("MyS3cretPassw0rd!@#") == []

    def test_too_short(self):
        issues = validate_password_strength("Ab1!")
        assert any("8 characters" in i for i in issues)

    def test_missing_uppercase(self):
        issues = validate_password_strength("nouppercase1!")
        assert any("uppercase" in i for i in issues)

    def test_missing_lowercase(self):
        issues = validate_password_strength("NOLOWERCASE1!")
        assert any("lowercase" in i for i in issues)

    def test_missing_digit(self):
        issues = validate_password_strength("NoDigitsHere!")
        assert any("digit" in i for i in issues)

    def test_missing_special(self):
        issues = validate_password_strength("NoSpecial1")
        assert any("special" in i for i in issues)

    def test_all_issues_reported(self):
        issues = validate_password_strength("a")
        # Should have issues for length, uppercase, digit, special (at least 4)
        assert len(issues) >= 4


# ── Registration endpoint tests ──────────────────────────────────────────────
class TestRegistrationControl:
    @pytest.mark.asyncio
    async def test_registration_disabled_returns_403(self, auth_client):
        """When allow_registration=False, registration returns 403."""
        import studio_api.config as cfg

        cfg.settings.allow_registration = False
        try:
            resp = await auth_client.post(
                "/api/v1/auth/register",
                json={
                    "username": "blocked",
                    "password": "Strong1!",
                },
            )
            assert resp.status_code == 403
            assert resp.json()["detail"]["error"]["code"] == "REGISTRATION_DISABLED"
        finally:
            cfg.settings.allow_registration = True

    @pytest.mark.asyncio
    async def test_weak_password_returns_422(self, auth_client):
        """Password that fails strength validation is rejected."""
        import os

        # Disable test mode so password validation is enforced
        orig = os.environ.get("EQ_STUDIO_TESTING")
        os.environ["EQ_STUDIO_TESTING"] = "0"
        try:
            resp = await auth_client.post(
                "/api/v1/auth/register",
                json={
                    "username": "weakpwd",
                    "password": "weak",
                },
            )
            assert resp.status_code == 422
        finally:
            if orig is None:
                os.environ.pop("EQ_STUDIO_TESTING", None)
            else:
                os.environ["EQ_STUDIO_TESTING"] = orig

    @pytest.mark.asyncio
    async def test_strong_password_accepted(self, auth_client):
        resp = await auth_client.post(
            "/api/v1/auth/register",
            json={
                "username": "strong_user",
                "password": "StrongPass1!",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "strong_user"
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_invite_code_required(self, auth_client):
        """When require_invite_code=True, missing code is rejected."""
        import studio_api.config as cfg

        cfg.settings.require_invite_code = True
        try:
            resp = await auth_client.post(
                "/api/v1/auth/register",
                json={
                    "username": "invite_user",
                    "password": "Strong1!",
                },
            )
            assert resp.status_code == 400
            assert resp.json()["detail"]["error"]["code"] == "INVITE_CODE_REQUIRED"
        finally:
            cfg.settings.require_invite_code = False

    @pytest.mark.asyncio
    async def test_invalid_invite_code(self, auth_client):
        import studio_api.config as cfg

        cfg.settings.require_invite_code = True
        cfg.settings.valid_invite_codes = ["VALIDCODE"]
        try:
            resp = await auth_client.post(
                "/api/v1/auth/register",
                json={
                    "username": "invite_bad",
                    "password": "Strong1!",
                    "invite_code": "WRONG",
                },
            )
            assert resp.status_code == 400
            assert resp.json()["detail"]["error"]["code"] == "INVITE_CODE_INVALID"
        finally:
            cfg.settings.require_invite_code = False

    @pytest.mark.asyncio
    async def test_valid_invite_code_accepted(self, auth_client):
        import studio_api.config as cfg

        cfg.settings.require_invite_code = True
        cfg.settings.valid_invite_codes = ["VALIDCODE"]
        try:
            resp = await auth_client.post(
                "/api/v1/auth/register",
                json={
                    "username": "invite_ok",
                    "password": "Strong1!",
                    "invite_code": "VALIDCODE",
                },
            )
            assert resp.status_code == 201
        finally:
            cfg.settings.require_invite_code = False

    @pytest.mark.asyncio
    async def test_duplicate_username_409(self, auth_client):
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "dupreg", "password": "First123!"},
        )
        resp = await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "dupreg", "password": "Second456!"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "USERNAME_TAKEN"
