import { useEffect, useState, type FormEvent } from "react";
import { api, type BillableTreatment, type Invoice, type PatientListItem, type PaymentMethod, type Service } from "../api";
import { INVOICE_STATUS, PAYMENT_METHOD, euro, formatDate, parseEuro, today } from "../labels";
import { ErrorBox, Field, ReasonDialog, TextArea, TextField } from "./fields";
import Modal from "./Modal";
import PatientPicker from "./PatientPicker";

/** Neue Rechnung aus abgeschlossenen Behandlungen eines Patienten. */
export function NewInvoiceDialog({ patient: initial, onClose, onCreated }: { patient?: PatientListItem | null; onClose: () => void; onCreated: (inv: Invoice) => void }) {
  const [patient, setPatient] = useState<PatientListItem | null>(initial ?? null);
  const [billable, setBillable] = useState<BillableTreatment[]>([]);
  const [picked, setPicked] = useState<number[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [serviceId, setServiceId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Service[]>("/services").then((s) => {
      setServices(s);
      setServiceId(s[0]?.id ?? null);
    });
  }, []);
  useEffect(() => {
    setPicked([]);
    if (!patient) return setBillable([]);
    api<BillableTreatment[]>(`/patients/${patient.id}/billable`).then((b) => {
      setBillable(b);
      setPicked(b.map((x) => x.treatment_id));
    });
  }, [patient]);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      onCreated(await api<Invoice>("/invoices/from-treatments", { method: "POST", body: { patient_id: patient!.id, treatment_ids: picked, service_id: serviceId } }));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function createManual() {
    setError(null);
    try {
      const p = patient!;
      const name = `${p.first_name} ${p.last_name}`;
      onCreated(await api<Invoice>(`/patients/${p.id}/invoices`, { method: "POST", body: { recipient_name: name, items: [{ treatment_id: null, service_date: today(), description: "", quantity: 1, unit_price_cents: 0 }] } }));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Modal title="Neue Rechnung" onClose={onClose} wide>
      <form className="form-grid" onSubmit={create}>
        <div className="field wide">
          <span className="field-label">Patient *</span>
          <PatientPicker value={patient} onChange={setPatient} autoFocus={!initial} />
        </div>
        {patient && (
          <>
            <Field label="Leistung" wide>
              <select value={serviceId ?? ""} onChange={(e) => setServiceId(Number(e.target.value))} required>
                {services.length === 0 && <option value="">Zuerst Leistungen anlegen (Reiter „Leistungen“)</option>}
                {services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} – {euro(s.price_cents)}
                  </option>
                ))}
              </select>
            </Field>
            <div className="field wide">
              <span className="field-label">Abgeschlossene, noch nicht abgerechnete Behandlungen</span>
              {billable.length === 0 ? (
                <p className="muted">Keine offenen Behandlungen. Eine Rechnung mit freien Positionen ist möglich.</p>
              ) : (
                <ul className="plain checklist">
                  {billable.map((b) => (
                    <li key={b.treatment_id}>
                      <label className="check">
                        <input type="checkbox" checked={picked.includes(b.treatment_id)} onChange={(e) => setPicked((p) => (e.target.checked ? [...p, b.treatment_id] : p.filter((x) => x !== b.treatment_id)))} />
                        <span>
                          {formatDate(b.treated_on)}
                          {b.measures.length > 0 && ` · ${b.measures.join(", ")}`}
                          {b.prescription_label && <span className="muted"> · Verordnung {b.prescription_label}</span>}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
        <div className="wide">
          <ErrorBox error={error} />
        </div>
        <div className="actions wide">
          <button type="button" className="btn" onClick={onClose}>
            Abbrechen
          </button>
          {patient && (
            <button type="button" className="btn" onClick={createManual}>
              Freie Rechnung
            </button>
          )}
          <button className="btn primary" disabled={!patient || picked.length === 0 || !serviceId}>
            Entwurf erstellen ({picked.length})
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** Rechnung ansehen/bearbeiten: Entwurf ändern, stellen, Zahlungen erfassen, stornieren, PDF. */
export function InvoiceDialog({ invoiceId, onClose, onChanged }: { invoiceId: number; onClose: () => void; onChanged: () => void }) {
  const [inv, setInv] = useState<Invoice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recipient, setRecipient] = useState("");
  const [address, setAddress] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [items, setItems] = useState<{ treatment_id: number | null; service_date: string; description: string; quantity: number; price: string }[]>([]);
  const [cancelling, setCancelling] = useState(false);
  const [voidPay, setVoidPay] = useState<number | null>(null);
  const [pay, setPay] = useState({ paid_on: today(), amount: "", method: "transfer" as PaymentMethod, note: "" });

  function load(i: Invoice) {
    setInv(i);
    setRecipient(i.recipient_name);
    setAddress(i.recipient_address);
    setNote(i.note);
    setItems(i.items.map((x) => ({ treatment_id: x.treatment_id, service_date: x.service_date, description: x.description, quantity: x.quantity, price: (x.unit_price_cents / 100).toFixed(2).replace(".", ",") })));
    setPay((p) => ({ ...p, amount: ((i.total_cents - i.paid_cents) / 100).toFixed(2).replace(".", ",") }));
  }
  useEffect(() => {
    api<Invoice>(`/invoices/${invoiceId}`).then(load, (e: Error) => setError(e.message));
  }, [invoiceId]);

  async function run<T>(fn: () => Promise<T>, done?: (r: T) => void) {
    setError(null);
    try {
      const r = await fn();
      done?.(r);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!inv) return <Modal title="Rechnung" onClose={onClose}>{error ? <ErrorBox error={error} /> : <p className="muted">Lade …</p>}</Modal>;

  const draft = inv.status === "draft";
  const parsed = items.map((i) => ({ ...i, cents: parseEuro(i.price) }));
  const valid = parsed.every((i) => i.cents !== null && i.description.trim());
  const body = () => ({
    recipient_name: recipient,
    recipient_address: address,
    note,
    items: parsed.map((i) => ({ treatment_id: i.treatment_id, service_date: i.service_date, description: i.description, quantity: i.quantity, unit_price_cents: i.cents })),
  });
  const total = parsed.reduce((s, i) => s + (i.cents ?? 0) * i.quantity, 0);
  const title = inv.number ? `Rechnung ${inv.number}` : "Rechnungsentwurf";

  return (
    <Modal title={title} onClose={onClose} wide>
      <p className="muted">
        {inv.patient.last_name}, {inv.patient.first_name} · <span className={`badge ${inv.status === "paid" ? "ok" : inv.overdue ? "danger" : inv.status === "draft" ? "warn" : ""}`}>{inv.overdue ? "überfällig" : INVOICE_STATUS[inv.status]}</span>
        {inv.issue_date && <> · vom {formatDate(inv.issue_date)}</>}
        {inv.due_date && inv.status === "issued" && <> · fällig {formatDate(inv.due_date)}</>}
        {inv.cancels_id && <> · Stornorechnung</>}
      </p>
      <ErrorBox error={error} />

      {draft ? (
        <div className="stack">
          <div className="form-grid">
            <TextField label="Rechnungsempfänger" value={recipient} onChange={(v) => setRecipient(v ?? "")} required />
            <TextArea label="Anschrift" value={address} onChange={setAddress} rows={3} />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Datum</th>
                  <th>Leistung</th>
                  <th>Menge</th>
                  <th>Einzelpreis (€)</th>
                  <th>Betrag</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((it, i) => (
                  <tr key={i}>
                    <td>
                      <input type="date" value={it.service_date} onChange={(e) => setItems((l) => l.map((x, j) => (j === i ? { ...x, service_date: e.target.value } : x)))} />
                    </td>
                    <td>
                      <input value={it.description} onChange={(e) => setItems((l) => l.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))} />
                    </td>
                    <td>
                      <input type="number" min={1} value={it.quantity} onChange={(e) => setItems((l) => l.map((x, j) => (j === i ? { ...x, quantity: Math.max(1, Number(e.target.value)) } : x)))} />
                    </td>
                    <td>
                      <input inputMode="decimal" value={it.price} onChange={(e) => setItems((l) => l.map((x, j) => (j === i ? { ...x, price: e.target.value } : x)))} />
                    </td>
                    <td>{euro((parsed[i].cents ?? 0) * it.quantity)}</td>
                    <td>
                      <button type="button" className="btn small danger" onClick={() => setItems((l) => l.filter((_, j) => j !== i))} disabled={items.length === 1}>
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={4} className="right">
                    <strong>Gesamt</strong>
                  </td>
                  <td colSpan={2}>
                    <strong>{euro(total)}</strong>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          <button type="button" className="btn small" onClick={() => setItems((l) => [...l, { treatment_id: null, service_date: today(), description: "", quantity: 1, price: "0,00" }])}>
            + Position
          </button>
          <TextArea label="Hinweis auf der Rechnung" value={note} onChange={setNote} rows={2} />
          <div className="actions">
            <button
              className="btn danger"
              onClick={() => run(() => api(`/invoices/${inv.id}`, { method: "DELETE" }), () => onClose())}
            >
              Entwurf löschen
            </button>
            <button className="btn" disabled={!valid || !recipient.trim()} onClick={() => run(() => api<Invoice>(`/invoices/${inv.id}`, { method: "PUT", body: body() }), load)}>
              Speichern
            </button>
            <a className="btn" href={`/api/invoices/${inv.id}/pdf`} target="_blank" rel="noreferrer">
              Vorschau (PDF)
            </a>
            <button
              className="btn primary"
              disabled={!valid || !recipient.trim()}
              onClick={() =>
                run(async () => {
                  await api(`/invoices/${inv.id}`, { method: "PUT", body: body() });
                  return api<Invoice>(`/invoices/${inv.id}/issue`, { method: "POST" });
                }, load)
              }
            >
              Rechnung stellen
            </button>
          </div>
          <p className="muted">Beim Stellen erhält die Rechnung ihre fortlaufende Nummer und kann danach nur noch per Storno korrigiert werden.</p>
        </div>
      ) : (
        <div className="stack">
          <p>
            <strong>{inv.recipient_name}</strong>
            {inv.recipient_address && <span className="muted block pre">{inv.recipient_address}</span>}
          </p>
          <div className="table-wrap">
            <table>
              <tbody>
                {inv.items.map((i) => (
                  <tr key={i.id}>
                    <td>{formatDate(i.service_date)}</td>
                    <td>{i.description}</td>
                    <td>{i.quantity} ×</td>
                    <td>{euro(i.unit_price_cents)}</td>
                    <td className="right">{euro(i.total_cents)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={4} className="right">
                    <strong>Gesamt</strong>
                  </td>
                  <td className="right">
                    <strong>{euro(inv.total_cents)}</strong>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          {inv.note && <p className="muted">{inv.note}</p>}

          {!inv.cancels_id && inv.status !== "cancelled" && (
            <section className="card">
              <h3>Zahlungen · bezahlt {euro(inv.paid_cents)} von {euro(inv.total_cents)}</h3>
              {inv.payments.length > 0 && (
                <ul className="plain">
                  {inv.payments.map((p) => (
                    <li key={p.id} className={p.voided ? "struck" : undefined}>
                      {formatDate(p.paid_on)} · {euro(p.amount_cents)} · {PAYMENT_METHOD[p.method]}
                      {p.note && ` · ${p.note}`}
                      {p.voided ? ` · storniert: ${p.void_reason}` : (
                        <button className="link-btn" onClick={() => setVoidPay(p.id)}>
                          {" "}
                          stornieren
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              <form
                className="form-grid"
                onSubmit={(e) => {
                  e.preventDefault();
                  const cents = parseEuro(pay.amount);
                  if (cents && cents > 0) run(() => api<Invoice>(`/invoices/${inv.id}/payments`, { method: "POST", body: { paid_on: pay.paid_on, amount_cents: cents, method: pay.method, note: pay.note || null } }), load);
                }}
              >
                <TextField label="Eingang am" type="date" value={pay.paid_on} onChange={(v) => setPay({ ...pay, paid_on: v ?? "" })} required />
                <TextField label="Betrag (€)" value={pay.amount} onChange={(v) => setPay({ ...pay, amount: v ?? "" })} required />
                <Field label="Art">
                  <select value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value as PaymentMethod })}>
                    {Object.entries(PAYMENT_METHOD).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                </Field>
                <TextField label="Notiz" value={pay.note} onChange={(v) => setPay({ ...pay, note: v ?? "" })} />
                <div className="actions wide">
                  <button className="btn primary">Zahlung erfassen</button>
                </div>
              </form>
            </section>
          )}
          <div className="actions">
            <a className="btn" href={`/api/invoices/${inv.id}/pdf`} target="_blank" rel="noreferrer">
              🖨 PDF / Drucken
            </a>
            {!inv.cancels_id && inv.status !== "cancelled" && (
              <button className="btn danger" onClick={() => setCancelling(true)}>
                Stornieren
              </button>
            )}
          </div>
        </div>
      )}
      {cancelling && (
        <ReasonDialog
          title="Rechnung stornieren (Stornorechnung wird erstellt)"
          confirmLabel="Stornieren"
          onConfirm={(reason) => {
            setCancelling(false);
            run(() => api<Invoice>(`/invoices/${inv.id}/cancel`, { method: "POST", body: { reason } }), (storno) => load(storno));
          }}
          onCancel={() => setCancelling(false)}
        />
      )}
      {voidPay !== null && (
        <ReasonDialog
          title="Zahlung stornieren"
          confirmLabel="Stornieren"
          onConfirm={(reason) => {
            const id = voidPay;
            setVoidPay(null);
            run(() => api<Invoice>(`/invoices/${inv.id}/payments/${id}/void`, { method: "POST", body: { reason } }), load);
          }}
          onCancel={() => setVoidPay(null)}
        />
      )}
    </Modal>
  );
}
