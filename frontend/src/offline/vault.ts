// Tresor: Die lokalen Offline-Daten sind mit einem Schlüssel aus PIN/Passphrase verschlüsselt. Der Schlüssel liegt nur im
// Arbeitsspeicher und verschwindet nach Inaktivität oder beim Abmelden. Er schützt vor dem Auslesen des Speichers eines
// verlorenen Geräts; die Gerätesperre und -verschlüsselung des Tablets bleiben die wichtigste Absicherung.
import * as db from "./db";
import { deriveKey, open, randomBytes, seal, type Sealed } from "./crypto";

interface Meta {
  salt: Uint8Array;
  verifier: Sealed;
}

const AUTO_LOCK_MS = 15 * 60_000;
export const MIN_PASSPHRASE = 8;

let key: CryptoKey | null = null;
let timer: ReturnType<typeof setTimeout> | undefined;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const subscribe = (fn: () => void) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

export const isUnlocked = () => key !== null;
export function getKey(): CryptoKey {
  if (!key) throw new Error("Offline-Daten sind gesperrt");
  return key;
}

export async function isSetUp(): Promise<boolean> {
  return (await db.get<Meta>("meta", "vault")) !== undefined;
}

function touch() {
  clearTimeout(timer);
  if (key) timer = setTimeout(lock, AUTO_LOCK_MS);
}

if (typeof window !== "undefined") {
  for (const ev of ["pointerdown", "keydown"]) window.addEventListener(ev, touch, { passive: true });
}

export function lock() {
  key = null;
  clearTimeout(timer);
  emit();
}

export async function setup(secret: string): Promise<void> {
  if (secret.length < MIN_PASSPHRASE) throw new Error(`Mindestens ${MIN_PASSPHRASE} Zeichen`);
  const salt = randomBytes(16);
  const k = await deriveKey(secret, salt);
  await db.put("meta", "vault", { salt, verifier: await seal(k, "ok") } satisfies Meta);
  key = k;
  touch();
  emit();
}

export async function unlock(secret: string): Promise<void> {
  const meta = await db.get<Meta>("meta", "vault");
  if (!meta) throw new Error("Offline-Modus ist nicht eingerichtet");
  const k = await deriveKey(secret, meta.salt);
  try {
    if ((await open<string>(k, meta.verifier)) !== "ok") throw new Error();
  } catch {
    throw new Error("PIN/Passphrase falsch");
  }
  key = k;
  touch();
  emit();
}

/** Löscht alle lokalen Offline-Daten (Zwischenspeicher, Warteschlange, Tresor). */
export async function wipe(): Promise<void> {
  key = null;
  await Promise.all([db.clear("cache"), db.clear("queue"), db.clear("meta")]);
  emit();
}
