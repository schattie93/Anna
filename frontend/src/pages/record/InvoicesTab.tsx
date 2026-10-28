import { useState } from "react";
import type { InvoiceListItem, PatientListItem } from "../../api";
import { InvoiceDialog, NewInvoiceDialog } from "../../components/InvoiceDialogs";
import { useApi } from "../../hooks";
import { INVOICE_STATUS, euro, formatDate } from "../../labels";
import { TabHead } from "./common";

export default function InvoicesTab({ patient }: { patient: PatientListItem }) {
  const { data, reload } = useApi<InvoiceListItem[]>(`/invoices?patient_id=${patient.id}`);
  const [openId, setOpenId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);

  return (
    <div className="stack">
      <TabHead title="Rechnungen" newLabel="Neue Rechnung" onNew={() => setCreating(true)} />
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nr.</th>
              <th>Datum</th>
              <th className="right">Betrag</th>
              <th className="right">Bezahlt</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((i) => (
              <tr key={i.id} className="clickable" onClick={() => setOpenId(i.id)}>
                <td>{i.number ?? "–"}</td>
                <td>{formatDate(i.issue_date)}</td>
                <td className="right">{euro(i.total_cents)}</td>
                <td className="right">{i.cancels_id ? "–" : euro(i.paid_cents)}</td>
                <td>
                  <span className={`badge ${i.status === "paid" ? "ok" : i.overdue ? "danger" : i.status === "draft" ? "warn" : ""}`}>
                    {i.cancels_id ? "Storno" : i.overdue ? "überfällig" : INVOICE_STATUS[i.status]}
                  </span>
                </td>
              </tr>
            ))}
            {data?.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  Noch keine Rechnungen.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {openId !== null && <InvoiceDialog invoiceId={openId} onClose={() => setOpenId(null)} onChanged={reload} />}
      {creating && (
        <NewInvoiceDialog
          patient={patient}
          onClose={() => setCreating(false)}
          onCreated={(inv) => {
            setCreating(false);
            reload();
            setOpenId(inv.id);
          }}
        />
      )}
    </div>
  );
}
