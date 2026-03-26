"""Configuration and XDG data directory support.

Per-modlist configs are stored in each output directory.
Global settings and app data use XDG-compliant paths.
"""
import json, logging, os
from pathlib import Path

log = logging.getLogger(__name__)

CONFIG_FILE = '.wj-config.json'

# XDG Base Directories (https://specifications.freedesktop.org/basedir-spec)
APP_NAME = 'wabbajack-py'


def xdg_data_home() -> Path:
    """~/.local/share/wabbajack-py/ (XDG_DATA_HOME)"""
    base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    return base / APP_NAME


def xdg_config_home() -> Path:
    """~/.config/wabbajack-py/ (XDG_CONFIG_HOME)"""
    base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return base / APP_NAME


def xdg_cache_home() -> Path:
    """~/.cache/wabbajack-py/ (XDG_CACHE_HOME)"""
    base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    return base / APP_NAME


def ensure_app_dirs() -> dict[str, Path]:
    """Create the standard app directory structure. Returns paths dict."""
    dirs = {
        'data': xdg_data_home(),
        'config': xdg_config_home(),
        'cache': xdg_cache_home(),
        'modlists': xdg_data_home() / 'modlists',
        'profiles': xdg_data_home() / 'profiles',
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


class GlobalSettings:
    """App-wide settings stored in XDG config dir."""

    DEFAULTS = {
        'default_workers': 12,
        'verify_hashes': False,
    }

    def __init__(self):
        self.path = xdg_config_home() / 'settings.json'
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return {**self.DEFAULTS, **json.loads(self.path.read_text())}
            except (json.JSONDecodeError, OSError):
                pass
        return dict(self.DEFAULTS)

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self._data, indent=2))
            tmp.replace(self.path)
        except OSError as e:
            log.debug(f"Could not save global settings: {e}")

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def summary(self) -> dict:
        return dict(self._data)


class InstallConfig:
    """Per-modlist install configuration."""

    KEYS = {
        'wabbajack_path', 'output_dir', 'downloads_dir', 'game_dir',
        'workers', 'verify_hashes', 'cache_dir', 'profile_name',
        'modlist_name', 'modlist_version', 'game_type',
    }

    def __init__(self, output_dir):
        self.path = Path(output_dir) / CONFIG_FILE
        self._data = self._load()

    def _load(self):
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self._data, indent=2))
            tmp.replace(self.path)
        except OSError as e:
            log.debug(f"Could not save config: {e}")

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        if key in self.KEYS:
            self._data[key] = str(value) if isinstance(value, Path) else value

    def update_from_install(self, installer):
        """Save current install parameters for future re-runs."""
        self.set('wabbajack_path', str(installer.ml.path))
        self.set('output_dir', str(installer.output))
        self.set('downloads_dir', str(installer.downloads))
        self.set('game_dir', str(installer.game_dir))
        self.set('workers', installer.workers)
        self.set('verify_hashes', installer.verify_hashes)
        self.set('modlist_name', installer.ml.name)
        self.set('modlist_version', installer.ml.version)
        self.set('game_type', installer.ml.game)
        if installer.cache_dir:
            self.set('cache_dir', str(installer.cache_dir))
        self.save()
        log.info(f"  Saved config to {self.path}")

    def summary(self):
        return {k: v for k, v in self._data.items() if k in self.KEYS}
