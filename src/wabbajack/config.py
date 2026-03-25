"""Per-modlist configuration file support.

Saves install settings so re-runs don't need all CLI args.
Stored as JSON in the output directory.
"""
import json, logging
from pathlib import Path

log = logging.getLogger(__name__)

CONFIG_FILE = '.wj-config.json'


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
