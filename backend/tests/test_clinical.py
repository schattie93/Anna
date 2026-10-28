"""Fachliche Ergänzungen: Leistungsnachweis, Neutral-Null-Methode, Anamnese, Erstbefund, Heilmittelkatalog, Übungsfreigabe."""

import io
from datetime import date, timedelta

import pytest
from PIL import Image

from app.exercise_defaults import DEFAULT_EXERCISES


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (60, 30), (255, 255, 255)).save(buf, "PNG")
    return buf.getvalue()


def sign(client, base, treatment_id):
    r = client.post(f"{base}/treatments/{treatment_id}/signature", files={"file": ("u.png", png(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()


# --- Leistungsnachweis ---------------------------------------------------------------


def test_signature_marks_treatment_signed(client, base):
    t = client.post(f"{base}/treatments", json={"treated_on": date.today().isoformat(), "finalize": True}).json()
    assert t["signed"] is False
    att = sign(client, base, t["id"])
    assert att["kind"] == "signature" and att["treatment_id"] == t["id"]
    assert client.get(f"{base}/treatments").json()[0]["signed"] is True
    dup = client.post(f"{base}/treatments/{t['id']}/signature", files={"file": ("u.png", png(), "image/png")})
    assert dup.status_code == 409
    # Stornierte Unterschrift: wieder unsigniert, neue möglich
    client.post(f"{base}/attachments/{att['id']}/void", json={"reason": "Versehen"})
    assert client.get(f"{base}/treatments").json()[0]["signed"] is False
    sign(client, base, t["id"])


def test_signature_must_be_png_and_belong_to_patient(client, base, admin):
    t = client.post(f"{base}/treatments", json={"treated_on": date.today().isoformat()}).json()
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "JPEG")
    assert client.post(f"{base}/treatments/{t['id']}/signature", files={"file": ("u.jpg", buf.getvalue(), "image/jpeg")}).status_code == 422
    other = client.post("/api/patients", json={"first_name": "A", "last_name": "B", "birth_date": "1980-01-01"}).json()
    assert client.post(f"/api/patients/{other['id']}/treatments/{t['id']}/signature", files={"file": ("u.png", png(), "image/png")}).status_code == 404


# --- Neutral-Null-Methode -------------------------------------------------------------


def test_neutral_zero_rom(client, base):
    ok = {"recorded_on": date.today().isoformat(), "category": "rom", "name": "Knie (Extension/Flexion)", "unit": "°", "value_num": 130, "value_neutral": 0, "value_opposite": 5}
    r = client.post(f"{base}/findings", json=ok)
    assert r.status_code == 201 and (r.json()["value_opposite"], r.json()["value_neutral"], r.json()["value_num"]) == (5, 0, 130)
    assert client.post(f"{base}/findings", json={**ok, "value_opposite": None}).status_code == 422  # Neutralwert ohne Gegenrichtung
    # Nur für Beweglichkeit: bei Kraft werden die Zusatzwerte verworfen
    kraft = client.post(f"{base}/findings", json={**ok, "category": "strength", "name": "Quadrizeps", "unit": "0-5", "value_num": 4}).json()
    assert kraft["value_opposite"] is None and kraft["value_neutral"] is None
    cat = client.get("/api/catalog").json()
    assert cat["rom_norms"]["Knie (Extension/Flexion)"] == [0, 0, 140]
    assert any(p["name"] == "PSFS (Patient-Specific Functional Scale)" for p in cat["finding_presets"])


# --- Anamnese ---------------------------------------------------------------------------


def test_yellow_flags_and_new_red_flags(client, base):
    body = {"recorded_on": date.today().isoformat(), "chief_complaint": "Rücken", "red_flags": ["dvt", "thunderclap"], "yellow_flags": ["fear_avoidance", "work_conflict"], "social_history": "Pflegekraft, Schichtdienst", "sleep": "wacht nachts auf"}
    r = client.post(f"{base}/anamneses", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["yellow_flags"] == ["fear_avoidance", "work_conflict"] and r.json()["social_history"].startswith("Pflege")
    assert client.post(f"{base}/anamneses", json={**body, "yellow_flags": ["erfunden"]}).status_code == 422


# --- Erstbefund ---------------------------------------------------------------------------


def test_examination_crud_with_correction_reason(client, base):
    e = client.post(f"{base}/examinations", json={"recorded_on": date.today().isoformat(), "inspection": "Schonhaltung", "hypothesis": "Facettengelenksirritation", "icf_activity": "Sitzen > 20 min eingeschränkt"}).json()
    assert e["inspection"] == "Schonhaltung"
    body = {k: e[k] for k in ("recorded_on", "inspection", "palpation", "function", "hypothesis", "icf_body", "icf_activity", "icf_participation", "notes")}
    assert client.put(f"{base}/examinations/{e['id']}", json={**body, "palpation": "Hartspann"}).status_code == 422
    r = client.put(f"{base}/examinations/{e['id']}", json={**body, "palpation": "Hartspann paravertebral", "correction_reason": "ergänzt"})
    assert r.status_code == 200 and r.json()["palpation"].startswith("Hartspann")
    assert client.post(f"{base}/examinations/{e['id']}/void", json={"reason": "doppelt"}).json()["voided"] is True


# --- Heilmittelkatalog ------------------------------------------------------------------------


def rx(client, base, **extra):
    body = {"issued_on": date.today().isoformat(), "measure": "Krankengymnastik", "total_units": 6, "physician": "Dr. Fiktiv", **extra}
    r = client.post(f"{base}/prescriptions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_indication_catalog_checks_quantities(client, base, admin):
    r = client.post("/api/indications", json={"key": "ws1", "name": "Wirbelsäulenerkrankungen (Beispiel)", "max_units_per_rx": 6, "orienting_total_units": 12})
    assert r.status_code == 201 and r.json()["key"] == "WS1"
    assert client.post("/api/indications", json={"key": "WS1", "name": "doppelt"}).status_code == 409

    unknown = rx(client, base, indication_key="XY9")
    assert any("nicht gepflegt" in w["text"] for w in unknown["warnings"])
    too_many = rx(client, base, indication_key="WS1", total_units=10)
    assert any(w["level"] == "warn" and "Höchstmenge" in w["text"] for w in too_many["warnings"])
    ok = rx(client, base, indication_key="ws1", total_units=6)
    assert not any("Höchstmenge" in w["text"] for w in ok["warnings"])
    # Gesamtmenge über orientierender Behandlungsmenge: 10 + 6 + 6 = 22 > 12
    latest = client.get(f"{base}/prescriptions").json()
    assert any("orientierende" in w["text"] and w["level"] == "info" for r in latest for w in r["warnings"])


def test_indication_catalog_admin_only_edit(client, base, admin):
    e = client.post("/api/indications", json={"key": "EX1", "name": "Beispiel"}).json()
    client.post("/api/users", json={"username": "thea", "full_name": "T T", "password": "noch-ein-passwort", "role": "therapist"})
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "thea", "password": "noch-ein-passwort"})
    assert client.get("/api/indications").status_code == 200
    assert client.put(f"/api/indications/{e['id']}", json={"key": "EX1", "name": "geändert"}).status_code == 403


# --- Übungen: Freigabe -----------------------------------------------------------------------


def test_seeded_exercises_need_approval_before_printing(client, base, admin):
    seeded = client.post("/api/exercises/seed-defaults").json()
    assert len(seeded) == len(DEFAULT_EXERCISES) and all(e["approved"] is False for e in seeded)
    assert not any("Gehen mit Stöcken" in e["title"] for e in seeded)  # entfernte Übung
    ex = seeded[0]
    plan = client.post(f"{base}/exercise-plans", json={"title": "P", "issued_on": date.today().isoformat(), "items": [{"exercise_id": ex["id"], "title": ex["title"]}]}).json()
    assert plan["items"][0]["approved"] is False
    blocked = client.get(f"{base}/exercise-plans/{plan['id']}/pdf")
    assert blocked.status_code == 409 and "freigegeben" in blocked.json()["detail"]

    approved = client.post(f"/api/exercises/{ex['id']}/approve").json()
    assert approved["approved"] is True and approved["approved_by"] == "Test Admin"
    client.put(f"/api/exercises/{ex['id']}", json={"title": ex["title"], "contraindications": "Akute Bandscheibenvorfälle mit Ausfällen", "archived": False})
    ok = client.get(f"{base}/exercise-plans/{plan['id']}/pdf")
    assert ok.status_code == 200 and ok.content.startswith(b"%PDF-")


def test_own_exercises_are_approved_by_author(client, admin):
    e = client.post("/api/exercises", json={"title": "Eigene Übung"}).json()
    assert e["approved"] is True and e["approved_by"] == "Test Admin"
