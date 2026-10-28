import os

os.environ.setdefault("PHYSIOFLOW_DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app, headers={"X-PhysioFlow": "1"}) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def admin(client):
    r = client.post("/api/auth/setup", json={"username": "admin", "full_name": "Test Admin", "password": "geheim-genug-123"})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def patient(client, admin):
    r = client.post(
        "/api/patients",
        json={"first_name": "Erika", "last_name": "Musterfrau", "birth_date": "1970-05-12", "city": "Beispielstadt"},
    )
    assert r.status_code == 201, r.text
    return r.json()
