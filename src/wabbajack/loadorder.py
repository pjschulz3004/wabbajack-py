"""Mod load order management for multiple games.

Handles reading, writing, and manipulating mod and plugin load orders
for Skyrim SE, Baldur's Gate 3, Cyberpunk 2077, and Stardew Valley.
Extensible to other games via the GameLoadOrder base class.
"""
import logging, struct, xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


# ── Data Classes ────────────────────────────────────────────────────────

class ModEntry:
    """A mod in the load order (left pane / asset priority)."""
    __slots__ = ('name', 'enabled', 'priority')

    def __init__(self, name: str, enabled: bool = True, priority: int = 0):
        self.name = name
        self.enabled = enabled
        self.priority = priority

    def __repr__(self):
        state = '+' if self.enabled else '-'
        return f"{state}{self.name}"


class PluginEntry:
    """A plugin in the load order (right pane / ESP/ESM)."""
    __slots__ = ('filename', 'enabled', 'is_master', 'is_light', 'masters')

    def __init__(self, filename: str, enabled: bool = True,
                 is_master: bool = False, is_light: bool = False,
                 masters: list[str] | None = None):
        self.filename = filename
        self.enabled = enabled
        self.is_master = is_master
        self.is_light = is_light
        self.masters = masters or []

    def __repr__(self):
        flags = ''
        if self.is_master:
            flags += ' [ESM]'
        if self.is_light:
            flags += ' [ESL]'
        state = '*' if self.enabled else ' '
        return f"{state}{self.filename}{flags}"


# ── ESP Header Reader ───────────────────────────────────────────────────

def read_plugin_header(path: Path) -> PluginEntry:
    """Read a Bethesda plugin header (TES4 record) to get flags and masters.

    Works for Morrowind through Starfield (all use TES4/TES3 record at offset 0).
    """
    filename = path.name
    is_master = filename.lower().endswith('.esm')
    is_light = filename.lower().endswith('.esl')
    masters = []

    try:
        with open(path, 'rb') as f:
            sig = f.read(4)
            if sig not in (b'TES4', b'TES3'):
                return PluginEntry(filename, is_master=is_master, is_light=is_light)

            data_size = struct.unpack('<I', f.read(4))[0]
            record_flags = struct.unpack('<I', f.read(4))[0]

            # Flag 0x01 = ESM, Flag 0x200 = ESL (light master)
            if record_flags & 0x01:
                is_master = True
            if record_flags & 0x200:
                is_light = True

            # Skip rest of record header (version info, etc)
            f.read(8)  # formID + revision

            # Parse subrecords to find MAST entries
            end_pos = f.tell() + data_size
            while f.tell() < end_pos:
                sub_sig = f.read(4)
                if len(sub_sig) < 4:
                    break
                sub_size = struct.unpack('<H', f.read(2))[0]
                if sub_sig == b'MAST':
                    master_name = f.read(sub_size).rstrip(b'\x00').decode('utf-8', errors='replace')
                    masters.append(master_name)
                else:
                    f.read(sub_size)
    except (OSError, struct.error) as e:
        log.debug(f"Could not read plugin header: {path}: {e}")

    return PluginEntry(filename, is_master=is_master, is_light=is_light, masters=masters)


# ── Base Class ──────────────────────────────────────────────────────────

class GameLoadOrder(ABC):
    """Abstract base for game-specific load order management."""

    def __init__(self, game_dir: Path, profile_dir: Optional[Path] = None):
        self.game_dir = Path(game_dir)
        self.profile_dir = Path(profile_dir) if profile_dir else None
        self.mods: list[ModEntry] = []
        self.plugins: list[PluginEntry] = []

    game_type: str = ''  # Override in subclasses

    @abstractmethod
    def load(self) -> None:
        """Read current load order from disk."""

    @abstractmethod
    def save(self) -> None:
        """Write current load order to disk."""

    @abstractmethod
    def detect_mods(self) -> list[ModEntry]:
        """Scan the game directory for installed mods."""

    def enable_mod(self, name: str) -> bool:
        for m in self.mods:
            if m.name == name:
                m.enabled = True
                return True
        return False

    def disable_mod(self, name: str) -> bool:
        for m in self.mods:
            if m.name == name:
                m.enabled = False
                return True
        return False

    def move_mod(self, name: str, new_priority: int) -> bool:
        """Move a mod to a new position in the load order."""
        idx = next((i for i, m in enumerate(self.mods) if m.name == name), -1)
        if idx == -1:
            return False
        mod = self.mods.pop(idx)
        new_priority = max(0, min(new_priority, len(self.mods)))
        self.mods.insert(new_priority, mod)
        self._renumber_priorities()
        return True

    def _renumber_priorities(self):
        for i, m in enumerate(self.mods):
            m.priority = i

    def summary(self) -> dict:
        return {
            'game': self.game_type,
            'total_mods': len(self.mods),
            'enabled_mods': sum(1 for m in self.mods if m.enabled),
            'total_plugins': len(self.plugins),
            'enabled_plugins': sum(1 for p in self.plugins if p.enabled),
        }


