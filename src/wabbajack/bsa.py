"""BSA/BA2 archive creation for Wabbajack's CreateBSA directive.

Supports two backends:
  1. sse-bsa (pip install sse-bsa) -- native Python, Skyrim SE BSA only
  2. BSArch via Wine -- all Bethesda games, requires wine + BSArch.exe

The CreateBSA directive contains:
  - To: destination path (e.g. mods/SomeMod/SomeMod.bsa)
  - TempID: staging directory identifier
  - State: archive type descriptor (BSAState, BA2State, TES3State)
  - FileStates: list of files to include with path and flags
"""
import subprocess, shutil, logging
from pathlib import Path

log = logging.getLogger(__name__)

# Try to import sse-bsa for native BSA creation
try:
    from sse_bsa import BSAArchive
    HAS_SSE_BSA = True
except ImportError:
    HAS_SSE_BSA = False

# Check for BSArch via Wine
_bsarch_path = None


def _find_bsarch():
    """Find BSArch.exe in common locations."""
    global _bsarch_path
    if _bsarch_path is not None:
        return _bsarch_path

    # Check common locations
    candidates = [
        Path.home() / '.local' / 'share' / 'bsarch' / 'BSArch.exe',
        Path.home() / 'BSArch.exe',
        Path('/usr/local/bin/BSArch.exe'),
        Path('/opt/bsarch/BSArch.exe'),
    ]
    # Also check PATH
    for p in candidates:
        if p.exists():
            _bsarch_path = p
            return p

    # Check if bsarch wrapper script exists
    bsarch = shutil.which('bsarch')
    if bsarch:
        _bsarch_path = Path(bsarch)
        return _bsarch_path

    _bsarch_path = False  # Mark as not found (don't re-search)
    return None


def _detect_game_flag(state):
    """Map Wabbajack BSA State type to BSArch game flag."""
    state_type = state.get('$type', '')
    if 'BA2State' in state_type:
        return '-fo4'
    if 'TES3State' in state_type:
        return '-tes3'
    # BSAState -- detect game from version
    version = state.get('Version', 105)
    if version == 103:
        return '-tes4'  # Oblivion
    if version == 104:
        return '-tes5'  # Skyrim LE / FO3 / FNV
    if version == 105:
        return '-sse'   # Skyrim SE/AE
    return '-sse'  # Default


def create_bsa_native(staging_dir, output_path, state):
    """Create BSA using sse-bsa (Skyrim SE only)."""
    if not HAS_SSE_BSA:
        return False

    state_type = state.get('$type', '')
    if 'BA2State' in state_type or 'TES3State' in state_type:
        return False  # sse-bsa only handles SSE BSA

    version = state.get('Version', 105)
    if version != 105:
        return False  # sse-bsa only handles version 105

    try:
        staging = Path(staging_dir)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        BSAArchive.create_archive(staging, output)
        if output.exists() and output.stat().st_size > 0:
            log.info(f"    Created BSA (sse-bsa): {output.name} ({output.stat().st_size/1048576:.1f} MB)")
            return True
        return False
    except Exception as e:
        log.warning(f"    sse-bsa failed: {type(e).__name__}: {e}")
        return False


def create_bsa_bsarch(staging_dir, output_path, state):
    """Create BSA/BA2 using BSArch via Wine."""
    bsarch = _find_bsarch()
    if not bsarch:
        return False

    game_flag = _detect_game_flag(state)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Validate game_flag (whitelist only)
    valid_flags = {'-tes3', '-tes4', '-fo3', '-fnv', '-tes5', '-sse', '-fo4', '-sf1'}
    if game_flag not in valid_flags:
        log.warning(f"    Invalid game flag: {game_flag}")
        return False

    # Build command -- all args are Path objects or whitelisted flags, safe from injection
    cmd = []
    bsarch_str = str(bsarch)
    if bsarch_str.endswith('.exe'):
        cmd = ['wine', bsarch_str]
    else:
        cmd = [bsarch_str]

    cmd.extend(['pack', str(staging_dir), str(output), game_flag, '-z', '-mt'])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0 and output.exists() and output.stat().st_size > 0:
            log.info(f"    Created BSA (BSArch): {output.name} ({output.stat().st_size/1048576:.1f} MB)")
            return True
        else:
            err = result.stderr[:200] if result.stderr else result.stdout[:200]
            log.warning(f"    BSArch failed (exit {result.returncode}): {err}")
            return False
    except FileNotFoundError:
        log.debug("    wine or BSArch not found")
        return False
    except subprocess.TimeoutExpired:
        log.warning(f"    BSArch timed out for {output.name}")
        return False
    except Exception as e:
        log.warning(f"    BSArch error: {type(e).__name__}: {e}")
        return False


def create_bsa(staging_dir, output_path, state):
    """Create a BSA/BA2 archive using the best available backend.

    Tries sse-bsa (native Python) first, falls back to BSArch via Wine.
    Returns True on success.
    """
    # Try native Python first (fast, no Wine dependency)
    if create_bsa_native(staging_dir, output_path, state):
        return True

    # Fallback to BSArch via Wine
    if create_bsa_bsarch(staging_dir, output_path, state):
        return True

    log.warning(f"    No BSA backend available for {Path(output_path).name}")
    log.warning(f"    Install sse-bsa (pip install sse-bsa) or BSArch.exe + Wine")
    return False


def stage_bsa_files(directive, _archive_cache, output_dir, cache_dir):
    """Stage files for BSA creation from a CreateBSA directive.

    Returns (staging_dir, file_count) or (None, 0) if staging fails.
    """
    temp_id = directive.get('TempID', '')
    file_states = directive.get('FileStates', [])
    dest_name = directive.get('To', 'unknown.bsa')

    if not file_states:
        return None, 0

    # Create staging directory
    staging = Path(cache_dir) / f'_bsa_staging' / (temp_id or dest_name.replace('/', '_'))
    staging.mkdir(parents=True, exist_ok=True)

    staged = 0
    # The files should already be placed in the output directory under TEMP_BSA_FILES/
    # by the FromArchive directives. We look for them there.
    temp_bsa_dir = Path(output_dir) / 'TEMP_BSA_FILES' / temp_id

    if temp_bsa_dir.exists():
        # Files already staged by FromArchive directives
        return str(temp_bsa_dir), len(file_states)

    # Fallback: try to find files by their paths in the output directory
    for fs in file_states:
        file_path = fs.get('Path', '')
        if not file_path:
            continue
        # Look in output directory
        src = Path(output_dir) / file_path.replace('\\', '/')
        if src.exists():
            dest = staging / file_path.replace('\\', '/')
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copyfile(src, dest)
                staged += 1
            except OSError:
                pass

    if staged > 0:
        return str(staging), staged
    return None, 0
