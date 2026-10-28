"""Lokale Assistenzfunktionen: Sprache-zu-Text, Texterkennung (OCR) und Textvorschläge.

Grundsatz: Keine Patientendaten verlassen das Praxisnetz. Darum werden Dienst-Adressen nur akzeptiert, wenn sie
auf den eigenen Rechner oder auf Adressen im privaten Netz zeigen (localhost, Docker-Dienstnamen, *.local/*.lan,
RFC-1918-Adressen). Alle Funktionen sind optional und ohne Konfiguration abgeschaltet.
"""

import ipaddress
import json
import re
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from .config import get_settings

LOCAL_SUFFIXES = (".local", ".lan", ".internal", ".home.arpa", ".localdomain")


class AssistUnavailable(HTTPException):
    def __init__(self, message: str):
        super().__init__(status.HTTP_501_NOT_IMPLEMENTED, message)


def is_local_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname
    if parsed.scheme not in ("http", "https") or not host:
        return False
    if "." not in host and ":" not in host:  # Docker-Dienstname oder localhost
        return True
    if host.endswith(LOCAL_SUFFIXES):
        return True
    try:
        infos = socket.getaddrinfo(host, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    addrs = {ipaddress.ip_address(i[4][0]) for i in infos}
    return bool(addrs) and all(a.is_private or a.is_loopback or a.is_link_local for a in addrs)


def _service_url(url: str | None, what: str) -> str:
    if not url:
        raise AssistUnavailable(f"{what} ist nicht eingerichtet")
    if not is_local_url(url):
        raise AssistUnavailable(f"{what}: Die Adresse liegt nicht im lokalen Netz und wird aus Datenschutzgründen nicht verwendet")
    return url.rstrip("/")


def ocr_languages() -> str | None:
    exe = shutil.which("tesseract")
    if not exe:
        return None
    out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=10).stdout.split()
    langs = [l for l in ("deu", "eng") if l in out]
    return "+".join(langs) or None


def status_info() -> dict:
    s = get_settings()
    return {
        "transcribe": bool(s.whisper_url and is_local_url(s.whisper_url)),
        "ocr": bool(s.ocr_enabled and ocr_languages()),
        "suggest": bool(s.llm_url and is_local_url(s.llm_url)),
    }


# --- Sprache -> Text ------------------------------------------------------------


def transcribe(audio: bytes, filename: str, content_type: str) -> str:
    s = get_settings()
    base = _service_url(s.whisper_url, "Spracherkennung")
    try:
        r = httpx.post(
            f"{base}/v1/audio/transcriptions",
            files={"file": (filename or "audio.webm", audio, content_type or "audio/webm")},
            data={"model": s.whisper_model, "language": "de", "response_format": "json"},
            timeout=s.llm_timeout_seconds,
        )
        r.raise_for_status()
        return str(r.json().get("text", "")).strip()
    except (httpx.HTTPError, ValueError) as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Spracherkennung nicht erreichbar: {e.__class__.__name__}") from None


# --- OCR ----------------------------------------------------------------------


def _tesseract(image_path: Path, lang: str) -> str:
    result = subprocess.run(
        [shutil.which("tesseract") or "tesseract", str(image_path), "stdout", "-l", lang, "--psm", "6"],
        capture_output=True, text=True, timeout=90,
    )
    return result.stdout.strip()


def ocr(data: bytes, is_pdf: bool) -> str:
    lang = ocr_languages() if get_settings().ocr_enabled else None
    if not lang:
        raise AssistUnavailable("Texterkennung ist nicht installiert (Tesseract fehlt)")
    with tempfile.TemporaryDirectory(prefix="physioflow-ocr-") as tmp:
        folder = Path(tmp)
        if is_pdf:
            if not shutil.which("pdftoppm"):
                raise AssistUnavailable("PDF-Texterkennung benötigt poppler-utils (pdftoppm)")
            (folder / "in.pdf").write_bytes(data)
            subprocess.run(["pdftoppm", "-r", "200", "-l", "10", "-png", str(folder / "in.pdf"), str(folder / "page")], check=True, timeout=120)
            pages = sorted(folder.glob("page*.png"))
        else:
            (folder / "in.img").write_bytes(data)
            pages = [folder / "in.img"]
        try:
            return "\n\n".join(t for t in (_tesseract(p, lang) for p in pages) if t)
        except subprocess.TimeoutExpired:
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "Texterkennung hat zu lange gedauert") from None


# --- Textvorschläge (lokales Sprachmodell) -----------------------------------------

SYSTEM = (
    "Du unterstützt eine Physiotherapeutin bzw. einen Physiotherapeuten beim Dokumentieren. "
    "Schreibe sachlich, knapp und in korrektem Fachdeutsch. Erfinde niemals Befunde, Messwerte, Diagnosen oder Maßnahmen, "
    "die nicht im Text stehen. Wenn etwas fehlt, lass es weg. Dein Ergebnis ist ein Entwurf, den die Fachperson prüft."
)

TASKS = {
    "polish": "Formuliere die folgenden Stichpunkte bzw. das Diktat zu klaren, vollständigen Sätzen um. Behalte alle Fakten bei und füge nichts hinzu.\n\n",
    "soap": (
        "Ordne den folgenden Text den vier SOAP-Feldern zu und antworte AUSSCHLIESSLICH mit einem JSON-Objekt mit den Schlüsseln "
        '"subjective" (Befinden/Angaben des Patienten), "objective" (Befund, Messwerte, Tests), "assessment" (Beurteilung), '
        '"plan" (nächste Schritte). Fehlt etwas, setze den Wert auf null. Keine Erklärungen.\n\n'
    ),
    "report": (
        "Verfasse aus den folgenden Verlaufsdaten einen kurzen Absatz 'Beurteilung und weiteres Vorgehen' für einen Therapiebericht an die "
        "verordnende Ärztin bzw. den verordnenden Arzt (maximal 120 Wörter). Nenne Verlauf, Fortschritte bei Schmerz und Befunden sowie die Empfehlung, "
        "soweit sie aus den Daten hervorgeht.\n\n"
    ),
}


def suggest(task: str, text: str) -> str:
    s = get_settings()
    base = _service_url(s.llm_url, "Textvorschläge")
    if task not in TASKS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unbekannte Aufgabe")
    try:
        r = httpx.post(
            f"{base}/v1/chat/completions",
            json={
                "model": s.llm_model,
                "temperature": 0.2,
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": TASKS[task] + text}],
            },
            timeout=s.llm_timeout_seconds,
        )
        r.raise_for_status()
        return str(r.json()["choices"][0]["message"]["content"]).strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Sprachmodell nicht erreichbar: {e.__class__.__name__}") from None


def parse_soap(raw: str) -> dict[str, str | None]:
    """Liest die SOAP-Antwort tolerant (Modelle packen JSON gern in Codeblöcke oder Fließtext)."""
    match = re.search(r"\{.*\}", raw, re.S)
    data: dict = {}
    if match:
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            data = {}
    return {k: (str(data[k]).strip() if data.get(k) else None) for k in ("subjective", "objective", "assessment", "plan")}
