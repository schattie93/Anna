// Offline-Logik: Erreichbarkeit, Zwischenspeicher für Lesezugriffe, Warteschlange für Neuanlagen, Übertragung.
// Offline möglich sind nur Neuanlagen (Behandlung, Befund, Körperatlas, Erstbefund, Anamnese, Unterschrift). Korrekturen und
// Stornierungen erfordern die Verbindung. Dadurch kann es keine Konflikte mit anderen Änderungen geben.
import type { PatientListItem } from "../api";
import * as store from "./store";
import type { QueuedKind, QueuedOp } from "./store";
import * as vault from "./vault";

export class OfflineError extends Error {}

type ApiFn = <T>(path: string, options?: { method?: string; body?: unknown }) => Promise<T>;
let apiFn: ApiFn | null = null;
export const registerApi = (fn: ApiFn) => {
  apiFn = fn;
};

export interface OfflineState {
  reachable: boolean;
  vault: "unknown" | "none" | "locked" | "unlocked";
  pending: number;
  failed: QueuedOp[];
  syncing: boolean;
  preparing: boolean;
  lastPrepared: number | null;
  preparedCount: number;
  unlockRequested: boolean;
}

let state: OfflineState = {
  reachable: true,
  vault: "unknown",
  pending: 0,
  failed: [],
  syncing: false,
  preparing: false,
  lastPrepared: Number(localStorage.getItem("physioflow_prepared_at")) || null,
  preparedCount: Number(localStorage.getItem("physioflow_prepared_count")) || 0,
  unlockRequested: false,
};
const listeners = new Set<() => void>();
const set = (patch: Partial<OfflineState>) => {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
};
export const subscribe = (fn: () => void) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};
export const getState = () => state;

let queue: QueuedOp[] = []; // entschlüsselte Kopie der Warteschlange (nur solange entsperrt)
let user: { id: number; full_name: string } | null = null;
export const setUser = (u: { id: number; full_name: string } | null) => {
  user = u;
};

// --- Initialisierung und Tresor-Status -------------------------------------------------------

let initPromise: Promise<void> | null = null;
export function init(): Promise<void> {
  initPromise ??= (async () => {
    vault.subscribe(() => void refreshVault());
    await store.cachePurgeOld().catch(() => undefined);
    await refreshVault();
  })();
  return initPromise;
}

async function refreshVault() {
  const setUp = await vault.isSetUp().catch(() => false);
  const unlocked = vault.isUnlocked();
  if (unlocked && !queueLoaded) {
    queue = await store.queueList().catch(() => []);
    queueLoaded = true;
  }
  if (!unlocked) {
    queue = [];
    queueLoaded = false;
  }
  set({
    vault: !setUp ? "none" : unlocked ? "unlocked" : "locked",
    pending: unlocked ? queue.length : await store.queueCount().catch(() => 0),
    failed: unlocked ? queue.filter((o) => o.error) : [],
  });
  if (unlocked) {
    resolveUnlock();
    syncSoon();
  }
}
let queueLoaded = false;

let waiters: { resolve: () => void; reject: (e: Error) => void }[] = [];
export async function ensureUnlocked(): Promise<void> {
  await init();
  if (vault.isUnlocked()) return;
  if (state.vault === "none") throw new OfflineError("Der Offline-Modus ist auf diesem Gerät nicht eingerichtet (Einstellungen → Offline-Modus).");
  return new Promise((resolve, reject) => {
    waiters.push({ resolve, reject });
    set({ unlockRequested: true });
  });
}
export function resolveUnlock() {
  waiters.forEach((w) => w.resolve());
  waiters = [];
  set({ unlockRequested: false });
}
export function cancelUnlock() {
  waiters.forEach((w) => w.reject(new OfflineError("Offline-Daten sind gesperrt.")));
  waiters = [];
  set({ unlockRequested: false });
}

export async function wipeAll() {
  await vault.wipe();
  queue = [];
  queueLoaded = false;
  localStorage.removeItem("physioflow_prepared_at");
  localStorage.removeItem("physioflow_prepared_count");
  set({ vault: "none", pending: 0, failed: [], lastPrepared: null, preparedCount: 0 });
}

