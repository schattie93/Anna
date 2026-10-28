import io
import json
import shutil

import httpx
import pytest
from PIL import Image, ImageDraw, ImageFont

from app import assist
from app.config import get_settings


def test_local_url_rules():
    for url in ("http://localhost:11434", "http://127.0.0.1:8000", "http://ollama:11434", "http://pc-praxis.local:8080", "http://192.168.1.50:9000", "http://10.0.0.5", "https://172.16.4.2"):
        assert assist.is_local_url(url), url
    for url in ("https://api.openai.com", "http://8.8.8.8", "https://example.com/v1", "ftp://localhost", "not a url", "http://"):
        assert not assist.is_local_url(url), url


def configure(monkeypatch, **values):
    get_settings.cache_clear()
    for k, v in values.items():
        monkeypatch.setenv(f"PHYSIOFLOW_{k.upper()}", v)
    yield_settings = get_settings()
    return yield_settings


@pytest.fixture(autouse=True)
def reset_settings():
    yield
    get_settings.cache_clear()


def test_status_unconfigured(client, admin):
    st = client.get("/api/assist/status").json()
    assert st["transcribe"] is False and st["suggest"] is False
    assert client.post("/api/assist/polish", json={"task": "polish", "text": "x"}).status_code == 501


def test_external_url_is_refused(client, admin, monkeypatch):
    configure(monkeypatch, llm_url="https://api.example-ai.com", whisper_url="https://stt.example.com")
    st = client.get("/api/assist/status").json()
    assert st["suggest"] is False and st["transcribe"] is False
    r = client.post("/api/assist/polish", json={"task": "polish", "text": "x"})
    assert r.status_code == 501 and "lokalen Netz" in r.json()["detail"]


def fake_post(handler):
    def post(url, **kwargs):
        request = httpx.Request("POST", url)
        status, body = handler(url, kwargs)
        return httpx.Response(status, json=body, request=request)

    return post


def test_soap_and_polish_with_local_llm(client, admin, monkeypatch):
    configure(monkeypatch, llm_url="http://llm:11434")
    seen = {}

    def handler(url, kwargs):
        seen["url"] = url
        seen["prompt"] = kwargs["json"]["messages"][1]["content"]
        content = '```json\n{"subjective": "Schmerz besser", "objective": "FBA 10 cm", "assessment": null, "plan": "Fortsetzen"}\n```'
        return 200, {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(assist.httpx, "post", fake_post(handler))
    assert client.get("/api/assist/status").json()["suggest"] is True
    r = client.post("/api/assist/soap", json={"task": "soap", "text": "Patient sagt Schmerz besser, FBA 10cm, weiter so"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subjective"] == "Schmerz besser" and body["assessment"] is None and "prüfen" in body["notice"]
    assert seen["url"] == "http://llm:11434/v1/chat/completions" and "FBA 10cm" in seen["prompt"]

    monkeypatch.setattr(assist.httpx, "post", fake_post(lambda u, k: (200, {"choices": [{"message": {"content": "Der Patient berichtet über Besserung."}}]})))
    assert client.post("/api/assist/polish", json={"task": "polish", "text": "besser"}).json()["text"].startswith("Der Patient")


def test_llm_failure_is_reported_as_gateway_error(client, admin, monkeypatch):
    configure(monkeypatch, llm_url="http://llm:11434")
    monkeypatch.setattr(assist.httpx, "post", fake_post(lambda u, k: (500, {"error": "boom"})))
    assert client.post("/api/assist/polish", json={"task": "polish", "text": "x"}).status_code == 502


def test_report_draft_contains_no_identifying_data(client, base, patient, monkeypatch):
    configure(monkeypatch, llm_url="http://llm:11434")
    captured = {}

    def handler(url, kwargs):
        captured["prompt"] = kwargs["json"]["messages"][1]["content"]
        return 200, {"choices": [{"message": {"content": "Entwurf"}}]}

    monkeypatch.setattr(assist.httpx, "post", fake_post(handler))
    client.put(f"/api/patients/{patient['id']}", json={"first_name": "Erika", "last_name": "Musterfrau", "birth_date": "1970-05-12", "insurance_number": "X123456789", "street": "Geheimweg 7", "archived": False})
    client.post(f"{base}/diagnoses", json={"description": "Lumbalgie", "icd10_code": "M54.5", "is_primary": True})
    client.post(f"{base}/treatments", json={"treated_on": "2026-01-05", "pain_before": 6, "pain_after": 4, "assessment": "gutes Ansprechen", "finalize": True})
    r = client.post(f"{base}/assist/report-draft")
    assert r.status_code == 200 and r.json()["text"] == "Entwurf"
    prompt = captured["prompt"]
    assert "Lumbalgie" in prompt and "gutes Ansprechen" in prompt
    for secret in ("Erika", "Musterfrau", "X123456789", "Geheimweg"):
        assert secret not in prompt


def test_transcribe_forwards_audio(client, admin, monkeypatch):
    configure(monkeypatch, whisper_url="http://whisper:8000")
    seen = {}

    def handler(url, kwargs):
        seen["url"], seen["data"] = url, kwargs["data"]
        return 200, {"text": " Lendenwirbelsäule frei beweglich. "}

    monkeypatch.setattr(assist.httpx, "post", fake_post(handler))
    r = client.post("/api/assist/transcribe", files={"file": ("a.webm", b"\x1aE\xdf\xa3fake", "audio/webm")})
    assert r.status_code == 200 and r.json()["text"] == "Lendenwirbelsäule frei beweglich."
    assert seen["url"].endswith("/v1/audio/transcriptions") and seen["data"]["language"] == "de"
    assert client.post("/api/assist/transcribe", files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 422


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract nicht installiert")
def test_ocr_reads_text_from_image_and_attachment(client, base, patient):
    img = Image.new("RGB", (900, 200), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 56)
    except OSError:
        font = ImageFont.load_default(size=56)
    draw.text((30, 60), "Krankengymnastik 6x", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")

    r = client.post("/api/assist/ocr", files={"file": ("v.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200, r.text
    assert "Krankengymnastik" in r.json()["text"]

    a = client.post(f"{base}/attachments", data={"kind": "document"}, files={"file": ("v.png", buf.getvalue(), "image/png")}).json()
    r = client.post(f"{base}/attachments/{a['id']}/ocr")
    assert r.status_code == 200 and "Krankengymnastik" in r.json()["ocr_text"]
    fixed = client.patch(f"{base}/attachments/{a['id']}", json={"ocr_text": "Krankengymnastik 6 x (korrigiert)"})
    assert fixed.json()["ocr_text"].endswith("(korrigiert)")


def test_assist_requires_medical_role(client, admin):
    client.post("/api/users", json={"username": "empfang", "full_name": "E E", "password": "noch-ein-passwort", "role": "reception"})
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "empfang", "password": "noch-ein-passwort"})
    assert client.get("/api/assist/status").status_code == 403
