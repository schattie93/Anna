# PhysioFlow

Lokale Praxissoftware für die Physiotherapie: Patientenaufnahme, Anamnese, Diagnosen und Behandlungsdokumentation.
Alle Daten bleiben im Praxisnetz. Es gibt keine Cloud-Dienste und keine externe KI.

Grundlage ist das Projektkonzept vom 28.10.2026. Dieser Stand setzt **Phase 1 – Grundsystem** um.

> ⚠️ **Noch nicht für den Produktivbetrieb freigegeben.** Vor der Nutzung mit echten Patientendaten
> stehen die Sicherheitsprüfung, Restore-Tests und das NAS-Deployment aus (Phase 6). Für Entwicklung und Tests
> nur fiktive Daten verwenden.

## Funktionsumfang (Phase 1)

| Bereich | Inhalt |
|---|---|
| **Anmeldung** | Lokale Benutzerkonten mit den Rollen Administrator und Therapeut/in. Die Sitzung läuft über ein HttpOnly-Cookie und endet nach 12 h. Beim ersten Start wird das Administratorkonto eingerichtet. |
| **Dashboard** | Patientensuche, Kennzahlen, offene Dokumentationen (Entwürfe) und zuletzt bearbeitete Patienten |
| **Patientenakte** | Stammdaten, Kontakt, Notfallkontakt, Versicherung, verordnende Ärztin bzw. verordnender Arzt, Einwilligungen (Behandlung/DSGVO) und Archivierung |
| **Anamnese** | Hauptbeschwerde, Verlauf, Schmerz (NRS 0–10 als Touch-Skala), Schmerzcharakter, Red-Flag-Checkliste, Vorgeschichte, OPs, Medikamente und Therapieziele |
| **Diagnosen** | ICD-10, Seite, Hauptdiagnose, Status sowie wer die Diagnose wann gestellt hat |
| **Behandlungen** | SOAP-Struktur, Maßnahmen als Schnellauswahl, Dauer, Schmerz vorher/nachher und Hausübungen. Werte der letzten Behandlung lassen sich bewusst übernehmen. Eine Behandlung ist erst Entwurf und wird dann abgeschlossen. |
| **Nachvollziehbarkeit** | Medizinische Einträge werden nie gelöscht, sondern **storniert** (mit Begründung). Wer eine Anamnese oder eine abgeschlossene Behandlung ändert, muss einen **Korrekturgrund** angeben. Jede Änderung landet mit Vorher/Nachher im unveränderlichen **Änderungsprotokoll**. Auch Zugriffe auf Akten und Anmeldeversuche werden protokolliert. |

Die Oberfläche ist für die Bedienung per Tablet ausgelegt: große Touchflächen, Chips statt Tipparbeit und ein Layout, das sich an die Bildschirmbreite anpasst.
Am PC gibt es Tastaturkürzel: `/` öffnet die Patientensuche, `n` legt einen neuen Patienten an.

## Aufbau

```
backend/    Python 3.13, FastAPI, SQLAlchemy 2, Alembic (Migrationen), PostgreSQL
frontend/   React 19 + TypeScript, Vite
Dockerfile, docker-compose.yml, Caddyfile   Betrieb auf dem NAS (amd64 und arm64)
scripts/backup.sh   verschlüsseltes Datenbank-Backup
```

Das Backend liefert auch die gebaute Weboberfläche aus. So braucht man auf dem NAS nur einen App-Container, eine Datenbank und den HTTPS-Proxy.

## Entwicklung

Voraussetzungen: Python 3.12 oder neuer, Node.js 20 oder neuer.

```bash
# Backend (nutzt ohne weitere Konfiguration eine lokale SQLite-Datei)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli seed-demo        # fiktive Beispieldaten, Login: demo / demo-passwort
uvicorn app.main:app --reload      # http://localhost:8000/api/docs

# Frontend (zweites Terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173, leitet /api an das Backend weiter
```

Tests und Typprüfung:

```bash
cd backend && pytest
cd frontend && npm run build
```

Wer das Datenmodell ändert, erzeugt danach eine neue Migration:

```bash
cd backend
alembic revision --autogenerate -m "beschreibung"
```

## Betrieb im Praxisnetz (Docker Compose)

1. `cp .env.example .env`, dann ein starkes `POSTGRES_PASSWORD` und den Hostnamen bzw. die IP des NAS eintragen.
2. `docker compose up -d --build` ausführen.
3. `https://<PHYSIOFLOW_HOST>` im Browser öffnen und das Administratorkonto anlegen.
4. Das Root-Zertifikat von Caddy (`data/caddy/pki/authorities/local/root.crt`) auf PC und Tablets als vertrauenswürdig installieren.

Wichtig:

- **Keine Portfreigabe im Router.** PhysioFlow darf nur im lokalen Netz erreichbar sein.
- **Backups** mit `scripts/backup.sh` regelmäßig auf ein getrenntes Medium schreiben. Die Backups sind mit GPG verschlüsselt. Die Wiederherstellung regelmäßig testen, denn RAID ist kein Backup.
- Ein vergessenes Passwort setzt man so zurück: `docker compose exec app python -m app.cli reset-password <benutzername>`.
- Ob das ASUSTOR-Modell (vorläufig AS3302T, ARM64) Docker unterstützt und genug RAM hat, ist noch zu bestätigen. Die Images sind für arm64 verfügbar. PostgreSQL ist auf geringen Speicherbedarf eingestellt.

## Sicherheit (Stand Phase 1)

- Passwörter werden mit scrypt gehasht. Sitzungstokens liegen nur als SHA-256-Hash in der Datenbank.
- Cookies sind `HttpOnly` und `SameSite=Strict`, hinter HTTPS zusätzlich `Secure`. Schreibende API-Aufrufe brauchen einen eigenen Header als CSRF-Schutz.
- Benutzer verwalten dürfen nur Administratoren. Wird ein Konto deaktiviert oder sein Passwort zurückgesetzt, beendet das alle Sitzungen dieses Kontos.
- Noch offen für die Produktivfreigabe: Sperre nach mehreren Fehlanmeldungen, feinere Rollenrechte, Aufbewahrungs- und Löschkonzept, Datenexport und eine externe Sicherheitsprüfung.

## Nächste Schritte laut Konzept

- **Phase 2 – Dokumentation:** Körperatlas mit Schmerzmarkierungen, Stifteingabe, Fotos, Befundbögen (Beweglichkeit, Kraft, Tests), Verlaufsdiagramme, PDF-Berichte
- **Phase 3 – Praxisabläufe:** Termine, Verordnungen mit Fristen, Wiedervorlagen, Übungsbibliothek
- **Phase 4 – Lokale Assistenz:** OCR, Handschrifterkennung, Sprachtranskription, geprüfte KI-Vorschläge (alles lokal)
- **Phase 5 – Abrechnung**, **Phase 6 – Produktivfreigabe**
