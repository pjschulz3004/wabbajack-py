"""Cross-platform game directory detection and path utilities."""
import os, sys, logging
from pathlib import Path

log = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')

# Game type -> (Windows paths, macOS paths, Linux paths)
# Windows paths are relative to each Steam library
GAME_DIRS = {
    # Bethesda
    'Morrowind':              {'steam_subdir': 'Morrowind',                   'display': 'Morrowind'},
    'Oblivion':               {'steam_subdir': 'Oblivion',                    'display': 'Oblivion'},
    'OblivionRemastered':     {'steam_subdir': 'Oblivion Remastered',         'display': 'Oblivion Remastered'},
    'Skyrim':                 {'steam_subdir': 'Skyrim',                      'display': 'Skyrim (LE)'},
    'SkyrimSpecialEdition':   {'steam_subdir': 'Skyrim Special Edition',      'display': 'Skyrim Special Edition'},
    'SkyrimVR':               {'steam_subdir': 'SkyrimVR',                    'display': 'Skyrim VR'},
    'Enderal':                {'steam_subdir': 'Enderal',                     'display': 'Enderal'},
    'EnderalSpecialEdition':  {'steam_subdir': 'Enderal Special Edition',     'display': 'Enderal SE'},
    'Fallout3':               {'steam_subdir': 'Fallout 3',                   'display': 'Fallout 3'},
    'FalloutNewVegas':        {'steam_subdir': 'Fallout New Vegas',           'display': 'Fallout: New Vegas'},
    'Fallout4':               {'steam_subdir': 'Fallout 4',                   'display': 'Fallout 4'},
    'Fallout4VR':             {'steam_subdir': 'Fallout 4 VR',               'display': 'Fallout 4 VR'},
    'Fallout4London':         {'steam_subdir': 'Fallout London',              'display': 'Fallout 4: London'},
    'Fallout76':              {'steam_subdir': 'Fallout 76',                  'display': 'Fallout 76'},
    'Starfield':              {'steam_subdir': 'Starfield',                   'display': 'Starfield'},
    # RPG/Action
    'BaldursGate3':           {'steam_subdir': 'Baldurs Gate 3',              'display': "Baldur's Gate 3"},
    'Cyberpunk2077':          {'steam_subdir': 'Cyberpunk 2077',              'display': 'Cyberpunk 2077'},
    'Witcher3':               {'steam_subdir': 'The Witcher 3 Wild Hunt',     'display': 'The Witcher 3'},
    'DragonsDogma':           {'steam_subdir': "Dragon's Dogma Dark Arisen",  'display': "Dragon's Dogma"},
    'DragonsDogma2':          {'steam_subdir': "Dragon's Dogma 2",            'display': "Dragon's Dogma 2"},
    'KingdomComeDeliverance': {'steam_subdir': 'KingdomComeDeliverance',      'display': 'Kingdom Come: Deliverance'},
    'KingdomComeDeliverance2': {'steam_subdir': 'KingdomComeDeliverance2',    'display': 'Kingdom Come: Deliverance 2'},
    'Bannerlord':             {'steam_subdir': 'Mount & Blade II Bannerlord', 'display': 'Bannerlord'},
    'KOTOR2':                 {'steam_subdir': 'Knights of the Old Republic II', 'display': 'KOTOR 2'},
    'VTMB':                   {'steam_subdir': 'Vampire The Masquerade - Bloodlines', 'display': 'VTM: Bloodlines'},
    # Strategy/Sim
    'StardewValley':          {'steam_subdir': 'Stardew Valley',              'display': 'Stardew Valley'},
    'Terraria':               {'steam_subdir': 'Terraria',                    'display': 'Terraria'},
    'KerbalSpaceProgram':     {'steam_subdir': 'Kerbal Space Program',        'display': 'KSP'},
    'Valheim':                {'steam_subdir': 'Valheim',                     'display': 'Valheim'},
    'NoMansSky':              {'steam_subdir': "No Man's Sky",                'display': "No Man's Sky"},
    'Sims4':                  {'steam_subdir': 'The Sims 4',                  'display': 'The Sims 4'},
    '7DaysToDie':             {'steam_subdir': '7 Days To Die',               'display': '7 Days to Die'},
    # BioWare
    'DragonAgeOrigins':       {'steam_subdir': 'Dragon Age Origins',          'display': 'Dragon Age: Origins'},
    'DragonAge2':             {'steam_subdir': 'Dragon Age II',               'display': 'Dragon Age II'},
    'DragonAgeInquisition':   {'steam_subdir': 'Dragon Age Inquisition',      'display': 'Dragon Age: Inquisition'},
    # Stealth/Action
    'DarkestDungeon':         {'steam_subdir': 'DarkestDungeon',              'display': 'Darkest Dungeon'},
    'Dishonored':             {'steam_subdir': 'Dishonored',                  'display': 'Dishonored'},
    'MechWarrior5Mercenaries': {'steam_subdir': 'MechWarrior 5 Mercenaries',  'display': 'MechWarrior 5'},
    'FF7Remake':              {'steam_subdir': 'FINAL FANTASY VII REMAKE',    'display': 'FF7 Remake'},
    'Warhammer40kDarktide':   {'steam_subdir': 'Warhammer 40000 Darktide',    'display': 'Darktide'},
    'KarrynsPrison':          {'steam_subdir': "Karryn's Prison",             'display': "Karryn's Prison"},
}


