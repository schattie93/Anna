from datetime import date, timedelta

import pytest


@pytest.fixture
def service(client, admin):
    r = client.post("/api/services", json={"code": "KG", "name": "Krankengymnastik 25 Min.", "price_cents": 3800})
    assert r.status_code == 201, r.text
    return r.json()


def final_treatment(client, base, day=None, **extra):
    day = day or date.today().isoformat()
    r = client.post(f"{base}/treatments", json={"treated_on": day, "finalize": True, "measures": ["Krankengymnastik (KG)"], **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_services_admin_only(client, admin, service):
    client.post("/api/users", json={"username": "empfang", "full_name": "E E", "password": "noch-ein-passwort", "role": "reception"})
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "empfang", "password": "noch-ein-passwort"})
    assert client.get("/api/services").status_code == 200
    assert client.post("/api/services", json={"name": "x", "price_cents": 1}).status_code == 403


def test_invoice_flow_with_numbering_payment_and_storno(client, base, patient, service):
    t1 = final_treatment(client, base, (date.today() - timedelta(days=7)).isoformat())
    t2 = final_treatment(client, base)
    assert len(client.get(f"{base}/billable").json()) == 2

    r = client.post("/api/invoices/from-treatments", json={"patient_id": patient["id"], "treatment_ids": [t1["id"], t2["id"]], "service_id": service["id"]})
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["status"] == "draft" and inv["number"] is None and inv["total_cents"] == 7600
    assert inv["recipient_name"] == "Erika Musterfrau" and len(inv["items"]) == 2
    assert client.get(f"{base}/billable").json() == []  # Entwurf reserviert die Behandlungen

    issued = client.post(f"/api/invoices/{inv['id']}/issue").json()
    assert issued["status"] == "issued" and issued["number"] == f"{date.today().year}-0001"
    assert issued["due_date"] == (date.today() + timedelta(days=14)).isoformat()
    # Gestellte Rechnung ist unveränderlich
    body = {"recipient_name": "X", "items": [{"service_date": date.today().isoformat(), "description": "x", "unit_price_cents": 1}]}
    assert client.put(f"/api/invoices/{inv['id']}", json=body).status_code == 409
    assert client.delete(f"/api/invoices/{inv['id']}").status_code == 409

    part = client.post(f"/api/invoices/{inv['id']}/payments", json={"paid_on": date.today().isoformat(), "amount_cents": 3800, "method": "cash"}).json()
    assert part["status"] == "issued" and part["paid_cents"] == 3800
    paid = client.post(f"/api/invoices/{inv['id']}/payments", json={"paid_on": date.today().isoformat(), "amount_cents": 3800}).json()
    assert paid["status"] == "paid"
    pay_id = paid["payments"][-1]["id"]
    back = client.post(f"/api/invoices/{inv['id']}/payments/{pay_id}/void", json={"reason": "Fehlbuchung"}).json()
    assert back["status"] == "issued" and back["paid_cents"] == 3800

    storno = client.post(f"/api/invoices/{inv['id']}/cancel", json={"reason": "Falscher Empfänger"}).json()
    assert storno["number"] == f"{date.today().year}-0002" and storno["total_cents"] == -7600 and storno["cancels_id"] == inv["id"]
    assert client.get(f"/api/invoices/{inv['id']}").json()["status"] == "cancelled"
    assert len(client.get(f"{base}/billable").json()) == 2  # Behandlungen wieder frei
    assert client.post(f"/api/invoices/{inv['id']}/cancel", json={"reason": "nochmal"}).status_code == 409


def test_treatment_cannot_be_billed_twice(client, base, patient, service):
    t = final_treatment(client, base)
    ok = client.post("/api/invoices/from-treatments", json={"patient_id": patient["id"], "treatment_ids": [t["id"]], "service_id": service["id"]})
    assert ok.status_code == 201
    dup = client.post("/api/invoices/from-treatments", json={"patient_id": patient["id"], "treatment_ids": [t["id"]], "service_id": service["id"]})
    assert dup.status_code == 409 and "bereits abgerechnet" in dup.json()["detail"]


def test_draft_treatment_not_billable(client, base, patient, service):
    t = client.post(f"{base}/treatments", json={"treated_on": date.today().isoformat()}).json()
    r = client.post("/api/invoices/from-treatments", json={"patient_id": patient["id"], "treatment_ids": [t["id"]], "service_id": service["id"]})
    assert r.status_code == 422


def test_draft_edit_delete_and_gapless_numbers(client, base, patient, service):
    d = client.post(f"/api/patients/{patient['id']}/invoices", json={"recipient_name": "Erika Musterfrau", "items": [{"service_date": date.today().isoformat(), "description": "Gutachten", "quantity": 2, "unit_price_cents": 2500}]}).json()
    assert d["total_cents"] == 5000
    upd = client.put(f"/api/invoices/{d['id']}", json={"recipient_name": "Firma GmbH", "recipient_address": "Weg 1\n12345 Stadt", "items": [{"service_date": date.today().isoformat(), "description": "Gutachten", "quantity": 1, "unit_price_cents": 2500}]}).json()
    assert upd["total_cents"] == 2500 and upd["recipient_name"] == "Firma GmbH"
    other = client.post(f"/api/patients/{patient['id']}/invoices", json={"recipient_name": "A", "items": [{"service_date": date.today().isoformat(), "description": "x", "unit_price_cents": 100}]}).json()
    assert client.delete(f"/api/invoices/{other['id']}").status_code == 204  # Entwurf ohne Nummer löschbar
    n1 = client.post(f"/api/invoices/{d['id']}/issue").json()["number"]
    e = client.post(f"/api/patients/{patient['id']}/invoices", json={"recipient_name": "B", "items": [{"service_date": date.today().isoformat(), "description": "y", "unit_price_cents": 100}]}).json()
    n2 = client.post(f"/api/invoices/{e['id']}/issue").json()["number"]
    assert (n1, n2) == (f"{date.today().year}-0001", f"{date.today().year}-0002")


