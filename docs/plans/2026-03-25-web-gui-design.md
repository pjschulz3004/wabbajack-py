# Web GUI Design -- wabbajack-py

## Overview

Self-hosted web GUI for wabbajack-py. FastAPI backend serves a Svelte SPA on `localhost:6969`. Real-time progress via WebSocket. Nexus OAuth2 with non-premium manual download support. Packaged as single binary for Windows (installer), Linux (AppImage), macOS (Homebrew cask).

## Architecture

Two layers, one process:

- **Backend**: FastAPI app mounted at `/api/` and `/ws`, serves Svelte build from `/static/`
- **Frontend**: Svelte 5 + TypeScript + Vite, builds into `src/wabbajack/web/static/`
- **Launch**: `wabbajack-py serve` starts uvicorn, opens browser, shows system tray icon

```
src/wabbajack/
├── web/
│   ├── __init__.py       # create_app(), mount static, startup/shutdown
│   ├── api.py            # REST endpoints
│   ├── ws.py             # WebSocket handler + log interceptor
│   ├── auth.py           # Nexus SSO WebSocket flow
│   ├── gallery.py        # modlist gallery fetcher (cached)
│   └── static/           # Svelte build output (gitignored)
frontend/
├── src/
│   ├── App.svelte
│   ├── lib/
│   │   ├── stores/       # wsStore, settingsStore, galleryStore
│   │   ├── components/   # ProgressBar, LogViewer, ModCard, etc.
│   │   └── api.ts        # REST + WS client wrappers
│   └── routes/           # Gallery, Install, Downloads, Profiles, Settings
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## REST API

```
GET  /api/gallery              cached modlist gallery
GET  /api/gallery/{id}         single modlist detail
GET  /api/games                detected game installations
GET  /api/settings             current config
PUT  /api/settings             update config
GET  /api/profiles             installed profiles
GET  /api/downloads/{hash}     download status

POST /api/install/start        begin install
POST /api/install/pause        pause
POST /api/install/resume       resume from state
POST /api/download/start       download-only
POST /api/modlist/open         parse .wabbajack file

GET  /api/auth/nexus/status    login + premium status
GET  /api/auth/nexus/login     initiate SSO, returns redirect URL
GET  /api/auth/nexus/callback  SSO completion
POST /api/auth/nexus/logout    clear token
```

## WebSocket Protocol

Single connection on `/ws`. Server pushes:

```json
{"type": "progress", "phase": "downloading", "current": 1200, "total": 5667, "speed": "45.2 MB/s", "eta": "1h 23m"}
{"type": "log", "level": "info", "message": "[1200/5667] OK: SomeModFile.7z (234.5 MB)"}
{"type": "download_file", "name": "SomeMod.7z", "status": "complete", "size": 245366784}
{"type": "state", "phase": "extracting", "batch": 3, "total_batches": 29}
{"type": "manual_needed", "name": "LoversLabMod.7z", "url": "https://..."}
```

Client sends:

```json
{"type": "cancel"}
{"type": "skip_file", "name": "SomeMod.7z"}
{"type": "manual_complete", "name": "LoversLabMod.7z"}
```

Log interception: custom `logging.Handler` subclass forwards all `wabbajack.*` log messages to connected WebSocket clients. Zero changes to existing modules.

## Frontend Pages

### 1. Gallery (home)
Card grid of modlists from Wabbajack API. Banner images, game badge, author, sizes, tags. Search + game filter + NSFW toggle. Card click opens detail view with install button.

### 2. Install
Progress ring + phase indicator (download/extract/place/BSA/MO2). Live progress bar with current file, speed, ETA. Scrolling log viewer (virtual scroll, color-coded, filterable). Pause/cancel/skip buttons. Non-premium manual download cards with "Open in Browser" button + file watcher.

### 3. Downloads
Table of all archives: name, source type, size, status icon. Sortable, filterable. Retry failed, export list. File watcher indicator.

### 4. Profiles
Cards per installed profile. Game, version, archives, date, disk usage. Switch active. Shared downloads analysis.

### 5. Settings
Paths (folder pickers), Performance (workers, parallel count sliders), Nexus (OAuth button, status badge, API remaining), Advanced (hash verify, cache dir, log level).

### Persistent Elements
Top bar: mini progress bar during install, Nexus status icon, disk space.

## Design System

```css
--bg-primary:     #0f0f13
--bg-secondary:   #1a1a24
--bg-tertiary:    #252532
--border:         #2d2d3d
--text-primary:   #e8e8f0
--text-secondary: #8888a0
--accent:         #e8922a
--accent-glow:    #e8922a40
--success:        #4ade80
--error:          #f87171
--warning:        #fbbf24
```

Cards: bg-secondary, 1px border, 8px radius, accent-glow on hover.
Progress bars: rounded, accent gradient, pulse animation.
Log viewer: monospace, virtual scrolling, color by level.
Gallery banners: 16:9, lazy loaded, zoom on hover.
Game badges: colored pills.
Typography: system fonts for UI, JetBrains Mono for logs/paths.
Animations: Svelte transitions (fly, fade, scale, slide), tweened stores for numbers.

## Nexus Authentication

### Premium (OAuth/SSO)
1. User clicks "Login with Nexus"
2. Backend opens WebSocket to `wss://sso.nexusmods.com`
3. Backend sends `{"id": uuid, "appid": "wabbajack-py"}`
4. Frontend opens `https://www.nexusmods.com/sso?id={uuid}&application=wabbajack-py`
5. User authorizes on Nexus
6. SSO WebSocket receives API key
7. Backend stores in keyring, validates premium, pushes status to frontend

