# Web GUI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-hosted web GUI for wabbajack-py with real-time progress, modlist gallery, Nexus OAuth, and cross-platform packaging.

**Architecture:** FastAPI backend serves REST + WebSocket API at `/api/` and `/ws`. Svelte 5 SPA built into `src/wabbajack/web/static/`. Single process launched via `wabbajack-py serve`.

**Tech Stack:** FastAPI, uvicorn, WebSocket, Svelte 5, TypeScript, Vite, watchdog, keyring, pystray, PyInstaller

---

### Task 1: Backend Skeleton -- FastAPI + WebSocket + Log Interceptor

**Files:**
- Create: `src/wabbajack/web/__init__.py`
- Create: `src/wabbajack/web/api.py`
- Create: `src/wabbajack/web/ws.py`
- Modify: `src/wabbajack/cli.py` (add `serve` command)
- Modify: `pyproject.toml` (add fastapi, uvicorn deps)

**Step 1: Create web package init with FastAPI app factory**

```python
# src/wabbajack/web/__init__.py
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
        allow_origins=["*"],  # localhost only in production
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .api import router as api_router
    from .ws import router as ws_router
    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    # Serve Svelte build if it exists
    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app
```

**Step 2: Create WebSocket handler with log interceptor**

```python
# src/wabbajack/web/ws.py
"""WebSocket handler for real-time progress and log streaming."""
import json, logging, asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# Connected WebSocket clients
_clients: set[WebSocket] = set()
# Queue for messages from sync code (installer threads) to async WS
_message_queue: asyncio.Queue | None = None


class WebSocketLogHandler(logging.Handler):
    """Intercepts log messages and forwards to WebSocket clients."""

    def emit(self, record):
        if _message_queue is None:
            return
        msg = {
            "type": "log",
            "level": record.levelname.lower(),
            "message": self.format(record),
        }
        try:
            _message_queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass  # Drop if queue is full (backpressure)


def install_log_handler():
    """Attach WebSocket log handler to the wabbajack logger."""
    handler = WebSocketLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("wabbajack").addHandler(handler)
    return handler


async def broadcast(msg: dict):
    """Send a message to all connected WebSocket clients."""
    data = json.dumps(msg)
    dead = set()
    for ws in _clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    _clients -= dead


def push_progress(phase, current, total, speed="", eta=""):
    """Push progress update from sync code (called from installer threads)."""
    if _message_queue is None:
        return
    _message_queue.put_nowait({
        "type": "progress",
        "phase": phase,
        "current": current,
        "total": total,
        "speed": speed,
        "eta": eta,
    })


def push_event(event_type, **kwargs):
    """Push arbitrary event from sync code."""
    if _message_queue is None:
        return
    _message_queue.put_nowait({"type": event_type, **kwargs})


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global _message_queue
    await ws.accept()
    _clients.add(ws)

    if _message_queue is None:
        _message_queue = asyncio.Queue(maxsize=10000)

    # Background task: drain queue and broadcast
    async def drain():
        while True:
            try:
                msg = await asyncio.wait_for(_message_queue.get(), timeout=0.1)
                await broadcast(msg)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    drain_task = asyncio.create_task(drain())

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            # Handle client commands
            if msg.get("type") == "cancel":
                push_event("cancel_requested")
            elif msg.get("type") == "skip_file":
                push_event("skip_file", name=msg.get("name", ""))
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
        if not _clients:
            drain_task.cancel()
```

**Step 3: Create REST API skeleton**

