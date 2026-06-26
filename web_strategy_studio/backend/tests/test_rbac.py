"""Tests for Module E4: Role-Based Access Control (RBAC)."""

from __future__ import annotations

import pytest

from studio_api.auth import (
    ROLE_ADMIN,
    ROLE_GUEST,
    ROLE_USER,
    has_permission,
)


class TestRolePermissions:
    """Unit tests for role → permission mapping."""

    def test_admin_has_all_permissions(self):
        for perm in ("read", "write", "execute", "delete", "admin"):
            assert has_permission(ROLE_ADMIN, perm)

    def test_user_has_standard_permissions(self):
        for perm in ("read", "write", "execute"):
            assert has_permission(ROLE_USER, perm)
        assert not has_permission(ROLE_USER, "delete")
        assert not has_permission(ROLE_USER, "admin")

    def test_guest_can_only_read(self):
        assert has_permission(ROLE_GUEST, "read")
        assert not has_permission(ROLE_GUEST, "write")
        assert not has_permission(ROLE_GUEST, "execute")

    def test_unknown_role_has_no_permissions(self):
        assert not has_permission("nonexistent", "read")


class TestRBACMiddleware:
    """Test require_permission / require_role dependencies via HTTP."""

    @pytest.mark.asyncio
    async def test_me_returns_role_and_permissions(self, auth_client):
        reg = await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "rbac_user", "password": "RbacPass1!"},
        )
        token = reg.json()["access_token"]
        resp = await auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "user"
        # Default user role should grant read/write/execute
        assert "read" in data["permissions"]
        assert "write" in data["permissions"]
        assert "execute" in data["permissions"]
        assert "admin" not in data["permissions"]

    @pytest.mark.asyncio
    async def test_admin_endpoint_requires_admin(self, auth_client):
        """A non-admin user cannot access admin-only endpoints."""
        reg = await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "notadmin", "password": "NotAdmin1!"},
        )
        token = reg.json()["access_token"]
        resp = await auth_client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"]["code"] == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_admin_can_list_users(self, auth_client):
        """The seeded admin user can access admin endpoints."""
        # Seed the admin user
        import studio_api.db as db_mod
        from studio_api.auth import ensure_admin_user

        async with db_mod.SessionLocal() as session:
            await ensure_admin_user(session)

        # Login as admin
        login = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        assert login.json()["role"] == "admin"

        resp = await auth_client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert "admin" in usernames

    @pytest.mark.asyncio
    async def test_admin_can_change_user_role(self, auth_client):
        # Register a normal user
        reg = await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "promote_me", "password": "Promote1!"},
        )
        user_id = reg.json()["user_id"]

        # Login as admin
        import studio_api.db as db_mod
        from studio_api.auth import ensure_admin_user

        async with db_mod.SessionLocal() as session:
            await ensure_admin_user(session)

        login = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
        admin_token = login.json()["access_token"]

        # Promote the user to admin
        resp = await auth_client.patch(
            f"/api/v1/admin/users/{user_id}/role",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    @pytest.mark.asyncio
    async def test_invalid_role_rejected(self, auth_client):
        # Login as admin
        import studio_api.db as db_mod
        from studio_api.auth import ensure_admin_user

        async with db_mod.SessionLocal() as session:
            await ensure_admin_user(session)

        login = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
        admin_token = login.json()["access_token"]

        resp = await auth_client.patch(
            "/api/v1/admin/users/admin/role",
            json={"role": "superuser"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_non_admin_cannot_change_role(self, auth_client):
        # Register two normal users
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "attacker", "password": "Attack1!"},
        )
        await auth_client.post(
            "/api/v1/auth/register",
            json={"username": "victim", "password": "Victim1!"},
        )
        login = await auth_client.post(
            "/api/v1/auth/login",
            json={"username": "attacker", "password": "Attack1!"},
        )
        token = login.json()["access_token"]

        resp = await auth_client.patch(
            "/api/v1/admin/users/victim/role",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
