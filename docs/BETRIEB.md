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

## 2a. Installation mit Portainer (z. B. ASUSTOR, zum Testen)

Ohne Kommandozeile: Portainer klont das Repository selbst, baut das Image und startet alle Container. Dafür gibt es die eigene Datei **`docker-compose.portainer.yml`**.

**Warum eine eigene Datei?** Portainer legt Git-Stacks in seinem eigenen Datenverzeichnis ab. Relative Pfade wie `./Caddyfile` oder `./data/postgres` zeigen dort ins Leere: Docker legt dann leere Ordner an, und Caddy startet ohne Konfiguration nicht. Die Portainer-Variante nutzt deshalb nur benannte Volumes, erzeugt die Caddy-Konfiguration beim Start selbst (gleicher Inhalt wie die `Caddyfile`) und lauscht standardmäßig auf Port **8443** statt 443, damit nichts mit der NAS-Oberfläche kollidiert. Außerdem ist `default_sni` gesetzt: Beim Aufruf per IP schicken Browser keinen Servernamen mit, und Caddy würde sonst ein Zertifikat für die interne Container-IP suchen.

**Portainer auf dem ASUSTOR:** In ADM unter **App Central** die Apps **Docker Engine** und **Portainer CE** installieren. Portainer ist dann unter `https://<NAS-IP>:19943` erreichbar. Das Startpasswort für `admin` steht in `/Docker/PortainerCE/portainer_password.txt` (ADM File Explorer).

**Stack anlegen:**

1. Portainer → Umgebung **local** → **Stacks** → **Add stack**
2. Name: `physioflow`
3. Build method: **Repository**
   - Repository URL: `https://github.com/schattie93/Anna`
   - Repository reference: `refs/heads/claude/physiotherapy-management-app-cend0z`
   - Compose path: `docker-compose.portainer.yml`
4. **Environment variables** (am einfachsten über *Advanced mode* als Text einfügen):
   ```
   POSTGRES_PASSWORD=langesZufallspasswortNurBuchstabenUndZiffern
   PHYSIOFLOW_HOST=192.168.178.20
   ```
   - `PHYSIOFLOW_HOST` ist die IP (oder der Name) des NAS, **ohne** `https://` und ohne Port.
   - Im Passwort keine Sonderzeichen wie `@ / : #`. Es wird in die Datenbankadresse eingebaut.
   - Optional `PHYSIOFLOW_HTTPS_PORT=…`, falls 8443 schon belegt ist.
5. **Deploy the stack.** Der erste Build dauert auf dem NAS mehrere Minuten (Frontend, Python, Texterkennung). Den Fortschritt zeigt Portainer; Fehler stehen unter **Containers → physioflow-app-1 → Logs**.
6. Im Browser `https://<NAS-IP>:8443` öffnen und die Zertifikatswarnung bestätigen (für Tests ausreichend). Beim ersten Aufruf wird das Administratorkonto angelegt.

**Fiktive Testdaten:** Containers → `physioflow-app-1` → **Console** → *Connect* → `python -m app.cli seed-demo`. Danach ist die Anmeldung mit `demo` / `demo-passwort` möglich. Nur auf einer leeren Datenbank; nie mit echten Patientendaten mischen.

**Root-Zertifikat** (damit die Warnung verschwindet): Containers → `physioflow-proxy-1` → Console → `cat /data/caddy/pki/authorities/local/root.crt`, den Text als `root.crt` speichern und auf den Geräten als vertrauenswürdig installieren.

**Aktualisieren:** Stack öffnen → **Pull and redeploy**, dabei *Re-pull image and redeploy* aktivieren, damit das App-Image neu gebaut wird. Die Daten in den Volumes bleiben erhalten.

**Komplett zurücksetzen** (alle Testdaten weg): Stack löschen, danach unter **Volumes** die Volumes `physioflow_pgdata`, `physioflow_files` und `physioflow_caddy_data` entfernen.

**Grenzen dieser Variante:** Die Skripte `backup.sh`, `restore.sh` und `restore-test.sh` erwarten die normale `docker-compose.yml` im Projektordner und laufen hier nicht direkt. Für den Produktivbetrieb deshalb die Installation aus Abschnitt 2 verwenden (oder die Skripte anpassen). Die Datei wurde formal mit `docker compose config` geprüft; ein vollständiger Start auf dem NAS steht noch aus.

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
| Handschrift erkennen | `PHYSIOFLOW_VISION_MODEL=<Modellname>`, optional `PHYSIOFLOW_VISION_URL` (sonst die LLM-Adresse) | Lokales **Bild-Sprachmodell** (z. B. über Ollama, Kandidaten zum Ausprobieren: Qwen2.5-VL, MiniCPM-V, Llama-3.2-Vision). Braucht deutlich mehr Rechenleistung als das NAS bietet, also einen PC im Praxisnetz, am besten mit Grafikkarte. Die Erkennungsqualität hängt stark vom Modell und von der Handschrift ab und muss mit **echten Beispielen aus der Praxis** geprüft werden |
| Texterkennung (OCR) | `WITH_OCR` beim Bauen (Standard an) | Tesseract im App-Container, läuft vollständig lokal |