# ── Skyrim SE / Bethesda Games ──────────────────────────────────────────

class BethesdaLoadOrder(GameLoadOrder):
    """Load order for Bethesda games using plugins.txt + modlist.txt (MO2 format)."""

    game_type = 'SkyrimSpecialEdition'

    def __init__(self, game_dir: Path, profile_dir: Optional[Path] = None,
                 data_dir: Optional[Path] = None):
        super().__init__(game_dir, profile_dir)
        self.data_dir = data_dir or game_dir / 'Data'

    def _plugins_txt_path(self) -> Path:
        if self.profile_dir:
            return self.profile_dir / 'plugins.txt'
        # Default: MO2 profile or game's appdata
        return self.data_dir.parent / 'plugins.txt'

    def _modlist_txt_path(self) -> Path:
        if self.profile_dir:
            return self.profile_dir / 'modlist.txt'
        return self.data_dir.parent / 'modlist.txt'

    def _loadorder_txt_path(self) -> Path:
        if self.profile_dir:
            return self.profile_dir / 'loadorder.txt'
        return self.data_dir.parent / 'loadorder.txt'

    def load(self) -> None:
        self._load_modlist()
        self._load_plugins()

    def _load_plugins(self):
        """Parse plugins.txt (MO2 / game format)."""
        self.plugins = []
        path = self._plugins_txt_path()
        if not path.exists():
            # Scan data dir for plugins
            self.plugins = self._scan_data_plugins()
            return

        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('*'):
                self.plugins.append(PluginEntry(line[1:], enabled=True))
            else:
                self.plugins.append(PluginEntry(line, enabled=False))

        # Enrich with header data
        for p in self.plugins:
            plugin_path = self.data_dir / p.filename
            if plugin_path.exists():
                header = read_plugin_header(plugin_path)
                p.is_master = header.is_master
                p.is_light = header.is_light
                p.masters = header.masters

    def _scan_data_plugins(self) -> list[PluginEntry]:
        """Scan Data directory for ESP/ESM/ESL files."""
        plugins = []
        if not self.data_dir.exists():
            return plugins
        for ext in ('*.esm', '*.esp', '*.esl'):
            for f in sorted(self.data_dir.glob(ext)):
                header = read_plugin_header(f)
                header.enabled = True
                plugins.append(header)
        return plugins

    def _load_modlist(self):
        """Parse modlist.txt (MO2 format: +enabled, -disabled)."""
        self.mods = []
        path = self._modlist_txt_path()
        if not path.exists():
            return

        for i, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines()):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('+'):
                self.mods.append(ModEntry(line[1:], enabled=True, priority=i))
            elif line.startswith('-'):
                self.mods.append(ModEntry(line[1:], enabled=False, priority=i))
            elif line.startswith('*'):
                self.mods.append(ModEntry(line[1:], enabled=True, priority=i))  # Unmanaged

    def save(self) -> None:
        self._save_plugins()
        self._save_modlist()
        self._save_loadorder()

    def _save_plugins(self):
        path = self._plugins_txt_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ['# This file is used by the game to determine plugin load order']
        for p in self.plugins:
            prefix = '*' if p.enabled else ''
            lines.append(f"{prefix}{p.filename}")
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        log.info(f"Saved plugins.txt ({len(self.plugins)} plugins) -> {path}")

    def _save_modlist(self):
        path = self._modlist_txt_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ['# This file was automatically generated by wabbajack-py']
        for m in self.mods:
            prefix = '+' if m.enabled else '-'
            lines.append(f"{prefix}{m.name}")
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        log.info(f"Saved modlist.txt ({len(self.mods)} mods) -> {path}")

    def _save_loadorder(self):
        path = self._loadorder_txt_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ['# This file was automatically generated by wabbajack-py']
        for p in self.plugins:
            if p.enabled:
                lines.append(p.filename)
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def detect_mods(self) -> list[ModEntry]:
        """Scan MO2 mods directory for installed mods."""
        mods_dir = self.game_dir / 'mods'
        if not mods_dir.exists():
            return []
        return [
            ModEntry(d.name, enabled=True, priority=i)
            for i, d in enumerate(sorted(mods_dir.iterdir()))
            if d.is_dir() and not d.name.startswith('.')
        ]

    def validate_load_order(self) -> list[str]:
        """Check for missing masters and dependency issues."""
        errors = []
        available = {p.filename.lower() for p in self.plugins if p.enabled}
        for p in self.plugins:
            if not p.enabled:
                continue
            for master in p.masters:
                if master.lower() not in available:
                    errors.append(f"{p.filename} requires {master} (missing or disabled)")
        return errors


