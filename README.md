# PhysioFlow

Lokale Praxissoftware für die Physiotherapie: von der Patientenaufnahme über Dokumentation, Termine und Verordnungen bis zur Abrechnung.
**Alle Patientendaten bleiben im Praxisnetz.** Es gibt keine Cloud-Dienste und keine externe KI.

Grundlage ist das Projektkonzept vom 28.10.2026. Alle sechs Phasen sind umgesetzt (siehe Tabelle unten). Offene Punkte stehen im Abschnitt „Vor dem Produktivbetrieb“.

> ⚠️ **Noch nicht für den Produktivbetrieb mit echten Patientendaten freigegeben.** Dafür fehlen die Installation auf dem Ziel-NAS, eine rechtliche Prüfung und eine unabhängige Sicherheitsprüfung (siehe unten und `docs/DATENSCHUTZ.md`). Für Entwicklung und Tests nur fiktive Daten verwenden.

## Funktionsumfang

| Phase | Bereich | Inhalt |
|---|---|---|
| 1 | **Grundsystem** | Lokale Anmeldung, Rollen, Patientenakte (Stammdaten, Versicherung, Einwilligungen), Anamnese mit Red-Flag-Checkliste, Diagnosen (ICD-10), Behandlungen im SOAP-Format (Entwurf → abgeschlossen), Änderungsprotokoll |
| 2 | **Dokumentation** | Befunde und Messwerte (Beweglichkeit, Kraft, Tests) mit Verlaufsdiagrammen, **Körperatlas** (Schmerzmarkierungen vorne/hinten), Fotos, PDFs und **Stiftzeichnungen** (Einzeichnen in Fotos, Vorher/Nachher-Vergleich), Therapieziele mit Zielerreichung, **Therapiebericht als PDF** |
| 3 | **Praxisabläufe** | Kalender (Tag/Woche, Serientermine, Blockzeiten, Absagen), **Verordnungen** mit Einheitenzähler und Prüfhinweisen (Fristen, Unterbrechungen), Wiedervorlagen, Erinnerungsliste, **Übungsbibliothek** und Übungspläne als PDF zum Mitgeben |
| 4 | **Lokale Assistenz** | Diktieren (lokales Whisper), Texterkennung (Tesseract), SOAP aus Diktat und Berichtsentwurf (lokales Sprachmodell). Alles optional, KI-Texte werden nie ungeprüft übernommen |
| 5 | **Abrechnung** | Leistungskatalog, Rechnungen für Privat-/Selbstzahler (lückenlose Nummern, Storno, Zahlungen, überfällig, PDF), **Kassenabrechnung (GKV) als Prüfliste mit CSV-Export**, Auswertungen (Behandlungen, Umsatz, Terminquoten, Dokumentationsvollständigkeit) |
| 6 | **Betrieb & Datenschutz** | Automatische Abmeldung, Kontosperre, unveränderliches Protokoll (auch in der Datenbank erzwungen), Akten-Export (Art. 15/20), Aufbewahrung und Löschung, verschlüsselte Backups mit Wiederherstellungstest, Integritätsprüfung, Lasttest, CI |

**Rollen:** *Administrator* (alles, Verwaltung), *Therapeut/in* (alles außer Verwaltung), *Empfang* (Stammdaten, Termine, Rechnungen, **keine** medizinischen Daten).

**Bedienung:** Die Oberfläche ist für Tablet und PC gebaut. Große Touchflächen, Schnellauswahl statt Tippen (Maßnahmen, Warnzeichen, Schmerzskala), Werte der letzten Behandlung übernehmen. Am PC: `/` öffnet die Patientensuche, `n` legt einen neuen Patienten an. Bei WLAN-Ausfall erscheint eine Warnung.

### Ausdrücklich nicht enthalten

- **Datenträgeraustausch mit den Krankenkassen (§ 302 SGB V):** Die Software prüft die Vollständigkeit der Verordnungen und exportiert CSV für die Abrechnungsstelle. Die eigentliche GKV-Abrechnung (Preislisten, Zuzahlungsberechnung, Übermittlung, IK-Verfahren) braucht eine eigene fachliche Spezifikation, wie im Konzept vorgesehen.
- **Echter Offline-Modus für Tablets** (offene Entscheidung im Konzept, siehe `docs/BETRIEB.md`).
- **Umsatzsteuer:** Rechnungen weisen Heilbehandlungen als umsatzsteuerfrei aus (Hinweistext einstellbar). Andere Konstellationen sind nicht abgebildet.

## Aufbau

```
backend/    Python 3.13, FastAPI, SQLAlchemy 2, Alembic (Migrationen), PostgreSQL (Entwicklung auch SQLite)
frontend/   React 19 + TypeScript, Vite (keine Laufzeit-Abhängigkeiten außer React und React Router)
scripts/    backup.sh, restore.sh, restore-test.sh, loadtest.py
docs/       BETRIEB.md (Installation, Backup, Wiederherstellung), DATENSCHUTZ.md (Maßnahmen, Betroffenenrechte)
Dockerfile, docker-compose.yml, Caddyfile   Betrieb auf dem NAS (amd64 und arm64)
.github/workflows/ci.yml                    Tests, Typprüfung, Schwachstellen-Audit, Docker-Build
```