Berichtsentwürfe der KI enthalten **keine** Namen, Adressen oder Versichertennummern (nur Alter, Geschlecht, Diagnosen und Verlauf). KI-Texte sind immer Entwürfe und werden erst nach Prüfung durch die Fachperson übernommen. Die Nutzung wird ohne Inhalte im Protokoll vermerkt.

**Handschrift:** Es gibt drei Wege. (1) Apple Scribble (iPad) und die Handschrift-zu-Text-Funktion von Samsung/Android arbeiten direkt im Gerät in allen Textfeldern. (2) Die Stift-Taste ✍ in den Textfeldern der Software: Sie schreiben in eine Fläche, ein lokales Bild-Sprachmodell erkennt die Schrift, und der Text wird erst nach Ihrer Prüfung ins Feld übernommen. (3) Gespeicherte Zeichnungen, Fotos und PDFs lassen sich im Dateibetrachter mit „Handschrift erkennen“ auslesen. Tesseract („Text erkennen (Druckschrift)“) ist für gedruckte Texte gedacht. Handschrifterkennung ist nie fehlerfrei: unleserliche Stellen werden als `[unleserlich]` markiert, ein Ergebnis darf nie ungeprüft übernommen werden. Welche Tablets, Stifte und Modelle im Alltag am besten funktionieren, muss noch getestet werden.

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

## 10. Arbeiten ohne WLAN (Offline-Modus)

Für die Tablets gibt es einen Offline-Modus, der bei WLAN-Ausfall die Arbeit in der Behandlung ermöglicht.

**Einrichten (einmal je Gerät):** Die Seite über das vertrauenswürdige HTTPS öffnen (Zertifikat installiert, siehe Abschnitt 2), anmelden, dann **Einstellungen → Offline-Modus** → eine Passphrase (mind. 8 Zeichen) festlegen. Danach „Jetzt für Offline vorbereiten“. Auf dem iPad die Seite zusätzlich **„Zum Home-Bildschirm“** hinzufügen, sonst kann Safari lokale Daten nach längerer Nichtnutzung löschen. Auf Android die Seite als App installieren.

**Was funktioniert offline:**
- Die Oberfläche startet auch ohne Server (Service Worker).
- Akten der Patienten, die heute Termine haben oder zuletzt geöffnet wurden, sind lesbar. Sie werden automatisch beim Arbeiten und alle 10 Minuten aktualisiert, solange der Offline-Speicher entsperrt ist.
- **Neu erfassen** lassen sich Behandlungen (auch abschließen), Messwerte/Tests, Körperatlas-Markierungen, Erstbefund, Anamnese und die **Unterschrift des Patienten**. Sie erscheinen mit dem Vermerk „offline erfasst – noch nicht übertragen“ und werden bei Verbindung automatisch übertragen. Das Änderungsprotokoll hält fest, dass sie offline erfasst wurden, und wann.

**Was nicht geht:** Korrigieren und Stornieren, Fotos/Dokumente hochladen, Rechnungen, neue Patienten, Termine ändern, KI-Funktionen. Dadurch können keine Konflikte mit anderen Änderungen entstehen. Patienten ohne Termin, die vorher nicht geöffnet wurden, sind offline nicht verfügbar.

**Sicherheit:** Die lokalen Daten sind mit einem Schlüssel aus Ihrer Passphrase verschlüsselt (AES-256, PBKDF2). Der Schlüssel liegt nur im Arbeitsspeicher; nach 15 Minuten ohne Bedienung oder beim Abmelden ist der Speicher wieder gesperrt. Das ersetzt **nicht** die Gerätesicherung: Tablets brauchen Sperrcode, Geräteverschlüsselung und Fernlöschung. Eine kurze oder leicht zu erratende Passphrase ist angreifbar, wenn jemand den Speicher eines verlorenen Geräts ausliest, deshalb eine ausreichend lange Passphrase wählen. Wer die Passphrase vergisst, kann den lokalen Speicher nur löschen. Noch nicht übertragene Einträge gehen dabei verloren, deshalb vor dem Löschen die Verbindung herstellen.

**Praxisregel:** Nach einem WLAN-Ausfall im Programm prüfen, dass keine Einträge mehr „warten“. Bei einem Übertragungsfehler zeigt die rote Leiste die Ursache, der Eintrag lässt sich erneut versuchen oder verwerfen.

## 11. Offene Entscheidungen

- NAS-Modell, RAM, Container-Unterstützung bestätigen (Abschnitt 1).
