# Datenschutz und Sicherheit

> **Hinweis:** Dieses Dokument beschreibt, was die Software technisch tut. Es ist **keine Rechtsberatung**. Für den Produktivbetrieb mit Gesundheitsdaten (Art. 9 DSGVO) sind eine Prüfung durch die Datenschutzbeauftragte bzw. den Datenschutzbeauftragten oder eine Fachanwältin bzw. einen Fachanwalt sowie die Berufsordnung und aktuelle Vorgaben nötig.

## Grundsätze

- **Alle Patientendaten bleiben im Praxisnetz.** Keine Cloud, keine externen Dienste, keine Telemetrie. Die Weboberfläche lädt keine Schriften, Skripte oder Bilder von anderen Servern (Content-Security-Policy `default-src 'self'`).
- **KI nur lokal.** Dienst-Adressen außerhalb des eigenen Netzes werden von der Software abgelehnt. Das gilt auch für die Handschrifterkennung: Bilder mit Patientendaten gehen nur an Modelle im Praxisnetz.
- **Datenminimierung.** Berichtsentwürfe der KI enthalten keine Namen, Adressen oder Versichertennummern. Fotos werden neu kodiert und verlieren dabei EXIF-/GPS-Daten.
- **Entwicklung nur mit fiktiven Daten.** Die Beispieldaten (`python -m app.cli seed-demo`) sind frei erfunden.

## Technische und organisatorische Maßnahmen (Überblick)

| Bereich | Umsetzung |
|---|---|
| Zugang | Eigene Benutzerkonten, Passwörter mit scrypt gehasht (mind. 10 Zeichen), Sperre nach 5 Fehlversuchen, automatische Abmeldung nach Inaktivität, „Auf allen Geräten abmelden“ |
| Berechtigungen | Rollen **Administrator**, **Therapeut/in**, **Empfang**. Der Empfang sieht Stammdaten, Termine und Rechnungen, aber keine Anamnesen, Befunde, Behandlungen, Dateien oder Berichte |
| Übertragung | Nur HTTPS im Praxisnetz (Caddy mit interner Zertifizierungsstelle), Cookies `HttpOnly`, `SameSite=Strict`, `Secure`; CSRF-Schutz per Pflicht-Header; keine Portfreigabe im Router |
| Nachvollziehbarkeit | Medizinische Einträge werden nie gelöscht, nur storniert (mit Begründung). Korrekturen an Anamnesen, Befunden und abgeschlossenen Behandlungen erfordern eine Begründung. Das Änderungsprotokoll hält Vorher/Nachher, Aktenzugriffe und Anmeldeversuche fest und ist in der **Datenbank selbst** gegen Änderung und Löschung geschützt (Trigger) |
| Offline (Tablet) | Nur nach Einrichtung je Gerät. Lokale Daten mit Schlüssel aus Passphrase verschlüsselt (AES-256-GCM, PBKDF2), Schlüssel nur im Arbeitsspeicher, automatische Sperre nach 15 Minuten, Aufbewahrung höchstens 7 Tage, Löschfunktion. Der Service Worker speichert nur Programmdateien. Offline erfasste Einträge sind im Protokoll gekennzeichnet |
| Dateien | Geschützter Speicher außerhalb des Web-Verzeichnisses, zufällige Dateinamen, Auslieferung nur an angemeldete Berechtigte, Inhaltsprüfung (nur JPEG/PNG/WebP/PDF), Prüfsummen |
| Rechnungen | Fortlaufende Nummern ohne Lücken, gestellte Rechnungen unveränderlich, Korrektur nur per Stornorechnung |
| Backup | Täglich, verschlüsselt (AES-256), Datenbank und Dateien, Prüfsummen, getrennt vom Server aufbewahren; Wiederherstellungstest mit Vermerk im System |
| Integrität | Prüfung von Schema, Dateien (SHA-256) und Rechnungsnummern per Knopfdruck bzw. Kommandozeile |

## Betroffenenrechte

- **Auskunft und Übertragbarkeit (Art. 15, 20):** In der Patientenakte **Akte exportieren** liefert eine ZIP-Datei mit allen Daten (JSON) und allen Dateien. Der Export wird protokolliert.
- **Löschung (Art. 17):** Unter **Verwaltung > Aufbewahrung & Löschung** sind Akten mit abgelaufener Aufbewahrungsfrist aufgelistet. Löschen erfordert die Eingabe der Patientennummer und eine Begründung und entfernt alle Daten einschließlich Dateien und der personenbezogenen Protokolleinträge. Übrig bleibt nur ein Eintrag ohne Personenbezug (Patientennummer, Anzahl, Begründung). Vor Fristablauf warnt die Software; ein Löschverlangen sollte vorher rechtlich geprüft werden (gesetzliche Aufbewahrungspflichten gehen vor).
- **Einwilligungen** (Behandlung, Datenverarbeitung) werden je Patient mit Datum erfasst. Fehlende Einwilligungen zeigt die Auswertung an.

## Aufbewahrungsfristen

Voreingestellt sind **10 Jahre ab der letzten Aktivität** (`PHYSIOFLOW_RETENTION_YEARS`). Die Dokumentationspflicht (§ 630f BGB) und steuerliche Aufbewahrungsfristen für Rechnungen können abweichen. **Bitte die für Ihre Praxis geltenden Fristen prüfen und einstellen.** Die Software löscht nie automatisch.

## Was vor dem Produktivbetrieb noch fehlt

- Rechtliche Prüfung (Verzeichnis der Verarbeitungstätigkeiten, ggf. Datenschutz-Folgenabschätzung, Einwilligungstexte, Aufbewahrungsfristen).
- **Unabhängige Sicherheitsprüfung** (Penetrationstest) der installierten Praxisumgebung.
- Festlegung der Praxis-Prozesse: wer Administrator ist, wo Backup-Medium und Passphrase liegen, wer den Wiederherstellungstest durchführt.
- Gerätesicherheit der Tablets (Bildschirmsperre, Geräteverschlüsselung, Fernlöschung). Die Software legt Patientendaten nur verschlüsselt und nur nach Einrichten des Offline-Modus auf dem Gerät ab.
- Der Offline-Modus legt verschlüsselte Patientendaten auf den Tablets ab (siehe `docs/BETRIEB.md`, Abschnitt 10). Das gehört in das Verzeichnis der Verarbeitungstätigkeiten und in die technisch-organisatorischen Maßnahmen: Geräteverwaltung, Sperrcode, Geräteverschlüsselung, Fernlöschung, Umgang mit verlorenen Geräten (Passwort ändern, „auf allen Geräten abmelden“).
