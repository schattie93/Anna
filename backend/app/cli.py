"""Verwaltungsbefehle: python -m app.cli <befehl>

  seed-demo       legt fiktive Beispieldaten an (nur für Entwicklung/Demo!)
  reset-password  setzt das Passwort eines Benutzers neu (hebt auch eine Sperre auf)
  unlock          hebt die Sperre nach Fehlversuchen für einen Benutzer auf
  check-integrity prüft Datenbankstand, Dateien (Prüfsummen) und Rechnungsnummern; Exitcode 1 bei Problemen
  backup-done     vermerkt ein erfolgreiches Backup (wird von scripts/backup.sh aufgerufen)
  restore-test-done  vermerkt einen erfolgreichen Wiederherstellungstest
"""

import argparse
import getpass
import sys
from datetime import date, timedelta

from sqlalchemy import select

from .db import SessionLocal
from .models import Anamnesis, Diagnosis, InsuranceType, Patient, Role, ServiceItem, Sex, Side, Treatment, TreatmentStatus, User
from .security import hash_password

DEMO_PATIENTS = [
    ("Erika", "Musterfrau", date(1968, 4, 12), Sex.female, InsuranceType.gkv, "Demo-Krankenkasse", "Lumbalgie", "M54.5", Side.none),
    ("Max", "Mustermann", date(1979, 9, 3), Sex.male, InsuranceType.private, "Beispiel PKV", "Impingement-Syndrom Schulter", "M75.4", Side.right),
    ("Lena", "Beispiel", date(1995, 1, 27), Sex.female, InsuranceType.gkv, "Demo-Krankenkasse", "Z. n. VKB-Plastik", "Z98.8", Side.left),
    ("Paul", "Platzhalter", date(1952, 11, 8), Sex.male, InsuranceType.gkv, "Fiktiv BKK", "Gonarthrose", "M17.1", Side.both),
]


def seed_demo() -> None:
    with SessionLocal() as db:
        if db.scalar(select(Patient.id).limit(1)):
            sys.exit("Es sind bereits Patienten vorhanden – Demo-Daten werden nicht angelegt.")
        user = db.scalar(select(User).where(User.username == "demo"))
        if not user:
            user = User(username="demo", full_name="Demo Therapeut", role=Role.admin, password_hash=hash_password("demo-passwort"))
            db.add(user)
            db.flush()
        today = date.today()
        for i, (first, last, born, sex, ins, ins_name, diag, icd, side) in enumerate(DEMO_PATIENTS, start=1):
            p = Patient(
                patient_number=f"P{i:05d}", first_name=first, last_name=last, birth_date=born, sex=sex,
                street="Beispielweg 1", postal_code="00000", city="Musterstadt", phone="0000 000000",
                insurance_type=ins, insurance_name=ins_name, insurance_number=f"X00000000{i}",
                referring_physician="Dr. med. Fiktiv", consent_treatment=True, consent_data_processing=True,
                consent_date=today - timedelta(days=30),
            )
            db.add(p)
            db.flush()
            db.add(Anamnesis(
                patient_id=p.id, created_by_id=user.id, recorded_on=today - timedelta(days=28),
                chief_complaint=f"Beschwerden bei {diag}", onset="seit ca. 6 Wochen", pain_current=5, pain_max=7,
                goals="Schmerzreduktion, Rückkehr zu Alltagsaktivitäten", red_flags=[],
            ))
            d = Diagnosis(patient_id=p.id, created_by_id=user.id, description=diag, icd10_code=icd, side=side,
                          is_primary=True, diagnosed_by="Dr. med. Fiktiv", diagnosed_on=today - timedelta(days=35))
            db.add(d)
            db.flush()
            for n, days_ago in enumerate((21, 14, 7, 0)):
                db.add(Treatment(
                    patient_id=p.id, diagnosis_id=d.id, created_by_id=user.id, treated_on=today - timedelta(days=days_ago),
                    duration_minutes=25, measures=["Krankengymnastik (KG)", "Manuelle Therapie (MT)"],
                    subjective="Schmerzen etwas rückläufig" if n else "Schmerzen unverändert",
                    pain_before=6 - n, pain_after=5 - n,
                    status=TreatmentStatus.draft if days_ago == 0 else TreatmentStatus.final,
                ))
        # Beispiel-Leistungen (erfundene Preise – für den echten Betrieb unter Abrechnung > Leistungen anpassen)
        for code, name, cents in (("KG", "Krankengymnastik 25 Min.", 3800), ("MT", "Manuelle Therapie 25 Min.", 4200), ("MLD", "Manuelle Lymphdrainage 45 Min.", 6500)):
            db.add(ServiceItem(code=code, name=name, price_cents=cents))
        db.commit()
    print("Demo-Daten angelegt. Anmeldung: demo / demo-passwort")


def reset_password(username: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if not user:
            sys.exit(f"Benutzer '{username}' nicht gefunden")
        pw = getpass.getpass("Neues Passwort (min. 10 Zeichen): ")
        if len(pw) < 10 or pw != getpass.getpass("Wiederholen: "):
            sys.exit("Passwort zu kurz oder stimmt nicht überein")
        user.password_hash = hash_password(pw)
        user.is_active = True
        user.failed_attempts, user.locked_until = 0, None
        db.commit()
    print("Passwort gesetzt.")


def unlock(username: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if not user:
            sys.exit(f"Benutzer '{username}' nicht gefunden")
        user.failed_attempts, user.locked_until = 0, None
        db.commit()
    print(f"Konto '{username}' ist freigegeben.")


def check_integrity() -> None:
    from . import ops

    with SessionLocal() as db:
        result = ops.check_integrity(db)
    print(f"Schema: {result['schema']['current']} (erwartet {result['schema']['head']})")
    print(f"Datensätze: {result['counts']}; Dateien geprüft: {result['files_hash_checked']}")
    for problem in result["problems"]:
        print("PROBLEM:", problem)
    print("OK" if result["ok"] else "FEHLER")
    sys.exit(0 if result["ok"] else 1)


def mark(key: str, value: str) -> None:
    from datetime import datetime, timezone

    from . import ops

    with SessionLocal() as db:
        ops.set_ops(db, key, value)
        if key == "last_backup_file":
            ops.set_ops(db, "last_backup_at", datetime.now(timezone.utc).isoformat())
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-demo")
    rp = sub.add_parser("reset-password")
    rp.add_argument("username")
    ul = sub.add_parser("unlock")
    ul.add_argument("username")
    sub.add_parser("check-integrity")
    bd = sub.add_parser("backup-done")
    bd.add_argument("filename")
    sub.add_parser("restore-test-done")
    args = parser.parse_args()
    if args.cmd == "seed-demo":
        seed_demo()
    elif args.cmd == "unlock":
        unlock(args.username)
    elif args.cmd == "check-integrity":
        check_integrity()
    elif args.cmd == "backup-done":
        mark("last_backup_file", args.filename)
        print("Backup vermerkt.")
    elif args.cmd == "restore-test-done":
        from datetime import datetime, timezone

        mark("last_restore_test_at", datetime.now(timezone.utc).isoformat())
        print("Wiederherstellungstest vermerkt.")
    else:
        reset_password(args.username)


if __name__ == "__main__":
    main()