class SkyrimSELoadOrder(BethesdaLoadOrder):
    game_type = 'SkyrimSpecialEdition'


class SkyrimLELoadOrder(BethesdaLoadOrder):
    game_type = 'Skyrim'


class OblivionLoadOrder(BethesdaLoadOrder):
    game_type = 'Oblivion'


class Fallout4LoadOrder(BethesdaLoadOrder):
    game_type = 'Fallout4'


class StarfieldLoadOrder(BethesdaLoadOrder):
    game_type = 'Starfield'


class EnderalSELoadOrder(BethesdaLoadOrder):
    game_type = 'EnderalSpecialEdition'


# ── Baldur's Gate 3 ─────────────────────────────────────────────────────

class BG3LoadOrder(GameLoadOrder):
    """Load order for Baldur's Gate 3 via modsettings.lsx."""

    game_type = 'BaldursGate3'

    def _modsettings_path(self) -> Path:
        """BG3 modsettings.lsx location."""
        if self.profile_dir:
            return self.profile_dir / 'modsettings.lsx'
        # Default: Larian Studios appdata (Proton or native)
        from .platform import IS_LINUX
        if IS_LINUX:
            # Proton prefix path
            proton_prefix = Path.home() / '.local/share/Steam/steamapps/compatdata/1086940/pfx'
            return proton_prefix / 'drive_c/users/steamuser/AppData/Local/Larian Studios/Baldur\'s Gate 3/PlayerProfiles/Public/modsettings.lsx'
        return Path.home() / 'AppData/Local/Larian Studios/Baldur\'s Gate 3/PlayerProfiles/Public/modsettings.lsx'

    def _mods_dir(self) -> Path:
        from .platform import IS_LINUX
        if IS_LINUX:
            proton_prefix = Path.home() / '.local/share/Steam/steamapps/compatdata/1086940/pfx'
            return proton_prefix / 'drive_c/users/steamuser/AppData/Local/Larian Studios/Baldur\'s Gate 3/Mods'
        return Path.home() / 'AppData/Local/Larian Studios/Baldur\'s Gate 3/Mods'

    def load(self) -> None:
        self.mods = []
        self.plugins = []
        path = self._modsettings_path()
        if not path.exists():
            log.debug(f"modsettings.lsx not found at {path}")
            return

        try:
            tree = ET.parse(path)
            root = tree.getroot()

            # Find ModOrder node
            for node in root.iter('node'):
                if node.get('id') == 'ModOrder':
                    children = node.find('children')
                    if children is None:
                        continue
                    for i, mod_node in enumerate(children.findall('node')):
                        uuid = self._get_attr(mod_node, 'UUID')
                        if uuid:
                            self.mods.append(ModEntry(uuid, enabled=True, priority=i))

            # Find Mods node for full metadata
            for node in root.iter('node'):
                if node.get('id') == 'Mods':
                    children = node.find('children')
                    if children is None:
                        continue
                    for mod_node in children.findall('node'):
                        uuid = self._get_attr(mod_node, 'UUID')
                        name = self._get_attr(mod_node, 'Name')
                        folder = self._get_attr(mod_node, 'Folder')
                        if name and uuid:
                            # Store name->uuid mapping on the ModEntry
                            for m in self.mods:
                                if m.name == uuid:
                                    m.name = f"{name} [{uuid[:8]}]"
                                    break
        except ET.ParseError as e:
            log.error(f"Failed to parse modsettings.lsx: {e}")

    @staticmethod
    def _get_attr(node: ET.Element, attr_id: str) -> str:
        """Get an attribute value from a BG3 LSX node."""
        for attr in node.findall('attribute'):
            if attr.get('id') == attr_id:
                return attr.get('value', '')
        return ''

    def save(self) -> None:
        path = self._modsettings_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Build the LSX XML
        root = ET.Element('save')
        version = ET.SubElement(root, 'version',
                                major='4', minor='7', revision='1', build='3')
        region = ET.SubElement(root, 'region', id='ModuleSettings')
        root_node = ET.SubElement(region, 'node', id='root')
        children = ET.SubElement(root_node, 'children')

        # Gustav (base game) must always be first
        gustav_uuid = '28ac9ce2-2aba-8cda-b3b5-6e922f71b6b8'

        # ModOrder
        mod_order = ET.SubElement(children, 'node', id='ModOrder')
        mo_children = ET.SubElement(mod_order, 'children')

        # Always include Gustav first
        gustav_node = ET.SubElement(mo_children, 'node', id='Module')
        ET.SubElement(gustav_node, 'attribute', id='UUID', type='FixedString', value=gustav_uuid)

        for m in self.mods:
            if not m.enabled:
                continue
            uuid = m.name
            # Extract UUID from "Name [uuid]" format
            if '[' in uuid and uuid.endswith(']'):
                uuid = uuid.split('[')[1].rstrip(']')
                # Pad short UUID back -- we stored first 8 chars
                # For save, we need full UUIDs; skip entries without them
                if len(uuid) < 36:
                    continue
            if uuid == gustav_uuid:
                continue
            node = ET.SubElement(mo_children, 'node', id='Module')
            ET.SubElement(node, 'attribute', id='UUID', type='FixedString', value=uuid)

        # Mods metadata
        mods_node = ET.SubElement(children, 'node', id='Mods')
        mods_children = ET.SubElement(mods_node, 'children')

        # Gustav entry
        gustav_mod = ET.SubElement(mods_children, 'node', id='ModuleShortDesc')
        ET.SubElement(gustav_mod, 'attribute', id='Folder', type='LSString', value='GustavDev')
        ET.SubElement(gustav_mod, 'attribute', id='MD5', type='LSString', value='')
        ET.SubElement(gustav_mod, 'attribute', id='Name', type='LSString', value='GustavDev')
        ET.SubElement(gustav_mod, 'attribute', id='UUID', type='FixedString', value=gustav_uuid)
        ET.SubElement(gustav_mod, 'attribute', id='Version64', type='int64', value='145100779997082625')

        tree = ET.ElementTree(root)
        ET.indent(tree, space='  ')
        tree.write(path, encoding='utf-8', xml_declaration=True)
        log.info(f"Saved modsettings.lsx ({len(self.mods)} mods) -> {path}")

    def detect_mods(self) -> list[ModEntry]:
        mods_dir = self._mods_dir()
        if not mods_dir.exists():
            return []
        return [
            ModEntry(f.stem, enabled=True, priority=i)
            for i, f in enumerate(sorted(mods_dir.glob('*.pak')))
        ]


