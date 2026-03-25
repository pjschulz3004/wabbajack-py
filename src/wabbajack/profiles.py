"""Multi-modlist profile management with shared downloads."""
import json, time, logging
from pathlib import Path
from .modlist import WabbajackModlist

log = logging.getLogger(__name__)

DEFAULT_BASE = Path.home() / 'Games'
PROFILES_FILE = 'wabbajack-profiles.json'


class ProfileManager:
    """Manage multiple modlist installations with shared downloads."""

    def __init__(self, base_dir=None):
        self.base = Path(base_dir) if base_dir else DEFAULT_BASE
        self.base.mkdir(parents=True, exist_ok=True)
        self.profiles_path = self.base / PROFILES_FILE
        self._data = self._load()

    def _load(self):
        if self.profiles_path.exists():
            return json.loads(self.profiles_path.read_text())
        return {'active': None, 'shared_downloads': str(self.base / 'WabbajackDownloads'), 'profiles': {}}

    def _save(self):
        self.profiles_path.write_text(json.dumps(self._data, indent=2))

    @property
    def shared_downloads(self):
        return Path(self._data['shared_downloads'])

    @property
    def active(self):
        return self._data.get('active')

    @property
    def profiles(self):
        return self._data.get('profiles', {})

    def register(self, name, wabbajack_path, output_dir, game_dir):
        ml = WabbajackModlist(wabbajack_path)
        archive_hashes = [a['Hash'] for a in ml.archives]
        self._data['profiles'][name] = {
            'title': ml.name, 'version': ml.version, 'game': ml.game,
            'wabbajack': str(wabbajack_path), 'output': str(output_dir),
            'game_dir': str(game_dir), 'archive_count': len(ml.archives),
            'archive_hashes': archive_hashes,
            'installed_at': time.strftime('%Y-%m-%d %H:%M'),
        }
        if not self._data['active']:
            self._data['active'] = name
        self._save()
        log.info(f"Registered profile: {name} ({ml.name} v{ml.version})")

    def switch(self, name):
        if name not in self._data['profiles']:
            log.error(f"Profile '{name}' not found. Available: {', '.join(self._data['profiles'].keys())}")
            return False
        self._data['active'] = name
        self._save()
        p = self._data['profiles'][name]
        log.info(f"Switched to: {name} ({p['title']} v{p['version']})")
        return True

    def analyze_shared(self, new_wabbajack_path=None):
        all_hashes = {}
        for name, p in self._data['profiles'].items():
            for h in p.get('archive_hashes', []):
                all_hashes.setdefault(h, []).append(name)

        shared = {h: names for h, names in all_hashes.items() if len(names) > 1}
        result = {
            'total_unique': len(all_hashes),
            'shared_count': len(shared),
        }

        if new_wabbajack_path:
            ml = WabbajackModlist(new_wabbajack_path)
            new_hashes = {a['Hash'] for a in ml.archives}
            reusable = new_hashes & set(all_hashes.keys())
            new_only = new_hashes - set(all_hashes.keys())
            reusable_size = sum(a.get('Size', 0) for a in ml.archives if a['Hash'] in reusable)
            new_size = sum(a.get('Size', 0) for a in ml.archives if a['Hash'] in new_only)
            result.update({
                'new_title': ml.name, 'new_version': ml.version,
                'new_total': len(new_hashes), 'reusable': len(reusable),
                'new_only': len(new_only), 'reusable_size': reusable_size,
                'new_size': new_size,
                'savings_pct': len(reusable) / max(1, len(new_hashes)) * 100,
            })
        return result
