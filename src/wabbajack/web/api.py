"""REST API endpoints for wabbajack-py web GUI."""
import logging, threading, asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

log = logging.getLogger(__name__)
router = APIRouter()

_install_lock = threading.Lock()
_install_thread: Optional[threading.Thread] = None
_sso_task: Optional[asyncio.Task] = None


class InstallRequest(BaseModel):
    wabbajack_path: str
    output_dir: str
    downloads_dir: str
    game_dir: str
    nexus_key: Optional[str] = None
    workers: int = 12
    verify_hashes: bool = False
    skip_download: bool = False

    @field_validator('wabbajack_path', 'output_dir', 'downloads_dir', 'game_dir')
    @classmethod
    def validate_paths(cls, v: str) -> str:
        """Reject path traversal attempts and null bytes."""
        if '\x00' in v:
            raise ValueError("Null bytes not allowed in paths")
        if '..' in Path(v).parts:
            raise ValueError("Path traversal not allowed")
        return v

    @field_validator('workers')
    @classmethod
    def validate_workers(cls, v: int) -> int:
        if v < 1 or v > 64:
            raise ValueError("Workers must be between 1 and 64")
        return v


class SettingsUpdate(BaseModel):
    output_dir: Optional[str] = None
    downloads_dir: Optional[str] = None
    game_dir: Optional[str] = None
    workers: Optional[int] = None
    verify_hashes: Optional[bool] = None


# ── Gallery ──────────────────────────────────────────────────────────

@router.get("/gallery")
async def get_gallery():
    from .gallery import fetch_gallery
    return await fetch_gallery()


@router.get("/gallery/{machine_url:path}")
async def get_gallery_item(machine_url: str):
    from .gallery import fetch_gallery_item
    item = await fetch_gallery_item(machine_url)
    if not item:
        raise HTTPException(404, "Modlist not found")
    return item


# ── Games ────────────────────────────────────────────────────────────

@router.get("/games")
async def get_games():
    from ..platform import find_steam_libraries, GAME_DIRS
    libraries = find_steam_libraries()
    games = []
    for game_type, info in sorted(GAME_DIRS.items()):
        found = None
        for lib in libraries:
            p = lib / info["steam_subdir"]
            if p.exists():
                found = str(p)
                break
        games.append({
            "id": game_type,
            "name": info["display"],
            "path": found,
            "installed": found is not None,
        })
    return {"libraries": [str(l) for l in libraries], "games": games}


# ── Settings ─────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings():
    from ..config import InstallConfig
    config = InstallConfig(Path.home() / "Games")
    return config.summary()


@router.put("/settings")
async def update_settings(settings: SettingsUpdate):
    from ..config import InstallConfig
    config = InstallConfig(Path.home() / "Games")
    for key, val in settings.model_dump(exclude_none=True).items():
        config.set(key, val)
    config.save()
    return {"status": "ok"}


# ── Profiles ─────────────────────────────────────────────────────────

@router.get("/profiles")
async def get_profiles():
    from ..profiles import ProfileManager
    pm = ProfileManager()
    return {
        "active": pm.active,
        "shared_downloads": str(pm.shared_downloads),
        "profiles": pm.profiles,
    }


@router.post("/profiles/{name}/switch")
async def switch_profile(name: str):
    from ..profiles import ProfileManager
    pm = ProfileManager()
    if pm.switch(name):
        return {"status": "ok", "active": name}
    raise HTTPException(404, f"Profile '{name}' not found")


# ── Modlist ──────────────────────────────────────────────────────────

@router.post("/modlist/open")
async def open_modlist(wabbajack_path: str):
    from ..modlist import WabbajackModlist
    # Validate: must be a .wabbajack file, no traversal, must exist
    p = Path(wabbajack_path)
    if '\x00' in wabbajack_path or '..' in p.parts:
        raise HTTPException(400, "Invalid path")
    if not p.suffix.lower() in ('.wabbajack', '.bak'):
        raise HTTPException(400, "Not a .wabbajack file")
    if not p.exists():
        raise HTTPException(404, "File not found")
    try:
        with WabbajackModlist(wabbajack_path) as ml:
            return ml.summary()
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e))


# ── Install ──────────────────────────────────────────────────────────

@router.post("/install/start")
async def start_install(req: InstallRequest):
    global _install_thread
    with _install_lock:
        if _install_thread and _install_thread.is_alive():
            raise HTTPException(409, "Install already in progress")

    def run_install():
        from ..modlist import WabbajackModlist
        from ..installer import ModlistInstaller
        from .ws import install_log_handler, push_event

        handler = install_log_handler()
        try:
            with WabbajackModlist(req.wabbajack_path) as ml:
                # Use Nexus token from auth module if no key provided
                nexus_key = req.nexus_key
                if not nexus_key:
                    from .auth import get_nexus_token
                    nexus_key = get_nexus_token()

                inst = ModlistInstaller(
                    ml, req.output_dir, req.downloads_dir, req.game_dir,
                    nexus_key=nexus_key, workers=req.workers,
                    verify_hashes=req.verify_hashes,
                )
                push_event("state", phase="started", modlist=ml.name, version=ml.version)
                inst.install(skip_download=req.skip_download)
                push_event("state", phase="complete")
        except Exception as e:
            log.error(f"Install failed: {e}")
            push_event("error", message=str(e))
        finally:
            logging.getLogger("wabbajack").removeHandler(handler)

    _install_thread = threading.Thread(target=run_install, daemon=True)
    _install_thread.start()
    return {"status": "started"}


@router.get("/install/status")
async def install_status():
    return {"running": _install_thread is not None and _install_thread.is_alive()}


# ── Nexus Auth ───────────────────────────────────────────────────────

@router.get("/auth/nexus/status")
async def nexus_status():
    from .auth import get_nexus_status, load_saved_token
    status = get_nexus_status()
    if not status["logged_in"]:
        load_saved_token()
        status = get_nexus_status()
    return status


@router.get("/auth/nexus/login")
async def nexus_login():
    global _sso_task
    from .auth import initiate_sso
    auth_url, wait_fn = await initiate_sso()
    if not auth_url:
        raise HTTPException(500, "Could not start SSO (websockets package missing?)")

    # Start background task to wait for token
    _sso_task = asyncio.create_task(wait_fn())
    return {"auth_url": auth_url}


@router.get("/auth/nexus/sso-status")
async def nexus_sso_status():
    """Check if SSO completed."""
    from .auth import get_nexus_status
    status = get_nexus_status()
    done = _sso_task is None or _sso_task.done() if _sso_task else True
    return {**status, "sso_complete": done}


class NexusKeyRequest(BaseModel):
    key: str

@router.post("/auth/nexus/key")
async def nexus_set_key(req: NexusKeyRequest):
    """Manually set API key (alternative to SSO). Key in body, not URL."""
    from .auth import save_token, get_nexus_status
    save_token(req.key)
    return get_nexus_status()


# ── Updates ──────────────────────────────────────────────────────────

@router.get("/update/check")
async def update_check():
    from ..updater import check_for_update
    return check_for_update()


@router.post("/update/apply")
async def update_apply():
    from ..updater import apply_update
    return apply_update()


# ── Nexus Auth (continued) ──────────────────────────────────────────

@router.post("/auth/nexus/logout")
async def nexus_logout():
    from .auth import logout
    logout()
    return {"status": "ok"}
