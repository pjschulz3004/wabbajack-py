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

    _DEFAULTS = {'active': None, 'shared_downloads': '', 'profiles': {}}

    def _fresh_defaults(self):
        return {'active': None, 'shared_downloads': str(self.base / 'WabbajackDownloads'), 'profiles': {}}

    def _load(self):
        if not self.profiles_path.exists():
            return self._fresh_defaults()
        try:
            data = json.loads(self.profiles_path.read_text())
            if not isinstance(data.get('profiles'), dict):
                raise ValueError("invalid profiles structure")
            return data
        except (json.JSONDecodeError, ValueError, OSError) as e:
            log.warning(f"Profile data corrupted ({e}), resetting to defaults: {self.profiles_path}")
            return self._fresh_defaults()

    def _save(self):
        tmp = self.profiles_path.with_suffix('.tmp')
        try:
            tmp.write_text(json.dumps(self._data, indent=2))
            tmp.replace(self.profiles_path)  # atomic on POSIX
        except OSError as e:
            log.error(f"Failed to save profiles: {e}")
            tmp.unlink(missing_ok=True)

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
        with WabbajackModlist(wabbajack_path) as ml:
            title, version, game = ml.name, ml.version, ml.game
            archive_hashes = [a['Hash'] for a in ml.archives]
            archive_count = len(ml.archives)
        self._data['profiles'][name] = {
            'title': title, 'version': version, 'game': game,
            'wabbajack': str(wabbajack_path), 'output': str(output_dir),
            'game_dir': str(game_dir), 'archive_count': archive_count,
            'archive_hashes': archive_hashes,
            'installed_at': time.strftime('%Y-%m-%d %H:%M'),
        }
        if not self._data['active']:
            self._data['active'] = name
        self._save()
        log.info(f"Registered profile: {name} ({title} v{version})")

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
            with WabbajackModlist(new_wabbajack_path) as ml:
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
