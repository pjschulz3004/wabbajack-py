# wabbajack-py

Cross-platform Wabbajack modlist installer. Downloads, extracts, and places mod files from `.wabbajack` modlist files on Windows, macOS, and Linux.

## Features

- **8 download sources**: Nexus (Premium), MediaFire, Mega, Google Drive, ModDB, WabbajackCDN, HTTP, game files
- **Parallel everything**: downloads (4 threads), extraction (12 workers), file placement (ThreadPoolExecutor)
- **Resume support**: interrupted downloads resume from where they left off (.part files)
- **Connection pooling**: HTTP keep-alive via requests.Session (20-connection pool)
- **41 supported games**: all Wabbajack-supported titles auto-detected via Steam
- **Cross-platform**: Windows, macOS, Linux with case-insensitive file matching
- **Hash verification**: xxHash64 warn-only mode (never blocks)
- **MO2 integration**: portable.txt, ModOrganizer.ini remapping, .meta files, path magic replacement
- **Optimized re-install**: skips already-correct files based on size
- **Multi-modlist profiles**: shared downloads across modlists
- **10 CLI commands**: info, install, download, verify, status, list-games, hash-file, extract, list-downloads, profiles

## Install

```bash
pip install .                    # basic install
pip install ".[gdrive]"          # with Google Drive support (gdown)
```

### System dependencies

- **7z** (p7zip): for extracting archives
- **megadl** (megatools): for Mega.nz downloads (optional)
- **gdown**: for Google Drive downloads (optional, installed with `[gdrive]`)

## Quick Start

```bash
# Check modlist contents
wabbajack-py info modlist.wabbajack

# Check what games are installed
wabbajack-py list-games

# See download status
wabbajack-py status modlist.wabbajack -d ./downloads

# Full install
export NEXUS_API_KEY=your_key_here
wabbajack-py install modlist.wabbajack -o ./output -d ./downloads -j 12
```

## CLI Commands

```bash
# Modlist info
wabbajack-py info modlist.wabbajack

# Full install (download + extract + place)
wabbajack-py install modlist.wabbajack -o ./output -d ./downloads -j 12

# Download only (no install)
wabbajack-py download modlist.wabbajack -d ./downloads

# Download specific types only
wabbajack-py download modlist.wabbajack -d ./downloads --type mediafire --type gdrive

# Verify archive hashes
wabbajack-py verify modlist.wabbajack -d ./downloads

# Installation status
wabbajack-py status modlist.wabbajack -d ./downloads -o ./output

# List archives by type
wabbajack-py list-downloads modlist.wabbajack -d ./downloads

# Detect installed games
wabbajack-py list-games

# Hash a single file
wabbajack-py hash-file somefile.7z

# Extract inline data from .wabbajack
wabbajack-py extract modlist.wabbajack -o ./inline-data

# Skip downloads (use existing files)
wabbajack-py install modlist.wabbajack -o ./output -d ./downloads --skip-download

# Verbose + log file
wabbajack-py -v --log-file install.log install modlist.wabbajack -o ./output -d ./downloads
```

## Multi-Modlist Profiles

Share a single downloads directory across multiple modlists:

```bash
# Install first modlist with profile
wabbajack-py install first.wabbajack -o ~/Games/FirstList -d ~/Games/Downloads --profile first

# Check reuse potential for second modlist
wabbajack-py shared --new second.wabbajack

# Install second modlist (shared downloads)
wabbajack-py install second.wabbajack -o ~/Games/SecondList -d ~/Games/Downloads --profile second

# Switch between profiles
wabbajack-py profiles
wabbajack-py switch first
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `NEXUS_API_KEY` | Nexus Mods API key (Premium required for auto-download) |

## How It Works

1. **Parse**: Reads the `.wabbajack` ZIP (modlist JSON with archives + directives)
2. **Download**: Parallel fetches from all sources (game files, CDN, HTTP, MediaFire, Mega, GDrive, ModDB, Nexus)
3. **Extract**: Parallel extraction into cache using 7z/zipfile
4. **Place**: Parallel file placement per directives with size-check skip
5. **Remap**: RemappedInlineFile path magic replaced with actual paths
6. **MO2 Setup**: portable.txt, INI remapping, .meta files, standard dirs
7. **Patch**: PatchedFromArchive uses base copies (binary patching WIP)
8. **BSA**: CreateBSA logged to bsa-todo.txt (BSA packing WIP)

## Known Limitations

- **Binary patching**: PatchedFromArchive copies base file, doesn't apply OctoDiff delta
- **BSA/BA2 creation**: CreateBSA directives need a BSA packing library
- **LoversLab/VectorPlexus**: IPS4 OAuth2 downloaders not implemented
- **Texture transforms**: TransformedTexture (DDS recompression) not implemented
- **Modlist compilation**: Install-only (no MO2 -> .wabbajack export)

## Platform Notes

### Linux
- Case-insensitive file matching handles Windows paths automatically
- Use Proton/Wine for MO2 after installation
- Games detected from `~/.local/share/Steam/` and Flatpak paths

### Windows
- Native case-insensitive filesystem
- Games detected from Steam registry and common install paths

### macOS
- Games detected from `~/Library/Application Support/Steam/`

## License

MIT
