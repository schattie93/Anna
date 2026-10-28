"""Therapiebericht als PDF (lokal erzeugt)."""

from collections import defaultdict

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, pdf
from ..db import get_db
from ..deps import get_current_user, get_patient, require_medical
from ..models import (
    Anamnesis,
    Diagnosis,
    Finding,
    FindingCategory,
    GoalStatus,
    Patient,
    Treatment,
    TreatmentStatus,
    TherapyGoal,
    User,
)
from ..practice import get_practice
from ..schemas import ReportIn

router = APIRouter(prefix="/api/patients/{patient_id}", tags=["reports"], dependencies=[Depends(require_medical)])

SIDE = {"none": "", "left": " links", "right": " rechts", "both": " beidseits"}
GOAL = {GoalStatus.open: "offen", GoalStatus.achieved: "erreicht", GoalStatus.dropped: "verworfen"}


def _finding_value(f: Finding) -> str:
    if f.category == FindingCategory.test:
        return f.value_text or "–"
    if f.value_opposite is not None:  # Neutral-Null-Methode
        return f"{pdf.de_number(f.value_opposite)}-{pdf.de_number(f.value_neutral or 0)}-{pdf.de_number(f.value_num)} {f.unit or ''}".strip()
    return f"{pdf.de_number(f.value_num)} {f.unit or ''}".strip()


