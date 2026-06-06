"""Tests for Module E5 (login lockout) and E6 (session management)."""

from __future__ import annotations

import asyncio

import pytest


class TestLoginLockout:
    """E5: After N failed login attempts, account is locked for M seconds."""

    @pytest.mark.asyncio
    async def test_lockout_after_max_attempts(self, auth_client):
        import studio_api.config as cfg

        # Register a user
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "lockme", "password": "LockMe1!"},
        )

        # Fail N times
        for i in range(cfg.settings.max_login_attempts):
            resp = await auth_client.post(
                "/api/v1/auth/login",
                json={"username": "lockme", "password": "Wrong123!"},
            )
            assert resp.status_code == 401

        # Next attempt should be locked (423)
        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "lockme", "password": "LockMe1!"},
        )
        assert resp.status_code == 423
        assert resp.json()["detail"]["error"]["code"] == "ACCOUNT_LOCKED"

    @pytest.mark.asyncio
    async def test_correct_password_resets_counter(self, auth_client):
        # Register
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "resetcount", "password": "Reset12!"},
        )

        # 3 failed attempts
        for _ in range(3):
            await auth_client.post(
                "/api/v1/auth/login",
                json={"username": "resetcount", "password": "Wrong123!"},
            )

        # Then correct login
        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "resetcount", "password": "Reset12!"},
        )
        assert resp.status_code == 200

        # Counter should be reset — 4 more fails should NOT lock out
        for _ in range(4):
            await auth_client.post(
                "/api/v1/auth/login",
                json={"username": "resetcount", "password": "Wrong123!"},
            )
        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "resetcount", "password": "Reset12!"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_lockout_expires(self, auth_client):
        """After the lockout duration, login should work again."""
        import studio_api.config as cfg

        cfg.settings.lockout_duration_sec = 1  # 1 second for test
        try:
            await auth_client.post(
                "/api/v1/auth/register",
                json={"username": "expire_test", "password": "Expire1!"},
            )
            for _ in range(cfg.settings.max_login_attempts):
                await auth_client.post(
                    "/api/v1/auth/login",
                    json={"username": "expire_test", "password": "Wrong123!"},
                )

            # Should be locked
            resp = await auth_client.post(
                "/api/v1/auth/login",
                json={"username": "expire_test", "password": "Expire1!"},
            )
            assert resp.status_code == 423

            # Wait for lockout to expire
            await asyncio.sleep(1.5)

            # Should be able to login now
            resp = await auth_client.post(
                "/api/v1/auth/login",
                json={"username": "expire_test", "password": "Expire1!"},
            )
            assert resp.status_code == 200
        finally:
            cfg.settings.lockout_duration_sec = 900

    @pytest.mark.asyncio
    async def test_unknown_user_does_not_reveal_lockout(self, auth_client):
        """Logging in with an unknown user shouldn't reveal lockout state."""
        resp = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "ghost_user", "password": "Whatever1!"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"]["code"] == "INVALID_CREDENTIALS"