def find_steam_libraries():
    """Find all Steam library directories on this system."""
    libraries = []

    if IS_WINDOWS:
        # Check registry for Steam install path
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam")
            steam_path = Path(winreg.QueryValueEx(key, "InstallPath")[0])
            winreg.CloseKey(key)
            libraries.append(steam_path / "steamapps" / "common")
        except (OSError, ImportError):
            pass
        # Common default locations
        for drive in ['C:', 'D:', 'E:', 'F:']:
            for steam_dir in ['Program Files (x86)/Steam', 'Program Files/Steam', 'Steam', 'SteamLibrary']:
                p = Path(f"{drive}/{steam_dir}/steamapps/common")
                if p.exists() and p not in libraries:
                    libraries.append(p)
        # Parse libraryfolders.vdf for additional libraries
        for lib in list(libraries):
            vdf = lib.parent / "libraryfolders.vdf"
            if vdf.exists():
                libraries.extend(_parse_library_folders(vdf))

    elif IS_MACOS:
        default = Path.home() / "Library/Application Support/Steam/steamapps/common"
        if default.exists():
            libraries.append(default)

    elif IS_LINUX:
        # Standard locations
        for base in [
            Path.home() / ".local/share/Steam",
            Path.home() / ".steam/steam",
            Path.home() / ".steam/debian-installation",
            Path("/usr/share/steam"),
        ]:
            common = base / "steamapps" / "common"
            if common.exists() and common not in libraries:
                libraries.append(common)
            # Parse libraryfolders.vdf for additional Steam libraries
            vdf = base / "steamapps" / "libraryfolders.vdf"
            if vdf.exists():
                libraries.extend(_parse_library_folders(vdf))
        # Flatpak Steam
        flatpak_base = Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam"
        flatpak_common = flatpak_base / "steamapps" / "common"
        if flatpak_common.exists():
            libraries.append(flatpak_common)
        flatpak_vdf = flatpak_base / "steamapps" / "libraryfolders.vdf"
        if flatpak_vdf.exists():
            libraries.extend(_parse_library_folders(flatpak_vdf))

    # Deduplicate (resolve symlinks)
    seen = set()
    unique = []
    for lib in libraries:
        try:
            resolved = lib.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique.append(lib)
        except OSError:
            unique.append(lib)
    return unique


def _parse_library_folders(vdf_path):
    """Parse Steam's libraryfolders.vdf to find additional library paths."""
    import re
    extra = []
    try:
        text = vdf_path.read_text(encoding='utf-8', errors='replace')
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            p = Path(match.group(1)) / "steamapps" / "common"
            if p.exists():
                extra.append(p)
    except OSError:
        pass
    return extra


def detect_game_dir(game_type):
    """Auto-detect the game installation directory.

    Returns the path if found, None otherwise.
    """
    info = GAME_DIRS.get(game_type)
    if not info:
        # Fallback: try the game type name directly as a subdirectory
        info = {'steam_subdir': game_type, 'display': game_type}

    libraries = find_steam_libraries()
    log.debug(f"Found {len(libraries)} Steam libraries: {libraries}")

    for lib in libraries:
        game_path = lib / info['steam_subdir']
        if game_path.exists():
            log.info(f"Found {info['display']}: {game_path}")
            return game_path

    log.warning(f"Could not auto-detect {info['display']}. Use -g to specify the path.")
    return None


def normalize_path(path_str):
    """Normalize a Windows-style path for the current OS.

    Converts backslashes to forward slashes and returns a Path object.
    """
    return Path(path_str.replace('\\', '/'))
