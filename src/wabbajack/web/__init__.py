"""FastAPI web application for wabbajack-py."""
import logging, secrets
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Session token for local auth (prevents cross-site request forgery on mutating endpoints)
SESSION_TOKEN = secrets.token_urlsafe(32)

# Stored by cli.py serve command so the update endpoint can restart with the same args
_serve_restart_cmd: list[str] | None = None


def create_app():
    from .. import __version__
    app = FastAPI(title="wabbajack-py", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Session-Token"],
    )

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """Require session token for mutating API requests."""
        if request.method in ("POST", "PUT", "DELETE") and request.url.path.startswith("/api/"):
            token = request.headers.get("X-Session-Token")
            if token != SESSION_TOKEN:
                return JSONResponse(status_code=403, content={"detail": "Invalid session token"})
        return await call_next(request)

    # Provide the session token on a GET endpoint (only accessible from localhost)
    @app.get("/api/session")
    async def get_session():
        return {"token": SESSION_TOKEN}

    from .api import router as api_router
    from .ws import router as ws_router
    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    # Serve Svelte build if it exists (production mode)
    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app
