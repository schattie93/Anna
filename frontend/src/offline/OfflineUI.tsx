import { useState, useSyncExternalStore, type FormEvent } from "react";
import Modal from "../components/Modal";
import { ErrorBox } from "../components/fields";
import { formatDateTime } from "../labels";
import * as core from "./core";
import * as vault from "./vault";

export const useOffline = () => useSyncExternalStore(core.subscribe, core.getState);

/** Hinweisleiste: Verbindungsstatus, wartende Einträge, Übertragungsfehler. */
export function OfflineBar() {
  const s = useOffline();
  if (s.reachable && s.pending === 0) return null;
  return (
    <div className={s.reachable ? "offline-banner sync" : "offline-banner"} role="status">
      {!s.reachable ? (
        <>
          <strong>Keine Verbindung zum Praxisserver.</strong>{" "}
          {s.vault === "none"
            ? "Der Offline-Modus ist auf diesem Gerät nicht eingerichtet (Einstellungen → Offline-Modus); bereits geöffnete Seiten bleiben sichtbar, Eingaben können nicht gespeichert werden."
            : "Sie können zwischengespeicherte Akten ansehen und neue Einträge erfassen. Sie werden übertragen, sobald die Verbindung wieder da ist."}
          {s.pending > 0 && <> {s.pending} Eintrag/Einträge warten auf Übertragung.</>}
        </>
      ) : s.vault !== "unlocked" ? (
        <>
          {s.pending} offline erfasste Einträge warten auf Übertragung.{" "}
          <button className="btn small" onClick={() => core.ensureUnlocked().catch(() => undefined)}>
            Entsperren und übertragen
          </button>
        </>
      ) : (
        <>
          {s.syncing ? "Offline erfasste Einträge werden übertragen …" : `${s.pending - s.failed.length} Eintrag/Einträge warten auf Übertragung.`}{" "}
          {!s.syncing && s.pending > s.failed.length && (
            <button className="btn small" onClick={() => void core.syncNow()}>
              Jetzt übertragen
            </button>
          )}
        </>
      )}
      {s.failed.length > 0 && (
        <ul className="sync-failed">
          {s.failed.map((o) => (
            <li key={o.op_id}>
              <strong>Nicht übertragen ({formatDateTime(o.client_time)}):</strong> {o.error}{" "}
              <button className="btn small" onClick={() => void core.retryOp(o.op_id)}>
                Erneut versuchen
              </button>{" "}
              <button className="btn small" onClick={() => void core.discardOp(o.op_id)}>
                Verwerfen
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Abfrage der PIN/Passphrase, wenn Offline-Daten gebraucht werden. */
export function UnlockDialog() {
  const s = useOffline();
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!s.unlockRequested) return null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await vault.unlock(pin);
      setPin("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Offline-Daten entsperren" onClose={core.cancelUnlock}>
      <form className="stack" onSubmit={submit}>
        <p className="muted">Geben Sie die PIN/Passphrase ein, die Sie für den Offline-Modus auf diesem Gerät festgelegt haben.</p>
        <input type="password" autoFocus value={pin} onChange={(e) => setPin(e.target.value)} aria-label="PIN oder Passphrase" autoComplete="off" />
        <ErrorBox error={error} />
        <div className="actions">
          <button type="button" className="btn" onClick={core.cancelUnlock}>
            Abbrechen
          </button>
          <button className="btn primary" disabled={busy || !pin}>
            Entsperren
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** Einstellungen: Offline-Modus einrichten, vorbereiten, sperren, löschen. */
export function OfflineCard() {
  const s = useOffline();
  const [pin, setPin] = useState("");
  const [pin2, setPin2] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function setup(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (pin !== pin2) return setError("Die Eingaben stimmen nicht überein");
    try {
      await vault.setup(pin);
      setPin("");
      setPin2("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="card stack">
      <h2>Offline-Modus (dieses Gerät)</h2>
      <p className="muted">
        Bei WLAN-Ausfall bleiben die Akten der heutigen Patienten lesbar, und neue Behandlungen, Befunde, Körperatlas-Markierungen, Erstbefunde, Anamnesen und Unterschriften lassen sich erfassen. Sie werden automatisch
        übertragen, sobald die Verbindung wieder da ist. Korrekturen, Stornierungen, Fotos und Abrechnung brauchen die Verbindung. Die Daten liegen <strong>verschlüsselt</strong> auf dem Gerät (Schlüssel aus Ihrer
        Passphrase). Zusätzlich sollte das Tablet selbst mit Sperrcode und Geräteverschlüsselung gesichert sein.
      </p>
      {s.vault === "none" || s.vault === "unknown" ? (
        <form className="form-grid" onSubmit={setup}>
          <label className="field">
            <span className="field-label">Passphrase für dieses Gerät (mind. 8 Zeichen)</span>
            <input type="password" value={pin} onChange={(e) => setPin(e.target.value)} autoComplete="new-password" required />
          </label>
          <label className="field">
            <span className="field-label">Wiederholen</span>
            <input type="password" value={pin2} onChange={(e) => setPin2(e.target.value)} autoComplete="new-password" required />
          </label>
          <div className="wide">
            <ErrorBox error={error} />
            <p className="muted">Wer die Passphrase vergisst, kann die lokalen Offline-Daten nicht mehr öffnen. Sie lassen sich dann nur löschen. Noch nicht übertragene Einträge gingen dabei verloren.</p>
            <button className="btn primary">Offline-Modus einrichten</button>
          </div>
        </form>
      ) : (
        <div className="stack">
          <ul className="plain checks-list">
            <li className={s.vault === "unlocked" ? "ok" : "warn"}>{s.vault === "unlocked" ? "Entsperrt (sperrt sich nach 15 Minuten ohne Bedienung)" : "Gesperrt – zum Nutzen der Offline-Daten entsperren"}</li>
            <li className={s.lastPrepared ? "ok" : "warn"}>
              {s.lastPrepared ? `Zuletzt vorbereitet: ${formatDateTime(new Date(s.lastPrepared).toISOString())} (${s.preparedCount} Akten)` : "Noch nicht vorbereitet"}
            </li>
            <li className={s.pending === 0 ? "ok" : "warn"}>{s.pending} Einträge warten auf Übertragung</li>
          </ul>
          <div className="actions">
            {s.vault === "locked" ? (
              <button className="btn primary" onClick={() => core.ensureUnlocked().catch(() => undefined)}>
                Entsperren
              </button>
            ) : (
              <>
                <button className="btn primary" disabled={s.preparing || !s.reachable} onClick={() => void core.prepare()}>
                  {s.preparing ? "Wird vorbereitet …" : "Jetzt für Offline vorbereiten"}
                </button>
                <button className="btn" onClick={vault.lock}>
                  Sperren
                </button>
              </>
            )}
            <button
              className="btn danger"
              onClick={async () => {
                const warn = s.pending > 0 ? `${s.pending} noch nicht übertragene Einträge gehen verloren! ` : "";
                if (window.confirm(`${warn}Alle Offline-Daten und die Passphrase auf diesem Gerät löschen?`)) await core.wipeAll();
              }}
            >
              Offline-Daten auf diesem Gerät löschen
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