def build_report(db: Session, patient: Patient, data: ReportIn, author: User) -> bytes:
    practice = get_practice(db)
    full = pdf.A4_WIDTH - 36 * pdf.mm
    story = pdf.letterhead(practice)
    story.append(pdf.Paragraph("Therapiebericht", pdf.H1))
    if data.recipient:
        story += [pdf.P(f"An: {data.recipient}"), pdf.Spacer(1, 3 * pdf.mm)]

    p = patient
    story.append(
        pdf.table(
            [
                [pdf.P("Patient/in", pdf.CELLB), pdf.P(f"{p.first_name} {p.last_name}, geb. {pdf.de_date(p.birth_date)}", pdf.CELL)],
                [pdf.P("Patientennr.", pdf.CELLB), pdf.P(p.patient_number, pdf.CELL)],
                [pdf.P("Kostenträger", pdf.CELLB), pdf.P(" – ".join(x for x in [p.insurance_name, p.insurance_number] if x) or None, pdf.CELL)],
                [pdf.P("Verordnung durch", pdf.CELLB), pdf.P(p.referring_physician, pdf.CELL)],
            ],
            [35 * pdf.mm, full - 35 * pdf.mm], header=False, zebra=False,
        )
    )

    diagnoses = db.scalars(
        select(Diagnosis).where(Diagnosis.patient_id == p.id, Diagnosis.voided.is_(False)).order_by(Diagnosis.is_primary.desc(), Diagnosis.created_at)
    ).all()
    if diagnoses:
        story.append(pdf.Paragraph("Diagnosen", pdf.H2))
        rows = [[pdf.P(h, pdf.CELLB) for h in ("ICD-10", "Diagnose", "Seite", "Status")]]
        for d in diagnoses:
            rows.append([
                pdf.P(d.icd10_code, pdf.CELL),
                pdf.P(d.description + (" (Hauptdiagnose)" if d.is_primary else ""), pdf.CELL),
                pdf.P(SIDE[d.side.value].strip() or "–", pdf.CELL),
                pdf.P("aktiv" if d.status.value == "active" else "abgeschlossen", pdf.CELL),
            ])
        story.append(pdf.table(rows, [22 * pdf.mm, full - 70 * pdf.mm, 22 * pdf.mm, 26 * pdf.mm]))

    anamnesis = db.scalars(
        select(Anamnesis).where(Anamnesis.patient_id == p.id, Anamnesis.voided.is_(False)).order_by(Anamnesis.recorded_on, Anamnesis.id)
    ).first()
    if anamnesis:
        story.append(pdf.Paragraph(f"Anamnese / Erstbefund ({pdf.de_date(anamnesis.recorded_on)})", pdf.H2))
        rows = [[pdf.P("Hauptbeschwerde", pdf.CELLB), pdf.P(anamnesis.chief_complaint, pdf.CELL)]]
        if anamnesis.onset:
            rows.append([pdf.P("Beginn / Auslöser", pdf.CELLB), pdf.P(anamnesis.onset, pdf.CELL)])
        if anamnesis.pain_current is not None:
            rows.append([pdf.P("Schmerz bei Aufnahme", pdf.CELLB), pdf.P(f"{anamnesis.pain_current}/10 (maximal {anamnesis.pain_max if anamnesis.pain_max is not None else '–'}/10)", pdf.CELL)])
        if anamnesis.goals:
            rows.append([pdf.P("Therapieziele", pdf.CELLB), pdf.P(anamnesis.goals, pdf.CELL)])
        story.append(pdf.table(rows, [35 * pdf.mm, full - 35 * pdf.mm], header=False, zebra=False))

    stmt = select(Treatment).where(Treatment.patient_id == p.id, Treatment.voided.is_(False), Treatment.status == TreatmentStatus.final)
    if data.from_date:
        stmt = stmt.where(Treatment.treated_on >= data.from_date)
    if data.to_date:
        stmt = stmt.where(Treatment.treated_on <= data.to_date)
    treatments = db.scalars(stmt.order_by(Treatment.treated_on, Treatment.id)).all()
    story.append(pdf.Paragraph("Behandlungsverlauf", pdf.H2))
    if treatments:
        story.append(pdf.P(f"{len(treatments)} abgeschlossene Behandlungen vom {pdf.de_date(treatments[0].treated_on)} bis {pdf.de_date(treatments[-1].treated_on)}.", pdf.CELL))
        story.append(pdf.Spacer(1, 2 * pdf.mm))
        rows = [[pdf.P(h, pdf.CELLB) for h in ("Nr.", "Datum", "Maßnahmen", "Schmerz vor -> nach")]]
        for i, t in enumerate(treatments, start=1):
            rows.append([
                pdf.P(str(i), pdf.CELL), pdf.P(pdf.de_date(t.treated_on), pdf.CELL), pdf.P(", ".join(t.measures) or None, pdf.CELL),
                pdf.P(f"{t.pain_before if t.pain_before is not None else '–'} -> {t.pain_after if t.pain_after is not None else '–'}", pdf.CELL),
            ])
        story.append(pdf.table(rows, [10 * pdf.mm, 22 * pdf.mm, full - 70 * pdf.mm, 38 * pdf.mm]))
        chart = pdf.pain_chart([(t.treated_on, t.pain_before, t.pain_after) for t in treatments], full)
        if chart:
            story += [pdf.Spacer(1, 3 * pdf.mm), pdf.KeepTogether([chart])]
    else:
        story.append(pdf.P("Keine abgeschlossenen Behandlungen im gewählten Zeitraum.", pdf.CELL))

    findings = db.scalars(
        select(Finding).where(Finding.patient_id == p.id, Finding.voided.is_(False)).order_by(Finding.recorded_on, Finding.id)
    ).all()
    groups: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for f in findings:
        groups[(f.name, f.side.value)].append(f)
    compare = [g for g in groups.values() if len(g) >= 2]
    if compare:
        story.append(pdf.Paragraph("Befundentwicklung", pdf.H2))
        rows = [[pdf.P(h, pdf.CELLB) for h in ("Befund", "Erstbefund", "Letzter Befund", "Veränderung")]]
        for g in compare:
            first, last = g[0], g[-1]
            change = "–"
            if first.value_num is not None and last.value_num is not None:
                delta = last.value_num - first.value_num
                change = ("+" if delta > 0 else "") + pdf.de_number(delta) + (f" {first.unit}" if first.unit else "")
            rows.append([
                pdf.P(first.name + SIDE[first.side.value], pdf.CELL),
                pdf.P(f"{_finding_value(first)} ({pdf.de_date(first.recorded_on)})", pdf.CELL),
                pdf.P(f"{_finding_value(last)} ({pdf.de_date(last.recorded_on)})", pdf.CELL),
                pdf.P(change, pdf.CELL),
            ])
        story.append(pdf.table(rows, [55 * pdf.mm, 40 * pdf.mm, 40 * pdf.mm, full - 135 * pdf.mm]))

    goals = db.scalars(select(TherapyGoal).where(TherapyGoal.patient_id == p.id, TherapyGoal.voided.is_(False)).order_by(TherapyGoal.created_at)).all()
    if goals:
        story.append(pdf.Paragraph("Therapieziele", pdf.H2))
        rows = [[pdf.P(h, pdf.CELLB) for h in ("Ziel", "Status")]]
        for g in goals:
            status = GOAL[g.status] + (f" am {pdf.de_date(g.achieved_on)}" if g.achieved_on else "")
            rows.append([pdf.P(g.description, pdf.CELL), pdf.P(status, pdf.CELL)])
        story.append(pdf.table(rows, [full - 45 * pdf.mm, 45 * pdf.mm]))

    if data.summary and data.summary.strip():
        story += [pdf.Paragraph("Beurteilung und weiteres Vorgehen", pdf.H2), pdf.P(data.summary.strip())]

    story += [
        pdf.Spacer(1, 18 * pdf.mm),
        pdf.table([[pdf.P("Ort, Datum", pdf.SMALL), pdf.P(f"Unterschrift ({author.full_name})", pdf.SMALL)]], [60 * pdf.mm, full - 60 * pdf.mm], header=False, zebra=False),
    ]
    return pdf.build(story, f"Therapiebericht {p.last_name}", practice, f"Therapiebericht – {p.first_name} {p.last_name} – {p.patient_number}")


@router.post("/report.pdf")
def report_pdf(
    data: ReportIn,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content = build_report(db, patient, data, user)
    audit.log(db, user, "export", "report", None, patient.id)
    db.commit()
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="therapiebericht-{patient.patient_number}.pdf"', "Cache-Control": "no-store"},
    )
