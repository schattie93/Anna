"""PDF-Erzeugung (Therapiebericht, später Rechnungen und Übungspläne) mit reportlab.

Es werden nur die eingebauten Standardschriften verwendet; sie decken Deutsch (ä ö ü ß, €, °) ab.
"""

import io
from datetime import date
from xml.sax.saxutils import escape

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import KeepTogether

A4_WIDTH = A4[0]
TEAL = colors.HexColor("#0f766e")
GREY = colors.HexColor("#5f6b6d")
LIGHT = colors.HexColor("#e8eeee")

_base = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=_base["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10.5, textColor=GREY)
H1 = ParagraphStyle("h1", parent=BODY, fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=TEAL, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=BODY, fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=TEAL, spaceBefore=10, spaceAfter=3)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.5, leading=11)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")


def de_date(d: date | None) -> str:
    return d.strftime("%d.%m.%Y") if d else "–"


def de_number(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "–"
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".") if digits else f"{value:.0f}"
    return text.replace(".", ",")


def euro(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    whole = f"{cents // 100:,}".replace(",", ".")
    return f"{sign}{whole},{cents % 100:02d} €"


def P(text: str | None, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(escape(text or "–").replace("\n", "<br/>"), style)


def table(rows: list[list], widths: list[float], header: bool = True, zebra: bool = True) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e0e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), LIGHT)]
    if zebra:
        style += [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f9f9")])]
    t.setStyle(TableStyle(style))
    return t


def letterhead(practice: dict) -> list:
    lines = [practice.get("practice_name") or "", practice.get("practice_owner") or ""]
    contact = " · ".join(x for x in [practice.get("practice_phone"), practice.get("practice_email")] if x)
    address = (practice.get("practice_address") or "").replace("\n", ", ")
    head = [Paragraph(f"<b>{escape(lines[0])}</b>", ParagraphStyle("lh", parent=BODY, fontSize=12, textColor=TEAL))]
    rest = " · ".join(x for x in [lines[1], address, contact] if x)
    if rest:
        head.append(Paragraph(escape(rest), SMALL))
    head.append(Spacer(1, 6 * mm))
    return head


def build(story: list, title: str, practice: dict, footer_note: str | None = None) -> bytes:
    buffer = io.BytesIO()

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GREY)
        left = footer_note or practice.get("practice_name") or ""
        canvas.drawString(18 * mm, 10 * mm, left[:120])
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Seite {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
        title=title, author=practice.get("practice_name") or "PhysioFlow",
    )
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()


def pain_chart(points: list[tuple[date, int | None, int | None]], width: float, height: float = 140) -> Drawing | None:
    """Liniendiagramm Schmerz (NRS) vor/nach der Behandlung über die Zeit."""
    before = [(i, b) for i, (_, b, _a) in enumerate(points) if b is not None]
    after = [(i, a) for i, (_, _b, a) in enumerate(points) if a is not None]
    if len(before) + len(after) < 2:
        return None
    d = Drawing(width, height)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 28, 22, width - 44, height - 40
    lp.data = [s for s in (before, after) if s]
    palette = [colors.HexColor("#b42318"), TEAL]
    names = []
    if before:
        names.append("vor Behandlung")
    if after:
        names.append("nach Behandlung")
    for i in range(len(lp.data)):
        lp.lines[i].strokeColor = palette[i if len(lp.data) == 2 else (0 if before else 1)]
        lp.lines[i].strokeWidth = 1.6
        lp.lines[i].symbol = None
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax, lp.yValueAxis.valueStep = 0, 10, 2
    lp.xValueAxis.valueMin = 0
    lp.xValueAxis.valueMax = max(len(points) - 1, 1)
    lp.xValueAxis.valueStep = max(1, len(points) // 8)
    lp.xValueAxis.labelTextFormat = lambda v: str(int(v) + 1)
    lp.yValueAxis.labels.fontSize = lp.xValueAxis.labels.fontSize = 7
    d.add(lp)
    d.add(String(28, height - 10, "Schmerz (NRS 0–10) nach Behandlungsnummer: " + ", ".join(names), fontSize=7.5, fillColor=GREY, fontName="Helvetica"))
    return d


__all__ = ["A4_WIDTH", "BODY", "ParagraphStyle", "TEAL", "GREY", "escape", "CELL", "CELLB", "H1", "H2", "SMALL", "KeepTogether", "P", "Paragraph", "Spacer", "build", "de_date",
           "de_number", "euro", "letterhead", "mm", "pain_chart", "table"]
