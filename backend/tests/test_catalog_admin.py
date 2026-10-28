from datetime import date

import pytest


def anamnesis(client, base, **extra):
    return client.post(f"{base}/anamneses", json={"recorded_on": date.today().isoformat(), "chief_complaint": "Rücken", **extra})


def items(client, kind):
    return client.get("/api/admin/catalog", params={"kind": kind}).json()


def test_defaults_are_seeded_unreviewed_and_ordered(client, admin):
    reds = items(client, "red_flag")
    assert reds[0]["key"] == "weight_loss" and all(i["reviewed"] is False and i["active"] for i in reds)
    assert [i["sort_order"] for i in reds] == sorted(i["sort_order"] for i in reds)
    assert client.get("/api/admin/ops").json()["unreviewed_templates"] > 50
    cat = client.get("/api/catalog").json()
    assert cat["red_flags"]["night_pain"] and "Krankengymnastik (KG)" in cat["measures"]


def test_admin_adds_red_flag_and_it_is_usable(client, base, admin):
    r = client.post("/api/admin/catalog", json={"kind": "red_flag", "label": "Neu aufgetretene Gangunsicherheit"})
    assert r.status_code == 201 and r.json()["key"] == "neu_aufgetretene_gangunsicherheit" and r.json()["reviewed"] is True
    key = r.json()["key"]
    assert client.get("/api/catalog").json()["red_flags"][key] == "Neu aufgetretene Gangunsicherheit"
    assert anamnesis(client, base, red_flags=[key]).status_code == 201
    assert anamnesis(client, base, red_flags=["gibt_es_nicht"]).status_code == 422
    assert anamnesis(client, base, yellow_flags=["gibt_es_nicht"]).status_code == 422


def test_deactivated_flag_stays_valid_for_old_records_but_is_not_offered(client, base, admin):
    key = "night_pain"
    old = anamnesis(client, base, red_flags=[key]).json()
    item = next(i for i in items(client, "red_flag") if i["key"] == key)
    r = client.put(f"/api/admin/catalog/{item['id']}", json={"label": item["label"], "active": False, "reviewed": True})
    assert r.status_code == 200 and r.json()["active"] is False
    cat = client.get("/api/catalog").json()
    assert key not in cat["red_flags"] and key in cat["red_flags_all"]  # Anzeige alter Einträge bleibt möglich
    assert anamnesis(client, base, red_flags=[key]).status_code == 201  # Schlüssel bleibt gültig
    assert old["red_flags"] == [key]


def test_edit_label_keeps_key_and_review_marks_reviewer(client, admin):
    item = next(i for i in items(client, "yellow_flag") if i["key"] == "fear_avoidance")
    r = client.put(f"/api/admin/catalog/{item['id']}", json={"label": "Bewegungsangst", "active": True, "reviewed": True}).json()
    assert r["key"] == "fear_avoidance" and r["label"] == "Bewegungsangst" and r["reviewed"] and r["reviewed_by"] == "Test Admin"
    assert client.get("/api/catalog").json()["yellow_flags"]["fear_avoidance"] == "Bewegungsangst"


def test_finding_preset_with_norms_and_category_check(client, admin):
    bad = client.post("/api/admin/catalog", json={"kind": "finding_preset", "label": "Test X"})
    assert bad.status_code == 422
    r = client.post("/api/admin/catalog", json={"kind": "finding_preset", "label": "Handgelenk (Extension/Flexion)", "category": "rom", "unit": "°", "norm_opposite": 70, "norm_neutral": 0, "norm_main": 80})
    assert r.status_code == 201
    preset = next(p for p in client.get("/api/catalog").json()["finding_presets"] if p["name"] == "Handgelenk (Extension/Flexion)")
    assert preset["norm"] == [70, 0, 80] and preset["reviewed"] is True and preset["category"] == "rom"
    assert client.post("/api/admin/catalog", json={"kind": "unsinn", "label": "x"}).status_code == 422


def test_measures_add_and_reorder(client, admin):
    client.post("/api/admin/catalog", json={"kind": "measure", "label": "Schlingentisch"})
    assert client.get("/api/catalog").json()["measures"][-1] == "Schlingentisch"
    last = items(client, "measure")[-1]
    moved = client.post(f"/api/admin/catalog/{last['id']}/move", json={"direction": "up"}).json()
    assert [m["label"] for m in moved][-2] == "Schlingentisch"
    assert client.get("/api/catalog").json()["measures"][-2] == "Schlingentisch"
    top = items(client, "measure")[0]
    assert client.post(f"/api/admin/catalog/{top['id']}/move", json={"direction": "up"}).status_code == 200  # am Rand: keine Änderung


def test_review_all(client, admin):
    r = client.post("/api/admin/catalog/review-all", json={"kind": "red_flag"})
    assert r.json()["reviewed"] == len(items(client, "red_flag"))
    assert all(i["reviewed"] for i in items(client, "red_flag"))
    assert not all(i["reviewed"] for i in items(client, "measure"))  # andere Arten unberührt


def test_only_admin_can_edit_catalog(client, admin):
    client.post("/api/users", json={"username": "thea", "full_name": "T T", "password": "noch-ein-passwort", "role": "therapist"})
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "thea", "password": "noch-ein-passwort"})
    assert client.get("/api/catalog").status_code == 200
    assert client.get("/api/admin/catalog", params={"kind": "red_flag"}).status_code == 403
    assert client.post("/api/admin/catalog", json={"kind": "measure", "label": "x"}).status_code == 403
