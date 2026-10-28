from datetime import date, datetime, timedelta, timezone

import pytest

from app.exercise_defaults import DEFAULT_EXERCISES


def local(dt: datetime) -> str:
    return dt.isoformat()


def slot(days: int = 1, hour: int = 9, minute: int = 0) -> datetime:
    base = datetime.now(timezone.utc).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base + timedelta(days=days)


# --- Verordnungen --------------------------------------------------------------


def make_rx(client, base, **extra):
    body = {"issued_on": date.today().isoformat(), "measure": "Krankengymnastik", "total_units": 6, "physician": "Dr. med. Fiktiv", "frequency": "2x pro Woche", **extra}
    r = client.post(f"{base}/prescriptions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_prescription_units_and_status(client, base):
    rx = make_rx(client, base, total_units=2)
    assert rx["units_done"] == 0 and rx["units_remaining"] == 2 and rx["status"] == "open"
    for d in (0, 1):
        t = client.post(f"{base}/treatments", json={"treated_on": (date.today() - timedelta(days=d)).isoformat(), "prescription_id": rx["id"], "finalize": True})
        assert t.status_code == 201, t.text
    rxs = client.get(f"{base}/prescriptions").json()
    assert rxs[0]["units_done"] == 2 and rxs[0]["status"] == "completed"


def test_prescription_expired_without_start(client, base):
    old = (date.today() - timedelta(days=40)).isoformat()
    rx = make_rx(client, base, issued_on=old)
    assert rx["status"] == "expired" and any("nicht mehr gültig" in w["text"] for w in rx["warnings"])
    urgent = make_rx(client, base, issued_on=(date.today() - timedelta(days=20)).isoformat(), urgent=True)
    assert urgent["status"] == "expired"  # dringlich: nur 14 Tage Beginn-Frist
    ok = make_rx(client, base, issued_on=(date.today() - timedelta(days=20)).isoformat())
    assert ok["status"] == "open"


def test_prescription_break_warning(client, base):
    rx = make_rx(client, base, issued_on=(date.today() - timedelta(days=30)).isoformat())
    for d in (28, 5):
        client.post(f"{base}/treatments", json={"treated_on": (date.today() - timedelta(days=d)).isoformat(), "prescription_id": rx["id"], "finalize": True})
    out = client.get(f"{base}/prescriptions").json()[0]
    assert any("Unterbrechung von 23 Tagen" in w["text"] for w in out["warnings"])


def test_treatment_rejects_foreign_prescription(client, base, admin):
    other = client.post("/api/patients", json={"first_name": "Max", "last_name": "Muster", "birth_date": "1980-01-01"}).json()
    rx = client.post(f"/api/patients/{other['id']}/prescriptions", json={"issued_on": date.today().isoformat(), "measure": "KG", "total_units": 6}).json()
    r = client.post(f"{base}/treatments", json={"treated_on": date.today().isoformat(), "prescription_id": rx["id"]})
    assert r.status_code == 422


def test_dashboard_lists_rx_attention(client, base):
    make_rx(client, base, total_units=3, issued_on=(date.today() - timedelta(days=3)).isoformat())
    t = client.post(f"{base}/treatments", json={"treated_on": date.today().isoformat(), "finalize": True}).json()
    rx = client.get(f"{base}/prescriptions").json()[0]
    client.put(f"{base}/treatments/{t['id']}", json={"treated_on": date.today().isoformat(), "prescription_id": rx["id"], "correction_reason": "Zuordnung ergänzt"})
    att = client.get("/api/dashboard").json()["rx_attention"]
    assert att and att[0]["warnings"][0]["level"] == "info"


# --- Termine -------------------------------------------------------------------


def test_appointment_conflict_and_series(client, base, patient):
    first = client.post("/api/appointments", json={"patient_id": patient["id"], "start": local(slot()), "duration_minutes": 30})
    assert first.status_code == 201, first.text
    clash = client.post("/api/appointments", json={"patient_id": patient["id"], "start": local(slot(minute=15)), "duration_minutes": 30})
    assert clash.status_code == 409 and "Überschneidung" in clash.json()["detail"]
    forced = client.post("/api/appointments", json={"patient_id": patient["id"], "start": local(slot(minute=15)), "duration_minutes": 30, "force": True})
    assert forced.status_code == 201

    series = client.post("/api/appointments", json={"patient_id": patient["id"], "start": local(slot(days=1, hour=11)), "duration_minutes": 30, "repeat_count": 4, "repeat_days": 7})
    assert series.status_code == 201 and len(series.json()["created"]) == 4
    # Zweite Serie überschneidet sich teilweise -> übersprungen statt Abbruch
    again = client.post("/api/appointments", json={"patient_id": patient["id"], "start": local(slot(days=22, hour=11)), "duration_minutes": 30, "repeat_count": 3})
    body = again.json()
    assert len(body["created"]) == 2 and len(body["skipped"]) == 1


def test_block_time_needs_title(client, admin):
    assert client.post("/api/appointments", json={"start": local(slot()), "duration_minutes": 60}).status_code == 422
    ok = client.post("/api/appointments", json={"start": local(slot()), "duration_minutes": 60, "title": "Mittagspause"})
    assert ok.status_code == 201 and ok.json()["created"][0]["patient"] is None


def test_appointment_list_move_cancel(client, patient):
    a = client.post("/api/appointments", json={"patient_id": patient["id"], "start": local(slot()), "duration_minutes": 30}).json()["created"][0]
    lo, hi = local(slot(days=0, hour=0)), local(slot(days=3, hour=23))
    assert [x["id"] for x in client.get("/api/appointments", params={"start": lo, "end": hi}).json()] == [a["id"]]
    moved = client.patch(f"/api/appointments/{a['id']}", json={"start": local(slot(hour=14))})
    assert moved.status_code == 200 and moved.json()["start"].startswith(slot(hour=14).strftime("%Y-%m-%dT14:00"))
    cancelled = client.patch(f"/api/appointments/{a['id']}", json={"status": "cancelled", "cancel_reason": "krank"})
    assert cancelled.json()["status"] == "cancelled"
    # Abgesagter Termin blockiert den Slot nicht mehr
    assert client.post("/api/appointments", json={"patient_id": patient["id"], "start": local(slot(hour=14)), "duration_minutes": 30}).status_code == 201


def test_start_treatment_from_appointment(client, base, patient):
    rx = make_rx(client, base)
    a = client.post("/api/appointments", json={"patient_id": patient["id"], "prescription_id": rx["id"], "start": local(slot()), "duration_minutes": 25}).json()["created"][0]
    assert a["prescription_label"] == "Krankengymnastik 0/6"
    t = client.post(f"/api/appointments/{a['id']}/start", json={"treated_on": date.today().isoformat()})
    assert t.status_code == 200 and t.json()["status"] == "draft" and t.json()["prescription_id"] == rx["id"] and t.json()["duration_minutes"] == 25
    again = client.post(f"/api/appointments/{a['id']}/start", json={"treated_on": date.today().isoformat()})
    assert again.json()["id"] == t.json()["id"]  # kein Duplikat
    assert client.get("/api/appointments", params={"start": local(slot(days=0, hour=0)), "end": local(slot(days=3, hour=23))}).json()[0]["status"] == "done"


def test_reminders_for_tomorrow(client, patient):
    client.put(f"/api/patients/{patient['id']}", json={**{k: patient[k] for k in ("first_name", "last_name", "birth_date")}, "mobile": "0170 0000000", "archived": False})
    client.post("/api/appointments", json={"patient_id": patient["id"], "start": local(slot(days=1, hour=10)), "duration_minutes": 30})
    r = client.get("/api/appointments/reminders").json()
    assert r and r[0]["mobile"] == "0170 0000000"


def test_follow_ups(client, patient):
    pid = patient["id"]
    f = client.post(f"/api/patients/{pid}/follow-ups", json={"due_on": date.today().isoformat(), "text": "Folgeverordnung anfragen"}).json()
    assert [x["id"] for x in client.get("/api/dashboard").json()["follow_ups_due"]] == [f["id"]]
    assert client.patch(f"/api/follow-ups/{f['id']}", json={"done": True}).json()["done"] is True
    assert client.get("/api/dashboard").json()["follow_ups_due"] == []


def test_reception_can_schedule_but_not_see_medical(client, patient, admin):
    client.post("/api/users", json={"username": "empfang", "full_name": "Emma Empfang", "password": "noch-ein-passwort", "role": "reception"})
    therapist_id = admin["id"]
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "empfang", "password": "noch-ein-passwort"})
    r = client.post("/api/appointments", json={"patient_id": patient["id"], "therapist_id": therapist_id, "start": local(slot()), "duration_minutes": 30})
    assert r.status_code == 201
    a = r.json()["created"][0]
    assert client.post(f"/api/appointments/{a['id']}/start", json={"treated_on": date.today().isoformat()}).status_code == 403
    assert client.get(f"/api/patients/{patient['id']}/prescriptions").status_code == 403
    assert client.get("/api/exercises").status_code == 403
    # Der Empfang darf keine Termine für sich selbst anlegen (kein Behandler)
    assert client.post("/api/appointments", json={"patient_id": patient["id"], "start": local(slot(hour=15)), "duration_minutes": 30}).status_code == 422


