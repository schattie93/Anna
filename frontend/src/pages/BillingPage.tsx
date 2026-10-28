import { useState } from "react";
import { NavLink, useParams } from "react-router-dom";
import { api, type BillingSummary, type GkvRow, type Invoice, type InvoiceListItem, type Service } from "../api";
import { useUser } from "../auth";
import { ErrorBox, TextField } from "../components/fields";
import { InvoiceDialog, NewInvoiceDialog } from "../components/InvoiceDialogs";
import Modal from "../components/Modal";
import { useApi } from "../hooks";
import { INVOICE_STATUS, euro, formatDate, parseEuro } from "../labels";

const FILTERS = [
  ["all", "Alle"],
  ["draft", "Entwürfe"],
  ["issued", "Offen"],
  ["overdue", "Überfällig"],
  ["paid", "Bezahlt"],
  ["cancelled", "Storniert"],
] as const;

export default function BillingPage() {
  const { tab = "rechnungen" } = useParams();
  const medical = useUser().role !== "reception";
  return (
    <div className="stack">
      <h1>Abrechnung</h1>
      <nav className="tabs">
        <NavLink to="/abrechnung" end>
          Rechnungen
        </NavLink>
        <NavLink to="/abrechnung/leistungen">Leistungen</NavLink>
        {medical && <NavLink to="/abrechnung/gkv">Kassenabrechnung (GKV)</NavLink>}
      </nav>
      {tab === "rechnungen" && <InvoicesTab />}
      {tab === "leistungen" && <ServicesTab />}
      {tab === "gkv" && medical && <GkvTab />}
    </div>
  );
}

function InvoicesTab() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>("all");
  const summary = useApi<BillingSummary>("/billing/summary");
  const query = new URLSearchParams();
  if (filter === "overdue") query.set("overdue", "true");
  else if (filter !== "all") query.set("status_filter", filter);
  const list = useApi<InvoiceListItem[]>(`/invoices?${query}`);
  const [openId, setOpenId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const refresh = () => {
    list.reload();
    summary.reload();
  };

  return (
    <div className="stack">
      {summary.data && (
        <div className="stats">
          <div className="stat">
            <span className="stat-value">{euro(summary.data.revenue_year_cents)}</span>
            <span className="stat-label">Umsatz {summary.data.year}</span>
          </div>
          <div className="stat">
            <span className="stat-value">{euro(summary.data.open_cents)}</span>
            <span className="stat-label">offene Posten</span>
          </div>
          <div className="stat">
            <span className={summary.data.overdue_count ? "stat-value danger-text" : "stat-value"}>{summary.data.overdue_count}</span>
            <span className="stat-label">überfällig ({euro(summary.data.overdue_cents)})</span>
          </div>
          <button className="stat stat-action" onClick={() => setCreating(true)}>
            <span className="stat-value">+</span>
            <span className="stat-label">Neue Rechnung</span>
          </button>
        </div>
      )}
      <div className="chips">
        {FILTERS.map(([k, label]) => (
          <button key={k} type="button" className={filter === k ? "chip on" : "chip"} onClick={() => setFilter(k)}>
            {label}
          </button>
        ))}
      </div>
      <ErrorBox error={list.error} />
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nr.</th>
              <th>Datum</th>
              <th>Patient</th>
              <th className="right">Betrag</th>
              <th className="right">Bezahlt</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(list.data ?? []).map((i) => (
              <tr key={i.id} className="clickable" onClick={() => setOpenId(i.id)}>
                <td>{i.number ?? "–"}</td>
                <td>{formatDate(i.issue_date)}</td>
                <td>
                  {i.patient.last_name}, {i.patient.first_name}
                </td>
                <td className="right">{euro(i.total_cents)}</td>
                <td className="right">{i.cancels_id ? "–" : euro(i.paid_cents)}</td>
                <td>
                  <span className={`badge ${i.status === "paid" ? "ok" : i.overdue ? "danger" : i.status === "draft" ? "warn" : ""}`}>
                    {i.cancels_id ? "Storno" : i.overdue ? "überfällig" : INVOICE_STATUS[i.status]}
                  </span>
                </td>
              </tr>
            ))}
            {list.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  Keine Rechnungen.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {openId !== null && <InvoiceDialog invoiceId={openId} onClose={() => setOpenId(null)} onChanged={refresh} />}
      {creating && (
        <NewInvoiceDialog
          onClose={() => setCreating(false)}
          onCreated={(inv: Invoice) => {
            setCreating(false);
            refresh();
            setOpenId(inv.id);
          }}
        />
      )}
    </div>
  );
}