```python
# src/wabbajack/web/api.py
"""REST API endpoints for wabbajack-py web GUI."""
import logging, threading
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

log = logging.getLogger(__name__)
router = APIRouter()

# Shared state
_install_thread: Optional[threading.Thread] = None


class InstallRequest(BaseModel):
    wabbajack_path: str
    output_dir: str
    downloads_dir: str
    game_dir: str
    nexus_key: Optional[str] = None
    workers: int = 12
    verify_hashes: bool = False
    skip_download: bool = False


class SettingsUpdate(BaseModel):
    output_dir: Optional[str] = None
    downloads_dir: Optional[str] = None
    game_dir: Optional[str] = None
    workers: Optional[int] = None
    verify_hashes: Optional[bool] = None
    nexus_key: Optional[str] = None


# -- Gallery --

@router.get("/gallery")
async def get_gallery():
    from .gallery import fetch_gallery
    return await fetch_gallery()


@router.get("/gallery/{machine_url}")
async def get_gallery_item(machine_url: str):
    from .gallery import fetch_gallery_item
    item = await fetch_gallery_item(machine_url)
    if not item:
        raise HTTPException(404, "Modlist not found")
    return item


# -- Games --

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


# -- Settings --

@router.get("/settings")
async def get_settings():
    from ..config import InstallConfig
    # Load from default location or most recent install
    home = Path.home() / "Games"
    config = InstallConfig(home)
    return config.summary()


@router.put("/settings")
async def update_settings(settings: SettingsUpdate):
    from ..config import InstallConfig
    home = Path.home() / "Games"
    config = InstallConfig(home)
    for key, val in settings.model_dump(exclude_none=True).items():
        config.set(key, val)
    config.save()
    return {"status": "ok"}


# -- Profiles --

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


# -- Modlist --

@router.post("/modlist/open")
async def open_modlist(wabbajack_path: str):
    from ..modlist import WabbajackModlist
    try:
        with WabbajackModlist(wabbajack_path) as ml:
            return ml.summary()
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e))


# -- Install --

@router.post("/install/start")
async def start_install(req: InstallRequest):
    global _install_thread
    if _install_thread and _install_thread.is_alive():
        raise HTTPException(409, "Install already in progress")

    def run_install():
        from ..modlist import WabbajackModlist
        from ..installer import ModlistInstaller
        from .ws import install_log_handler, push_progress, push_event

        handler = install_log_handler()
        try:
            with WabbajackModlist(req.wabbajack_path) as ml:
                inst = ModlistInstaller(
                    ml, req.output_dir, req.downloads_dir, req.game_dir,
                    nexus_key=req.nexus_key, workers=req.workers,
                    verify_hashes=req.verify_hashes,
                )
                push_event("state", phase="started", modlist=ml.name, version=ml.version)
                inst.install(skip_download=req.skip_download)
                push_event("state", phase="complete")
        except Exception as e:
            push_event("error", message=str(e))
        finally:
            logging.getLogger("wabbajack").removeHandler(handler)

    _install_thread = threading.Thread(target=run_install, daemon=True)
    _install_thread.start()
    return {"status": "started"}


@router.get("/install/status")
async def install_status():
    is_running = _install_thread is not None and _install_thread.is_alive()
    return {"running": is_running}
```

**Step 4: Add `serve` command to CLI**

Add to `src/wabbajack/cli.py`:

```python
@main.command()
@click.option('--port', default=6969, help='Port for web UI')
@click.option('--no-browser', is_flag=True, help='Do not open browser on start')
@click.option('--host', default='127.0.0.1', help='Bind address')
def serve(port, no_browser, host):
    """Launch the web GUI."""
    import uvicorn
    from .web import create_app

    app = create_app()

    if not no_browser:
        import threading, webbrowser, time
        def open_browser():
            time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")
        threading.Thread(target=open_browser, daemon=True).start()

    log.info(f"Starting wabbajack-py web UI on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
```

**Step 5: Update pyproject.toml dependencies**

Add to `dependencies`:
```
"fastapi>=0.104",
"uvicorn[standard]>=0.24",
"websockets>=12.0",
```

Add to `[project.optional-dependencies]`:
```
web = ["watchdog>=3.0", "keyring>=24.0", "pystray>=0.19", "Pillow>=10.0"]
```

Update `all` to include web deps.

**Step 6: Commit**

