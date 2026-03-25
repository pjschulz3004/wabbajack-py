# wabbajack-py

Cross-platform Wabbajack modlist installer with web GUI. Runs natively on Linux, macOS, and Windows.

**Why?** Wabbajack only runs on Windows. This is a from-scratch Python implementation that handles the same `.wabbajack` modlist files but works everywhere. Built for gamers who mod on Linux/macOS via Proton/Wine.

## Features

- **Full modlist installation** -- downloads, extracts, places 650K+ file directives from `.wabbajack` files
- **9 download sources** -- Nexus, MediaFire, Mega, Google Drive, WabbajackCDN, HTTP, ModDB, game files, manual
- **Web GUI** -- dark gaming-native UI with real-time progress, log viewer, settings, gallery browsing
- **Load order management** -- plugins.txt/modlist.txt for Bethesda games, modsettings.lsx for BG3, REDmod for Cyberpunk, SMAPI for Stardew
- **Nexus OAuth** -- SSO login (premium auto-download) + API key fallback (manual download guidance for free accounts)
- **Multi-profile** -- manage multiple modlist installs with shared downloads
- **Self-updating** -- check for and apply updates from the app or CLI
- **Cross-platform** -- Linux, macOS, Windows. Handles case-insensitive paths, Proton prefixes, Wine BSA creation

## Quick Start

```bash
# Clone and install
git clone https://github.com/pjschulz3004/wabbajack-py.git
cd wabbajack-py
pip install -e ".[all]"

# Launch the web GUI
wabbajack-py serve

# Or use the CLI
wabbajack-py info path/to/modlist.wabbajack
wabbajack-py install path/to/modlist.wabbajack -o ~/Games/MyModlist -d ~/Downloads/WJ -g ~/Games/Skyrim
```

## Installation

### From source (recommended for development)

```bash
git clone https://github.com/pjschulz3004/wabbajack-py.git
cd wabbajack-py
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -e ".[all]"
```

### Dependencies

**Required:** Python 3.10+, click, xxhash, requests

**Optional extras:**
- `pip install -e ".[web]"` -- FastAPI, uvicorn, httpx (for web GUI)
- `pip install -e ".[rich]"` -- Rich terminal output
- `pip install -e ".[bsa]"` -- BSA archive creation (sse-bsa)
- `pip install -e ".[all]"` -- everything

### Build the frontend (for web GUI)

```bash
cd frontend
npm install
npx vite build
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `serve` | Launch web GUI (default: http://localhost:6969) |
| `info <.wabbajack>` | Show modlist info (name, game, archives, directives) |
| `install <.wabbajack>` | Full install with all options |
| `download <.wabbajack>` | Download archives only |
| `verify <.wabbajack>` | Verify archive hashes |
| `status <.wabbajack>` | Show installation progress |
| `load-order <game>` | Show/validate mod load order |
| `profiles` | List modlist profiles |
| `check-update` | Check for new versions |
| `update` | Apply available update |
| `list-games` | Show detected game installations |
| `list-downloads <.wabbajack>` | List archives by source type |

## Web GUI

```bash
wabbajack-py serve --port 6969
```

Opens a browser to the web interface with:
- **Gallery** -- browse Wabbajack modlist catalog
- **Install** -- start/pause/cancel installations with real-time progress
- **Downloads** -- sortable archive table with status (5667+ rows, virtualized)
- **Profiles** -- manage multiple modlist installations
- **Settings** -- paths, workers, Nexus auth, update checker

## Load Order Management

Supports reading, writing, and validating load orders for:

| Game | Format | Features |
|------|--------|----------|
| Skyrim SE/LE | plugins.txt, modlist.txt, loadorder.txt | ESP header reading, master dependency validation, ESL flag detection |
| Fallout 4 | plugins.txt, modlist.txt | Same Bethesda engine support |
| Starfield | plugins.txt, modlist.txt | Same Bethesda engine support |
| Oblivion | plugins.txt, modlist.txt | Same Bethesda engine support |
| Enderal SE | plugins.txt, modlist.txt | Same Bethesda engine support |
| Baldur's Gate 3 | modsettings.lsx | XML parser, Proton prefix auto-detect |
| Cyberpunk 2077 | load_order.txt | REDmod + archive mod detection |
| Stardew Valley | manifest.json | SMAPI dependency graph |

```bash
# Show Skyrim load order
wabbajack-py load-order SkyrimSpecialEdition --validate

# List supported games
wabbajack-py load-order list
```

## Updating

The app can update itself:

```bash
# Check for updates
wabbajack-py check-update

# Apply update (git pull for dev installs, pip upgrade for pip installs)
wabbajack-py update
```

Or use the Settings page in the web GUI.

- **Dev installs:** checks for new git commits, runs `git pull --ff-only` + reinstalls
- **Pip installs:** checks PyPI, runs `pip install --upgrade`
- **Binary installs:** checks GitHub releases, downloads and swaps the binary

## Architecture

```
src/wabbajack/
  installer.py     # Main orchestrator (651K+ directives, parallel extraction)
  modlist.py        # .wabbajack ZIP parser
  loadorder.py      # Load order management (9 games)
  downloaders/      # 9 source handlers (Nexus, Mega, CDN, etc.)
  cache.py          # Archive extraction cache with 7z/unzip
  hash.py           # xxHash64 verification
  profiles.py       # Multi-modlist profile management
  platform.py       # 41-game detection across Steam libraries
  updater.py        # Self-update (git/pip/binary)
  web/              # FastAPI + WebSocket backend
    api.py          # REST endpoints
    ws.py           # Real-time progress streaming
    gallery.py      # Wabbajack modlist catalog
    auth.py         # Nexus SSO + keyring

frontend/src/       # Svelte 5 + TypeScript
  App.svelte        # Sidebar layout, mobile responsive
  routes/           # Gallery, Install, Downloads, Profiles, Settings
  lib/components/   # ProgressBar, LogViewer, ModCard (virtual scrolling)
  lib/stores/       # WebSocket store with auto-reconnect
```

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Run frontend dev server (hot reload)
cd frontend && npm run dev

# Run backend
wabbajack-py serve --port 6969
```

98 unit tests cover: URL validation, archive classification, hash verification, path traversal protection, state persistence, profile management, modlist parsing, web API, WebSocket protocol.

## Supported Games (41)

Bethesda: Morrowind, Oblivion, Oblivion Remastered, Skyrim LE/SE/VR, Enderal/SE, Fallout 3/NV/4/4VR/76/London, Starfield

RPG/Action: Baldur's Gate 3, Cyberpunk 2077, Witcher 3, Dragon's Dogma 1/2, Kingdom Come 1/2, Bannerlord, KOTOR 2, VTM: Bloodlines

Strategy/Sim: Stardew Valley, Terraria, KSP, Valheim, No Man's Sky, Sims 4, 7 Days to Die

Plus: Dragon Age Origins/2/Inquisition/Veilguard, Darkest Dungeon, MechWarrior 5, and more.

## License

MIT
