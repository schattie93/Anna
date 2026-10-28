// Minimaler IndexedDB-Wrapper (Versprechen statt Callbacks).
const NAME = "physioflow-offline";
const STORES = ["meta", "cache", "queue"] as const;
export type StoreName = (typeof STORES)[number];

let dbPromise: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  dbPromise ??= new Promise((resolve, reject) => {
    const req = indexedDB.open(NAME, 1);
    req.onupgradeneeded = () => {
      for (const s of STORES) if (!req.result.objectStoreNames.contains(s)) req.result.createObjectStore(s);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

async function run<T>(store: StoreName, mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const req = fn(db.transaction(store, mode).objectStore(store));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export const get = <T>(store: StoreName, key: string) => run<T | undefined>(store, "readonly", (s) => s.get(key));
export const put = (store: StoreName, key: string, value: unknown) => run(store, "readwrite", (s) => s.put(value, key));
export const del = (store: StoreName, key: string) => run(store, "readwrite", (s) => s.delete(key));
export const count = (store: StoreName) => run(store, "readonly", (s) => s.count());
export const clear = (store: StoreName) => run(store, "readwrite", (s) => s.clear());
export const keys = (store: StoreName) => run<IDBValidKey[]>(store, "readonly", (s) => s.getAllKeys());
export const all = <T>(store: StoreName) => run<T[]>(store, "readonly", (s) => s.getAll());

export async function entries<T>(store: StoreName): Promise<[string, T][]> {
  const [ks, vs] = await Promise.all([keys(store), all<T>(store)]);
  return ks.map((k, i) => [String(k), vs[i]]);
}
