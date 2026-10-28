"""Abrechnung: Leistungskatalog, Rechnungen (Privat/Selbstzahler), Zahlungen, Storno, PDF und GKV-Vorbereitung."""

import csv
import io
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import audit, pdf
from ..db import get_db
from ..deps import get_current_user, get_patient, require_admin, require_medical
from ..models import (
    Attachment,
    AttachmentKind,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    InsuranceType,
    Patient,
    Payment,
    Prescription,
    ServiceItem,
    Treatment,
    TreatmentStatus,
    User,
)
from ..practice import get_practice
from ..prescription_rules import evaluate
from ..schemas import (
    BillableTreatment,
    GkvRow,
    InvoiceDraftIn,
    InvoiceFromTreatments,
    InvoiceItemIn,
    InvoiceListItem,
    InvoiceOut,
    PaymentIn,
    PaymentOut,
    ServiceIn,
    ServiceOut,
    VoidIn,
)
from ..timeutil import local_today

router = APIRouter(prefix="/api", tags=["billing"])


# --- Leistungskatalog ------------------------------------------------------------


@router.get("/services", response_model=list[ServiceOut])
def list_services(include_inactive: bool = False, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(ServiceItem).order_by(ServiceItem.name)
    if not include_inactive:
        stmt = stmt.where(ServiceItem.active.is_(True))
    return db.scalars(stmt).all()


@router.post("/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(data: ServiceIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    s = ServiceItem(**data.model_dump())
    db.add(s)
    db.flush()
    audit.log(db, admin, "create", "service", s.id, changes=data.model_dump())
    db.commit()
    return s


@router.put("/services/{service_id}", response_model=ServiceOut)
def update_service(service_id: int, data: ServiceIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    s = db.get(ServiceItem, service_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Leistung nicht gefunden")
    diff = audit.apply_changes(s, data.model_dump())
    if diff:
        audit.log(db, admin, "update", "service", s.id, changes=diff)
    db.commit()
    return s


# --- Rechnungen ------------------------------------------------------------------


def _load(db: Session, invoice_id: int) -> Invoice:
    inv = db.scalars(
        select(Invoice)
        .options(selectinload(Invoice.items), selectinload(Invoice.payments).selectinload(Payment.created_by), selectinload(Invoice.patient), selectinload(Invoice.created_by))
        .where(Invoice.id == invoice_id)
    ).first()
    if not inv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rechnung nicht gefunden")
    return inv


def _is_overdue(inv: Invoice) -> bool:
    return inv.status == InvoiceStatus.issued and inv.due_date is not None and inv.due_date < local_today() and inv.paid_cents < inv.total_cents


def _out(inv: Invoice) -> InvoiceOut:
    out = InvoiceOut.model_validate(inv)
    out.number, out.paid_cents, out.overdue = inv.number, inv.paid_cents, _is_overdue(inv)
    return out


def _list_item(inv: Invoice) -> InvoiceListItem:
    out = InvoiceListItem.model_validate(inv)
    out.number, out.paid_cents, out.overdue = inv.number, inv.paid_cents, _is_overdue(inv)
    return out


def _ensure_draft(inv: Invoice) -> None:
    if inv.status != InvoiceStatus.draft:
        raise HTTPException(status.HTTP_409_CONFLICT, "Nur Entwürfe können geändert werden – gestellte Rechnungen werden per Storno korrigiert")


def _check_treatments(db: Session, patient_id: int, items: list, invoice_id: int | None) -> None:
    ids = [i.treatment_id for i in items if i.treatment_id is not None]
    if len(ids) != len(set(ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Eine Behandlung ist doppelt in der Rechnung")
    for tid in ids:
        t = db.get(Treatment, tid)
        if not t or t.patient_id != patient_id or t.voided or t.status != TreatmentStatus.final:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Behandlung nicht abrechenbar (nicht abgeschlossen oder falscher Patient)")
        used = db.scalars(
            select(Invoice.id)
            .join(InvoiceItem)
            .where(InvoiceItem.treatment_id == tid, Invoice.status != InvoiceStatus.cancelled, Invoice.id != (invoice_id or 0))
        ).first()
        if used:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Behandlung vom {t.treated_on:%d.%m.%Y} ist bereits abgerechnet")


def _set_items(inv: Invoice, items: list) -> None:
    inv.items = [InvoiceItem(position=i, **it.model_dump()) for i, it in enumerate(items)]
    inv.total_cents = sum(i.total_cents for i in inv.items)


def _address(p: Patient) -> str | None:
    return "\n".join(x for x in [p.street, " ".join(x for x in [p.postal_code, p.city] if x)] if x) or None


@router.get("/invoices", response_model=list[InvoiceListItem])
def list_invoices(
    status_filter: InvoiceStatus | None = None,
    patient_id: int | None = None,
    year: int | None = None,
    overdue: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Invoice).options(selectinload(Invoice.patient), selectinload(Invoice.payments)).order_by(Invoice.issue_date.desc().nulls_first(), Invoice.id.desc())
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    if patient_id:
        stmt = stmt.where(Invoice.patient_id == patient_id)
    if year:
        stmt = stmt.where(Invoice.year == year)
    rows = [_list_item(i) for i in db.scalars(stmt)]
    return [r for r in rows if r.overdue] if overdue else rows


@router.get("/patients/{patient_id}/billable", response_model=list[BillableTreatment])
def billable(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    """Abgeschlossene, noch nicht abgerechnete Behandlungen."""
    invoiced = select(InvoiceItem.treatment_id).join(Invoice).where(InvoiceItem.treatment_id.is_not(None), Invoice.status != InvoiceStatus.cancelled)
    rows = db.scalars(
        select(Treatment)
        .where(Treatment.patient_id == patient.id, Treatment.voided.is_(False), Treatment.status == TreatmentStatus.final, Treatment.id.not_in(invoiced))
        .order_by(Treatment.treated_on)
    ).all()
    out = []
    for t in rows:
        rx = db.get(Prescription, t.prescription_id) if t.prescription_id else None
        out.append(BillableTreatment(treatment_id=t.id, treated_on=t.treated_on, duration_minutes=t.duration_minutes, measures=t.measures, prescription_label=rx.measure if rx else None))
    return out


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def read_invoice(invoice_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _out(_load(db, invoice_id))


@router.post("/invoices/from-treatments", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_from_treatments(data: InvoiceFromTreatments, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient = db.get(Patient, data.patient_id)
    service = db.get(ServiceItem, data.service_id)
    if not patient or not service or not service.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient oder Leistung nicht gefunden")
    treatments = [db.get(Treatment, tid) for tid in data.treatment_ids]
    if any(t is None for t in treatments):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Behandlung nicht gefunden")
    items = [
        InvoiceItemIn(treatment_id=t.id, service_date=t.treated_on, description=f"{service.name} am {t.treated_on:%d.%m.%Y}", quantity=1, unit_price_cents=service.price_cents)
        for t in sorted(treatments, key=lambda t: t.treated_on)
    ]
    _check_treatments(db, patient.id, items, None)
    inv = Invoice(
        patient_id=patient.id, created_by_id=user.id,
        recipient_name=(data.recipient_name or f"{patient.first_name} {patient.last_name}").strip(),
        recipient_address=data.recipient_address if data.recipient_address is not None else _address(patient),
    )
    _set_items(inv, items)
    db.add(inv)
    db.flush()
    audit.log(db, user, "create", "invoice", inv.id, patient.id, changes={"total_cents": inv.total_cents, "items": len(items)})
    db.commit()
    return _out(_load(db, inv.id))


@router.post("/patients/{patient_id}/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_manual(data: InvoiceDraftIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_treatments(db, patient.id, data.items, None)
    inv = Invoice(patient_id=patient.id, created_by_id=user.id, recipient_name=data.recipient_name, recipient_address=data.recipient_address, note=data.note)
    _set_items(inv, data.items)
    db.add(inv)
    db.flush()
    audit.log(db, user, "create", "invoice", inv.id, patient.id, changes={"total_cents": inv.total_cents, "items": len(data.items)})
    db.commit()
    return _out(_load(db, inv.id))


@router.put("/invoices/{invoice_id}", response_model=InvoiceOut)
def update_draft(invoice_id: int, data: InvoiceDraftIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inv = _load(db, invoice_id)
    _ensure_draft(inv)
    _check_treatments(db, inv.patient_id, data.items, inv.id)
    diff = audit.apply_changes(inv, {"recipient_name": data.recipient_name, "recipient_address": data.recipient_address, "note": data.note})
    old_total = inv.total_cents
    _set_items(inv, data.items)
    if inv.total_cents != old_total:
        diff["total_cents"] = {"old": old_total, "new": inv.total_cents}
    audit.log(db, user, "update", "invoice", inv.id, inv.patient_id, changes=diff or {"items": len(data.items)})
    db.commit()
    return _out(_load(db, inv.id))


@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Nur Entwürfe (ohne Rechnungsnummer) dürfen gelöscht werden – so entstehen keine Lücken in der Nummerierung."""
    inv = _load(db, invoice_id)
    _ensure_draft(inv)
    audit.log(db, user, "delete", "invoice", inv.id, inv.patient_id, changes={"total_cents": inv.total_cents})
    db.delete(inv)
    db.commit()


def _assign_number(db: Session, inv: Invoice, today: date) -> None:
    """Vergibt die nächste lückenlose Nummer des Jahres. Bei gleichzeitiger Vergabe verhindert die Eindeutigkeit Doppelnummern."""
    last = db.scalar(select(func.max(Invoice.seq)).where(Invoice.year == today.year)) or 0
    inv.year, inv.seq = today.year, last + 1
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Rechnungsnummer konnte nicht vergeben werden – bitte erneut versuchen") from None


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceOut)
def issue(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inv = _load(db, invoice_id)
    _ensure_draft(inv)
    if not inv.items:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Rechnung ohne Positionen")
    _check_treatments(db, inv.patient_id, inv.items, inv.id)
    practice = get_practice(db)
    today = local_today()
    inv.status = InvoiceStatus.issued
    inv.issue_date = today
    inv.due_date = today + timedelta(days=int(practice.get("invoice_payment_days") or 14))
    inv.vat_note = practice.get("invoice_vat_note")
    _assign_number(db, inv, today)
    audit.log(db, user, "issue", "invoice", inv.id, inv.patient_id, changes={"number": inv.number, "total_cents": inv.total_cents})
    db.commit()
    return _out(_load(db, inv.id))


def _sync_paid(inv: Invoice) -> None:
    if inv.status in (InvoiceStatus.issued, InvoiceStatus.paid):
        inv.status = InvoiceStatus.paid if inv.paid_cents >= inv.total_cents else InvoiceStatus.issued


@router.post("/invoices/{invoice_id}/payments", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def add_payment(invoice_id: int, data: PaymentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inv = _load(db, invoice_id)
    if inv.status not in (InvoiceStatus.issued, InvoiceStatus.paid) or inv.cancels_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Zahlungen nur bei gestellten, nicht stornierten Rechnungen")
    p = Payment(paid_on=data.paid_on, amount_cents=data.amount_cents, method=data.method, note=data.note, created_by_id=user.id)
    inv.payments.append(p)
    db.flush()
    _sync_paid(inv)
    audit.log(db, user, "create", "payment", p.id, inv.patient_id, changes={"invoice": inv.number, "amount_cents": p.amount_cents})
    db.commit()
    return _out(_load(db, inv.id))


@router.post("/invoices/{invoice_id}/payments/{payment_id}/void", response_model=InvoiceOut)
def void_payment(invoice_id: int, payment_id: int, data: VoidIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inv = _load(db, invoice_id)
    p = next((x for x in inv.payments if x.id == payment_id), None)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zahlung nicht gefunden")
    if p.voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "Zahlung bereits storniert")
    p.voided, p.void_reason, p.voided_at = True, data.reason, datetime.now(timezone.utc)
    _sync_paid(inv)
    audit.log(db, user, "void", "payment", p.id, inv.patient_id, reason=data.reason)
    db.commit()
    return _out(_load(db, inv.id))


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel(invoice_id: int, data: VoidIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Storniert eine gestellte Rechnung durch eine Stornorechnung (negative Positionen, eigene Nummer)."""
    inv = _load(db, invoice_id)
    if inv.status not in (InvoiceStatus.issued, InvoiceStatus.paid) or inv.cancels_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Nur gestellte Rechnungen können storniert werden")
    today = local_today()
    storno = Invoice(
        patient_id=inv.patient_id, created_by_id=user.id, status=InvoiceStatus.issued, issue_date=today, due_date=None,
        recipient_name=inv.recipient_name, recipient_address=inv.recipient_address, note=f"Stornierung: {data.reason}",
        vat_note=inv.vat_note, cancels_id=inv.id,
    )
    storno.items = [
        InvoiceItem(position=i.position, treatment_id=None, service_date=i.service_date, description=i.description, quantity=i.quantity, unit_price_cents=-i.unit_price_cents)
        for i in inv.items
    ]
    storno.total_cents = -inv.total_cents
    db.add(storno)
    db.flush()
    _assign_number(db, storno, today)
    inv.status = InvoiceStatus.cancelled
    audit.log(db, user, "cancel", "invoice", inv.id, inv.patient_id, changes={"number": inv.number, "storno": storno.number}, reason=data.reason)
    db.commit()
    return _out(_load(db, storno.id))


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inv = _load(db, invoice_id)
    practice = get_practice(db)
    full = pdf.A4_WIDTH - 36 * pdf.mm
    original = db.get(Invoice, inv.cancels_id) if inv.cancels_id else None
    story = pdf.letterhead(practice)

    recipient = [inv.recipient_name] + ((inv.recipient_address or "").split("\n") if inv.recipient_address else [])
    story.append(pdf.P("\n".join(recipient), pdf.BODY))
    story.append(pdf.Spacer(1, 8 * pdf.mm))
    if inv.status == InvoiceStatus.draft:
        title = "Rechnungsentwurf (ohne Rechnungsnummer)"
    elif original:
        title = f"Stornorechnung Nr. {inv.number} zu Rechnung Nr. {original.number}"
    else:
        title = f"Rechnung Nr. {inv.number}"
    story.append(pdf.Paragraph(pdf.escape(title), pdf.H1))
    dates = [i.service_date for i in inv.items]
    meta = [["Rechnungsdatum", pdf.de_date(inv.issue_date)], ["Patient/in", f"{inv.patient.first_name} {inv.patient.last_name}, geb. {pdf.de_date(inv.patient.birth_date)}"]]
    if dates:
        lo, hi = min(dates), max(dates)
        meta.append(["Leistungszeitraum", pdf.de_date(lo) if lo == hi else f"{pdf.de_date(lo)} – {pdf.de_date(hi)}"])
    if practice.get("practice_tax_number"):
        meta.append(["Steuernummer", practice["practice_tax_number"]])
    story.append(pdf.table([[pdf.P(a, pdf.CELLB), pdf.P(b, pdf.CELL)] for a, b in meta], [38 * pdf.mm, full - 38 * pdf.mm], header=False, zebra=False))
    story.append(pdf.Spacer(1, 5 * pdf.mm))

    right = pdf.ParagraphStyle("r", parent=pdf.CELL, alignment=2)
    rightb = pdf.ParagraphStyle("rb", parent=right, fontName="Helvetica-Bold")
    rows = [[pdf.P(h, pdf.CELLB if i in (0, 1, 2) else rightb) for i, h in enumerate(("Pos.", "Datum", "Leistung", "Menge", "Einzelpreis", "Betrag"))]]
    for n, it in enumerate(inv.items, start=1):
        rows.append([pdf.P(str(n), pdf.CELL), pdf.P(pdf.de_date(it.service_date), pdf.CELL), pdf.P(it.description, pdf.CELL),
                     pdf.P(str(it.quantity), right), pdf.P(pdf.euro(it.unit_price_cents), right), pdf.P(pdf.euro(it.total_cents), right)])
    rows.append(["", "", "", "", pdf.P("Gesamtbetrag", rightb), pdf.P(pdf.euro(inv.total_cents), rightb)])
    t = pdf.table(rows, [12 * pdf.mm, 22 * pdf.mm, full - 112 * pdf.mm, 16 * pdf.mm, 30 * pdf.mm, 32 * pdf.mm], zebra=False)
    story.append(t)
    if inv.vat_note:
        story += [pdf.Spacer(1, 4 * pdf.mm), pdf.P(inv.vat_note, pdf.SMALL)]
    if inv.note:
        story += [pdf.Spacer(1, 3 * pdf.mm), pdf.P(inv.note, pdf.BODY)]
    if inv.status != InvoiceStatus.draft and not original and inv.total_cents > 0:
        bank = " · ".join(x for x in [practice.get("practice_bank"), f"IBAN {practice['practice_iban']}" if practice.get("practice_iban") else None, f"BIC {practice['practice_bic']}" if practice.get("practice_bic") else None] if x)
        pay = f"Bitte überweisen Sie den Betrag bis zum {pdf.de_date(inv.due_date)} unter Angabe der Rechnungsnummer {inv.number}."
        story += [pdf.Spacer(1, 5 * pdf.mm), pdf.P(pay, pdf.BODY)]
        if bank:
            story.append(pdf.P(bank, pdf.BODY))
    if practice.get("invoice_footer"):
        story += [pdf.Spacer(1, 6 * pdf.mm), pdf.P(practice["invoice_footer"], pdf.SMALL)]
    content = pdf.build(story, title, practice, f"{practice.get('practice_name') or ''} · {inv.number or 'Entwurf'}")
    audit.log(db, user, "export", "invoice", inv.id, inv.patient_id)
    db.commit()
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="rechnung-{inv.number or "entwurf"}.pdf"', "Cache-Control": "no-store"})


# --- Übersicht & GKV-Vorbereitung -----------------------------------------------------


@router.get("/billing/summary")
def summary(year: int | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    year = year or local_today().year
    invoices = db.scalars(select(Invoice).options(selectinload(Invoice.payments)).where(Invoice.cancels_id.is_(None), Invoice.status.in_((InvoiceStatus.issued, InvoiceStatus.paid)))).all()
    revenue = [0] * 12
    for i in invoices:
        if i.issue_date and i.issue_date.year == year:
            revenue[i.issue_date.month - 1] += i.total_cents
    open_cents = sum(i.total_cents - i.paid_cents for i in invoices if i.status == InvoiceStatus.issued)
    overdue = [i for i in invoices if _is_overdue(i)]
    return {
        "year": year,
        "revenue_by_month_cents": revenue,
        "revenue_year_cents": sum(revenue),
        "open_cents": open_cents,
        "overdue_count": len(overdue),
        "overdue_cents": sum(i.total_cents - i.paid_cents for i in overdue),
        "drafts": db.scalar(select(func.count(Invoice.id)).where(Invoice.status == InvoiceStatus.draft)),
    }


def gkv_rows(db: Session, date_from: date | None, date_to: date | None) -> list[GkvRow]:
    rows = []
    stmt = (
        select(Prescription)
        .join(Patient, Patient.id == Prescription.patient_id)
        .where(Prescription.voided.is_(False), Patient.insurance_type == InsuranceType.gkv)
        .order_by(Prescription.issued_on)
    )
    if date_from:
        stmt = stmt.where(Prescription.issued_on >= date_from)
    if date_to:
        stmt = stmt.where(Prescription.issued_on <= date_to)
    for rx in db.scalars(stmt):
        patient = db.get(Patient, rx.patient_id)
        treatments = list(db.scalars(select(Treatment).where(Treatment.patient_id == rx.patient_id)))
        info = evaluate(rx, treatments, db=db)
        mine = sorted((t for t in treatments if t.prescription_id == rx.id and not t.voided), key=lambda t: t.treated_on)
        problems: list[str] = [w["text"] for w in info["warnings"] if w["level"] == "warn"]
        if not rx.physician:
            problems.append("Verordnende/r Ärztin/Arzt fehlt")
        if not (rx.icd10_code or rx.diagnosis_text):
            problems.append("Diagnose/ICD-10 fehlt")
        if not rx.indication_key:
            problems.append("Indikationsschlüssel fehlt")
        if not patient.insurance_number or not patient.insurance_name:
            problems.append("Kostenträger oder Versichertennummer fehlt")
        final = [t for t in mine if t.status == TreatmentStatus.final]
        signed = set(db.scalars(select(Attachment.treatment_id).where(Attachment.patient_id == rx.patient_id, Attachment.kind == AttachmentKind.signature, Attachment.voided.is_(False), Attachment.treatment_id.is_not(None))))
        unsigned = [t for t in final if t.id not in signed]
        if unsigned:
            problems.append("Unterschrift (Leistungsnachweis) fehlt: " + ", ".join(f"{t.treated_on:%d.%m.%Y}" for t in unsigned))
        if any(t.status != TreatmentStatus.final for t in mine):
            problems.append("Entwurf-Behandlungen noch nicht abgeschlossen")
        if info["units_done"] == 0:
            problems.append("Keine abgeschlossene Behandlung zugeordnet")
        elif info["status"] != "completed":
            problems.append(f"Noch nicht ausgeschöpft ({info['units_done']}/{rx.total_units})")
        rows.append(
            GkvRow(
                prescription_id=rx.id, patient=patient, insurance_name=patient.insurance_name, insurance_number=patient.insurance_number,
                issued_on=rx.issued_on, physician=rx.physician, icd10_code=rx.icd10_code, indication_key=rx.indication_key, measure=rx.measure,
                total_units=rx.total_units, units_done=info["units_done"], treatment_dates=[t.treated_on for t in mine if t.status == TreatmentStatus.final],
                problems=problems, ready=not problems,
            )
        )
    return rows


@router.get("/billing/gkv", response_model=list[GkvRow], dependencies=[Depends(require_medical)])
def gkv_check(date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db)):
    """Prüfliste für die Kassenabrechnung: Welche Verordnungen sind vollständig und abrechnungsreif?"""
    return gkv_rows(db, date_from, date_to)


@router.get("/billing/gkv.csv", dependencies=[Depends(require_medical)])
def gkv_csv(date_from: date | None = None, date_to: date | None = None, only_ready: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """CSV-Export (Semikolon, UTF-8 mit BOM) zur Übergabe an die Abrechnungsstelle bzw. zur Weiterverarbeitung."""
    out = io.StringIO()
    out.write("﻿")
    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    w.writerow(["Patientennr.", "Nachname", "Vorname", "Geburtsdatum", "Kostenträger", "Versichertennr.", "Verordnungsdatum", "Verordner", "ICD-10", "Indikationsschlüssel", "Heilmittel", "Einheiten verordnet", "Einheiten erbracht", "Behandlungsdaten", "Abrechnungsreif", "Hinweise"])
    for r in gkv_rows(db, date_from, date_to):
        if only_ready and not r.ready:
            continue
        p = db.get(Patient, r.patient.id)
        w.writerow([p.patient_number, p.last_name, p.first_name, f"{p.birth_date:%d.%m.%Y}", r.insurance_name or "", r.insurance_number or "", f"{r.issued_on:%d.%m.%Y}", r.physician or "",
                    r.icd10_code or "", r.indication_key or "", r.measure, r.total_units, r.units_done, ", ".join(f"{d:%d.%m.%Y}" for d in r.treatment_dates), "ja" if r.ready else "nein", " | ".join(r.problems)])
    audit.log(db, user, "export", "gkv_csv")
    db.commit()
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="gkv-abrechnungsvorbereitung.csv"', "Cache-Control": "no-store"})
