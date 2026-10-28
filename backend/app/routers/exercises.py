"""Übungsbibliothek und Übungspläne (Hausübungen) für Patienten, inkl. PDF zum Mitgeben."""

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .. import audit, pdf, storage
from ..db import get_db
from ..deps import get_current_user, get_patient, require_admin, require_medical
from ..exercise_defaults import DEFAULT_EXERCISES
from ..models import Exercise, ExercisePlan, ExercisePlanItem, Patient, User
from ..practice import get_practice
from ..schemas import ExerciseIn, ExerciseOut, ExercisePlanIn, ExercisePlanOut, ExerciseUpdate, PlanItemOut, VoidIn
from .medical import _ensure_not_voided, _get_entry, _void

library = APIRouter(prefix="/api/exercises", tags=["exercises"], dependencies=[Depends(require_medical)])
plans = APIRouter(prefix="/api/patients/{patient_id}/exercise-plans", tags=["exercises"], dependencies=[Depends(require_medical)])


def exercise_out(e: Exercise) -> ExerciseOut:
    out = ExerciseOut.model_validate(e)
    out.has_image = e.image_path is not None
    return out


@library.get("", response_model=list[ExerciseOut])
def list_exercises(q: str = "", region: str | None = None, include_archived: bool = False, db: Session = Depends(get_db)):
    stmt = select(Exercise)
    for term in q.split():
        like = f"%{term.lower()}%"
        stmt = stmt.where(or_(func.lower(Exercise.title).like(like), func.lower(Exercise.region).like(like), func.lower(Exercise.description).like(like)))
    if region:
        stmt = stmt.where(Exercise.region == region)
    if not include_archived:
        stmt = stmt.where(Exercise.archived.is_(False))
    return [exercise_out(e) for e in db.scalars(stmt.order_by(Exercise.region, Exercise.title))]