def test_payments_only_on_issued_invoice(client, base, patient, service):
    d = client.post(f"/api/patients/{patient['id']}/invoices", json={"recipient_name": "A", "items": [{"service_date": date.today().isoformat(), "description": "x", "unit_price_cents": 100}]}).json()
    assert client.post(f"/api/invoices/{d['id']}/payments", json={"paid_on": date.today().isoformat(), "amount_cents": 100}).status_code == 409


def test_overdue_and_summary(client, base, patient, service, monkeypatch):
    t = final_treatment(client, base)
    inv = client.post("/api/invoices/from-treatments", json={"patient_id": patient["id"], "treatment_ids": [t["id"]], "service_id": service["id"]}).json()
    issued = client.post(f"/api/invoices/{inv['id']}/issue").json()
    s = client.get("/api/billing/summary").json()
    assert s["revenue_year_cents"] == 3800 and s["open_cents"] == 3800 and s["overdue_count"] == 0
    # Zahlungsziel in der Vergangenheit (direkt in der DB, da gestellte Rechnungen API-seitig unveränderlich sind)
    from app.db import get_db
    from app.main import app
    from app.models import Invoice

    db = next(app.dependency_overrides[get_db]())
    row = db.get(Invoice, issued["id"])
    row.due_date = date.today() - timedelta(days=3)
    db.commit()
    assert client.get("/api/invoices", params={"overdue": True}).json()[0]["overdue"] is True
    assert client.get("/api/billing/summary").json()["overdue_count"] == 1


def test_invoice_pdf(client, base, patient, service):
    client.put("/api/settings/practice", json={"practice_name": "Praxis Beispiel", "practice_iban": "DE00 0000 0000 0000 0000 00", "practice_address": "Musterweg 1, 00000 Stadt"})
    t = final_treatment(client, base)
    inv = client.post("/api/invoices/from-treatments", json={"patient_id": patient["id"], "treatment_ids": [t["id"]], "service_id": service["id"]}).json()
    draft_pdf = client.get(f"/api/invoices/{inv['id']}/pdf")
    assert draft_pdf.status_code == 200 and draft_pdf.content.startswith(b"%PDF-")
    client.post(f"/api/invoices/{inv['id']}/issue")
    r = client.get(f"/api/invoices/{inv['id']}/pdf")
    assert r.status_code == 200 and r.headers["content-disposition"].endswith(f'rechnung-{date.today().year}-0001.pdf"')


# --- GKV-Vorbereitung ------------------------------------------------------------


def test_gkv_check_and_csv(client, base, patient):
    pid = patient["id"]
    client.put(f"/api/patients/{pid}", json={"first_name": "Erika", "last_name": "Musterfrau", "birth_date": "1970-05-12", "insurance_type": "gkv", "insurance_name": "Demo-Kasse", "insurance_number": "A123456789", "archived": False})
    rx = client.post(f"{base}/prescriptions", json={"issued_on": date.today().isoformat(), "measure": "Krankengymnastik", "total_units": 2, "physician": "Dr. Fiktiv", "icd10_code": "M54.5"}).json()
    rows = client.get("/api/billing/gkv").json()
    assert rows[0]["ready"] is False and "Indikationsschlüssel fehlt" in rows[0]["problems"] and "Keine abgeschlossene Behandlung zugeordnet" in rows[0]["problems"]

    client.put(f"{base}/prescriptions/{rx['id']}", json={"issued_on": date.today().isoformat(), "measure": "Krankengymnastik", "total_units": 2, "physician": "Dr. Fiktiv", "icd10_code": "M54.5", "indication_key": "WS1"})
    treatments = [final_treatment(client, base, (date.today() - timedelta(days=d)).isoformat(), prescription_id=rx["id"]) for d in (1, 0)]
    rows = client.get("/api/billing/gkv").json()
    assert rows[0]["ready"] is False and any("Unterschrift" in p for p in rows[0]["problems"])  # Leistungsnachweis fehlt
    from tests.test_clinical import sign

    for t in treatments:
        sign(client, base, t["id"])
    rows = client.get("/api/billing/gkv").json()
    assert rows[0]["ready"] is True and rows[0]["units_done"] == 2

    csv = client.get("/api/billing/gkv.csv", params={"only_ready": True})
    text = csv.content.decode("utf-8-sig")
    assert csv.headers["content-type"].startswith("text/csv")
    lines = text.strip().split("\r\n")
    assert len(lines) == 2 and "A123456789" in lines[1] and "WS1" in lines[1] and lines[1].split(";")[14] == "ja"


def test_stats(client, base, patient):
    final_treatment(client, base)
    client.post(f"{base}/treatments", json={"treated_on": (date.today() - timedelta(days=5)).isoformat()})  # alter Entwurf
    s = client.get("/api/stats").json()
    assert s["treatments_year"] == 1 and s["treatments_by_month"][date.today().month - 1] == 1
    assert s["measures"][0][0] == "Krankengymnastik (KG)"
    assert len(s["documentation"]["draft_treatments_overdue"]) == 1
    assert patient["id"] in s["documentation"]["treated_patients_without_anamnesis"]
