"""Tests gegen eine echte PostgreSQL (Migrationen, Schutz des Änderungsprotokolls).

Laufen nur, wenn PHYSIOFLOW_TEST_PG_URL gesetzt ist, z. B.
  PHYSIOFLOW_TEST_PG_URL=postgresql+psycopg://postgres@localhost:5432/physioflow_test pytest tests/test_postgres.py
Die Datenbank wird dabei geleert!
"""

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

PG_URL = os.environ.get("PHYSIOFLOW_TEST_PG_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="PHYSIOFLOW_TEST_PG_URL nicht gesetzt")

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(PG_URL)
    with engine.begin() as c:
        c.execute(text("drop schema public cascade"))
        c.execute(text("create schema public"))
    env = {**os.environ, "PHYSIOFLOW_DATABASE_URL": PG_URL}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True, capture_output=True)
    yield engine
    engine.dispose()


def test_migrations_match_models(engine):
    env = {**os.environ, "PHYSIOFLOW_DATABASE_URL": PG_URL}
    result = subprocess.run([sys.executable, "-m", "alembic", "check"], cwd=BACKEND, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_audit_log_is_immutable_but_erase_may_purge(engine, tmp_path, monkeypatch):
    monkeypatch.setenv("PHYSIOFLOW_DATA_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()
    from app import ops
    from app.models import AuditEntry, Patient, Role, User

    with Session(engine) as db:
        admin = User(username="a", full_name="A", password_hash="x", role=Role.admin)
        patient = Patient(patient_number="P00001", first_name="X", last_name="Y", birth_date=date(1980, 1, 1))
        db.add_all([admin, patient])
        db.flush()
        db.add(AuditEntry(user_id=admin.id, action="create", entity_type="patient", patient_id=patient.id, changes={"first_name": "X"}))
        db.commit()

        with pytest.raises(DBAPIError, match="unveraenderlich"):
            db.execute(text("update audit_log set reason = 'manipuliert'"))
        db.rollback()
        with pytest.raises(DBAPIError, match="unveraenderlich"):
            db.execute(text("delete from audit_log"))
        db.rollback()

        patient = db.get(Patient, patient.id)
        admin = db.get(User, admin.id)
        ops.erase_patient(db, patient, admin, "Test")
        db.commit()
        entries = db.query(AuditEntry).all()
        assert [e.action for e in entries] == ["erase"] and entries[0].changes["patient_number"] == "P00001"
        assert db.query(Patient).count() == 0
    get_settings.cache_clear()