# --- Übungen -------------------------------------------------------------------


def test_exercise_library_and_plan_pdf(client, base, admin):
    seeded = client.post("/api/exercises/seed-defaults").json()
    assert len(seeded) == len(DEFAULT_EXERCISES)
    assert client.post("/api/exercises/seed-defaults").json() == []  # idempotent
    lib = client.get("/api/exercises", params={"q": "brücke"}).json()
    assert lib and lib[0]["title"].startswith("Brücke")

    plan = client.post(
        f"{base}/exercise-plans",
        json={
            "title": "Hausübungen LWS", "issued_on": date.today().isoformat(), "notes": "Täglich üben.",
            "items": [
                {"exercise_id": lib[0]["id"], "title": lib[0]["title"], "instructions": lib[0]["instructions"], "sets": 3, "reps": 12, "frequency": "täglich"},
                {"title": "Eigene Übung", "instructions": "Frei formuliert", "hold_seconds": 20},
            ],
        },
    )
    assert plan.status_code == 201, plan.text
    pid = plan.json()["id"]
    pdf_r = client.get(f"{base}/exercise-plans/{pid}/pdf")
    assert pdf_r.status_code == 200 and pdf_r.content.startswith(b"%PDF-")
    # Bibliotheksänderung verändert ausgegebenen Plan nicht
    client.put(f"/api/exercises/{lib[0]['id']}", json={"title": "Geändert", "archived": False})
    assert client.get(f"{base}/exercise-plans").json()[0]["items"][0]["title"].startswith("Brücke")


def test_exercise_image_upload(client, admin):
    import io
    from PIL import Image

    e = client.post("/api/exercises", json={"title": "Test-Übung"}).json()
    buf = io.BytesIO()
    Image.new("RGB", (120, 90), (1, 2, 3)).save(buf, "PNG")
    r = client.post(f"/api/exercises/{e['id']}/image", files={"file": ("x.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200 and r.json()["has_image"] is True
    assert client.get(f"/api/exercises/{e['id']}/image").headers["content-type"] == "image/png"
    assert client.post(f"/api/exercises/{e['id']}/image", files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}).status_code == 422