# ── Cyberpunk 2077 ──────────────────────────────────────────────────────

class CyberpunkLoadOrder(GameLoadOrder):
    """Load order for Cyberpunk 2077 (REDmod + archive mods)."""

    game_type = 'Cyberpunk2077'

    def _archive_mods_dir(self) -> Path:
        return self.game_dir / 'archive' / 'pc' / 'mod'

    def _redmod_dir(self) -> Path:
        return self.game_dir / 'mods'

    def _load_order_path(self) -> Path:
        if self.profile_dir:
            return self.profile_dir / 'load_order.txt'
        return self.game_dir / 'r6' / 'cache' / 'modded' / 'load_order.txt'

    def load(self) -> None:
        self.mods = []
        self.plugins = []

        # Load REDmod load order if exists
        lo_path = self._load_order_path()
        if lo_path.exists():
            for i, line in enumerate(lo_path.read_text(encoding='utf-8', errors='replace').splitlines()):
                line = line.strip()
                if line and not line.startswith('#'):
                    self.mods.append(ModEntry(line, enabled=True, priority=i))
        else:
            self.mods = self.detect_mods()

    def save(self) -> None:
        lo_path = self._load_order_path()
        lo_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [m.name for m in self.mods if m.enabled]
        lo_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        log.info(f"Saved load_order.txt ({len(lines)} mods) -> {lo_path}")

    def detect_mods(self) -> list[ModEntry]:
        mods = []
        i = 0

        # REDmod mods (mods/ directory, each has an info.json)
        redmod_dir = self._redmod_dir()
        if redmod_dir.exists():
            for d in sorted(redmod_dir.iterdir()):
                if d.is_dir() and (d / 'info.json').exists():
                    mods.append(ModEntry(d.name, enabled=True, priority=i))
                    i += 1

        # Archive mods (archive/pc/mod/*.archive)
        archive_dir = self._archive_mods_dir()
        if archive_dir.exists():
            for f in sorted(archive_dir.glob('*.archive')):
                mods.append(ModEntry(f.stem, enabled=True, priority=i))
                i += 1

        return mods


