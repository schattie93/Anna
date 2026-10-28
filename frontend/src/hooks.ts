import { useCallback, useEffect, useState } from "react";
import { api, type Catalog } from "./api";

/** Lädt Daten von der API und bietet ein reload() nach Änderungen. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    setError(null);
    api<T>(path).then(
      (d) => !cancelled && setData(d),
      (e: Error) => !cancelled && setError(e.message),
    );
    return () => {
      cancelled = true;
    };
  }, [path, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, error, reload };
}

let catalogPromise: Promise<Catalog> | null = null;

export function useCatalog(): Catalog | null {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  useEffect(() => {
    catalogPromise ??= api<Catalog>("/catalog");
    catalogPromise.then(setCatalog, () => (catalogPromise = null));
  }, []);
  return catalog;
}
