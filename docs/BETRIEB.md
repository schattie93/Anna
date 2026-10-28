# Betriebshandbuch

Für die Person, die PhysioFlow im Praxisnetz installiert und betreut. Alle Befehle werden im Projektordner ausgeführt.

## 1. Voraussetzungen

- Ein Server im Praxisnetz mit Docker und Docker Compose (z. B. ASUSTOR-NAS mit Docker/Portainer). Das Modell (vorläufig AS3302T, ARM64) und der Arbeitsspeicher sind **noch zu bestätigen**. Alle Images (Python, Node, PostgreSQL, Caddy) gibt es für amd64 und arm64.
- Arbeitsspeicher: Postgres ist auf kleinen Speicherbedarf eingestellt. Grob 1 GB für das Gesamtsystem. Die Texterkennung (Tesseract) braucht beim Ausführen kurzzeitig mehr. Bei knappem RAM kann sie mit `--build-arg WITH_OCR=false` aus dem Image entfallen.
- Aufwendige KI (Spracherkennung, Textvorschläge) läuft **nicht** auf dem NAS, sondern bei Bedarf auf einem separaten Rechner im Praxisnetz (siehe Abschnitt 6).
- Der Router leitet **keine** Ports ins Internet weiter. PhysioFlow ist nur aus dem Praxisnetz erreichbar.

## 2. Installation

```bash
cp .env.example .env          # starkes POSTGRES_PASSWORD und PHYSIOFLOW_HOST (Name oder feste IP des Servers) eintragen
docker compose up -d --build
```

1. Im Browser `https://<PHYSIOFLOW_HOST>` öffnen. Beim ersten Start wird das Administratorkonto angelegt.
2. **Zertifikat:** Caddy erzeugt eine eigene Zertifizierungsstelle (`tls internal`). Das Root-Zertifikat `data/caddy/pki/authorities/local/root.crt` einmalig auf PC, Android- und iPad-Tablets installieren und als vertrauenswürdig markieren. Erst dann funktioniert HTTPS ohne Warnung. Außerdem erlauben Browser den Mikrofonzugriff nur über HTTPS.
3. Unter **Einstellungen** die Praxisdaten (Briefkopf, Bankverbindung, Steuernummer) eintragen.
4. Benutzer anlegen (Therapeut/in, Empfang). Für den täglichen Gebrauch nicht das Administratorkonto verwenden.
5. Unter **Übungen** die Beispielübungen laden, unter **Abrechnung > Leistungen** Leistungen und Preise anlegen.

Die Datenbank läuft nur im internen Docker-Netz. Der App-Container hat keinen veröffentlichten Port. Erreichbar ist nur Caddy auf 80/443.

## 3. Aktualisieren

```bash
git pull
./scripts/backup.sh /backup/ziel        # vorher immer ein Backup
docker compose up -d --build            # Datenbank-Migrationen laufen beim Start automatisch
```

Danach unter **Verwaltung > Betrieb** die Integritätsprüfung ausführen.

## 4. Datensicherung

**Was gesichert wird:** die Datenbank und alle Dateien (Fotos, PDFs, Zeichnungen). Beides ist mit AES-256 (GPG) verschlüsselt.

```bash
echo "eine-lange-zufaellige-passphrase" > /sicherer/ort/backup-passphrase   # einmalig; Rechte: chmod 600
BACKUP_PASSPHRASE_FILE=/sicherer/ort/backup-passphrase ./scripts/backup.sh /pfad/zum/backupmedium
```

- **Täglich** per Aufgabenplanung des NAS ausführen. Das Ziel muss ein **anderes Medium** sein (externe Platte, zweites NAS). **RAID ist kein Backup.**
- Die Passphrase getrennt vom Backup aufbewahren (z. B. Passwortmanager und ausgedruckt im Tresor). **Ohne Passphrase sind die Backups wertlos.**
- Das Skript prüft die Backups direkt nach dem Schreiben und vermerkt sie im System. Der Administrator sieht auf der Übersicht eine Warnung, wenn das letzte Backup älter als 2 Tage ist.
- Eine Kopie außer Haus (verschlüsselt, z. B. Platte im Bankschließfach) schützt vor Feuer, Einbruch und Ransomware.

## 5. Wiederherstellung und Wiederherstellungstest

**Test (mindestens vierteljährlich und nach größeren Änderungen):**

```bash
BACKUP_PASSPHRASE_FILE=/sicherer/ort/backup-passphrase ./scripts/restore-test.sh /pfad/zum/backupmedium
```

Das Skript spielt das neueste Backup in eine Wegwerf-Datenbank ein, prüft Schema, Dateien (Prüfsummen) und Rechnungsnummern und vermerkt den Test. Das laufende System bleibt unberührt.

**Im Ernstfall:**

```bash
BACKUP_PASSPHRASE_FILE=... ./scripts/restore.sh <physioflow-db-...gpg> <physioflow-files-...gpg>
```

Das ersetzt **alle** aktuellen Daten durch den Stand des Backups. Sie müssen zur Bestätigung `WIEDERHERSTELLEN` eintippen.