// --- Erreichbarkeit -------------------------------------------------------------------------------

export function setReachable(ok: boolean) {
  if (ok === state.reachable) return;
  set({ reachable: ok });
  if (ok) syncSoon();
}

// --- Zwischenspeicher --------------------------------------------------------------------------------

const PATIENT_PATH = /^\/patients\/(\d+)(\/(anamneses|diagnoses|treatments|findings|goals|prescriptions|examinations|body-marks|attachments|exercise-plans))?$/;
const COLLECTION = /^\/patients\/(\d+)\/(treatments|findings|body-marks|examinations|anamneses)$/;
const SIGNATURE = /^\/patients\/(\d+)\/treatments\/(-?\d+)\/signature$/;
const KIND_OF: Record<string, QueuedKind> = {
  treatments: "create_treatment",
  findings: "create_finding",
  "body-marks": "create_body_mark",
  examinations: "create_examination",
  anamneses: "create_anamnesis",
};
const SORT_FIELD: Record<string, string> = { treatments: "treated_on", findings: "recorded_on", "body-marks": "recorded_on", examinations: "recorded_on", anamneses: "recorded_on" };
const IDX = "idx:patients";

const localDate = (s: string | null) => (s ? new Date(s).toLocaleDateString("sv-SE") : "");

export function cacheKey(path: string): string | null {
  const [p, q] = path.split("?");
  if (PATIENT_PATH.test(p) && (!q || q === "cache=1")) return p;
  if (p === "/catalog" || p === "/dashboard") return p;
  if (p === "/appointments" && q) {
    const sp = new URLSearchParams(q);
    return `appointments:${localDate(sp.get("start"))}:${localDate(sp.get("end"))}:${sp.get("patient_id") ?? ""}:${sp.get("therapist_id") ?? ""}`;
  }
  return null;
}

let indexChain: Promise<void> = Promise.resolve();
function indexAdd(items: PatientListItem[]) {
  indexChain = indexChain.then(async () => {
    const cur = (await store.cacheGet<Record<number, PatientListItem>>(IDX)) ?? {};
    for (const it of items) cur[it.id] = { id: it.id, patient_number: it.patient_number, first_name: it.first_name, last_name: it.last_name, birth_date: it.birth_date, city: it.city, insurance_type: it.insurance_type, archived: it.archived };
    await store.cachePut(IDX, cur);
  }).catch(() => undefined);
}

const suggested = new Set<number>();

/** Wird nach jedem erfolgreichen Lesezugriff aufgerufen: Daten (verschlüsselt) für die Offline-Nutzung merken. */
export function onGet(path: string, data: unknown) {
  setReachable(true);
  if (!vault.isUnlocked()) return;
  const key = cacheKey(path);
  if (key) void store.cachePut(key, data).catch(() => undefined);
  if (path.startsWith("/patients?") && Array.isArray(data)) indexAdd(data as PatientListItem[]);
  else if (/^\/patients\/\d+(\?cache=1)?$/.test(path)) indexAdd([data as PatientListItem]);
  if (path === "/dashboard") {
    const d = data as { appointments_today: { patient: { id: number } | null }[]; recent_patients: { id: number }[] };
    d.appointments_today.forEach((a) => a.patient && suggested.add(a.patient.id));
    d.recent_patients.forEach((p) => suggested.add(p.id));
  }
}

async function searchIndex(path: string): Promise<PatientListItem[]> {
  await ensureUnlocked();
  const sp = new URLSearchParams(path.split("?")[1] ?? "");
  const terms = (sp.get("q") ?? "").toLowerCase().split(/\s+/).filter(Boolean);
  const includeArchived = sp.get("include_archived") === "true";
  const idx = (await store.cacheGet<Record<number, PatientListItem>>(IDX)) ?? {};
  return Object.values(idx)
    .filter((p) => (includeArchived || !p.archived) && terms.every((t) => [p.first_name, p.last_name, p.patient_number, p.city ?? ""].some((f) => f.toLowerCase().includes(t))))
    .sort((a, b) => a.last_name.localeCompare(b.last_name) || a.first_name.localeCompare(b.first_name))
    .slice(0, Number(sp.get("limit")) || 50);
}