Das Backend liefert auch die gebaute Weboberfläche aus. Auf dem NAS laufen nur drei Container: Datenbank, App und HTTPS-Proxy.

## Betrieb im Praxisnetz

Kurzfassung (Details in **`docs/BETRIEB.md`**):

```bash
cp .env.example .env              # POSTGRES_PASSWORD und PHYSIOFLOW_HOST eintragen
docker compose up -d --build
# https://<PHYSIOFLOW_HOST> öffnen, Administratorkonto anlegen, Caddy-Root-Zertifikat auf den Geräten installieren
```

- **Keine Portfreigabe im Router.** PhysioFlow ist nur im lokalen Netz erreichbar.
- **Backups:** `scripts/backup.sh` täglich, `scripts/restore-test.sh` mindestens vierteljährlich. Das System warnt den Administrator bei veralteten Backups. **RAID ist kein Backup.**
- Passwort vergessen: `docker compose exec app python -m app.cli reset-password <benutzername>`

## Entwicklung

Voraussetzungen: Python 3.12 oder neuer, Node.js 20 oder neuer. Optional `tesseract-ocr` mit `tesseract-ocr-deu` für den OCR-Test.

```bash
# Backend (nutzt ohne weitere Konfiguration eine lokale SQLite-Datei)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli seed-demo        # fiktive Beispieldaten, Login: demo / demo-passwort
uvicorn app.main:app --reload      # API-Dokumentation: http://localhost:8000/api/docs

# Frontend (zweites Terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173, leitet /api an das Backend weiter
```

Tests und Prüfungen:

```bash
cd backend && pytest                                   # SQLite, schnell
PHYSIOFLOW_TEST_PG_URL=postgresql+psycopg://postgres@localhost:5432/physioflow_test pytest   # zusätzlich Migrationen und DB-Trigger auf PostgreSQL
cd frontend && npm run build                           # Typprüfung und Build
python scripts/loadtest.py --user demo --password demo-passwort --users 8 --seconds 30
```

Nach Änderungen am Datenmodell eine Migration erzeugen und prüfen: `alembic revision --autogenerate -m "beschreibung"`, danach `alembic check`.

Weitere CLI-Befehle: `python -m app.cli check-integrity` prüft Schema, Dateien und Rechnungsnummern.

### Lokale Assistenz einrichten (optional)

In `.env` bzw. als Umgebungsvariablen: `PHYSIOFLOW_WHISPER_URL` (OpenAI-kompatibler Whisper-Server), `PHYSIOFLOW_LLM_URL` und `PHYSIOFLOW_LLM_MODEL` (OpenAI-kompatibel, z. B. Ollama). Es werden nur Adressen im eigenen Netz akzeptiert. OCR braucht Tesseract (im Docker-Image enthalten).

## Sicherheit und Datenschutz

Ausführlich in `docs/DATENSCHUTZ.md`. Kurz: Passwörter mit scrypt, `HttpOnly`/`SameSite=Strict`/`Secure`-Cookies, CSRF-Header, strenge Content-Security-Policy (keine externen Ressourcen), Rollen, Sperre nach Fehlversuchen, Abmeldung bei Inaktivität, Dateiprüfung am Inhalt und EXIF-Entfernung, nie löschen sondern stornieren, unveränderliches Änderungsprotokoll, Lösch- und Exportfunktion, verschlüsselte Backups. Abhängigkeiten sind auf feste Versionen gepinnt und werden in der CI auf bekannte Schwachstellen geprüft.

## Vor dem Produktivbetrieb

Diese Punkte kann die Software nicht selbst erledigen:

1. **NAS bestätigen:** Modell (vorläufig ASUSTOR AS3302T), RAM, Docker-Unterstützung. Installation und ein Lasttest auf dem echten Gerät (`scripts/loadtest.py`).
2. **Docker-Setup einmal komplett durchspielen:** Die Compose-Datei wurde in der Entwicklungsumgebung nur formal geprüft, die Container konnten dort nicht gestartet werden. Das gilt auch für `backup.sh`, `restore.sh` und `restore-test.sh`. Deren Kernschritte (Dump, Verschlüsselung, Wiederherstellung, Integritätsprüfung) wurden lokal gegen PostgreSQL geprüft.
3. **Rechtliche Prüfung** (Verarbeitungsverzeichnis, Einwilligungstexte, Aufbewahrungsfristen, Rechnungsangaben) und **unabhängige Sicherheitsprüfung** der Installation.
4. **Fachliche Spezifikation** für die GKV-Abrechnung und die Prüfregeln der Verordnungen. Die Fristen in `docs/BETRIEB.md` sind Voreinstellungen und müssen mit der aktuellen Heilmittel-Richtlinie abgeglichen werden.
5. **Tablets und Stifte testen** (Handschrift-zu-Text, Druckempfindlichkeit, Handballen-Ablehnung) und **Offline-Verhalten entscheiden**.
6. Praxisprozesse festlegen: Administrator, Backup-Medium, Passphrase-Aufbewahrung, Wiederherstellungstest.