```
git add src/wabbajack/web/ src/wabbajack/cli.py pyproject.toml
git commit -m "feat: FastAPI backend skeleton with WebSocket + log interceptor"
```

---

### Task 2: Gallery Fetcher -- Wabbajack Modlist API

**Files:**
- Create: `src/wabbajack/web/gallery.py`

**Step 1: Implement gallery fetcher with caching**

```python
# src/wabbajack/web/gallery.py
"""Fetch modlist gallery from Wabbajack's GitHub-hosted repos."""
import time, json, logging
from pathlib import Path

log = logging.getLogger(__name__)

GALLERY_URL = "https://raw.githubusercontent.com/wabbajack-tools/mod-lists/master/repositories.json"
CACHE_TTL = 3600  # 1 hour

_cache = {"data": None, "fetched_at": 0}


async def fetch_gallery():
    """Fetch and cache modlist gallery."""
    now = time.time()
    if _cache["data"] and now - _cache["fetched_at"] < CACHE_TTL:
        return _cache["data"]

    import httpx
    async with httpx.AsyncClient() as client:
        try:
            # Fetch repository index
            resp = await client.get(GALLERY_URL, timeout=30, follow_redirects=True)
            repos = resp.json()

            # Fetch each repository's modlists
            all_lists = []
            for repo in repos:
                try:
                    r = await client.get(repo["url"], timeout=15, follow_redirects=True)
                    lists = r.json()
                    if isinstance(lists, list):
                        all_lists.extend(lists)
                except Exception:
                    continue

            _cache["data"] = all_lists
            _cache["fetched_at"] = now
            log.info(f"Gallery: fetched {len(all_lists)} modlists from {len(repos)} repos")
            return all_lists

        except Exception as e:
            log.warning(f"Gallery fetch failed: {e}")
            return _cache["data"] or []


async def fetch_gallery_item(machine_url: str):
    """Find a single modlist by machineURL."""
    gallery = await fetch_gallery()
    for item in gallery:
        if item.get("links", {}).get("machineURL") == machine_url:
            return item
    return None
```

**Step 2: Add httpx dependency to pyproject.toml**

```
"httpx>=0.25",
```

**Step 3: Commit**

```
git commit -m "feat: gallery fetcher with 1hr cache from Wabbajack repos"
```

---

### Task 3: Svelte Project Scaffolding + Design System

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/App.svelte`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/app.css`
- Create: `frontend/src/lib/stores/ws.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/index.html`
- Create: `build.py`

**Step 1: Initialize Svelte project**

```bash
cd /home/paul/gaming-fix/wabbajack-py
npm create vite@latest frontend -- --template svelte-ts
cd frontend
npm install
npm install svelte-routing
```

**Step 2: Configure Vite to proxy API calls in dev mode**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:6969',
      '/ws': { target: 'ws://localhost:6969', ws: true },
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
```

**Step 3: Create global CSS with design system**

```css
/* frontend/src/app.css */
:root {
  --bg-primary: #0f0f13;
  --bg-secondary: #1a1a24;
  --bg-tertiary: #252532;
  --border: #2d2d3d;
  --text-primary: #e8e8f0;
  --text-secondary: #8888a0;
  --accent: #e8922a;
  --accent-hover: #f5a03d;
  --accent-glow: rgba(232, 146, 42, 0.25);
  --success: #4ade80;
  --error: #f87171;
  --warning: #fbbf24;
  --radius: 8px;
  --radius-sm: 4px;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  min-height: 100vh;
}

::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--bg-tertiary); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

a { color: var(--accent); text-decoration: none; }
a:hover { color: var(--accent-hover); }

.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  transition: box-shadow 0.2s, border-color 0.2s;
}
.card:hover {
  border-color: var(--accent);
  box-shadow: 0 0 20px var(--accent-glow);
}

