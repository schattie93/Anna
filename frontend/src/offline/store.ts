// Verschlüsselter Zwischenspeicher der Akten und Warteschlange der offline erfassten Einträge.
import * as db from "./db";
import { open, seal, type Sealed } from "./crypto";
import { getKey } from "./vault";

export type QueuedKind = "create_treatment" | "create_finding" | "create_body_mark" | "create_examination" | "create_anamnesis" | "sign_treatment";

export interface QueuedOp {
  op_id: string;
  kind: QueuedKind;
  patient_id: number;
  temp_id: number | null;
  client_time: string;
  data: Record<string, unknown>;
  collection: string | null; // Listenpfad, in dem der Eintrag lokal erscheint
  error?: string;
}

interface CacheRecord {
  at: number;
  sealed: Sealed;
}
interface QueueRecord {
  at: number;
  sealed: Sealed;
}

export const MAX_CACHE_AGE_MS = 7 * 24 * 3600_000;

export async function cachePut(path: string, value: unknown): Promise<void> {
  await db.put("cache", path, { at: Date.now(), sealed: await seal(getKey(), value) } satisfies CacheRecord);
}

export async function cacheGet<T>(path: string): Promise<T | undefined> {
  const rec = await db.get<CacheRecord>("cache", path);
  if (!rec || Date.now() - rec.at > MAX_CACHE_AGE_MS) return undefined;
  return open<T>(getKey(), rec.sealed);
}

export async function cacheDeletePrefix(prefix: string): Promise<void> {
  for (const k of await db.keys("cache")) if (String(k).startsWith(prefix)) await db.del("cache", String(k));
}

/** Entfernt abgelaufene Einträge (benötigt keinen Schlüssel: Zeitstempel liegt unverschlüsselt vor). */
export async function cachePurgeOld(): Promise<void> {
  for (const [k, rec] of await db.entries<CacheRecord>("cache")) if (Date.now() - rec.at > MAX_CACHE_AGE_MS) await db.del("cache", k);
}

export async function cacheCount(): Promise<number> {
  return db.count("cache");
}

export async function queueCount(): Promise<number> {
  return db.count("queue");
}

export async function queueSave(op: QueuedOp): Promise<void> {
  await db.put("queue", op.op_id, { at: Date.parse(op.client_time), sealed: await seal(getKey(), op) } satisfies QueueRecord);
}

export async function queueRemove(opId: string): Promise<void> {
  await db.del("queue", opId);
}

export async function queueList(): Promise<QueuedOp[]> {
  const rows = await db.entries<QueueRecord>("queue");
  rows.sort((a, b) => a[1].at - b[1].at);
  return Promise.all(rows.map(([, r]) => open<QueuedOp>(getKey(), r.sealed)));
}
