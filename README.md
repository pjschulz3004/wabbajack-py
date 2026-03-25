# wabbajack-py

Cross-platform Wabbajack modlist installer. Downloads, extracts, and places mod files from `.wabbajack` modlist files on Windows, macOS, and Linux.

## Features

- All download sources: Nexus (Premium), MediaFire, Mega, Google Drive, WabbajackCDN, HTTP, game files
- WabbajackCDN chunked protocol (files that return 404 with direct download)
- Cross-platform game directory auto-detection (Steam on Windows/macOS/Linux)
- Case-insensitive file matching (Linux compatibility)
- Hash verification (xxHash64, warn-only mode -- never blocks)
- Parallel archive extraction
- Resume support (skips already-downloaded files)
- Multi-modlist profile management with shared downloads
- Detailed logging with `--log-file` and `-v`

## Install

```bash
pip install .                    # basic install
pip install ".[gdrive]"          # with Google Drive support (gdown)
```

### System dependencies

- **7z** (p7zip): for extracting archives
- **megadl** (megatools): for Mega.nz downloads (optional)
- **gdown**: for Google Drive downloads (optional, installed with `[gdrive]`)

## Usage

```bash
# Show modlist info
wabbajack-py info modlist.wabbajack

# Download all missing archives
wabbajack-py download modlist.wabbajack -d ./downloads -k NEXUS_API_KEY

# Dry run (show what would be downloaded)
wabbajack-py download modlist.wabbajack -d ./downloads -k KEY --dry-run

# Download only specific types
wabbajack-py download modlist.wabbajack -d ./downloads -k KEY --type mediafire --type gdrive

# Full install
wabbajack-py install modlist.wabbajack -o ./output -d ./downloads -k KEY -j 12

# Install with hash verification and profile registration
wabbajack-py install modlist.wabbajack -o ./output -d ./downloads -k KEY --verify --profile mylist

# Skip downloads (use existing files)
wabbajack-py install modlist.wabbajack -o ./output -d ./downloads --skip-download

# Verbose output + log file
wabbajack-py -v --log-file install.log install modlist.wabbajack -o ./output -d ./downloads -k KEY
```

## Multi-Modlist Profiles

Share a single downloads directory across multiple modlists to avoid re-downloading common mods:

```bash
# Install first modlist
wabbajack-py install first.wabbajack -o ~/Games/FirstList -d ~/Games/Downloads -k KEY --profile first

# Check how much a second modlist can reuse
wabbajack-py shared --new second.wabbajack

# Install second modlist with same downloads dir
wabbajack-py install second.wabbajack -o ~/Games/SecondList -d ~/Games/Downloads -k KEY --profile second

# List profiles and switch
wabbajack-py profiles
wabbajack-py switch first
```

## Hash Verification

By default, hash checking is off for speed. Use `--verify` to enable:

```bash
wabbajack-py download modlist.wabbajack -d ./downloads -k KEY --verify
```

Mismatches are reported as warnings but never block the download. A summary of all mismatches is shown at the end.

## How It Works

1. **Parse**: Reads the `.wabbajack` ZIP (modlist JSON + inline data)
2. **Download**: Fetches missing archives from all sources in order (game files, CDN, MediaFire, Mega, GDrive, Nexus)
3. **Extract**: Parallel extraction with 7z/zipfile into a cache directory
4. **Place**: Copies files from extraction cache to output directory per modlist directives
5. **Patch**: PatchedFromArchive files use base copies (binary patching is WIP)
6. **BSA**: CreateBSA directives are logged to `bsa-todo.txt` (BSA packing is WIP)

## Platform Notes

### Linux
- Case-insensitive file matching handles Windows-style paths automatically
- Use Proton/Wine for MO2 after installation
- Game files detected from `~/.local/share/Steam/`

### Windows
- Native filesystem is case-insensitive (no special handling needed)
- Game files detected from Steam registry and common install paths

### macOS
- Game files detected from `~/Library/Application Support/Steam/`

## License

MIT