.btn {
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: none; border-radius: var(--radius-sm);
  font-size: 0.875rem; font-weight: 500;
  cursor: pointer; transition: all 0.15s;
}
.btn-primary { background: var(--accent); color: #000; }
.btn-primary:hover { background: var(--accent-hover); }
.btn-ghost { background: transparent; color: var(--text-secondary); border: 1px solid var(--border); }
.btn-ghost:hover { border-color: var(--accent); color: var(--text-primary); }

.badge {
  display: inline-block; padding: 0.15rem 0.5rem;
  border-radius: 9999px; font-size: 0.7rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.animate-pulse { animation: pulse 2s ease-in-out infinite; }
```

**Step 4: Create WebSocket store**

```typescript
// frontend/src/lib/stores/ws.ts
import { writable, derived } from 'svelte/store';

export interface WsMessage {
  type: string;
  [key: string]: any;
}

export const connected = writable(false);
export const logs = writable<WsMessage[]>([]);
export const progress = writable<WsMessage | null>(null);
export const installState = writable<WsMessage | null>(null);
export const manualDownloads = writable<WsMessage[]>([]);

let ws: WebSocket | null = null;
let reconnectTimer: number | null = null;

export function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    connected.set(true);
    if (reconnectTimer) clearInterval(reconnectTimer);
  };

  ws.onclose = () => {
    connected.set(false);
    reconnectTimer = setInterval(() => connectWs(), 3000) as any;
  };

  ws.onmessage = (event) => {
    const msg: WsMessage = JSON.parse(event.data);
    switch (msg.type) {
      case 'log':
        logs.update(l => { l.push(msg); if (l.length > 50000) l.shift(); return l; });
        break;
      case 'progress':
        progress.set(msg);
        break;
      case 'state':
        installState.set(msg);
        break;
      case 'manual_needed':
        manualDownloads.update(m => [...m, msg]);
        break;
      case 'manual_complete':
        manualDownloads.update(m => m.filter(d => d.name !== msg.name));
        break;
    }
  };
}

export function sendWs(msg: WsMessage) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
}
```

**Step 5: Create API client**

```typescript
// frontend/src/lib/api.ts
const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function post<T>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function put<T>(path: string, body: any): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  gallery: () => get<any[]>('/gallery'),
  galleryItem: (id: string) => get<any>(`/gallery/${id}`),
  games: () => get<any>('/games'),
  settings: () => get<any>('/settings'),
  updateSettings: (s: any) => put<any>('/settings', s),
  profiles: () => get<any>('/profiles'),
  switchProfile: (name: string) => post<any>(`/profiles/${name}/switch`),
  openModlist: (path: string) => post<any>('/modlist/open', { wabbajack_path: path }),
  startInstall: (req: any) => post<any>('/install/start', req),
  installStatus: () => get<any>('/install/status'),
  nexusStatus: () => get<any>('/auth/nexus/status'),
  nexusLogin: () => get<any>('/auth/nexus/login'),
  nexusLogout: () => post<any>('/auth/nexus/logout'),
};
```

**Step 6: Create App shell with sidebar layout**

```svelte
<!-- frontend/src/App.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { connectWs, connected, progress, installState } from './lib/stores/ws';
  import Gallery from './routes/Gallery.svelte';
  import Install from './routes/Install.svelte';
  import Downloads from './routes/Downloads.svelte';
  import Profiles from './routes/Profiles.svelte';
  import Settings from './routes/Settings.svelte';

  let currentPage = 'gallery';

  const pages: Record<string, any> = {
    gallery: Gallery,
    install: Install,
    downloads: Downloads,
    profiles: Profiles,
    settings: Settings,
  };

  const navItems = [
    { id: 'gallery', label: 'Gallery', icon: '&#9776;' },
    { id: 'install', label: 'Install', icon: '&#9654;' },
    { id: 'downloads', label: 'Downloads', icon: '&#8615;' },
    { id: 'profiles', label: 'Profiles', icon: '&#9881;' },
    { id: 'settings', label: 'Settings', icon: '&#9881;' },
  ];

  onMount(() => connectWs());
