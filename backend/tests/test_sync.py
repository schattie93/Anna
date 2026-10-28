import base64
import io
from datetime import date, datetime, timezone

from PIL import Image


def png_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def op(kind, pid, op_id, data, temp_id=None):
    return {"op_id": op_id, "kind": kind, "patient_id": pid, "temp_id": temp_id, "client_time": datetime.now(timezone.utc).isoformat(), "data": data}


def test_offline_batch_with_dependent_entries(client, patient):
    pid = patient["id"]
    today = date.today().isoformat()
    ops = [
        op("create_treatment", pid, "op-treatment-1", {"treated_on": today, "subjective": "offline erfasst", "measures": ["Krankengymnastik (KG)"], "finalize": True}, temp_id=-1001),
        op("create_finding", pid, "op-finding-1", {"recorded_on": today, "category": "rom", "name": "Knie (Extension/Flexion)", "value_num": 120, "value_opposite": 0, "value_neutral": 0, "unit": "°", "treatment_id": -1001}),
        op("sign_treatment", pid, "op-sign-1", {"treatment_id": -1001, "png_base64": png_b64()}),
        op("create_body_mark", pid, "op-mark-1", {"recorded_on": today, "view": "front", "x": 0.4, "y": 0.6, "kind": "pain", "intensity": 5}),
        op("create_examination", pid, "op-exam-1", {"recorded_on": today, "inspection": "Schwellung"}),
        op("create_anamnesis", pid, "op-anam-1", {"recorded_on": today, "chief_complaint": "Knie", "red_flags": ["night_pain"]}),
    ]
    r = client.post("/api/sync", json={"ops": ops})
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert all(x["ok"] for x in results), results
    treatment_id = results[0]["real_id"]
    assert treatment_id and treatment_id > 0

    treatments = client.get(f"/api/patients/{pid}/treatments").json()
    assert treatments[0]["id"] == treatment_id and treatments[0]["status"] == "final" and treatments[0]["signed"] is True
    finding = client.get(f"/api/patients/{pid}/findings").json()[0]
    assert finding["treatment_id"] == treatment_id and finding["value_opposite"] == 0
    # Herkunft im Protokoll: offline erfasst, mit Zeitpunkt der Erfassung
    history = client.get(f"/api/patients/{pid}/history").json()
    sync_entries = [h for h in history if h["action"] == "sync"]
    assert len(sync_entries) == 6 and sync_entries[0]["changes"]["offline_erfasst_am"]


def test_sync_is_idempotent(client, patient):
    pid = patient["id"]
    body = {"ops": [op("create_treatment", pid, "op-idem-0001", {"treated_on": date.today().isoformat()}, temp_id=-5)]}
    first = client.post("/api/sync", json=body).json()["results"][0]
    again = client.post("/api/sync", json=body).json()["results"][0]  # Antwort ging verloren, Tablet sendet erneut
    assert first["ok"] and again["ok"] and first["real_id"] == again["real_id"]
    assert len(client.get(f"/api/patients/{pid}/treatments").json()) == 1
    # Spätere Übertragung darf auf die frühere vorläufige Kennung verweisen (andere Charge)
    later = client.post("/api/sync", json={"ops": [op("create_finding", pid, "op-idem-0002", {"recorded_on": date.today().isoformat(), "category": "measure", "name": "Gehstrecke", "value_num": 300, "unit": "m", "treatment_id": -5})]})
    assert later.json()["results"][0]["ok"] is True


def test_errors_are_reported_per_operation(client, patient):
    pid = patient["id"]
    ops = [
        op("create_finding", pid, "op-bad-0001", {"recorded_on": date.today().isoformat(), "category": "test", "name": "Lasègue", "value_text": "vielleicht"}),
        op("create_finding", pid, "op-bad-0002", {"recorded_on": date.today().isoformat(), "category": "measure", "name": "x", "value_num": 1, "treatment_id": -999}),
        op("create_treatment", 99999, "op-bad-0003", {"treated_on": date.today().isoformat()}),
        op("create_anamnesis", pid, "op-bad-0004", {"recorded_on": date.today().isoformat(), "chief_complaint": "x", "red_flags": ["gibt_es_nicht"]}),
        op("create_treatment", pid, "op-good-0005", {"treated_on": date.today().isoformat()}),
    ]
    results = client.post("/api/sync", json={"ops": ops}).json()["results"]
    assert [r["ok"] for r in results] == [False, False, False, False, True]  # ein Fehler stoppt die anderen nicht
    assert "Testergebnis" in results[0]["error"] and "nicht übertragen" in results[1]["error"] and "nicht gefunden" in results[2]["error"] and "Unbekannte" in results[3]["error"]
    # Fehlgeschlagene Vorgänge werden gemerkt und beim Wiederholen gleich beantwortet
    again = client.post("/api/sync", json={"ops": ops[:1]}).json()["results"][0]
    assert again["ok"] is False and again["error"] == results[0]["error"]


def test_second_signature_conflicts(client, patient):
    pid = patient["id"]
    t = client.post("/api/sync", json={"ops": [op("create_treatment", pid, "op-sig-0001", {"treated_on": date.today().isoformat(), "finalize": True})]}).json()["results"][0]["real_id"]
    ok = client.post("/api/sync", json={"ops": [op("sign_treatment", pid, "op-sig-0002", {"treatment_id": t, "png_base64": png_b64()})]}).json()["results"][0]
    dup = client.post("/api/sync", json={"ops": [op("sign_treatment", pid, "op-sig-0003", {"treatment_id": t, "png_base64": png_b64()})]}).json()["results"][0]
    assert ok["ok"] and not dup["ok"] and "bereits eine Unterschrift" in dup["error"]
    bad = client.post("/api/sync", json={"ops": [op("sign_treatment", pid, "op-sig-0004", {"treatment_id": t, "png_base64": "%%%"})]}).json()["results"][0]
    assert not bad["ok"]


def test_reception_cannot_sync(client, patient, admin):
    client.post("/api/users", json={"username": "empfang", "full_name": "E E", "password": "noch-ein-passwort", "role": "reception"})
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "empfang", "password": "noch-ein-passwort"})
    assert client.post("/api/sync", json={"ops": []}).status_code == 403


def test_ops_are_per_user(client, patient, admin):
    pid = patient["id"]
    body = {"ops": [op("create_treatment", pid, "same-op-id-1", {"treated_on": date.today().isoformat()}, temp_id=-7)]}
    a = client.post("/api/sync", json=body).json()["results"][0]["real_id"]
    client.post("/api/users", json={"username": "thea", "full_name": "T T", "password": "noch-ein-passwort", "role": "therapist"})
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "thea", "password": "noch-ein-passwort"})
    b = client.post("/api/sync", json=body).json()["results"][0]["real_id"]
    assert a != b  # gleiche op_id bei anderem Benutzer ist ein eigener Vorgang