@library.post("", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
def create_exercise(data: ExerciseIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = Exercise(**data.model_dump(), approved=True, approved_by=user.full_name)  # wer die Übung anlegt, steht dafür ein
    db.add(e)
    db.flush()
    audit.log(db, user, "create", "exercise", e.id, changes={"title": e.title})
    db.commit()
    return exercise_out(e)


@library.post("/seed-defaults", response_model=list[ExerciseOut])
def seed_defaults(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Lädt die mitgelieferten Beispielübungen (nur Titel, die noch nicht existieren)."""
    existing = {t for (t,) in db.execute(select(Exercise.title))}
    added = []
    for title, region, description, instructions, sets, reps, hold in DEFAULT_EXERCISES:
        if title in existing:
            continue
        e = Exercise(title=title, region=region, description=description, instructions=instructions, default_sets=sets, default_reps=reps, default_hold_seconds=hold, approved=False)
        db.add(e)
        added.append(e)
    db.flush()
    audit.log(db, admin, "create", "exercise", changes={"seeded": len(added)})
    db.commit()
    return [exercise_out(e) for e in added]


def _exercise(db: Session, exercise_id: int) -> Exercise:
    e = db.get(Exercise, exercise_id)
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Übung nicht gefunden")
    return e


@library.post("/{exercise_id}/approve", response_model=ExerciseOut)
def approve_exercise(exercise_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Fachliche Freigabe: erst freigegebene Übungen werden in Übungsplänen gedruckt."""
    e = _exercise(db, exercise_id)
    e.approved, e.approved_by = True, user.full_name
    audit.log(db, user, "update", "exercise", e.id, changes={"approved": {"old": False, "new": True}})
    db.commit()
    return exercise_out(e)


@library.put("/{exercise_id}", response_model=ExerciseOut)
def update_exercise(exercise_id: int, data: ExerciseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = _exercise(db, exercise_id)
    diff = audit.apply_changes(e, data.model_dump())
    if diff:
        audit.log(db, user, "update", "exercise", e.id, changes=diff)
    db.commit()
    return exercise_out(e)


@library.post("/{exercise_id}/image", response_model=ExerciseOut)
async def upload_exercise_image(exercise_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = _exercise(db, exercise_id)
    data = await file.read(storage.get_settings().max_upload_mb * 1024 * 1024 + 1)
    stored = storage.save_upload("library", data, allow_pdf=False)
    e.image_path, e.image_content_type = stored.path, stored.content_type
    audit.log(db, user, "update", "exercise", e.id, changes={"image": stored.sha256})
    db.commit()
    return exercise_out(e)


@library.get("/{exercise_id}/image")
def exercise_image(exercise_id: int, db: Session = Depends(get_db)):
    e = _exercise(db, exercise_id)
    if not e.image_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kein Bild")
    path = storage.resolve(e.image_path)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kein Bild")
    return FileResponse(path, media_type=e.image_content_type, headers={"Cache-Control": "private, max-age=300"})


# --- Übungspläne ---------------------------------------------------------------


def plan_out(p: ExercisePlan) -> ExercisePlanOut:
    out = ExercisePlanOut.model_validate(p)
    for item_out, item in zip(out.items, p.items):
        item_out.has_image = bool(item.exercise and item.exercise.image_path)
        item_out.approved = item.exercise.approved if item.exercise else True
    return out


def _build_items(db: Session, data: ExercisePlanIn) -> list[ExercisePlanItem]:
    items = []
    for i, it in enumerate(data.items):
        if it.exercise_id is not None:
            _exercise(db, it.exercise_id)
        items.append(ExercisePlanItem(position=i, **it.model_dump()))
    return items


def _get_plan(db: Session, plan_id: int, patient: Patient) -> ExercisePlan:
    p = db.scalars(select(ExercisePlan).options(selectinload(ExercisePlan.items).selectinload(ExercisePlanItem.exercise)).where(ExercisePlan.id == plan_id)).first()
    if not p or p.patient_id != patient.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Übungsplan nicht gefunden")
    return p


@plans.get("", response_model=list[ExercisePlanOut])
def list_plans(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ExercisePlan)
        .options(selectinload(ExercisePlan.items).selectinload(ExercisePlanItem.exercise))
        .where(ExercisePlan.patient_id == patient.id)
        .order_by(ExercisePlan.issued_on.desc(), ExercisePlan.id.desc())
    )
    return [plan_out(p) for p in rows]


@plans.post("", response_model=ExercisePlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(data: ExercisePlanIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = ExercisePlan(patient_id=patient.id, created_by_id=user.id, title=data.title, issued_on=data.issued_on, notes=data.notes, items=_build_items(db, data))
    db.add(plan)
    db.flush()
    audit.log(db, user, "create", "exercise_plan", plan.id, patient.id, changes={"title": plan.title, "items": [i.title for i in plan.items]})
    db.commit()
    return plan_out(_get_plan(db, plan.id, patient))


@plans.put("/{plan_id}", response_model=ExercisePlanOut)
def update_plan(plan_id: int, data: ExercisePlanIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = _get_plan(db, plan_id, patient)
    _ensure_not_voided(plan)
    old_titles = [i.title for i in plan.items]
    diff = audit.apply_changes(plan, {"title": data.title, "issued_on": data.issued_on, "notes": data.notes})
    plan.items = _build_items(db, data)
    new_titles = [i.title for i in plan.items]
    if old_titles != new_titles:
        diff["items"] = {"old": old_titles, "new": new_titles}
    if diff:
        audit.log(db, user, "update", "exercise_plan", plan.id, patient.id, changes=diff)
    db.commit()
    return plan_out(_get_plan(db, plan.id, patient))


@plans.post("/{plan_id}/void", response_model=ExercisePlanOut)
def void_plan(plan_id: int, data: VoidIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_plan(db, plan_id, patient)
    _void(db, _get_entry(db, ExercisePlan, plan_id, patient), "exercise_plan", data.reason, user)
    return plan_out(_get_plan(db, plan_id, patient))


@plans.get("/{plan_id}/pdf")
def plan_pdf(plan_id: int, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = _get_plan(db, plan_id, patient)
    unapproved = [i.title for i in plan.items if i.exercise and not i.exercise.approved]
    if unapproved:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Noch nicht fachlich freigegeben: " + ", ".join(unapproved) + ". Bitte die Übungen in der Bibliothek prüfen und freigeben.",
        )
    practice = get_practice(db)
    story = pdf.letterhead(practice)
    story.append(pdf.Paragraph(pdf.escape(plan.title), pdf.H1))
    story.append(pdf.P(f"für {patient.first_name} {patient.last_name} · {pdf.de_date(plan.issued_on)}", pdf.BODY))
    story.append(pdf.Spacer(1, 4 * pdf.mm))

    big = pdf.ParagraphStyle("big", parent=pdf.BODY, fontSize=10.5, leading=14.5)
    bold = pdf.ParagraphStyle("bigb", parent=big, fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=pdf.TEAL)
    full = pdf.A4_WIDTH - 36 * pdf.mm
    for n, item in enumerate(plan.items, start=1):
        dose = []
        if item.sets and item.reps:
            dose.append(f"{item.sets} x {item.reps} Wiederholungen")
        elif item.reps:
            dose.append(f"{item.reps} Wiederholungen")
        elif item.sets:
            dose.append(f"{item.sets} Durchgänge")
        if item.hold_seconds:
            dose.append(f"{item.hold_seconds} Sekunden halten")
        if item.frequency:
            dose.append(item.frequency)
        text = [pdf.Paragraph(f"{n}. {pdf.escape(item.title)}", bold)]
        if dose:
            text.append(pdf.P(" · ".join(dose), pdf.ParagraphStyle("dose", parent=big, fontName="Helvetica-Bold")))
        if item.instructions:
            text.append(pdf.P(item.instructions, big))
        if item.notes:
            text.append(pdf.P("Hinweis: " + item.notes, pdf.ParagraphStyle("note", parent=big, textColor=pdf.GREY)))
        if item.exercise and item.exercise.contraindications:
            text.append(pdf.P("Vorsicht / nicht geeignet bei: " + item.exercise.contraindications, pdf.ParagraphStyle("contra", parent=big, textColor=pdf.GREY)))
        picture: list = []
        if item.exercise and item.exercise.image_path:
            path = storage.resolve(item.exercise.image_path)
            if path.is_file():
                w, h = ImageReader(str(path)).getSize()
                width = 42 * pdf.mm
                picture = [Image(str(path), width=width, height=width * h / w)]
        row = [picture or "", text]
        story.append(pdf.KeepTogether([pdf.table([row], [46 * pdf.mm, full - 46 * pdf.mm], header=False, zebra=False)]))
    if plan.notes:
        story += [pdf.Spacer(1, 4 * pdf.mm), pdf.Paragraph("Hinweise", pdf.H2), pdf.P(plan.notes, big)]
    story += [pdf.Spacer(1, 6 * pdf.mm), pdf.P("Bei starken oder zunehmenden Schmerzen, Schwindel oder Taubheitsgefühlen brechen Sie die Übung ab und sprechen Sie uns an.", pdf.SMALL)]
    content = pdf.build(story, plan.title, practice, f"Übungsplan – {patient.first_name} {patient.last_name}")
    audit.log(db, user, "export", "exercise_plan", plan.id, patient.id)
    db.commit()
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="uebungsplan.pdf"', "Cache-Control": "no-store"})