</script>

<div class="layout">
  <nav class="sidebar">
    <div class="logo">
      <span class="logo-text">wabbajack-py</span>
      <span class="logo-version">v0.3.0</span>
    </div>
    {#each navItems as item}
      <button
        class="nav-item"
        class:active={currentPage === item.id}
        on:click={() => currentPage = item.id}
      >
        <span class="nav-icon">{@html item.icon}</span>
        <span class="nav-label">{item.label}</span>
      </button>
    {/each}
    <div class="sidebar-footer">
      <div class="ws-status" class:online={$connected}>
        {$connected ? 'Connected' : 'Disconnected'}
      </div>
    </div>
  </nav>

  <main class="content">
    {#if $progress && currentPage !== 'install'}
      <div class="mini-progress" on:click={() => currentPage = 'install'}>
        <div class="mini-bar" style="width: {($progress.current / Math.max(1, $progress.total)) * 100}%"></div>
        <span>{$progress.phase} {$progress.current}/{$progress.total}</span>
      </div>
    {/if}
    <svelte:component this={pages[currentPage]} />
  </main>
</div>

<style>
  .layout { display: flex; height: 100vh; }
  .sidebar {
    width: 200px; background: var(--bg-secondary); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; padding: 1rem 0; flex-shrink: 0;
  }
  .logo { padding: 0 1rem 1.5rem; border-bottom: 1px solid var(--border); margin-bottom: 0.5rem; }
  .logo-text { font-weight: 700; font-size: 1rem; color: var(--accent); }
  .logo-version { font-size: 0.7rem; color: var(--text-secondary); margin-left: 0.5rem; }
  .nav-item {
    display: flex; align-items: center; gap: 0.75rem; width: 100%;
    padding: 0.625rem 1rem; border: none; background: none;
    color: var(--text-secondary); cursor: pointer; font-size: 0.875rem;
    transition: all 0.15s; text-align: left;
  }
  .nav-item:hover { color: var(--text-primary); background: var(--bg-tertiary); }
  .nav-item.active { color: var(--accent); background: rgba(232, 146, 42, 0.1); border-right: 2px solid var(--accent); }
  .nav-icon { font-size: 1.1rem; width: 1.5rem; text-align: center; }
  .sidebar-footer { margin-top: auto; padding: 1rem; }
  .ws-status { font-size: 0.7rem; color: var(--error); }
  .ws-status.online { color: var(--success); }
  .content { flex: 1; overflow-y: auto; padding: 1.5rem; }
  .mini-progress {
    position: relative; height: 28px; background: var(--bg-secondary); border-radius: var(--radius-sm);
    margin-bottom: 1rem; cursor: pointer; overflow: hidden;
    display: flex; align-items: center; padding: 0 0.75rem;
    font-size: 0.75rem; color: var(--text-secondary);
  }
  .mini-bar {
    position: absolute; left: 0; top: 0; bottom: 0;
    background: linear-gradient(90deg, var(--accent), var(--accent-hover));
    opacity: 0.2; transition: width 0.3s;
  }
</style>
```

**Step 7: Create build script**

```python
# build.py
"""Build Svelte frontend and copy into Python package."""
import subprocess, shutil
from pathlib import Path

FRONTEND = Path("frontend")
STATIC = Path("src/wabbajack/web/static")

def build():
    print("Building Svelte frontend...")
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=True)

    print(f"Copying to {STATIC}...")
    if STATIC.exists():
        shutil.rmtree(STATIC)
    shutil.copytree(FRONTEND / "dist", STATIC)
    print(f"Done. {sum(1 for _ in STATIC.rglob('*') if _.is_file())} files copied.")

if __name__ == "__main__":
    build()
```

**Step 8: Commit**

```
git add frontend/ build.py src/wabbajack/web/
git commit -m "feat: Svelte project scaffold with design system, WS store, API client"
```

---

### Task 4: Gallery Page

**Files:**
- Create: `frontend/src/routes/Gallery.svelte`
- Create: `frontend/src/lib/components/ModCard.svelte`
- Create: `frontend/src/lib/components/GameBadge.svelte`

Fetches modlists from `/api/gallery`, renders card grid with search, game filter, NSFW toggle. Cards show banner, title, author, game badge, sizes. Click opens detail modal with install button.

**Step 1: Create GameBadge component**

Small colored pill component. Color derived from game name.

**Step 2: Create ModCard component**

Card with banner image (16:9, lazy loaded), title, author, game badge, download/install size, tags.

**Step 3: Create Gallery page**

Grid layout, search input, game filter dropdown, NSFW toggle. Fetches on mount, filters client-side.

**Step 4: Commit**

---

### Task 5: Install Page + Log Viewer

**Files:**
- Create: `frontend/src/routes/Install.svelte`
- Create: `frontend/src/lib/components/ProgressBar.svelte`
- Create: `frontend/src/lib/components/ProgressRing.svelte`
- Create: `frontend/src/lib/components/LogViewer.svelte`
- Create: `frontend/src/lib/components/ManualDownloadCard.svelte`

Progress ring at top, phase indicator, speed/ETA. Log viewer with virtual scrolling. Manual download cards for non-premium.

**Step 1: Create ProgressBar component** -- Rounded bar with gradient, pulse animation
**Step 2: Create ProgressRing component** -- SVG circle with animated stroke-dashoffset
**Step 3: Create LogViewer component** -- Virtual scroll, color by level, auto-scroll toggle
**Step 4: Create ManualDownloadCard** -- Amber card with pulse, "Open in Browser" button
**Step 5: Create Install page** -- Compose all components, wire to WS stores
**Step 6: Commit**

---

### Task 6: Nexus OAuth (SSO)

**Files:**
- Create: `src/wabbajack/web/auth.py`
- Modify: `src/wabbajack/web/api.py` (add auth endpoints)

**Step 1: Implement Nexus SSO WebSocket flow**

Connect to `wss://sso.nexusmods.com`, send app ID, wait for token.

**Step 2: Add keyring token storage**

Store/retrieve API key securely. Fallback to config file.

**Step 3: Add auth API endpoints**

`/api/auth/nexus/login`, `/status`, `/callback`, `/logout`

**Step 4: Commit**

---

### Task 7: Downloads, Profiles, Settings Pages

**Files:**
- Create: `frontend/src/routes/Downloads.svelte`
- Create: `frontend/src/routes/Profiles.svelte`
- Create: `frontend/src/routes/Settings.svelte`

**Step 1: Downloads page** -- Table of archives, status icons, sort/filter, retry button
**Step 2: Profiles page** -- Profile cards, switch button, shared analysis
**Step 3: Settings page** -- Forms for paths, performance sliders, Nexus login, advanced
**Step 4: Commit**

---

### Task 8: Packaging -- PyInstaller + Installers

**Files:**
- Create: `wabbajack-py.spec` (PyInstaller spec)
- Create: `packaging/windows/installer.iss` (Inno Setup)
- Create: `packaging/linux/wabbajack-py.desktop`
- Create: `packaging/linux/build-appimage.sh`
- Create: `packaging/macos/build-app.sh`
- Create: `.github/workflows/release.yml`

**Step 1: PyInstaller spec** -- Bundle Python + deps + Svelte static
**Step 2: Inno Setup script** -- Windows installer with shortcuts
**Step 3: AppImage build script** -- Linux portable binary
**Step 4: GitHub Actions release workflow** -- 3-platform parallel build
**Step 5: Commit**

---

## Execution Order

Tasks 1-3 are sequential (backend needs to exist before frontend connects).
Tasks 4-7 are parallelizable (independent pages).
Task 8 depends on all others.

Estimated: 8 tasks, ~2-3 hours with parallel agents.
