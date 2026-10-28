def test_setup_only_once(client, admin):
    r = client.post("/api/auth/setup", json={"username": "x", "full_name": "X", "password": "geheim-genug-123"})
    assert r.status_code == 409


def test_status_and_logout(client, admin):
    r = client.get("/api/auth/status").json()
    assert r["setup_required"] is False and r["user"]["username"] == "admin"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/patients").status_code == 401


def test_login_wrong_password(client, admin):
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": "admin", "password": "falsch"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "geheim-genug-123"}).status_code == 200


def test_csrf_header_required(client, admin):
    r = client.post("/api/patients", json={}, headers={"X-PhysioFlow": ""})
    assert r.status_code != 403  # Header vorhanden (leer) ist ok
    del client.headers["X-PhysioFlow"]
    r = client.post("/api/patients", json={"first_name": "A", "last_name": "B", "birth_date": "2000-01-01"})
    assert r.status_code == 403


def test_user_management_admin_only(client, admin):
    r = client.post("/api/users", json={"username": "thera", "full_name": "Thea Therapeutin", "password": "noch-ein-passwort"})
    assert r.status_code == 201
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "thera", "password": "noch-ein-passwort"})
    assert client.get("/api/users").status_code == 403


def test_deactivated_user_loses_session(client, admin):
    uid = client.post("/api/users", json={"username": "t2", "full_name": "T Zwei", "password": "noch-ein-passwort"}).json()["id"]
    assert client.patch(f"/api/users/{uid}", json={"is_active": False}).status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": "t2", "password": "noch-ein-passwort"}).status_code == 401


def test_admin_cannot_lock_self_out(client, admin):
    assert client.patch(f"/api/users/{admin['id']}", json={"is_active": False}).status_code == 400


def test_admin_can_unlock_locked_account(client, admin):
    client.post("/api/users", json={"username": "thea", "full_name": "Thea T", "password": "noch-ein-passwort", "role": "therapist"})
    uid = next(u["id"] for u in client.get("/api/users").json() if u["username"] == "thea")
    client.post("/api/auth/logout")
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "thea", "password": "falsch"})
    assert client.post("/api/auth/login", json={"username": "thea", "password": "noch-ein-passwort"}).status_code == 429
    client.post("/api/auth/login", json={"username": "admin", "password": "geheim-genug-123"})
    locked = next(u for u in client.get("/api/users").json() if u["id"] == uid)
    assert locked["locked_until"] is not None
    assert client.patch(f"/api/users/{uid}", json={"unlock": True}).status_code == 200
    assert next(u for u in client.get("/api/users").json() if u["id"] == uid)["locked_until"] is None
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": "thea", "password": "noch-ein-passwort"}).status_code == 200


def test_cli_unlock_and_reset_clear_lock(client, admin, monkeypatch):
    from app import cli
    from app.db import get_db
    from app.main import app
    from app.models import User

    db = next(app.dependency_overrides[get_db]())
    user = db.query(User).one()
    from datetime import datetime, timedelta, timezone

    user.failed_attempts, user.locked_until = 3, datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()
    monkeypatch.setattr(cli, "SessionLocal", lambda: next(app.dependency_overrides[get_db]()))
    cli.unlock("admin")
    db.refresh(user)
    assert user.locked_until is None and user.failed_attempts == 0
