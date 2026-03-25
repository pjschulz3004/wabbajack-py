"""Install state persistence -- resume interrupted installations."""
import json, time, logging
from pathlib import Path

log = logging.getLogger(__name__)

STATE_FILE = '.wj-install-state.json'


class InstallState:
    """Track installation progress for resume support."""

    def __init__(self, output_dir):
        self.path = Path(output_dir) / STATE_FILE
        self._data = self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return {
            'started_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'completed_hashes': [],
            'placed_files': 0,
            'failed_files': 0,
            'phase': 'init',
        }

    def _save(self):
        try:
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self._data, indent=2))
            tmp.replace(self.path)
        except OSError as e:
            log.debug(f"Could not save install state: {e}")

    @property
    def phase(self):
        return self._data.get('phase', 'init')

    @phase.setter
    def phase(self, value):
        self._data['phase'] = value
        self._data['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        self._save()

    @property
    def completed_hashes(self):
        if not hasattr(self, '_hash_set_cache'):
            self._hash_set_cache = set(self._data.get('completed_hashes', []))
        return self._hash_set_cache

    def mark_hash_done(self, archive_hash):
        """Mark an archive hash as fully processed (extracted + placed)."""
        hashes = self._data.setdefault('completed_hashes', [])
        if archive_hash not in self.completed_hashes:
            hashes.append(archive_hash)
            self._hash_set_cache.add(archive_hash)
        # Save periodically (every 100 hashes)
        if len(hashes) % 100 == 0:
            self._save()

    def update_stats(self, placed, failed):
        self._data['placed_files'] = placed
        self._data['failed_files'] = failed

    def mark_complete(self):
        self._data['phase'] = 'complete'
        self._data['completed_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        self._save()

    def is_hash_done(self, archive_hash):
        return archive_hash in self.completed_hashes

    def save(self):
        self._save()

    def reset(self):
        """Reset state for a fresh install."""
        self._data = {
            'started_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'completed_hashes': [],
            'placed_files': 0,
            'failed_files': 0,
            'phase': 'init',
        }
        self._save()

    def summary(self):
        return {
            'phase': self.phase,
            'completed_archives': len(self._data.get('completed_hashes', [])),
            'placed_files': self._data.get('placed_files', 0),
            'failed_files': self._data.get('failed_files', 0),
            'started': self._data.get('started_at', '?'),
            'updated': self._data.get('updated_at', '?'),
        }
