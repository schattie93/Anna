import io

import pytest
from PIL import Image


def png_bytes(size=(64, 48), color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def jpeg_with_exif() -> bytes:
    img = Image.new("RGB", (80, 60), (10, 120, 200))
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"  # Make
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


# --- Befunde -------------------------------------------------------------------


def test_finding_validation(client, base):
    ok = {"recorded_on": "2026-02-01", "category": "rom", "name": "Schulter Abduktion", "side": "right", "value_num": 95, "unit": "°"}
    assert client.post(f"{base}/findings", json=ok).status_code == 201
    assert client.post(f"{base}/findings", json={**ok, "value_num": None}).status_code == 422
    test = {"recorded_on": "2026-02-01", "category": "test", "name": "Neer-Zeichen", "side": "right", "value_text": "positiv"}
    assert client.post(f"{base}/findings", json=test).status_code == 201
    assert client.post(f"{base}/findings", json={**test, "value_text": "vielleicht"}).status_code == 422


def test_finding_correction_needs_reason(client, base):
    f = client.post(f"{base}/findings", json={"recorded_on": "2026-02-01", "category": "rom", "name": "HWS Rotation", "value_num": 50, "unit": "°"}).json()
    body = {k: f[k] for k in ("recorded_on", "category", "name", "side", "unit", "notes", "treatment_id")} | {"value_num": 60}
    assert client.put(f"{base}/findings/{f['id']}", json=body).status_code == 422
    r = client.put(f"{base}/findings/{f['id']}", json={**body, "correction_reason": "Messfehler"})
    assert r.status_code == 200 and r.json()["value_num"] == 60
    assert client.get(f"{base}/history").json()[0]["changes"]["value_num"] == {"old": 50.0, "new": 60.0}


def test_catalog_has_presets(client, admin):
    cat = client.get("/api/catalog").json()
    assert any(p["name"] == "Lasègue" and p["category"] == "test" for p in cat["finding_presets"])


# --- Körperatlas ----------------------------------------------------------------


def test_body_marks(client, base):
    mark = {"recorded_on": "2026-02-01", "view": "back", "x": 0.5, "y": 0.45, "kind": "pain", "intensity": 7, "note": "ziehend"}
    r = client.post(f"{base}/body-marks", json=mark)
    assert r.status_code == 201, r.text
    assert client.post(f"{base}/body-marks", json={**mark, "x": 1.5}).status_code == 422
    assert client.post(f"{base}/body-marks", json={**mark, "intensity": 11}).status_code == 422
    mid = r.json()["id"]
    assert client.put(f"{base}/body-marks/{mid}", json={**mark, "intensity": 4}).json()["intensity"] == 4
    assert client.post(f"{base}/body-marks/{mid}/void", json={"reason": "versehentlich"}).json()["voided"] is True


# --- Dateien --------------------------------------------------------------------


def test_photo_upload_strips_exif_and_serves(client, base, patient):
    r = client.post(f"{base}/attachments", data={"kind": "photo", "caption": "Haltung vorher"}, files={"file": ("foto.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["content_type"] == "image/jpeg" and a["has_thumb"] is True
    file = client.get(f"{base}/attachments/{a['id']}/file")
    assert file.status_code == 200 and file.headers["content-type"] == "image/jpeg"
    assert file.headers["cache-control"] == "private, no-store"
    assert b"SecretCameraMaker" not in file.content  # EXIF entfernt
    with Image.open(io.BytesIO(file.content)) as img:
        assert not img.getexif()
    thumb = client.get(f"{base}/attachments/{a['id']}/thumb")
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/jpeg"


def test_upload_rejects_fake_and_wrong_types(client, base):
    fake = client.post(f"{base}/attachments", data={"kind": "photo"}, files={"file": ("x.jpg", b"<html>not an image</html>", "image/jpeg")})
    assert fake.status_code == 422
    svg = client.post(f"{base}/attachments", data={"kind": "photo"}, files={"file": ("x.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml")})
    assert svg.status_code == 422
    pdf_as_photo = client.post(f"{base}/attachments", data={"kind": "photo"}, files={"file": ("x.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")})
    assert pdf_as_photo.status_code == 422
    pdf = client.post(f"{base}/attachments", data={"kind": "document", "caption": "Verordnung"}, files={"file": ("v.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")})
    assert pdf.status_code == 201 and pdf.json()["has_thumb"] is False


def test_attachment_access_is_isolated_per_patient(client, base, admin):
    a = client.post(f"{base}/attachments", data={"kind": "drawing"}, files={"file": ("z.png", png_bytes(), "image/png")}).json()
    other = client.post("/api/patients", json={"first_name": "Max", "last_name": "Muster", "birth_date": "1980-01-01"}).json()
    assert client.get(f"/api/patients/{other['id']}/attachments/{a['id']}/file").status_code == 404
    client.post("/api/auth/logout")
    assert client.get(f"{base}/attachments/{a['id']}/file").status_code == 401


def test_voided_attachment_keeps_file(client, base):
    a = client.post(f"{base}/attachments", data={"kind": "photo"}, files={"file": ("z.png", png_bytes(), "image/png")}).json()
    assert client.post(f"{base}/attachments/{a['id']}/void", json={"reason": "falsches Bild"}).json()["voided"] is True
    assert client.get(f"{base}/attachments/{a['id']}/file").status_code == 200


# --- Ziele ----------------------------------------------------------------------


def test_goals(client, base):
    g = client.post(f"{base}/goals", json={"description": "Haare kämmen ohne Schmerz", "metric_name": "Schulter Abduktion", "metric_side": "right", "baseline_value": 80, "target_value": 160}).json()
    assert g["status"] == "open" and g["achieved_on"] is None
    body = {k: g[k] for k in ("description", "target_date", "metric_name", "metric_side", "baseline_value", "target_value")}
    done = client.put(f"{base}/goals/{g['id']}", json={**body, "status": "achieved"}).json()
    assert done["status"] == "achieved" and done["achieved_on"]
    again = client.put(f"{base}/goals/{g['id']}", json={**body, "status": "open"}).json()
    assert again["achieved_on"] is None


# --- Bericht --------------------------------------------------------------------


def test_report_pdf(client, base):
    client.post(f"{base}/diagnoses", json={"description": "Impingement-Syndrom", "icd10_code": "M75.4", "is_primary": True})
    client.post(f"{base}/anamneses", json={"recorded_on": "2026-01-02", "chief_complaint": "Schulterschmerz rechts", "pain_current": 6})
    for day, val, before, after in (("2026-01-05", 80, 6, 5), ("2026-01-12", 110, 5, 3)):
        t = client.post(f"{base}/treatments", json={"treated_on": day, "measures": ["Manuelle Therapie (MT)"], "pain_before": before, "pain_after": after, "finalize": True}).json()
        client.post(f"{base}/findings", json={"recorded_on": day, "category": "rom", "name": "Schulter Abduktion", "side": "right", "value_num": val, "unit": "°", "treatment_id": t["id"]})
    r = client.post(f"{base}/report.pdf", json={"summary": "Gute Fortschritte, Fortsetzung empfohlen. Äußerst motiviert.", "recipient": "Dr. med. Fiktiv"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-") and len(r.content) > 2000
    assert client.get(f"{base}/history").json()  # Export wird protokolliert (ohne Inhalt in der Historie)


def test_reception_cannot_access_medical(client, base, admin):
    client.post("/api/users", json={"username": "empfang", "full_name": "Emma Empfang", "password": "noch-ein-passwort", "role": "reception"})
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "empfang", "password": "noch-ein-passwort"})
    pid = base.rsplit("/", 1)[1]
    assert client.get(f"/api/patients/{pid}").status_code == 200  # Stammdaten ja
    for path in ("anamneses", "diagnoses", "treatments", "findings", "body-marks", "attachments", "goals", "history"):
        assert client.get(f"{base}/{path}").status_code == 403, path
    assert client.post(f"{base}/report.pdf", json={}).status_code == 403
    assert client.get("/api/dashboard").json()["open_treatments"] == []


def test_login_lockout(client, admin):
    client.post("/api/auth/logout")
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "admin", "password": "falsch"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": "admin", "password": "geheim-genug-123"})
    assert r.status_code == 429
