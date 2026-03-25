"""Case-insensitive file finder for Linux compatibility.

Windows filesystems are case-insensitive, so Wabbajack modlists freely mix case.
On Linux/macOS (case-sensitive FS), we need to build an index and match by lowercase.
"""
import os, logging
from pathlib import Path

log = logging.getLogger(__name__)


class CaseInsensitiveFinder:
    """Index a directory tree and find files regardless of case."""

    def __init__(self, root):
        self.root = Path(root)
        self._cache = {}
        if self.root.exists():
            self._build_cache()
            log.debug(f"Indexed {len(self._cache)} files in {self.root}")

    def _build_cache(self):
        for dirpath, _, filenames in os.walk(self.root):
            rel = Path(dirpath).relative_to(self.root)
            for f in filenames:
                real_path = rel / f
                lower_path = str(real_path).lower().replace('\\', '/')
                self._cache[lower_path] = self.root / real_path

    def find(self, relative_path):
        """Find a file by path, case-insensitively. Returns Path or None."""
        normalized = relative_path.replace('\\', '/').lower()
        return self._cache.get(normalized)

    def __len__(self):
        return len(self._cache)
