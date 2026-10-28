import io
import json
import zipfile
from datetime import date, datetime, timedelta, timezone

import pytest
from PIL import Image

from app import storage
from app.db import get_db
from app.main import app
from app.models import Attachment, Patient, UserSession


def db_session():
    return next(app.dependency_overrides[get_db]())


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (9, 9, 9)).save(buf, "PNG")
    return buf.getvalue()


def test_security_headers(client):
    r = client.get("/api/health")
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "script-src 'self'" in csp
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"


def test_pdfs_are_served_without_csp_so_browser_viewer_works(client, base, patient):
    r = client.post(f"{base}/report.pdf", json={})
    assert r.headers["content-type"] == "application/pdf" and "content-security-policy" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


def test_idle_session_is_closed(client, admin):
    assert client.get("/api/patients").status_code == 200
    db = db_session()
    s = db.query(UserSession).one()
    s.last_seen = datetime.now(timezone.utc) - timedelta(minutes=61)
    db.commit()
    assert client.get("/api/patients").status_code == 401
    assert db_session().query(UserSession).count() == 0  # abgelaufene Sitzung gelöscht


def test_activity_keeps_session_alive(client, admin):
    db = db_session()
    s = db.query(UserSession).one()
    s.last_seen = datetime.now(timezone.utc) - timedelta(minutes=30)
    db.commit()
    assert client.get("/api/patients").status_code == 200
    refreshed = db_session().query(UserSession).one().last_seen
    assert datetime.now(timezone.utc) - refreshed.replace(tzinfo=timezone.utc) < timedelta(minutes=1)


def test_logout_all_ends_every_session(client, admin):
    client.post("/api/auth/login", json={"username": "admin", "password": "geheim-genug-123"})  # zweite Sitzung
    assert db_session().query(UserSession).count() == 2
    assert client.post("/api/auth/logout-all").status_code == 204
    assert db_session().query(UserSession).count() == 0
    assert client.get("/api/patients").status_code == 401


def test_export_zip_contains_record_and_files(client, base, patient):
    client.post(f"{base}/diagnoses", json={"description": "Lumbalgie", "icd10_code": "M54.5"})
    client.post(f"{base}/treatments", json={"treated_on": date.today().isoformat(), "finalize": True, "subjective": "besser"})
    a = client.post(f"{base}/attachments", data={"kind": "photo", "caption": "Foto"}, files={"file": ("f.png", png(), "image/png")}).json()
    r = client.get(f"{base}/export.zip")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    data = json.loads(z.read("akte.json"))
    assert data["patient"]["last_name"] == "Musterfrau" and data["diagnoses"][0]["icd10_code"] == "M54.5"
    assert data["treatments"][0]["subjective"] == "besser" and "password_hash" not in json.dumps(data)
    names = z.namelist()
    assert "LIESMICH.txt" in names and any(n.startswith(f"dateien/{a['id']}_") for n in names)
    assert data["attachments"][0]["archive_path"] in names


def test_export_requires_medical_role(client, base, admin):
    client.post("/api/users", json={"username": "empfang", "full_name": "E E", "password": "noch-ein-passwort", "role": "reception"})
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "empfang", "password": "noch-ein-passwort"})
    assert client.get(f"{base}/export.zip").status_code == 403


def full_patient(client, base):
    pid = int(base.rsplit("/", 1)[1])
    client.post(f"{base}/diagnoses", json={"description": "Lumbalgie"})
    rx = client.post(f"{base}/prescriptions", json={"issued_on": date.today().isoformat(), "measure": "KG", "total_units": 3}).json()
    t = client.post(f"{base}/treatments", json={"treated_on": date.today().isoformat(), "finalize": True, "prescription_id": rx["id"]}).json()
    client.post(f"{base}/findings", json={"recorded_on": date.today().isoformat(), "category": "rom", "name": "HWS Rotation", "value_num": 60, "treatment_id": t["id"]})
    client.post(f"{base}/body-marks", json={"recorded_on": date.today().isoformat(), "view": "front", "x": 0.4, "y": 0.4})
    client.post(f"{base}/goals", json={"description": "Gehen"})
    client.post(f"{base}/anamneses", json={"recorded_on": date.today().isoformat(), "chief_complaint": "Rücken"})
    att = client.post(f"{base}/attachments", data={"kind": "photo", "treatment_id": t["id"]}, files={"file": ("f.png", png(), "image/png")}).json()
    client.post(f"{base}/follow-ups", json={"due_on": date.today().isoformat(), "text": "x"})
    client.post("/api/appointments", json={"patient_id": pid, "prescription_id": rx["id"], "start": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(), "duration_minutes": 30})
    svc = client.post("/api/services", json={"name": "KG", "price_cents": 3800}).json()
    inv = client.post("/api/invoices/from-treatments", json={"patient_id": pid, "treatment_ids": [t["id"]], "service_id": svc["id"]}).json()
    client.post(f"/api/invoices/{inv['id']}/issue")
    client.post(f"/api/invoices/{inv['id']}/cancel", json={"reason": "Test"})  # Storno-Kette
    plan = client.post(f"{base}/exercise-plans", json={"title": "P", "issued_on": date.today().isoformat(), "items": [{"title": "Ü"}]})
    assert plan.status_code == 201
    return att


