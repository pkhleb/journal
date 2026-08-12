import pytest

class TestHealth:
    async def test_health(self, client):
        res = await client.get("/api/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}
