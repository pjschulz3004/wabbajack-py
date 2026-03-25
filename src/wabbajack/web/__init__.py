"""FastAPI web application for wabbajack-py."""
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app():
    app = FastAPI(title="wabbajack-py", version="0.3.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .api import router as api_router
    from .ws import router as ws_router
    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    # Serve Svelte build if it exists (production mode)
    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app