### Non-Premium
1. Installer encounters Nexus file, pushes `manual_needed` via WebSocket
2. Install page shows amber card: mod name, size, "Open in Browser"
3. User clicks, downloads from Nexus in browser to Downloads folder
4. `watchdog` file watcher detects file, pushes `manual_complete`
5. Card turns green, install continues
6. Multiple manual downloads queue simultaneously

### Token Storage
`keyring` library (OS keychain). Fallback: obfuscated file in `.wj-config.json`. Tokens never sent to frontend.

## Packaging

### Build Pipeline
```
npm run build          # Svelte → frontend/dist/
python build.py        # copy dist/ → src/wabbajack/web/static/
pyinstaller wabbajack.spec  # single binary
```

### Windows
- PyInstaller → `wabbajack-py.exe` (~40-60MB)
- Inno Setup → `wabbajack-py-setup.exe` installer
- Start Menu shortcut, desktop icon, PATH entry
- Bundles 7z.exe for extraction

### Linux
- PyInstaller → `wabbajack-py` binary
- AppImage (portable, Steam Deck compatible)
- AUR package for Arch users
- `.desktop` file with icon

### macOS
- PyInstaller → `wabbajack-py.app` bundle
- Homebrew cask from GitHub Releases
- `brew install --cask wabbajack-py`

### GitHub Actions Release
- Tag push triggers parallel builds (Windows/Linux/macOS)
- Uploads to GitHub Release
- Auto-updates Homebrew formula + AUR PKGBUILD

### Launch Behavior
Binary starts uvicorn on `localhost:6969`, opens browser, shows system tray icon (pystray). Tray has "Open UI" and "Quit". Closing browser tab keeps server alive.

## Dependencies

### Backend (added to pyproject.toml)
- `fastapi`
- `uvicorn[standard]`
- `watchdog`
- `keyring`
- `pystray`
- `Pillow`
- `websockets`

### Frontend
- `svelte` 5
- `typescript`
- `vite`
- `@sveltejs/vite-plugin-svelte`

## Scope Boundaries (v1.0)

Building:
- All 5 pages (Gallery, Install, Downloads, Profiles, Settings)
- Real-time WebSocket progress + log streaming
- Nexus SSO + non-premium manual flow
- 3-platform packaging

Not building:
- Multi-user / accounts
- Modlist compilation
- Auto-update
- Mobile responsive
- Electron/Tauri wrapper
