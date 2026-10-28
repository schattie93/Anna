// Verschlüsselung der lokal gespeicherten Daten: Schlüssel aus PIN/Passphrase (PBKDF2), Daten mit AES-GCM.
const enc = new TextEncoder();
const dec = new TextDecoder();
const ITERATIONS = 310_000;

export interface Sealed {
  iv: Uint8Array;
  data: ArrayBuffer;
}

export function randomBytes(n: number): Uint8Array {
  return crypto.getRandomValues(new Uint8Array(n));
}

export async function deriveKey(secret: string, salt: Uint8Array): Promise<CryptoKey> {
  const base = await crypto.subtle.importKey("raw", enc.encode(secret), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "PBKDF2", salt: salt as BufferSource, iterations: ITERATIONS, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
}

export async function seal(key: CryptoKey, value: unknown): Promise<Sealed> {
  const iv = randomBytes(12);
  const data = await crypto.subtle.encrypt({ name: "AES-GCM", iv: iv as BufferSource }, key, enc.encode(JSON.stringify(value)));
  return { iv, data };
}

export async function open<T>(key: CryptoKey, sealed: Sealed): Promise<T> {
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: sealed.iv as BufferSource }, key, sealed.data);
  return JSON.parse(dec.decode(plain)) as T;
}
