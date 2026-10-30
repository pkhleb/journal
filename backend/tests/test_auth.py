import pytest
from tests.conftest import TestSessionLocal

class TestRegister:
    async def test_register_success(self, client):
        res = await client.post("/api/users/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "password123"
        })
        assert res.status_code == 200
    
    async def test_register_duplicate_email(self, client):
        payload = {
            "email": "dupe@example.com",
            "username": "user1",
            "password": "password123"
        }
        await client.post("/api/users/register", json=payload)
        res = await client.post("/api/users/register", json={
            "email": "dupe@example.com",
            "username": "user2",
            "password": "password123"
        })
        assert res.status_code == 400

    async def test_register_duplicate_username(self, client):
        await client.post("/api/users/register", json={
            "email": "first@example.com",
            "username": "sameuser",
            "password": "password123"
        })
        res = await client.post("/api/users/register", json={
            "email": "second@example.com",
            "username": "sameuser",
            "password": "password123"
        })
        assert res.status_code == 400

    async def test_register_email_and_username_belong_to_different_users(self, client):
        for email, username in [("a@example.com", "usera"), ("b@example.com", "userb")]:
            await client.post("/api/users/register", json={
                "email": email, "username": username, "password": "password123"
            })
        res = await client.post("/api/users/register", json={
            "email": "a@example.com",
            "username": "userb",
            "password": "password123"
        })
        assert res.status_code == 400
        
class TestLogin:
    async def test_login_unverified(self, client):
        await client.post("/api/users/register", json={
            "email": "unverified@example.com",
            "username": "unverified",
            "password": "password123"
        })
        res = await client.post("/api/users/login", data={
            "username": "unverified@example.com",
            "password": "password123"
        })
        assert res.status_code == 403

    async def test_login_verified(self, auth_client):
        res = await auth_client.get("/api/users/me")
        assert res.status_code == 200

    async def test_login_wrong_password(self, client):
        await client.post("/api/users/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "password123"
        })
        from sqlalchemy import update
        from app import models
        async with TestSessionLocal() as db:
            await db.execute(
                update(models.User)
                .where(models.User.email == "test@example.com")
                .values(is_verified=True)
            )
            await db.commit()
        res = await client.post("/api/users/login", data={
            "username": "test@example.com",
            "password": "wrongpassword"
        })
        assert res.status_code == 401

    async def test_login_nonexistent_user(self, client):
        res = await client.post("/api/users/login", data={
            "username": "nobody@example.com",
            "password": "password123"
        })
        assert res.status_code == 401

    async def test_account_lockout(self, client):
        await client.post("/api/users/register", json={
            "email": "lockout@example.com",
            "username": "lockout",
            "password": "password123"
        })
        for _ in range(5):
            await client.post("/api/users/login", data={
                "username": "lockout@example.com",
                "password": "wrongpassword"
            })
        res = await client.post("/api/users/login", data={
            "username": "lockout@example.com",
            "password": "wrongpassword"
        })
        assert res.status_code == 403

class TestProtectedRoutes:
    async def test_no_token_rejected(self, client):
        res = await client.get("/api/entries")
        assert res.status_code == 401

    async def test_invalid_token_rejected(self, client):
        client.headers.update({"Authorization": "Bearer faketoken"})
        res = await client.get("/api/entries")
        assert res.status_code == 401

class TestEmailVerification:
    async def _register(self, client, email="verify@example.com", username="verifyuser"):
        await client.post("/api/users/register", json={
            "email": email,
            "username": username,
            "password": "password123"
        })

    async def _get_user(self, email="verify@example.com"):
        from sqlalchemy import select
        from app import models
        async with TestSessionLocal() as db:
            result = await db.execute(select(models.User).where(models.User.email == email))
            return result.scalar_one()

    async def test_get_does_not_verify(self, client):
        """A GET (e.g. from a mail scanner) must not consume the token."""
        await self._register(client)
        user = await self._get_user()
        res = await client.get("/api/users/verify-email", params={"token": user.verification_token})
        assert res.status_code == 405
        user = await self._get_user()
        assert user.is_verified is False
        assert user.verification_token is not None

    async def test_post_verifies(self, client):
        await self._register(client)
        token = (await self._get_user()).verification_token
        res = await client.post("/api/users/verify-email", params={"token": token})
        assert res.status_code == 200
        user = await self._get_user()
        assert user.is_verified is True
        assert user.verification_token is None

    async def test_post_invalid_token(self, client):
        res = await client.post("/api/users/verify-email", params = {"token": "nope"})
        assert res.status_code == 400
        
    async def test_resend_rotates_token(self, client):
        await self._register(client)
        old = (await self._get_user()).verification_token
        res = await client.post("/api/users/resend-verification", params={"email": "verify@example.com"})
        assert res.status_code == 200
        assert (await self._get_user()).verification_token != old

    async def test_resend_unknown_email_is_silent(self, client):
        res = await client.post("/api/users/resend-verification", params={"email": "ghost@example.com"})
        assert res.status_code == 200
        assert res.json() == {"ok": True}

    async def test_resend_requires_email_param(self, client):
        res = await client.post("/api/users/resend-verification")
        assert res.status_code == 422