## 6. Optionale lokale KI-Dienste

Standardmäßig ist alles aus. Es werden nur Adressen im eigenen Netz akzeptiert (localhost, Docker-Dienstnamen, `*.local`, `*.lan`, private IP-Bereiche). Eine Adresse im Internet wird abgelehnt.

| Funktion | Einstellung in `.env` | Hinweise |
|---|---|---|
| Diktieren | `PHYSIOFLOW_WHISPER_URL=http://rechner.local:8000` | OpenAI-kompatibler Whisper-Server, z. B. faster-whisper-server, auf einem Rechner im Praxisnetz |
| Textvorschläge | `PHYSIOFLOW_LLM_URL=http://rechner.local:11434`, `PHYSIOFLOW_LLM_MODEL=...` | OpenAI-kompatibel, z. B. Ollama. Läuft bei den meisten NAS zu langsam, besser auf einem PC mit Grafikkarte |
| Texterkennung (OCR) | `WITH_OCR` beim Bauen (Standard an) | Tesseract im App-Container, läuft vollständig lokal |

Berichtsentwürfe der KI enthalten **keine** Namen, Adressen oder Versichertennummern (nur Alter, Geschlecht, Diagnosen und Verlauf). KI-Texte sind immer Entwürfe und werden erst nach Prüfung durch die Fachperson übernommen. Die Nutzung wird ohne Inhalte im Protokoll vermerkt.

**Handschrift:** Apple Scribble (iPad) und die Handschrift-zu-Text-Funktion von Samsung/Android arbeiten direkt im Gerät in allen Textfeldern. Zusätzlich lässt sich eine eingescannte Notiz per OCR erkennen. Tesseract ist für **Druckschrift** gedacht und erkennt Handschrift nur eingeschränkt. Welche Tablets und Stifte im Alltag am besten funktionieren, muss noch getestet werden.

## 7. Passwort vergessen, Benutzer sperren

- Der Administrator kann Passwörter zurücksetzen und Konten deaktivieren (Einstellungen > Benutzerverwaltung). Deaktivieren beendet alle Sitzungen des Kontos.
- Passwort des Administrators vergessen: `docker compose exec app python -m app.cli reset-password <benutzername>`
- Nach 5 falschen Anmeldeversuchen wird ein Konto 15 Minuten gesperrt. Nach 60 Minuten Inaktivität erfolgt die automatische Abmeldung (`PHYSIOFLOW_IDLE_MINUTES`).
- Tablet verloren: unter Einstellungen **Auf allen Geräten abmelden**.

## 8. Konfiguration (Umgebungsvariablen)

Alle mit Präfix `PHYSIOFLOW_`:

| Variable | Standard | Bedeutung |
|---|---|---|
| `DATABASE_URL` | (Compose setzt sie) | PostgreSQL-Verbindung |
| `COOKIE_SECURE` | `true` im Compose | Cookies nur über HTTPS |
| `TIMEZONE` | `Europe/Berlin` | Praxis-Zeitzone für Tagesgrenzen und Fristen |
| `IDLE_MINUTES` | 60 | automatische Abmeldung |
| `RETENTION_YEARS` | 10 | Aufbewahrungsfrist für den Löschvorschlag |
| `MAX_UPLOAD_MB` | 25 | größte Datei |
| `RX_START_DAYS`, `RX_URGENT_START_DAYS`, `RX_MAX_BREAK_DAYS` | 28, 14, 14 | Fristen der Verordnungs-Prüfhinweise (mit der aktuellen Heilmittel-Richtlinie abgleichen) |

## 9. Überwachung und Fehlersuche

- Verwaltung > Betrieb: Backup-Alter, Wiederherstellungstest, Integritätsprüfung (Datenbank, Dateien, Rechnungsnummern). Dasselbe auf der Kommandozeile: `docker compose exec app python -m app.cli check-integrity`
- Logs: `docker compose logs -f app`
- Lasttest: `python scripts/loadtest.py --url https://<host> --user <benutzer> --password ... --users 8 --seconds 30 --insecure`
  Auf einem Entwicklungsrechner mit 8 gleichzeitigen Benutzern lagen die Antwortzeiten bei etwa 20 ms (Median) und unter 100 ms (95 %). Eine einzelne Praxis braucht wesentlich weniger. Auf dem NAS bitte selbst messen.

## 10. Offene Entscheidungen

- **Arbeiten bei WLAN-Ausfall:** Aktuell zeigt die Oberfläche eine Warnung, wenn der Server nicht erreichbar ist. Offene Formulare bleiben auf dem Bildschirm, werden aber nicht lokal gespeichert, damit keine Patientendaten auf den Tablets liegen. Ein echter Offline-Modus (zwischengespeicherte Akten, Warteschlange) ist ein eigenes Vorhaben mit Sicherheits- und Konfliktfragen und muss bewusst entschieden werden. Praktische Lösung bis dahin: ein eigener, robuster Access Point für den Behandlungsraum.
- NAS-Modell, RAM, Container-Unterstützung bestätigen (Abschnitt 1).
