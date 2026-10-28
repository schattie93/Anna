"""Geschützter lokaler Dateispeicher.

Dateien liegen unter data_dir/files/<patient_id>/ mit zufälligen Namen und werden nur über
authentifizierte API-Endpunkte ausgeliefert. Der Dateityp wird am Inhalt geprüft (nicht am Namen),
Bilder werden neu kodiert (entfernt EXIF/GPS-Daten) und erhalten ein Vorschaubild.
"""

import hashlib
import io
import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import get_settings

THUMB_SIZE = (320, 320)
MAX_PIXELS = 60_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

_FORMATS = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}


@dataclass
class StoredFile:
    content_type: str
    size: int
    sha256: str
    path: str  # relativ zu data_dir
    thumb_path: str | None


def root() -> Path:
    path = get_settings().data_dir.resolve() / "files"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve(relative: str) -> Path:
    full = (get_settings().data_dir.resolve() / relative).resolve()
    if not full.is_relative_to(get_settings().data_dir.resolve()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Datei nicht gefunden")
    return full


def _bad(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def _encode(image: Image.Image, fmt: str) -> bytes:
    out = io.BytesIO()
    save_kwargs = {"quality": 88} if fmt in ("JPEG", "WEBP") else {}
    if fmt == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.save(out, fmt, **save_kwargs)
    return out.getvalue()


def save_upload(patient_id: int, data: bytes) -> StoredFile:
    limit = get_settings().max_upload_mb * 1024 * 1024
    if not data:
        raise _bad("Leere Datei")
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Datei größer als {get_settings().max_upload_mb} MB")

    folder = root() / str(patient_id)
    folder.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(16)

    if data[:5] == b"%PDF-":
        content_type, ext, payload, thumb = "application/pdf", ".pdf", data, None
    else:
        try:
            with Image.open(io.BytesIO(data)) as probe:
                fmt = probe.format or ""
                if fmt not in _FORMATS:
                    raise _bad("Nur JPEG, PNG, WebP und PDF sind erlaubt")
                image = ImageOps.exif_transpose(probe)
                image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise _bad("Datei ist kein gültiges Bild oder PDF") from None
        content_type, ext = _FORMATS[fmt]
        payload = _encode(image, fmt)
        preview = image.copy()
        preview.thumbnail(THUMB_SIZE)
        thumb = _encode(preview.convert("RGB"), "JPEG")

    file = folder / f"{token}{ext}"
    file.write_bytes(payload)
    thumb_rel = None
    if thumb:
        thumb_file = folder / f"{token}.thumb.jpg"
        thumb_file.write_bytes(thumb)
        thumb_rel = str(thumb_file.relative_to(get_settings().data_dir.resolve()))
    return StoredFile(
        content_type=content_type,
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        path=str(file.relative_to(get_settings().data_dir.resolve())),
        thumb_path=thumb_rel,
    )