function ServicesTab() {
  const admin = useUser().role === "admin";
  const { data, reload, error } = useApi<Service[]>("/services?include_inactive=true");
  const [editing, setEditing] = useState<Service | "new" | null>(null);

  return (
    <div className="stack">
      <div className="page-head">
        <p className="muted">Leistungen und Preise für Privat- und Selbstzahlerrechnungen.</p>
        {admin && (
          <button className="btn primary" onClick={() => setEditing("new")}>
            + Neue Leistung
          </button>
        )}
      </div>
      <ErrorBox error={error} />
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Kürzel</th>
              <th>Bezeichnung</th>
              <th className="right">Preis</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((s) => (
              <tr key={s.id} className={s.active ? undefined : "struck"}>
                <td>{s.code}</td>
                <td>{s.name}</td>
                <td className="right">{euro(s.price_cents)}</td>
                <td className="row-actions">
                  {admin && (
                    <button className="btn small" onClick={() => setEditing(s)}>
                      Bearbeiten
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {data?.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  Noch keine Leistungen angelegt.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {editing && <ServiceDialog service={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />}
    </div>
  );
}

function ServiceDialog({ service, onClose, onSaved }: { service: Service | null; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(service?.name ?? "");
  const [code, setCode] = useState(service?.code ?? "");
  const [price, setPrice] = useState(service ? (service.price_cents / 100).toFixed(2).replace(".", ",") : "");
  const [active, setActive] = useState(service?.active ?? true);
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const cents = parseEuro(price);
    if (cents === null) return setError("Ungültiger Preis");
    try {
      const body = { name, code: code || null, price_cents: cents, active };
      if (service) await api(`/services/${service.id}`, { method: "PUT", body });
      else await api("/services", { method: "POST", body });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Modal title={service ? "Leistung bearbeiten" : "Neue Leistung"} onClose={onClose}>
      <form className="form-grid" onSubmit={save}>
        <TextField label="Bezeichnung" value={name} onChange={(v) => setName(v ?? "")} required wide autoFocus />
        <TextField label="Kürzel" value={code} onChange={(v) => setCode(v ?? "")} />
        <TextField label="Preis (€)" value={price} onChange={(v) => setPrice(v ?? "")} required />
        <label className="check wide">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          <span>Aktiv (bei neuen Rechnungen wählbar)</span>
        </label>
        <div className="wide">
          <ErrorBox error={error} />
        </div>
        <div className="actions wide">
          <button type="button" className="btn" onClick={onClose}>
            Abbrechen
          </button>
          <button className="btn primary">Speichern</button>
        </div>
      </form>
    </Modal>
  );
}

function GkvTab() {
  const [from, setFrom] = useState<string | null>(null);
  const [to, setTo] = useState<string | null>(null);
  const [onlyProblems, setOnlyProblems] = useState(false);
  const q = new URLSearchParams();
  if (from) q.set("date_from", from);
  if (to) q.set("date_to", to);
  const { data, error } = useApi<GkvRow[]>(`/billing/gkv?${q}`);
  const rows = (data ?? []).filter((r) => !onlyProblems || !r.ready);

  return (
    <div className="stack">
      <div className="card form-grid">
        <p className="muted wide">
          Prüfliste für die Abrechnung mit den Krankenkassen: Welche Verordnungen sind vollständig und abgeschlossen? Der Export (CSV) dient der Übergabe an die Abrechnungsstelle. Der eigentliche Datenträgeraustausch
          (§ 302 SGB V) ist nicht Teil dieser Software.
        </p>
        <TextField label="Verordnet ab" type="date" value={from} onChange={setFrom} />
        <TextField label="bis" type="date" value={to} onChange={setTo} />
        <label className="check">
          <input type="checkbox" checked={onlyProblems} onChange={(e) => setOnlyProblems(e.target.checked)} />
          <span>Nur mit Hinweisen</span>
        </label>
        <div className="actions wide">
          <a className="btn" href={`/api/billing/gkv.csv?${q}`}>
            CSV (alle)
          </a>
          <a className="btn primary" href={`/api/billing/gkv.csv?${new URLSearchParams([...q, ["only_ready", "true"]])}`}>
            CSV (nur abrechnungsreife)
          </a>
        </div>
      </div>
      <ErrorBox error={error} />
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Patient</th>
              <th>Verordnung</th>
              <th>Einheiten</th>
              <th>Status / Hinweise</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.prescription_id}>
                <td>
                  <a href={`/patienten/${r.patient.id}/verordnungen`}>
                    {r.patient.last_name}, {r.patient.first_name}
                  </a>
                  <span className="muted block">{r.insurance_name}</span>
                </td>
                <td>
                  {r.measure}
                  <span className="muted block">vom {formatDate(r.issued_on)}</span>
                </td>
                <td>
                  {r.units_done}/{r.total_units}
                </td>
                <td>
                  {r.ready ? (
                    <span className="badge ok">abrechnungsreif</span>
                  ) : (
                    <ul className="plain compact">
                      {r.problems.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  Keine Verordnungen gefunden.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
