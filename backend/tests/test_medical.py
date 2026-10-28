import pytest


@pytest.fixture
def base(patient):
    return f"/api/patients/{patient['id']}"


def test_anamnesis_correction_requires_reason(client, base):
    r = client.post(f"{base}/anamneses", json={"recorded_on": "2026-01-02", "chief_complaint": "LWS-Schmerz", "pain_current": 6, "red_flags": ["night_pain"]})
    assert r.status_code == 201, r.text
    a = r.json()
    body = {**a, "pain_current": 4}
    body.pop("correction_reason", None)
    assert client.put(f"{base}/anamneses/{a['id']}", json=body).status_code == 422
    r = client.put(f"{base}/anamneses/{a['id']}", json={**body, "correction_reason": "Tippfehler"})
    assert r.status_code == 200 and r.json()["pain_current"] == 4
    entry = client.get(f"{base}/history").json()[0]
    assert entry["action"] == "correct" and entry["reason"] == "Tippfehler"
    assert entry["changes"] == {"pain_current": {"old": 6, "new": 4}}


def test_anamnesis_validation(client, base):
    assert client.post(f"{base}/anamneses", json={"recorded_on": "2026-01-02", "chief_complaint": "x", "pain_current": 11}).status_code == 422
    assert client.post(f"{base}/anamneses", json={"recorded_on": "2026-01-02", "chief_complaint": "x", "red_flags": ["foo"]}).status_code == 422


def test_single_primary_diagnosis(client, base):
    d1 = client.post(f"{base}/diagnoses", json={"description": "Lumbalgie", "icd10_code": " m54.5 ", "is_primary": True}).json()
    assert d1["icd10_code"] == "M54.5"
    client.post(f"{base}/diagnoses", json={"description": "Zervikalsyndrom", "is_primary": True})
    primaries = [d for d in client.get(f"{base}/diagnoses").json() if d["is_primary"]]
    assert [d["description"] for d in primaries] == ["Zervikalsyndrom"]


def test_treatment_lifecycle(client, base):
    diag = client.post(f"{base}/diagnoses", json={"description": "Lumbalgie"}).json()
    t = client.post(f"{base}/treatments", json={"treated_on": "2026-01-05", "diagnosis_id": diag["id"], "measures": ["Manuelle Therapie (MT)"], "subjective": "besser"}).json()
    assert t["status"] == "draft"

    # Entwurf frei änderbar, dann abschließen
    body = {**t, "objective": "ROM frei", "finalize": True}
    t = client.put(f"{base}/treatments/{t['id']}", json=body).json()
    assert t["status"] == "final" and t["finalized_at"]

    # Abgeschlossene Behandlung nur mit Begründung korrigierbar
    body = {**t, "objective": "ROM endgradig eingeschränkt"}
    assert client.put(f"{base}/treatments/{t['id']}", json=body).status_code == 422
    r = client.put(f"{base}/treatments/{t['id']}", json={**body, "correction_reason": "Befund präzisiert"})
    assert r.status_code == 200
    assert client.get(f"{base}/history").json()[0]["action"] == "correct"

    # Stornieren statt löschen
    r = client.post(f"{base}/treatments/{t['id']}/void", json={"reason": "Falscher Patient"})
    assert r.json()["voided"] is True
    assert client.put(f"{base}/treatments/{t['id']}", json={**body, "correction_reason": "x"}).status_code == 409
    assert len(client.get(f"{base}/treatments").json()) == 1


def test_treatment_rejects_foreign_diagnosis(client, base, admin):
    other = client.post("/api/patients", json={"first_name": "Max", "last_name": "Muster", "birth_date": "1980-01-01"}).json()
    foreign = client.post(f"/api/patients/{other['id']}/diagnoses", json={"description": "x"}).json()
    r = client.post(f"{base}/treatments", json={"treated_on": "2026-01-05", "diagnosis_id": foreign["id"]})
    assert r.status_code == 422


def test_entry_of_other_patient_not_found(client, base, admin):
    other = client.post("/api/patients", json={"first_name": "Max", "last_name": "Muster", "birth_date": "1980-01-01"}).json()
    d = client.post(f"/api/patients/{other['id']}/diagnoses", json={"description": "x"}).json()
    assert client.post(f"{base}/diagnoses/{d['id']}/void", json={"reason": "x"}).status_code == 404