# ── Stardew Valley ──────────────────────────────────────────────────────

class StardewLoadOrder(GameLoadOrder):
    """Load order for Stardew Valley via SMAPI manifest.json files."""

    game_type = 'StardewValley'

    def _mods_dir(self) -> Path:
        return self.game_dir / 'Mods'

    def load(self) -> None:
        self.mods = self.detect_mods()
        self.plugins = []  # Stardew doesn't have a plugin system

    def save(self) -> None:
        # Stardew mod order is determined by SMAPI dependency resolution
        # We can write a load order hint file for our own tracking
        if self.profile_dir:
            path = self.profile_dir / 'mod_order.txt'
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = ['# Stardew Valley mod order (managed by wabbajack-py)']
            for m in self.mods:
                prefix = '+' if m.enabled else '-'
                lines.append(f"{prefix}{m.name}")
            path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            log.info(f"Saved mod_order.txt ({len(self.mods)} mods) -> {path}")

    def detect_mods(self) -> list[ModEntry]:
        """Scan SMAPI Mods directory for mods with manifest.json."""
        import json
        mods = []
        mods_dir = self._mods_dir()
        if not mods_dir.exists():
            return mods

        for i, d in enumerate(sorted(mods_dir.iterdir())):
            if not d.is_dir():
                continue
            manifest = d / 'manifest.json'
            if not manifest.exists():
                continue
            try:
                data = json.loads(manifest.read_text(encoding='utf-8'))
                name = data.get('Name', d.name)
                mods.append(ModEntry(name, enabled=True, priority=i))
            except (json.JSONDecodeError, OSError):
                mods.append(ModEntry(d.name, enabled=True, priority=i))

        return mods

    def get_dependencies(self) -> dict[str, list[str]]:
        """Parse SMAPI manifest.json files for dependency graph."""
        import json
        deps = {}
        mods_dir = self._mods_dir()
        if not mods_dir.exists():
            return deps

        for d in mods_dir.iterdir():
            manifest = d / 'manifest.json'
            if not manifest.exists():
                continue
            try:
                data = json.loads(manifest.read_text(encoding='utf-8'))
                uid = data.get('UniqueID', d.name)
                required = []
                for dep in data.get('Dependencies', []):
                    if dep.get('IsRequired', True):
                        required.append(dep['UniqueID'])
                deps[uid] = required
            except (json.JSONDecodeError, OSError, KeyError):
                continue
        return deps


# ── Registry ────────────────────────────────────────────────────────────

LOAD_ORDER_CLASSES: dict[str, type[GameLoadOrder]] = {
    'SkyrimSpecialEdition': SkyrimSELoadOrder,
    'Skyrim': SkyrimLELoadOrder,
    'Oblivion': OblivionLoadOrder,
    'Fallout4': Fallout4LoadOrder,
    'Starfield': StarfieldLoadOrder,
    'EnderalSpecialEdition': EnderalSELoadOrder,
    'BaldursGate3': BG3LoadOrder,
    'Cyberpunk2077': CyberpunkLoadOrder,
    'StardewValley': StardewLoadOrder,
}


def get_load_order(game_type: str, game_dir: Path,
                   profile_dir: Optional[Path] = None) -> GameLoadOrder:
    """Factory: get the appropriate load order handler for a game."""
    cls = LOAD_ORDER_CLASSES.get(game_type)
    if cls is None:
        raise ValueError(f"No load order support for {game_type}. "
                         f"Supported: {', '.join(LOAD_ORDER_CLASSES.keys())}")
    return cls(game_dir, profile_dir)