def test_erase_patient_removes_everything(client, base, patient):
    att = full_patient(client, base)
    pid = patient["id"]
    file_path = storage.resolve(db_session().get(Attachment, att["id"]).path)
    assert file_path.is_file()

    assert client.post(f"/api/admin/patients/{pid}/erase", json={"confirm_number": "falsch", "reason": "Test"}).status_code == 422
    assert client.post(f"/api/admin/patients/{pid}/erase", json={"confirm_number": patient["patient_number"], "reason": " "}).status_code == 422
    r = client.post(f"/api/admin/patients/{pid}/erase", json={"confirm_number": patient["patient_number"], "reason": "Löschverlangen Art. 17"})
    assert r.status_code == 200, r.text
    assert r.json()["patient_number"] == patient["patient_number"] and r.json()["attachments"] == 1

    assert client.get(f"/api/patients/{pid}").status_code == 404
    assert not file_path.exists()
    db = db_session()
    assert db.query(Patient).count() == 0
    log = client.get("/api/admin/audit", params={"action": "erase"}).json()
    assert len(log) == 1 and log[0]["changes"]["patient_number"] == patient["patient_number"] and log[0]["reason"].startswith("Löschverlangen")
    # Es bleiben keine personenbezogenen Protokolleinträge dieses Patienten übrig
    assert all(e["patient"] is None for e in client.get("/api/admin/audit", params={"include_views": True}).json())


def test_retention_candidates(client, base, patient):
    r = client.get("/api/admin/retention").json()
    assert r[0]["eligible"] is False and r[0]["patient"]["id"] == patient["id"]
    db = db_session()
    p = db.get(Patient, patient["id"])
    p.created_at = datetime.now(timezone.utc) - timedelta(days=365 * 12)
    db.commit()
    assert client.get("/api/admin/retention", params={"only_eligible": True}).json()[0]["eligible"] is True


def test_integrity_detects_tampering(client, base, patient):
    a = client.post(f"{base}/attachments", data={"kind": "photo"}, files={"file": ("f.png", png(), "image/png")}).json()
    assert client.get("/api/admin/integrity").json()["ok"] is False  # Test-DB hat keinen alembic_version-Eintrag
    from app import ops

    db = db_session()
    assert [p for p in ops.check_integrity(db)["problems"] if "Datei" in p or "Prüfsumme" in p] == []
    path = storage.resolve(db.get(Attachment, a["id"]).path)
    path.write_bytes(path.read_bytes() + b"x")
    assert any("Prüfsumme" in p for p in ops.check_integrity(db)["problems"])
    path.unlink()
    assert any("Datei fehlt" in p for p in ops.check_integrity(db)["problems"])


def test_admin_endpoints_are_admin_only(client, admin):
    client.post("/api/users", json={"username": "thea", "full_name": "T T", "password": "noch-ein-passwort", "role": "therapist"})
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "thea", "password": "noch-ein-passwort"})
    for path in ("/api/admin/audit", "/api/admin/ops", "/api/admin/integrity", "/api/admin/retention"):
        assert client.get(path).status_code == 403, path
    assert client.post("/api/admin/patients/1/erase", json={"confirm_number": "x", "reason": "x"}).status_code == 403


def test_ops_status_after_backup_mark(client, admin):
    from app import ops

    db = db_session()
    assert client.get("/api/admin/ops").json()["last_backup_at"] is None
    ops.set_ops(db, "last_backup_file", "x.gpg")
    ops.set_ops(db, "last_backup_at", datetime.now(timezone.utc).isoformat())
    db.commit()
    assert client.get("/api/admin/ops").json()["last_backup_file"] == "x.gpg"
