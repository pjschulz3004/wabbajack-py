"""Wabbajack .wabbajack file parser.

A .wabbajack file is a ZIP archive containing:
  - modlist: JSON with all archives, directives, and metadata
  - modlist-image.png: optional banner image
  - <hash-ids>: inline data files for InlineFile/PatchedFromArchive directives
"""
import json, zipfile, shutil, logging
from pathlib import Path
from collections import Counter

log = logging.getLogger(__name__)


class WabbajackModlist:
    """Parse and query a .wabbajack modlist file."""

    def __init__(self, wabbajack_path):
        self.path = Path(wabbajack_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Modlist not found: {self.path}")
        try:
            self.zf = zipfile.ZipFile(self.path, 'r')
        except zipfile.BadZipFile:
            raise ValueError(f"Not a valid .wabbajack archive (corrupt or truncated): {self.path}")
        self._modlist = None

    def close(self):
        self.zf.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def modlist(self):
        if self._modlist is None:
            log.info("Parsing modlist JSON...")
            try:
                with self.zf.open('modlist') as f:
                    self._modlist = json.load(f)
            except KeyError:
                raise ValueError(f"No 'modlist' entry found in {self.path} -- not a valid .wabbajack file")
            except json.JSONDecodeError as e:
                raise ValueError(f"Corrupt modlist JSON in {self.path}: {e}")
        return self._modlist

    @property
    def name(self): return self.modlist.get('Name', 'Unknown')
    @property
    def version(self): return self.modlist.get('Version', '?')
    @property
    def author(self): return self.modlist.get('Author', '?')
    @property
    def game(self): return self.modlist.get('GameType', '?')
    @property
    def is_nsfw(self): return self.modlist.get('IsNSFW', False)
    @property
    def archives(self): return self.modlist.get('Archives', [])
    @property
    def directives(self): return self.modlist.get('Directives', [])

    def extract_data(self, source_id, dest_path):
        """Extract a single inline data file from the .wabbajack ZIP."""
        dest_path = Path(dest_path)
        try:
            with self.zf.open(source_id) as src:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            return True
        except KeyError:
            log.debug(f"Inline data not found in ZIP: {source_id}")
            return False

    def extract_all_inline(self, output_dir):
        """Bulk extract all inline/patch data files from the .wabbajack.

        Sanitizes paths to prevent zip path traversal attacks.
        """
        names = set(self.zf.namelist()) - {'modlist', 'modlist-image.png'}
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"Extracting {len(names)} inline/patch data files...")
        for name in names:
            # Sanitize: reject absolute paths and path traversal
            if name.startswith('/') or '..' in name.split('/'):
                log.warning(f"Skipping unsafe ZIP entry: {name}")
                continue
            target = (output_dir / name).resolve()
            if not str(target).startswith(str(output_dir)):
                log.warning(f"Skipping path traversal attempt: {name}")
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                with self.zf.open(name) as src, open(target, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            except (OSError, KeyError) as e:
                log.warning(f"Failed to extract inline {name}: {type(e).__name__}: {e}")
        return len(names)

    def archive_type_counts(self):
        """Count archives by downloader type."""
        return Counter(a['State'].get('$type', '?') for a in self.archives)

    def directive_type_counts(self):
        """Count directives by type."""
        return Counter(d.get('$type', '?') for d in self.directives)

    def summary(self):
        """Return a dict summary of the modlist."""
        return {
            'name': self.name, 'version': self.version, 'author': self.author,
            'game': self.game, 'nsfw': self.is_nsfw,
            'archives': len(self.archives), 'directives': len(self.directives),
            'archive_types': dict(self.archive_type_counts()),
            'directive_types': dict(self.directive_type_counts()),
        }
