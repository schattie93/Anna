def test_create_and_search(client, patient):
    assert patient["patient_number"] == "P00001"
    assert [p["id"] for p in client.get("/api/patients", params={"q": "muster"}).json()] == [patient["id"]]
    assert client.get("/api/patients", params={"q": "erika beispiel"}).json()
    assert client.get("/api/patients", params={"q": "niemand"}).json() == []


def test_future_birth_date_rejected(client, admin):
    r = client.post("/api/patients", json={"first_name": "A", "last_name": "B", "birth_date": "2999-01-01"})
    assert r.status_code == 422


def test_update_is_audited_and_archive_hides(client, patient):
    body = {**patient, "phone": "0000 123456", "archived": True}
    r = client.put(f"/api/patients/{patient['id']}", json=body)
    assert r.status_code == 200 and r.json()["phone"] == "0000 123456"
    history = client.get(f"/api/patients/{patient['id']}/history").json()
    assert history[0]["action"] == "update"
    assert history[0]["changes"]["phone"] == {"old": None, "new": "0000 123456"}
    assert client.get("/api/patients").json() == []
    assert len(client.get("/api/patients", params={"include_archived": True}).json()) == 1


def test_dashboard(client, patient):
    client.get(f"/api/patients/{patient['id']}")
    client.post(f"/api/patients/{patient['id']}/treatments", json={"treated_on": "2026-01-05"})
    d = client.get("/api/dashboard").json()
    assert d["patient_count"] == 1
    assert d["recent_patients"][0]["id"] == patient["id"]
    assert d["open_treatments"][0]["patient"]["last_name"] == "Musterfrau"
