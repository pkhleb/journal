class TestUpdateEntryValidation:
    async def test_patch_cannot_blank_an_entry(self, auth_client):
        res = await auth_client.post("/api/entries", json={"prose": "hello"})
        entry_id = res.json()["id"]

        res = await auth_client.patch(f"/api/entries/{entry_id}", json={})
        assert res.status_code == 400

        res = await auth_client.patch(f"/api/entries/{entry_id}", json={"prose": ""})
        assert res.status_code == 400

        entries = (await auth_client.get("/api/entries")).json()
        assert entries[0]["prose"] == "hello"

    async def test_patch_with_prose_only_still_works(self, auth_client):
        res = await auth_client.post("/api/entries", json={"prose": "hello"})
        res = await auth_client.patch(f"/api/entries/{res.json()['id']}", json={"prose": "bye"})
        assert res.status_code == 200
