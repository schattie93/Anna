from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import admin, assist, auth, billing, documentation, exercises, medical, misc, patients, prescriptions, reports, scheduling, settings, stats, users

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "x-physioflow"

app = FastAPI(title="PhysioFlow", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.middleware("http")
async def protect(request: Request, call_next):
    # Einfacher CSRF-Schutz: Schreibende API-Aufrufe müssen einen eigenen Header tragen,
    # den fremde Webseiten ohne CORS-Freigabe nicht setzen können.
    if request.url.path.startswith("/api/") and request.method not in SAFE_METHODS and CSRF_HEADER not in request.headers:
        return JSONResponse({"detail": "CSRF-Header fehlt"}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
    # Der PDF-Betrachter von Chrome ist mit "object-src 'none'" nicht nutzbar. Direkt ausgelieferte PDFs bekommen daher keine
    # CSP (statischer Inhalt, nosniff bleibt), und für blob:-PDFs (Therapiebericht) erlaubt die Seiten-CSP object-src blob:.
    if not response.headers.get("content-type", "").startswith("application/pdf"):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; object-src 'self' blob:; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


app.include_router(exercises.library)
app.include_router(exercises.plans)

for module in (auth, users, settings, patients, medical, documentation, prescriptions, scheduling, reports, assist, billing, stats, admin, misc):
    app.include_router(module.router)


@app.get("/api/health", include_in_schema=False)
def health():
    return {"status": "ok"}


def _mount_frontend(dist: Path) -> None:
    index = dist / "index.html"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)


_dist = get_settings().frontend_dist
if _dist and (_dist / "index.html").is_file():
    _mount_frontend(_dist)