// --- Offline erfasste Einträge im Verlauf anzeigen ---------------------------------------------------------

function synth(op: QueuedOp): Record<string, unknown> {
  const { finalize, ...fields } = op.data as Record<string, unknown> & { finalize?: boolean };
  const base = {
    ...fields,
    id: op.temp_id,
    patient_id: op.patient_id,
    created_by: { id: user?.id ?? 0, full_name: user?.full_name ?? "Offline erfasst" },
    created_at: op.client_time,
    updated_at: op.client_time,
    voided: false,
    void_reason: null,
    voided_at: null,
    pending: true,
    pending_error: op.error ?? null,
  };
  return op.kind === "create_treatment" ? { ...base, status: finalize ? "final" : "draft", finalized_at: finalize ? op.client_time : null, signed: false } : base;
}

export function mergePending<T>(path: string, data: T): T {
  if (queue.length === 0 || !Array.isArray(data)) return data;
  const clean = path.split("?")[0];
  const m = clean.match(COLLECTION);
  if (!m) return data;
  const field = SORT_FIELD[m[2]];
  const extra = queue.filter((o) => o.collection === clean).map(synth);
  let items = [...(data as Record<string, unknown>[]), ...extra];
  if (m[2] === "treatments") {
    const signed = new Set(queue.filter((o) => o.kind === "sign_treatment" && o.patient_id === Number(m[1])).map((o) => o.data.treatment_id));
    items = items.map((t) => (signed.has(t.id) ? { ...t, signed: true } : t));
  }
  items.sort((a, b) => String(b[field]).localeCompare(String(a[field])) || Number(b.id) - Number(a.id));
  return items as T;
}

// --- Warteschlange ----------------------------------------------------------------------------------

const tempId = () => -(1 + Math.floor(Math.random() * 2_000_000_000));

async function push(op: Omit<QueuedOp, "op_id" | "client_time">): Promise<QueuedOp> {
  await ensureUnlocked();
  const full: QueuedOp = { ...op, op_id: crypto.randomUUID(), client_time: new Date().toISOString() };
  await store.queueSave(full);
  queue.push(full);
  set({ pending: queue.length });
  return full;
}

/** Netzwerkfehler: Lesezugriffe aus dem Zwischenspeicher bedienen, Neuanlagen in die Warteschlange legen. */
export async function handleNetworkFailure<T>(path: string, method: string, body: unknown): Promise<T> {
  setReachable(false);
  if (method === "GET") {
    const key = cacheKey(path);
    if (!key && !path.startsWith("/patients?")) throw new OfflineError("Ohne Verbindung nicht verfügbar.");
    await ensureUnlocked();
    if (path.startsWith("/patients?")) return (await searchIndex(path)) as T;
    const cached = key ? await store.cacheGet<T>(key) : undefined;
    if (cached === undefined) throw new OfflineError("Ohne Verbindung nicht verfügbar – diese Daten sind auf diesem Gerät nicht zwischengespeichert.");
    return mergePending(path, cached);
  }
  const m = path.match(COLLECTION);
  if (method === "POST" && m) {
    const op = await push({ kind: KIND_OF[m[2]], patient_id: Number(m[1]), temp_id: tempId(), data: body as Record<string, unknown>, collection: path });
    return synth(op) as T;
  }
  throw new OfflineError("Ohne Verbindung nicht möglich. Offline lassen sich nur neue Einträge erfassen (Behandlung, Befund, Körperatlas, Erstbefund, Anamnese, Unterschrift). Korrekturen und Stornierungen gehen erst mit Verbindung.");
}

export function isSignaturePath(path: string): boolean {
  return SIGNATURE.test(path);
}

