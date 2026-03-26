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


def _check_path(v: str) -> str:
    """Reject path traversal attempts and null bytes."""
    if '\x00' in v:
        raise ValueError("Null bytes not allowed in paths")
    if '..' in Path(v).parts:
        raise ValueError("Path traversal not allowed")
    return v


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
        return _check_path(v)

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

    @field_validator('output_dir', 'downloads_dir', 'game_dir')
    @classmethod
    def validate_paths(cls, v: str | None) -> str | None:
        return _check_path(v) if v is not None else v

    @field_validator('workers')
    @classmethod
    def validate_workers(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 64):
            raise ValueError("Workers must be between 1 and 64")
        return v


# ── Gallery ──────────────────────────────────────────────────────────

@router.get("/gallery")
async def get_gallery(q: str = '', game: str = '', nsfw: bool = False):
    """Get modlist gallery with optional search/filter."""
    from .gallery import search_gallery
    return await search_gallery(query=q, game=game, nsfw=nsfw)


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
    installed = []
    not_found = []
    for game_type, info in sorted(GAME_DIRS.items()):
        found = None
        for lib in libraries:
            p = lib / info["steam_subdir"]
            if p.exists():
                found = str(p)
                break
        entry = {"id": game_type, "name": info["display"], "path": found, "installed": found is not None}
        if found:
            installed.append(entry)
        else:
            not_found.append(entry)
    # Installed games first, not-found collapsed separately
    return {
        "libraries": [str(lib) for lib in libraries],
        "games": installed,
        "not_found": not_found,
        "total_supported": len(GAME_DIRS),
    }


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
    try:
        _check_path(wabbajack_path)
    except ValueError:
        raise HTTPException(400, "Invalid path")
    p = Path(wabbajack_path)
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
    # Cancel any in-progress SSO flow before starting a new one
    if _sso_task and not _sso_task.done():
        _sso_task.cancel()
    auth_url, wait_fn = await initiate_sso()
    if not auth_url:
        raise HTTPException(500, "Could not start SSO (websockets package missing?)")

    _sso_task = asyncio.create_task(wait_fn())
    return {"auth_url": auth_url}


@router.get("/auth/nexus/sso-status")
async def nexus_sso_status():
    """Check if SSO completed."""
    global _sso_task
    from .auth import get_nexus_status
    status = get_nexus_status()
    done = _sso_task is None or _sso_task.done() if _sso_task else True
    if done and _sso_task is not None:
        _sso_task = None  # Reset for future login attempts
    return {**status, "sso_complete": done}


class NexusKeyRequest(BaseModel):
    key: str

@router.post("/auth/nexus/key")
async def nexus_set_key(req: NexusKeyRequest):
    """Manually set API key (alternative to SSO). Key in body, not URL."""
    from .auth import save_token, get_nexus_status
    save_token(req.key)
    return get_nexus_status()


# ── Load Order ───────────────────────────────────────────────────────

@router.get("/loadorder/{game_type}")
async def load_order_get(game_type: str, game_dir: str = '', profile: str = ''):
    """Get load order for a game."""
    from ..loadorder import get_load_order, LOAD_ORDER_CLASSES
    from ..platform import detect_game_dir

    if game_type == 'supported':
        return {"games": list(LOAD_ORDER_CLASSES.keys())}

    try:
        for p in (game_dir, profile):
            if p:
                _check_path(p)
    except ValueError:
        raise HTTPException(400, "Invalid path")

    gd = game_dir or detect_game_dir(game_type)
    if not gd:
        raise HTTPException(404, f"Could not find {game_type} installation")

    lo = get_load_order(game_type, Path(gd), Path(profile) if profile else None)
    lo.load()

    errors = lo.validate_load_order()

    return {
        **lo.summary(),
        'mods': [{'name': m.name, 'enabled': m.enabled, 'priority': m.priority} for m in lo.mods],
        'plugins': [{'filename': p.filename, 'enabled': p.enabled,
                      'is_master': p.is_master, 'is_light': p.is_light,
                      'masters': p.masters} for p in lo.plugins],
        'errors': errors,
    }


class ModUpdate(BaseModel):
    name: str
    enabled: bool = True
    uid: str = ''

class PluginUpdate(BaseModel):
    filename: str
    enabled: bool = True

class LoadOrderUpdate(BaseModel):
    mods: list[ModUpdate] | None = None
    plugins: list[PluginUpdate] | None = None