class TestSessionManagement:
    """E6: Multi-device sessions and force logout."""

    @pytest.mark.asyncio
    async def test_login_creates_session(self, auth_client):
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "sess_user", "password": "Session1!"},
        )
        login = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "sess_user", "password": "Session1!"},
        )
        assert login.status_code == 200
        data = login.json()
        assert "session_id" in data
        assert data["session_id"]

    @pytest.mark.asyncio
    async def test_list_sessions(self, auth_client):
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "list_sess", "password": "ListSess1!"},
        )
        # Login twice to create 2 sessions
        login1 = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "list_sess", "password": "ListSess1!"},
        )
        token1 = login1.json()["access_token"]
        login2 = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "list_sess", "password": "ListSess1!"},
        )
        token2 = login2.json()["access_token"]

        # List sessions
        resp = await auth_client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        # At least 2 active sessions
        assert len(sessions) >= 2
        # The current one should be flagged
        current = [s for s in sessions if s["current"]]
        assert len(current) == 1

    @pytest.mark.asyncio
    async def test_revoke_specific_session(self, auth_client):
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "revoke_one", "password": "Revoke1!"},
        )
        login1 = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "revoke_one", "password": "Revoke1!"},
        )
        sid1 = login1.json()["session_id"]
        token1 = login1.json()["access_token"]

        login2 = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "revoke_one", "password": "Revoke1!"},
        )
        token2 = login2.json()["access_token"]

        # Revoke session 1 from session 2
        resp = await auth_client.post(
            "/api/v1/auth/sessions/revoke",
            json={"session_id": sid1},
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 204

        # Token1 should now be invalid (401 SESSION_REVOKED)
        resp = await auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert resp.status_code == 401
        # Token2 should still work
        resp = await auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_revoke_all_sessions(self, auth_client):
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "revoke_all", "password": "RevokeAll1!"},
        )
        # Create 3 sessions
        tokens = []
        for _ in range(3):
            login = await auth_client.post(
                "/api/v1/auth/login",
                json={"username": "revoke_all", "password": "RevokeAll1!"},
            )
            tokens.append(login.json()["access_token"])

        # Revoke all from the last token
        resp = await auth_client.post(
            "/api/v1/auth/sessions/revoke-all",
            headers={"Authorization": f"Bearer {tokens[-1]}"},
        )
        assert resp.status_code == 204

        # All tokens should now be invalid
        for tok in tokens:
            resp = await auth_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_revokes_current_session(self, auth_client):
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "logout_user", "password": "Logout1!"},
        )
        login = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "logout_user", "password": "Logout1!"},
        )
        token = login.json()["access_token"]

        resp = await auth_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

        # Token should no longer work
        resp = await auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_max_sessions_enforced(self, auth_client):
        """When max_sessions_per_user is exceeded, oldest are revoked."""
        import asyncio
        import studio_api.config as cfg

        original_limit = cfg.settings.max_sessions_per_user
        cfg.settings.max_sessions_per_user = 2
        try:
            await auth_client.post(
                "/api/v1/auth/register",
                json={"username": "max_sess", "password": "MaxSess1!"},
            )
            tokens = []
            for _ in range(4):
                # Small delay to ensure distinct created_at timestamps
                await asyncio.sleep(0.01)
                login = await auth_client.post(
                    "/api/v1/auth/login",
                    json={"username": "max_sess", "password": "MaxSess1!"},
                )
                tokens.append(login.json()["access_token"])

            # Check how many tokens are still valid
            valid_count = 0
            revoked_count = 0
            for tok in tokens:
                resp = await auth_client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {tok}"},
                )
                if resp.status_code == 200:
                    valid_count += 1
                else:
                    revoked_count += 1

            # With limit=2, exactly 2 should be valid and 2 revoked
            assert valid_count == 2, f"Expected 2 valid tokens, got {valid_count}"
            assert revoked_count == 2, f"Expected 2 revoked tokens, got {revoked_count}"
        finally:
            cfg.settings.max_sessions_per_user = original_limit

    @pytest.mark.asyncio
    async def test_admin_force_logout(self, auth_client):
        """Admin can revoke all sessions of another user."""
        # Register target user
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "target", "password": "Target1!"},
        )
        login = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "target", "password": "Target1!"},
        )
        target_token = login.json()["access_token"]

        # Seed admin
        from studio_api.auth import ensure_admin_user
        import studio_api.db as db_mod

        async with db_mod.SessionLocal() as session:
            await ensure_admin_user(session)

        admin_login = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
        admin_token = admin_login.json()["access_token"]

        # Admin force-logs out target (user_id is "user_target")
        resp = await auth_client.post(
            "/api/v1/admin/users/user_target/force-logout",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 204

        # Target token should now be invalid
        resp = await auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {target_token}"},
        )
        assert resp.status_code == 401
