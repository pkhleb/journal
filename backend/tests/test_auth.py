import pytest

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
        await client.post("/api/users/register", json={
            "email": "second@example.com",
            "username": "sameuser",
            "password": "password123"
        })
        assert res.status_code == 403
        
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
        assert res.status_code == 423

class TestProtectedRoutes:
    async def test_no_token_rejected(self, client):
        res = await client.get("/api/entries/")
        assert res.status_code == 401

    async def test_invalid_token_rejected(self, client):
        client.headers.update({"Authorization": "Bearer faketoken"})
        res = await client.get("/api/entries/")
        assert res.status_code == 401