@router.put("/loadorder/{game_type}")
async def load_order_update(game_type: str, req: LoadOrderUpdate,
                            game_dir: str = '', profile: str = ''):
    """Update load order for a game."""
    from ..loadorder import get_load_order, ModEntry, PluginEntry
    from ..platform import detect_game_dir

    try:
        for p in (game_dir, profile):
            if p:
                _check_path(p)
    except ValueError:
        raise HTTPException(400, "Invalid path")

    gd = game_dir or detect_game_dir(game_type)
    if not gd:
        raise HTTPException(404, f"Could not find {game_type} installation")

    lo = get_load_order(game_type, Path(gd), Path(profile) if profile else None)
    lo.load()

    if req.mods is not None:
        lo.mods = [ModEntry(m.name, m.enabled, i, m.uid) for i, m in enumerate(req.mods)]
    if req.plugins is not None:
        lo.plugins = [PluginEntry(p.filename, p.enabled) for p in req.plugins]

    lo.save()
    return {"status": "saved", **lo.summary()}


# ── Detected Installs ─────────────────────────────────────────────────

@router.get("/installs")
async def get_installs():
    """Scan for existing modlist installs and .wabbajack files."""
    from ..config import InstallConfig, CONFIG_FILE
    from ..state import InstallState, STATE_FILE

    home = Path.home()
    games_dir = home / "Games"
    downloads_base = games_dir / "WabbajackDownloads"
    installs = []

    # 1. Scan Games dir for output dirs with .wj-config.json
    if games_dir.exists():
        for d in sorted(games_dir.iterdir()):
            if not d.is_dir() or d.name == "WabbajackDownloads":
                continue
            config_path = d / CONFIG_FILE
            state_path = d / STATE_FILE
            if config_path.exists() or state_path.exists():
                config = InstallConfig(d) if config_path.exists() else None
                state = InstallState(d) if state_path.exists() else None
                cfg = config.summary() if config else {}
                st = state.summary() if state else {}
                installs.append({
                    "name": cfg.get("modlist_name", d.name),
                    "version": cfg.get("modlist_version", ""),
                    "game": cfg.get("game_type", ""),
                    "output_dir": str(d),
                    "downloads_dir": cfg.get("downloads_dir", ""),
                    "game_dir": cfg.get("game_dir", ""),
                    "wabbajack_path": cfg.get("wabbajack_path", ""),
                    "phase": st.get("phase", "unknown"),
                    "completed_archives": st.get("completed_archives", 0),
                    "placed_files": st.get("placed_files", 0),
                    "failed_files": st.get("failed_files", 0),
                    "started": st.get("started", ""),
                    "updated": st.get("updated", ""),
                    "source": "state_file",
                })

    # 2. Scan for .wabbajack files in common locations
    wj_files = []
    # XDG data dir for this app + common download locations
    app_data = home / ".local" / "share" / "wabbajack-py" / "modlists"
    scan_dirs = [
        app_data,
        home / "Downloads",
        games_dir,
    ]
    for scan_dir in scan_dirs:
        if scan_dir.exists():
            for f in scan_dir.iterdir():
                if f.is_file() and f.suffix.lower() in ('.wabbajack', '.bak') and f.stat().st_size > 1_000_000:
                    already = any(i.get("wabbajack_path") == str(f) for i in installs)
                    if not already:
                        wj_files.append(str(f))

    # 3. Per-game download stats
    game_downloads = {}
    if downloads_base.exists():
        for gd in sorted(downloads_base.iterdir()):
            if gd.is_dir():
                count = 0
                size = 0
                for f in gd.iterdir():
                    if f.is_file():
                        count += 1
                        size += f.stat().st_size
                game_downloads[gd.name] = {"count": count, "size": size}

    return {
        "installs": installs,
        "wabbajack_files": wj_files,
        "downloads_base": str(downloads_base),
        "game_downloads": game_downloads,
    }


# ── Updates ──────────────────────────────────────────────────────────

@router.get("/update/check")
async def update_check():
    from ..updater import check_for_update
    return check_for_update()


@router.post("/update/apply")
async def update_apply():
    from ..updater import check_for_update, apply_update, restart_server
    from .ws import push_event

    info = check_for_update()
    if not info.get('update_available'):
        return {"success": False, "message": "Already up to date"}

    def progress_fn(step, message, pct):
        push_event("update_progress", step=step, message=message, pct=pct)

    def run_update():
        import time
        result = apply_update(info, progress_fn=progress_fn)
        if result.get('success'):
            push_event("update_complete", message=result['message'])
            if result.get('restart_required'):
                time.sleep(1.5)  # Let WS events flush to clients
                push_event("update_restart")
                time.sleep(0.5)
                restart_server()
        else:
            push_event("update_error", message=result.get('message', 'Unknown error'))

    _update_thread = threading.Thread(target=run_update, daemon=True)
    _update_thread.start()
    return {"status": "updating"}


# ── Nexus Auth (continued) ──────────────────────────────────────────

@router.post("/auth/nexus/logout")
async def nexus_logout():
    from .auth import logout
    logout()
    return {"status": "ok"}
