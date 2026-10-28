export const SEX: Record<string, string> = { female: "weiblich", male: "männlich", diverse: "divers", unknown: "keine Angabe" };
export const INSURANCE: Record<string, string> = { gkv: "Gesetzlich (GKV)", private: "Privat", self_pay: "Selbstzahler", bg: "Berufsgenossenschaft" };
export const SIDE: Record<string, string> = { none: "–", left: "links", right: "rechts", both: "beidseits" };
export const ROLE: Record<string, string> = { admin: "Administrator", therapist: "Therapeut/in", reception: "Empfang" };
export const DIAGNOSIS_STATUS: Record<string, string> = { active: "aktiv", resolved: "abgeschlossen" };

export const CATEGORY: Record<string, string> = { rom: "Beweglichkeit", strength: "Kraft", test: "Tests", measure: "Messwerte" };
export const MARK_KIND: Record<string, string> = {
  pain: "Schmerz",
  tension: "Verspannung",
  numbness: "Taubheit/Kribbeln",
  swelling: "Schwellung",
  scar: "Narbe",
  other: "Sonstiges",
};
export const GOAL_STATUS: Record<string, string> = { open: "offen", achieved: "erreicht", dropped: "verworfen" };

export const ACTION: Record<string, string> = {
  create: "angelegt",
  update: "geändert",
  correct: "korrigiert",
  void: "storniert",
};
export const ENTITY: Record<string, string> = {
  finding: "Befund",
  body_mark: "Körperatlas-Markierung",
  attachment: "Datei",
  goal: "Therapieziel",
  patient: "Stammdaten",
  anamnesis: "Anamnese",
  diagnosis: "Diagnose",
  treatment: "Behandlung",
};

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
}

export function age(birthDate: string): number {
  const b = new Date(birthDate);
  const now = new Date();
  let a = now.getFullYear() - b.getFullYear();
  if (now.getMonth() < b.getMonth() || (now.getMonth() === b.getMonth() && now.getDate() < b.getDate())) a--;
  return a;
}

export function today(): string {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export const FIELD: Record<string, string> = {
  first_name: "Vorname", last_name: "Nachname", birth_date: "Geburtsdatum", sex: "Geschlecht",
  street: "Straße", postal_code: "PLZ", city: "Ort", phone: "Telefon", mobile: "Mobil", email: "E-Mail",
  occupation: "Beruf", emergency_contact: "Notfallkontakt", insurance_type: "Versicherungsart",
  insurance_name: "Kostenträger", insurance_number: "Versichertennr.", referring_physician: "Verordner/in",
  consent_treatment: "Einwilligung Behandlung", consent_data_processing: "Einwilligung Datenverarbeitung",
  consent_date: "Datum Einwilligung", notes: "Notizen", archived: "Archiviert",
  recorded_on: "Datum", chief_complaint: "Hauptbeschwerde", onset: "Beginn", current_history: "Aktuelle Anamnese",
  past_history: "Vorerkrankungen", surgeries: "Operationen", medication: "Medikamente",
  pain_current: "Schmerz aktuell", pain_max: "Schmerz maximal", pain_character: "Schmerzcharakter",
  aggravating_factors: "Verstärkend", relieving_factors: "Lindernd", red_flags: "Warnzeichen",
  red_flags_notes: "Anmerkung Warnzeichen", activity_sport: "Alltag/Sport", goals: "Therapieziele",
  icd10_code: "ICD-10", description: "Diagnose", side: "Seite", diagnosed_on: "Gestellt am",
  diagnosed_by: "Gestellt von", is_primary: "Hauptdiagnose", status: "Status",
  treated_on: "Datum", diagnosis_id: "Diagnose", duration_minutes: "Dauer (min)", measures: "Maßnahmen",
  subjective: "Subjektiv", objective: "Objektiv", assessment: "Beurteilung", plan: "Plan",
  pain_before: "Schmerz vorher", pain_after: "Schmerz nachher", home_exercises: "Hausübungen",
  category: "Kategorie", name: "Bezeichnung", value_num: "Messwert", value_text: "Ergebnis", unit: "Einheit",
  view: "Ansicht", x: "Position X", y: "Position Y", kind: "Art", intensity: "Intensität", note: "Notiz",
  caption: "Beschriftung", taken_on: "Aufnahmedatum", ocr_text: "Erkannter Text", target_date: "Zieldatum",
  achieved_on: "Erreicht am", metric_name: "Messgröße", metric_side: "Messseite", baseline_value: "Ausgangswert",
  target_value: "Zielwert",
};
