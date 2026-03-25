"""Archive extraction cache with parallel workers.

Manages bulk-extracted archive contents with case-insensitive lookup.
Archives are extracted once into a cache directory and indexed for fast access.
"""
import os, re, subprocess, zipfile, logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

log = logging.getLogger(__name__)


def extract_archive_worker(args):
    """Worker function for parallel archive extraction. Runs in subprocess pool."""
    archive_path, extract_dir = args
    archive_path = Path(archive_path)
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    name = archive_path.name

    try:
        if archive_path.suffix.lower() == '.zip':
            try:
                with zipfile.ZipFile(archive_path) as zf:
                    # Validate all paths before extraction to prevent traversal
                    resolved_base = extract_dir.resolve()
                    for info in zf.infolist():
                        target = (extract_dir / info.filename).resolve()
                        if not str(target).startswith(str(resolved_base)):
                            return (name, False, 0, f'path traversal in ZIP: {info.filename}')
                    zf.extractall(extract_dir)
                return (name, True, len(os.listdir(extract_dir)), '')
            except zipfile.BadZipFile:
                pass  # Not a valid ZIP, fall through to 7z
            except PermissionError as e:
                return (name, False, 0, f'permission denied: {e}')
            except OSError as e:
                # Disk full, too many open files, etc. -- don't retry with 7z
                if e.errno in (28, 24, 30):  # ENOSPC, EMFILE, EROFS
                    return (name, False, 0, f'{type(e).__name__}: {e}')
                pass  # Other OSError (e.g. encoding issue) -- try 7z

        result = subprocess.run(
            ['7z', 'x', '-y', '-bso0', '-bsp0', f'-o{extract_dir}', str(archive_path)],
            capture_output=True, timeout=600
        )
        if result.returncode == 0:
            count = sum(len(files) for _, _, files in os.walk(extract_dir))
            return (name, True, count, '')
        else:
            err = result.stderr.decode(errors='replace')[:200]
            return (name, False, 0, f'7z exit {result.returncode}: {err}')
    except subprocess.TimeoutExpired:
        return (name, False, 0, 'timed out after 600s')
    except FileNotFoundError:
        return (name, False, 0, '7z not found in PATH')
    except Exception as e:
        return (name, False, 0, f'{type(e).__name__}: {e}')


class ArchiveCache:
    """Manages bulk-extracted archive contents with case-insensitive lookup."""

    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index = {}
        self._extracted = set()  # Cache of known-extracted archives

    def get_extract_dir(self, archive_name):
        safe = re.sub(r'[^\w\-.]', '_', archive_name)
        return self.cache_dir / safe

    def is_extracted(self, archive_name):
        if archive_name in self._extracted:
            return True
        d = self.get_extract_dir(archive_name)
        try:
            if d.exists() and any(d.iterdir()):
                self._extracted.add(archive_name)
                return True
        except OSError:
            pass
        return False

    def index_archive(self, archive_name):
        """Build case-insensitive index for an extracted archive."""
        if archive_name in self._index:
            return
        extract_dir = self.get_extract_dir(archive_name)
        if not extract_dir.exists():
            return
        idx = {}
        for dirpath, _, filenames in os.walk(extract_dir):
            rel = Path(dirpath).relative_to(extract_dir)
            for f in filenames:
                real_path = extract_dir / rel / f
                full_rel = (rel / f).as_posix()
                idx[full_rel.lower()] = real_path
                idx[f.lower()] = real_path
        self._index[archive_name] = idx

    def find_file(self, archive_name, internal_path):
        """Find a file in an extracted archive, case-insensitively."""
        if archive_name not in self._index:
            self.index_archive(archive_name)

        idx = self._index.get(archive_name, {})
        normalized = internal_path.replace('\\', '/').lower()

        if normalized in idx:
            return idx[normalized]

        filename = Path(normalized).name
        if filename in idx:
            return idx[filename]

        parts = normalized.split('/')
        for i in range(len(parts)):
            partial = '/'.join(parts[i:])
            if partial in idx:
                return idx[partial]
        return None

    def batch_extract(self, archive_items, workers=12):
        """Extract multiple archives in parallel.

        Args:
            archive_items: list of (archive_path, archive_name) tuples
            workers: number of parallel workers
        Returns:
            (extracted_count, failed_count)
        """
        to_extract = []
        for archive_path, archive_name in archive_items:
            if self.is_extracted(archive_name):
                continue
            extract_dir = self.get_extract_dir(archive_name)
            to_extract.append((str(archive_path), str(extract_dir)))

        if not to_extract:
            return (0, 0)

        log.info(f"  Extracting {len(to_extract)} archives using {workers} workers...")
        completed = 0
        failed = 0

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(extract_archive_worker, args): args for args in to_extract}
            for future in as_completed(futures):
                try:
                    name, success, _count, err_msg = future.result()
                except Exception as e:
                    # BrokenProcessPool, killed worker, OOM, etc.
                    args = futures[future]
                    name = Path(args[0]).name
                    log.warning(f"  Extract worker crashed: {name}: {type(e).__name__}: {e}")
                    failed += 1
                    completed += 1
                    continue
                completed += 1
                if not success:
                    failed += 1
                    log.warning(f"  Extract failed: {name}: {err_msg}")
                if completed % 50 == 0:
                    log.info(f"    Extracted {completed}/{len(to_extract)} ({failed} failed)")

        log.info(f"  Extraction done: {completed - failed} ok, {failed} failed")
        return (completed - failed, failed)