export async function signatureOffline(path: string, png: Blob): Promise<unknown> {
  const m = path.match(SIGNATURE);
  if (!m) throw new OfflineError("Dateien können nur mit Verbindung hochgeladen werden.");
  const bytes = new Uint8Array(await png.arrayBuffer());
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  const op = await push({ kind: "sign_treatment", patient_id: Number(m[1]), temp_id: tempId(), data: { treatment_id: Number(m[2]), png_base64: btoa(bin) }, collection: null });
  return { id: op.temp_id, kind: "signature", treatment_id: Number(m[2]), pending: true };
}

export function touchesPending(path: string): boolean {
  return /\/-\d+(\/|$)/.test(path.split("?")[0]);
}

// --- Übertragung ------------------------------------------------------------------------------------

let syncTimer: ReturnType<typeof setTimeout> | undefined;
export function syncSoon() {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => void syncNow(), 600);
}

let syncing = false;
export async function syncNow(): Promise<void> {
  if (syncing || !state.reachable || !vault.isUnlocked()) return;
  const ops = queue.filter((o) => !o.error);
  if (ops.length === 0) return;
  syncing = true;
  set({ syncing: true });
  try {
    const res = await fetch("/api/sync", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-PhysioFlow": "1", "Content-Type": "application/json" },
      body: JSON.stringify({ ops: ops.map(({ error: _e, collection: _c, ...o }) => o) }),
      signal: AbortSignal.timeout(60_000),
    });
    if (res.status === 401) {
      window.dispatchEvent(new Event("physioflow:unauthorized")); // nach erneuter Anmeldung geht es weiter
      return;
    }
    if (!res.ok) return;
    const { results } = (await res.json()) as { results: { op_id: string; ok: boolean; error: string | null }[] };
    const touched = new Set<number>();
    for (const r of results) {
      const op = queue.find((o) => o.op_id === r.op_id);
      if (!op) continue;
      touched.add(op.patient_id);
      if (r.ok) {
        await store.queueRemove(op.op_id);
        queue = queue.filter((o) => o !== op);
      } else {
        op.error = r.error ?? "Fehler bei der Übertragung";
        await store.queueSave(op);
      }
    }
    for (const pid of touched) await store.cacheDeletePrefix(`/patients/${pid}`);
    set({ pending: queue.length, failed: queue.filter((o) => o.error) });
    window.dispatchEvent(new Event("physioflow:synced"));
  } catch {
    /* Verbindung weg: später erneut */
  } finally {
    syncing = false;
    set({ syncing: false });
  }
}

export async function discardOp(opId: string) {
  await store.queueRemove(opId);
  queue = queue.filter((o) => o.op_id !== opId);
  set({ pending: queue.length, failed: queue.filter((o) => o.error) });
  window.dispatchEvent(new Event("physioflow:synced"));
}

export async function retryOp(opId: string) {
  const op = queue.find((o) => o.op_id === opId);
  if (!op) return;
  delete op.error;
  await store.queueSave(op);
  set({ failed: queue.filter((o) => o.error) });
  syncSoon();
}

// --- Vorbereiten: Akten der heutigen Patienten laden ----------------------------------------------------------

const PATIENT_PARTS = ["", "/anamneses", "/diagnoses", "/treatments", "/findings", "/goals", "/prescriptions", "/examinations", "/body-marks", "/attachments", "/exercise-plans"];

export async function prepare(): Promise<void> {
  if (!apiFn || !vault.isUnlocked() || !state.reachable || state.preparing) return;
  set({ preparing: true });
  try {
    await apiFn("/dashboard");
    await apiFn("/catalog");
    const ids = [...suggested].slice(0, 25);
    let next = 0;
    const worker = async () => {
      while (next < ids.length) {
        const id = ids[next++];
        for (const part of PATIENT_PARTS) await apiFn!(`/patients/${id}${part}${part === "" ? "?cache=1" : ""}`);
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    const now = Date.now();
    localStorage.setItem("physioflow_prepared_at", String(now));
    localStorage.setItem("physioflow_prepared_count", String(ids.length));
    set({ lastPrepared: now, preparedCount: ids.length });
  } catch {
    /* bei Verbindungsproblemen später erneut */
  } finally {
    set({ preparing: false });
  }
}
