# Fachliche Prüfung – Checkliste für die Praxis

> **Anpassen ohne Programmierung:** Warnzeichen, psychosoziale Faktoren, Maßnahmen und Befundvorlagen (inkl. Richtwerte) pflegt der Administrator unter **Verwaltung → Fachliche Vorlagen**. Dort erscheinen die mitgelieferten Werte als „ungeprüft“, bis sie freigegeben werden. Der Heilmittelkatalog steht unter Einstellungen, die Übungen unter „Übungen“. Die Spalte „Wo im Programm / Code“ unten nennt noch die Standardwerte im Quelltext, die nur beim ersten Start als Vorlage dienen.

PhysioFlow wurde **nicht** von einer Physiotherapeutin oder einem Physiotherapeuten fachlich geprüft. Alle fachlichen Vorlagen stammen aus allgemeinem Wissen und können unvollständig oder falsch sein. Diese Liste zeigt, was die Praxis vor dem Produktivbetrieb durchsehen sollte. Bitte Ergebnisse mit Datum und Namen festhalten.

| Bereich | Wo im Programm / Code | Was prüfen | Status |
|---|---|---|---|
| Warnzeichen (Red Flags) | `backend/app/catalog.py` → `RED_FLAGS` | Vollständigkeit und Formulierung für Ihre Patientengruppen; Auswahl ggf. kürzen oder ergänzen | offen |
| Psychosoziale Faktoren (Yellow Flags) | `catalog.py` → `YELLOW_FLAGS` | Passen die Punkte zu Ihrem Vorgehen (z. B. mit einem Screening-Fragebogen kombinieren)? | offen |
| Befundvorlagen, Tests, Assessments | `catalog.py` → `FINDING_PRESETS` | Stimmen Namen und Einheiten? Fehlen häufig genutzte Tests oder Skalen? Bei Skalen (z. B. Berg, Barthel, NDI) Wertebereiche prüfen | offen |
| **Richtwerte Beweglichkeit** | `catalog.py` → `ROM_NORMS` | **Ungeprüfte Richtwerte** für die Neutral-Null-Methode, angezeigt als Orientierung. Quellen weichen voneinander ab. Mit Ihrer Lehrbuchquelle abgleichen oder die Werte entfernen | offen |
| Heilmittel / Maßnahmen | `catalog.py` → `MEASURES` | Entspricht die Liste Ihrem Leistungsspektrum und dem Heilmittelkatalog? | offen |
| Heilmittelkatalog (Mengenprüfung) | Einstellungen → Heilmittelkatalog | **Von der Praxis zu pflegen** (bewusst nicht vorbelegt): Indikationsschlüssel, Höchstmenge je Verordnung, orientierende Behandlungsmenge aus dem aktuellen Katalog | offen |
| Verordnungsfristen | `PHYSIOFLOW_RX_START_DAYS` (28), `PHYSIOFLOW_RX_URGENT_START_DAYS` (14), `PHYSIOFLOW_RX_MAX_BREAK_DAYS` (14) | Mit der aktuellen Heilmittel-Richtlinie abgleichen, Ausnahmen (z. B. längere Unterbrechungen bei medizinischer Begründung) berücksichtigen. Die Prüfhinweise sind Hilfen, keine rechtliche Prüfung | offen |
| Verordnungsangaben | Reiter Verordnungen | Sind alle Pflichtangaben Ihrer Kassen abgebildet (z. B. Diagnosegruppe, Leitsymptomatik, Hausbesuch, Gültigkeit)? | offen |
| Leistungsnachweis | Reiter Behandlungen → Unterschrift | Entspricht die digitale Unterschrift den Anforderungen Ihrer Abrechnungsstelle/Kassen? **Rückfrage bei der Abrechnungsstelle**; ggf. bleibt die Unterschrift auf der Papierverordnung nötig | offen |
| Kassenabrechnung | Abrechnung → Kassenabrechnung | Die Prüfliste ersetzt nicht die Regeln Ihrer Abrechnungsstelle. Abgleich mit deren Anforderungen | offen |
| Beispielübungen | Übungen | 25 Beispielübungen, **nicht freigegeben**. Jede Übung prüfen, Kontraindikationen ergänzen, dann freigeben. Erst danach druckbar | offen |
| Rechnungen | Abrechnung → Rechnungen | Pflichtangaben (§ 14 UStG), Umsatzsteuer-Hinweis, Preisbezug (z. B. Gebührenordnung für Privatpatienten) steuerlich/rechtlich prüfen | offen |
| Aufbewahrung/Löschung | `PHYSIOFLOW_RETENTION_YEARS` (10) | Fristen für Behandlungsdokumentation und Buchungsbelege prüfen | offen |
| Einwilligungstexte | – (nicht Teil der Software) | Texte für Behandlung und Datenverarbeitung rechtlich prüfen lassen | offen |

## Hinweise

- Die **Neutral-Null-Methode** wird als „Gegenrichtung – Neutral – Hauptrichtung“ erfasst (z. B. Knie Extension/Flexion 0-0-130). Für Diagramme und Zielwerte zählt der Wert der Hauptrichtung.
- Der **Erstbefund** (Inspektion, Palpation, Funktion, Hypothese, ICF) ist ein freier Gliederungsvorschlag. Wenn Ihre Praxis einen festen Befundbogen nutzt, lässt sich die Gliederung anpassen.
- Die Software gibt keine klinischen Empfehlungen. Die KI-Funktionen formulieren nur Texte aus vorhandenen Angaben und sind Entwürfe.
