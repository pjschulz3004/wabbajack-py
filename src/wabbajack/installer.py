"""Modlist installer -- orchestrates downloads, extraction, and file placement."""
from __future__ import annotations
import re, time, shutil, logging, threading
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .modlist import WabbajackModlist

from .finder import CaseInsensitiveFinder
from .cache import ArchiveCache
from .hash import verify_archive
from .downloaders import download_with_progress, classify_archive, MAX_RETRIES
from .downloaders.cdn import download_wabbajack_cdn
from .downloaders.nexus import NexusClient, download_nexus_files
from .downloaders.mediafire import download_mediafire_files
from .downloaders.mega import download_mega_files
from .downloaders.gdrive import download_gdrive_files
from .downloaders.moddb import download_moddb_files
from .state import InstallState
from .config import InstallConfig
from .bsa import create_bsa, stage_bsa_files
from .progress import print_install_complete, HAS_RICH

log = logging.getLogger(__name__)

# Wabbajack path magic constants used in RemappedInlineFile directives.
# These get replaced with actual paths so MO2 configs point to the right locations.
PATH_MAGIC = {
    '{--||GAME_PATH_MAGIC_BACK||--}':          ('game', '\\'),
    '{--||GAME_PATH_MAGIC_DOUBLE_BACK||--}':   ('game', '\\\\'),
    '{--||GAME_PATH_MAGIC_FORWARD||--}':       ('game', '/'),
    '{--||MO2_PATH_MAGIC_BACK||--}':           ('output', '\\'),
    '{--||MO2_PATH_MAGIC_DOUBLE_BACK||--}':    ('output', '\\\\'),
    '{--||MO2_PATH_MAGIC_FORWARD||--}':        ('output', '/'),
    '{--||DOWNLOAD_PATH_MAGIC_BACK||--}':      ('downloads', '\\'),
    '{--||DOWNLOAD_PATH_MAGIC_DOUBLE_BACK||--}': ('downloads', '\\\\'),
    '{--||DOWNLOAD_PATH_MAGIC_FORWARD||--}':   ('downloads', '/'),
}


class ModlistInstaller:
    """Full modlist installer: download, extract, place."""

    def __init__(self, modlist: WabbajackModlist, output_dir: str | Path,
                 downloads_dir: str | Path, game_dir: str | Path,
                 nexus_key: str | None = None, workers: int = 12,
                 cache_dir: str | Path | None = None, verify_hashes: bool = False) -> None:
        self.ml = modlist
        self.output = Path(output_dir)
        self.downloads = Path(downloads_dir)
        self.game_dir = Path(game_dir)
        self.workers = workers
        self.verify_hashes = verify_hashes
        self.nexus = NexusClient(nexus_key) if nexus_key else None

        self.output.mkdir(parents=True, exist_ok=True)
        self.downloads.mkdir(parents=True, exist_ok=True)


        self.archive_by_hash = {a['Hash']: a for a in self.ml.archives}

        log.info("Building game file index...")
        self.game_finder = CaseInsensitiveFinder(self.game_dir)

        self._refresh_downloads_index()

        self.cache_dir = Path(cache_dir) if cache_dir else self.output.parent / '.wj-cache'
        self.archive_cache = ArchiveCache(self.cache_dir)
        self.inline_dir = self.cache_dir / '_inline'

        self._stats_lock = threading.Lock()
        self.stats = defaultdict(int)
        self.failed_downloads = []
        self.hash_mismatches = []
        self.state = InstallState(self.output)
        self.config = InstallConfig(self.output)

    def _refresh_downloads_index(self):
        self.downloads_index = {}
        if self.downloads.exists():
            for f in self.downloads.iterdir():
                if f.is_file():
                    self.downloads_index[f.name] = f
                    self.downloads_index[f.name.lower()] = f

    def _is_archive_present(self, archive):
        name = archive['Name']
        expected_size = archive.get('Size', 0)

        for key in (name, name.lower()):
            if key in self.downloads_index:
                path = self.downloads_index[key]
                try:
                    actual_size = path.stat().st_size
                    if expected_size == 0 or actual_size == expected_size:
                        return True
                    if expected_size > 0 and actual_size >= expected_size * 0.95:
                        return True
                except OSError:
                    pass

        state_type = archive['State'].get('$type', '')
        if 'GameFileSource' in state_type:
            game_file = archive['State'].get('GameFile', '')
            if self.game_finder.find(game_file):
                return True
        return False

    def find_archive_path(self, archive_hash: str) -> Path | None:
        info = self.archive_by_hash.get(archive_hash)
        if not info:
            return None
        state_type = info['State'].get('$type', '')
        name = info['Name']

        if 'GameFileSource' in state_type:
            found = self.game_finder.find(info['State'].get('GameFile', ''))
            if found:
                return found

        for key in (name, name.lower()):
            if key in self.downloads_index:
                p = self.downloads_index[key]
                try:
                    if p.stat().st_size > 0:
                        return p
                except OSError:
                    pass
        return None

    def _register_download(self, archive):
        name = archive['Name']
        path = self.downloads / name
        if path.exists():
            self.downloads_index[name] = path
            self.downloads_index[name.lower()] = path
            if self.verify_hashes:
                result = verify_archive(path, archive.get('Hash'), name)
                if not result.ok:
                    self.hash_mismatches.append(result)

    # Common file extensions that indicate extractable archives
    ARCHIVE_EXTS = ('.bsa', '.ba2', '.zip', '.7z', '.rar')

    def _remap_inline_content(self, data):
        """Replace Wabbajack path magic strings with actual paths."""
        try:
            text = data.decode('utf-8')
        except (UnicodeDecodeError, AttributeError):
            return data  # Binary file, no remapping needed

        if '{--||' not in text:
            return data  # Fast path: no magic strings possible

        paths = {
            'game': str(self.game_dir),
            'output': str(self.output),
            'downloads': str(self.downloads),
        }
        changed = False
        for magic, (path_key, sep) in PATH_MAGIC.items():
            if magic in text:
                real_path = paths[path_key]
                if sep == '/':
                    real_path = real_path.replace('\\', '/')
                elif sep == '\\\\':
                    real_path = real_path.replace('/', '\\').replace('\\', '\\\\')
                elif sep == '\\':
                    real_path = real_path.replace('/', '\\')
                text = text.replace(magic, real_path)
                changed = True
        return text.encode('utf-8') if changed else data

    def _setup_mo2(self):
        """Set up MO2 directory structure and config for a working install."""
        # Create portable.txt so MO2 runs in portable mode
        portable = self.output / 'portable.txt'
        if not portable.exists():
            portable.write_text('')
            log.info("  Created portable.txt")

        # Remap ModOrganizer.ini download directory
        mo2_ini = self.output / 'ModOrganizer.ini'
        if mo2_ini.exists():
            try:
                content = mo2_ini.read_text(encoding='utf-8', errors='replace')
                new_content = content
                # Fix download_directory to point to actual downloads path
                dl_path = str(self.downloads).replace('\\', '/')
                new_content = re.sub(
                    r'download_directory\s*=.*',
                    f'download_directory={dl_path}',
                    new_content
                )
                # Fix base_directory to output
                out_path = str(self.output).replace('\\', '/')
                new_content = re.sub(
                    r'base_directory\s*=.*',
                    f'base_directory={out_path}',
                    new_content
                )
                if new_content != content:
                    mo2_ini.write_text(new_content, encoding='utf-8')
                    log.info("  Remapped ModOrganizer.ini paths")
            except OSError as e:
                log.warning(f"  Could not remap ModOrganizer.ini: {e}")

        # Create standard MO2 subdirectories
        for subdir in ('mods', 'profiles', 'overwrite', 'crashDumps'):
            (self.output / subdir).mkdir(exist_ok=True)

        # Write .meta files for downloaded archives (so MO2 knows their source)
        self._write_meta_files()

    def _write_meta_files(self):
        """Write .meta INI files for downloads so MO2 tracks their source."""
        wrote = 0
        for a in self.ml.archives:
            name = a['Name']
            meta_path = self.downloads / (name + '.meta')
            if meta_path.exists():
                continue
            path = self.downloads / name
            if not path.exists():
                continue

            state = a['State']
            state_type = state.get('$type', '')
            lines = ['[General]', f'installed=true']

            if 'NexusDownloader' in state_type:
                game = state.get('GameName', 'skyrimspecialedition')
                mod_id = state.get('ModID', 0)
                file_id = state.get('FileID', 0)
                lines.append(f'gameName={game}')
                lines.append(f'modID={mod_id}')
                lines.append(f'fileID={file_id}')
            elif 'HttpDownloader' in state_type or 'WabbajackCDN' in state_type:
                url = state.get('Url', '')
                if url:
                    lines.append(f'directURL={url}')
            elif 'GoogleDrive' in state_type:
                lines.append(f'directURL=https://drive.google.com/uc?id={state.get("Id", "")}')
            elif 'MediaFire' in state_type:
                lines.append(f'directURL={state.get("Url", "")}')
            elif 'ModDB' in state_type:
                lines.append(f'directURL={state.get("Url", "")}')
            elif 'MegaDownloader' in state_type:
                lines.append(f'directURL={state.get("Url", "")}')

            try:
                meta_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
                wrote += 1
            except OSError:
                pass

        if wrote:
            log.info(f"  Wrote {wrote} .meta files for MO2")

    def _place_file(self, src, to_field):
        """Place a file from src to the output path derived from a directive's To field.

        Validates against path traversal. Skips if dest already matches source size.
        Returns True on success.
        """
        # Fast string-based traversal check (catches 99.9% of cases without syscall)
        normalized = to_field.replace('\\', '/')
        parts = normalized.split('/')
        if '..' in parts or normalized.startswith('/'):
            log.warning(f"  Path traversal blocked: {to_field}")
            return False

        dest = self.output / normalized

        # Verify destination stays within output dir (no symlink resolution needed —
        # the string check above already caught '..' and absolute paths)
        try:
            if not dest.is_relative_to(self.output):
                log.warning(f"  Path escape blocked: {to_field}")
                return False
        except (TypeError, ValueError):
            return False

        # Skip if destination already exists with matching size (optimized re-install)
        try:
            src_size = src.stat().st_size
            dest_size = dest.stat().st_size
            if src_size == dest_size:
                return True  # Already correct, skip copy
        except OSError:
            pass  # dest doesn't exist or src stat failed, proceed with copy

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            return True
        except (OSError, PermissionError) as e:
            # Use WARNING for first 20 failures, then DEBUG. Read under lock for thread safety.
            with self._stats_lock:
                fail_count = self.stats['fail']
            lvl = logging.WARNING if fail_count < 20 else logging.DEBUG
            log.log(lvl, f'    Place failed: {dest} -- {e}')
            return False

    # ── Downloads ─────────────────────────────────────────────────────────

    def _download_game_files(self, archives):
        if not archives:
            return
        log.info(f"\n--- Copying {len(archives)} game files ---")
        ok = 0
        for a in archives:
            game_file = a['State'].get('GameFile', '')
            src = self.game_finder.find(game_file)
            if src:
                dest = self.downloads / a['Name']
                try:
                    shutil.copy2(src, dest)
                    self._register_download(a)
                    ok += 1
                except (OSError, PermissionError) as e:
                    log.error(f"  Copy failed: {src} -> {dest}: {e}")
                    self.failed_downloads.append(a)
            else:
                log.warning(f"  NOT FOUND in game dir: {game_file}")
                self.failed_downloads.append(a)
        log.info(f"  Game files: {ok}/{len(archives)} copied")

    HTTP_PARALLEL = 4  # Concurrent HTTP downloads

    def _download_http_one(self, archive):
        """Download a single HTTP/CDN archive. Returns (archive, success)."""
        url = archive['State'].get('Url', '')
        if not url:
            m = re.search(r'directURL=(.*)', archive.get('Meta', ''))
            if m:
                url = m.group(1).strip()
        if not url:
            return archive, False

        dest = self.downloads / archive['Name']
        is_cdn = 'authored-files.wabbajack.org' in url or 'WabbajackCDN' in archive['State'].get('$type', '')

        for attempt in range(MAX_RETRIES):
            if is_cdn:
                if download_wabbajack_cdn(url, dest):
                    return archive, True
            else:
                if download_with_progress(url, dest, quiet=True):
                    return archive, True
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
        return archive, False

    def _download_http_files(self, archives):
        if not archives:
            return
        log.info(f"\n--- Downloading {len(archives)} HTTP/CDN files ({self.HTTP_PARALLEL} parallel) ---")
        ok = 0
        completed = 0

        with ThreadPoolExecutor(max_workers=self.HTTP_PARALLEL) as pool:
            futures = {pool.submit(self._download_http_one, a): a for a in archives}
            for future in as_completed(futures):
                completed += 1
                archive, success = future.result()
                if success:
                    self._register_download(archive)
                    ok += 1
                    size_mb = archive.get('Size', 0) / 1048576
                    log.info(f"  [{completed}/{len(archives)}] OK: {archive['Name'][:70]} ({size_mb:.1f} MB)")
                else:
                    self.failed_downloads.append(archive)
                    log.warning(f"  [{completed}/{len(archives)}] FAIL: {archive['Name'][:70]}")
        log.info(f"  HTTP/CDN: {ok}/{len(archives)} downloaded")

    def _skip_manual(self, archives):
        if not archives:
            return
        log.warning(f"\n--- {len(archives)} manual downloads required ---")
        manual_file = self.downloads / 'manual-downloads.txt'
        with manual_file.open('w', encoding='utf-8') as f:
            for a in archives:
                url = a['State'].get('Url', a['State'].get('Prompt', ''))
                log.warning(f"  MANUAL: {a['Name']}")
                if url:
                    log.warning(f"          {url}")
                f.write(f"{a['Name']}\t{url}\n")
        log.warning(f"  URLs saved to: {manual_file}")
        log.warning(f"  Download these files manually and place in: {self.downloads}")

    def download_all(self, types: list[str] | None = None, dry_run: bool = False) -> None:
        missing = [a for a in self.ml.archives if not self._is_archive_present(a)]
        if not missing:
            log.info(f"\nAll {len(self.ml.archives)} archives present!")
            return

        groups = defaultdict(list)
        for a in missing:
            groups[classify_archive(a)].append(a)

        present = len(self.ml.archives) - len(missing)
        total_size = sum(a.get('Size', 0) for a in missing)
        log.info(f"\n{'='*60}")
        log.info(f"Download Summary")
        log.info(f"  Already present: {present}/{len(self.ml.archives)}")
        log.info(f"  Need download:   {len(missing)} (~{total_size/1073741824:.1f} GB)")
        for g in ['game', 'http', 'mediafire', 'mega', 'gdrive', 'moddb', 'nexus', 'manual']:
            if g in groups:
                items = groups[g]
                size = sum(a.get('Size', 0) for a in items) / 1073741824
                log.info(f"    {g:>12}: {len(items):>5} files ({size:.2f} GB)")
        log.info(f"{'='*60}")

        if dry_run:
            log.info("\n[DRY RUN] No downloads performed")
            return

        dispatch = {
            'game': self._download_game_files,
            'http': self._download_http_files,
            'mediafire': lambda a: download_mediafire_files(a, self.downloads, self._register_download, self.failed_downloads),
            'mega': lambda a: download_mega_files(a, self.downloads, self._is_archive_present, self._register_download, self.failed_downloads),
            'gdrive': lambda a: download_gdrive_files(a, self.downloads, self._register_download, self.failed_downloads),
            'moddb': lambda a: download_moddb_files(a, self.downloads, self._register_download, self.failed_downloads),
            'nexus': lambda a: download_nexus_files(a, self.downloads, self.nexus, self._register_download, self.failed_downloads),
            'manual': self._skip_manual,
        }

        for t in ['game', 'http', 'mediafire', 'mega', 'gdrive', 'moddb', 'nexus', 'manual']:
            if types and t not in types:
                continue
            if t in groups and groups[t]:
                dispatch[t](groups[t])

        # Warn about archive types we don't know how to download
        unknown = groups.get('unknown', [])
        if unknown:
            log.warning(f"\n--- {len(unknown)} archives with unknown download type ---")
            for a in unknown:
                log.warning(f"  {a['Name']} ({a['State'].get('$type', '?')})")
            self.failed_downloads.extend(unknown)

        # _register_download already updates the index incrementally, so no full rescan needed

        still_missing = [a for a in self.ml.archives if not self._is_archive_present(a)]
        manual_count = len(groups.get('manual', []))
        log.info(f"\n{'='*60}")
        log.info(f"Download Complete")
        log.info(f"  Archives ready:  {len(self.ml.archives) - len(still_missing)}/{len(self.ml.archives)}")
        log.info(f"  Still missing:   {len(still_missing) - manual_count}")
        log.info(f"  Skipped manual:  {manual_count}")
        if self.hash_mismatches:
            log.warning(f"  Hash mismatches: {len(self.hash_mismatches)}")
            for r in self.hash_mismatches:
                log.warning(f"    {r.message}")
        if self.failed_downloads:
            log.error(f"  Download errors: {len(self.failed_downloads)}")
            failed_file = self.downloads / 'failed-downloads.txt'
            with failed_file.open('w', encoding='utf-8') as f:
                for a in self.failed_downloads:
                    t = a['State'].get('$type', '?')
                    url = a['State'].get('Url', a['State'].get('Id', ''))
                    f.write(f"{a['Name']}\t{t}\t{url}\n")
            log.error(f"  Failed list: {failed_file}")
        log.info(f"{'='*60}")

    # ── Extraction & Placement ────────────────────────────────────────────

    def _group_directives_by_archive(self):
        groups = defaultdict(list)
        inline_directives = []
        patched_directives = []
        bsa_directives = []
        for d in self.ml.directives:
            dtype = d.get('$type', '')
            if dtype == 'FromArchive':
                ahp = d.get('ArchiveHashPath', [])
                if ahp:
                    groups[ahp[0]].append(d)
                else:
                    inline_directives.append(d)
            elif dtype == 'InlineFile':
                inline_directives.append(d)
            elif dtype == 'RemappedInlineFile':
                inline_directives.append(d)  # handled separately with path remapping
            elif dtype == 'PatchedFromArchive':
                patched_directives.append(d)
            elif dtype == 'CreateBSA':
                bsa_directives.append(d)
        return groups, inline_directives, patched_directives, bsa_directives

    def _batch_extract_archives(self, archive_hashes):
        items = []
        for h in archive_hashes:
            info = self.archive_by_hash.get(h)
            if not info:
                continue
            name = info['Name']
            if self.archive_cache.is_extracted(name):
                continue
            path = self.find_archive_path(h)
            if not path:
                continue
            state_type = info['State'].get('$type', '')
            if 'GameFileSource' in state_type:
                gf = info['State'].get('GameFile', '')
                if not any(gf.lower().endswith(ext) for ext in ('.bsa', '.ba2', '.zip', '.7z', '.rar')):
                    continue
            items.append((path, name))

        ok, fail = self.archive_cache.batch_extract(items, workers=self.workers)
        self.stats['archives_extracted'] += ok

        # Only index newly-extracted archives (skip already-indexed)
        newly_extracted = {name for _, name in items}
        for h in archive_hashes:
            info = self.archive_by_hash.get(h)
            if info and info['Name'] in newly_extracted:
                self.archive_cache.index_archive(info['Name'])

    def _extract_nested_archive(self, archive_path, archive_name):
        """Extract a nested archive (BSA/7z/ZIP inside an outer archive) into the cache."""
        nested_name = f"{archive_name}__{archive_path.name}"
        if self.archive_cache.is_extracted(nested_name):
            return nested_name
        extract_dir = self.archive_cache.get_extract_dir(nested_name)
        from .cache import extract_archive_worker
        _, success, _, err = extract_archive_worker((str(archive_path), str(extract_dir)))
        if success:
            self.archive_cache.index_archive(nested_name)
            return nested_name
        log.debug(f"    Nested extract failed: {archive_path.name}: {err}")
        return None

    def _resolve_directive_sources(self, archive_hash, directives):
        """Resolve source files for directives. Returns list of (src, to_field) pairs.

        Handles nested archives (ArchiveHashPath depth 3+) by extracting inner archives.
        """
        info = self.archive_by_hash.get(archive_hash)
        if not info:
            return [], len(directives)

        name = info['Name']
        state_type = info['State'].get('$type', '')
        pairs = []
        fail = 0

        if 'GameFileSource' in state_type:
            gf = info['State'].get('GameFile', '')
            if not any(gf.lower().endswith(ext) for ext in self.ARCHIVE_EXTS):
                src = self.find_archive_path(archive_hash)
                if not src:
                    return [], len(directives)
                for d in directives:
                    pairs.append((src, d.get('To', '')))
                return pairs, 0

        # Cache for nested archive names resolved in this batch
        nested_cache = {}

        for d in directives:
            ahp = d.get('ArchiveHashPath', [])

            if len(ahp) <= 1:
                src = self.find_archive_path(archive_hash)
            elif len(ahp) == 2:
                # Simple: outer_archive -> file
                src = self.archive_cache.find_file(name, ahp[1])
            elif len(ahp) >= 3:
                # Nested: outer_archive -> inner_archive -> file [-> deeper...]
                inner_archive_path_str = ahp[1]
                inner_file = '\\'.join(ahp[2:])

                # Find the inner archive in the outer extraction
                inner_path = self.archive_cache.find_file(name, inner_archive_path_str)
                if inner_path and inner_path.exists():
                    cache_key = (name, inner_archive_path_str)
                    if cache_key not in nested_cache:
                        nested_cache[cache_key] = self._extract_nested_archive(inner_path, name)
                    nested_name = nested_cache[cache_key]
                    if nested_name:
                        src = self.archive_cache.find_file(nested_name, inner_file)
                    else:
                        src = None
                else:
                    src = None
            else:
                src = None

            if src and src.exists():
                pairs.append((src, d.get('To', '')))
            else:
                fail += 1
        return pairs, fail

    def _place_batch_parallel(self, all_pairs, label=""):
        """Place files in parallel using ThreadPoolExecutor."""
        if not all_pairs:
            return

        ok = 0
        fail = 0
        placement_workers = min(self.workers, len(all_pairs))
        with ThreadPoolExecutor(max_workers=placement_workers) as pool:
            futures = {pool.submit(self._place_file, src, to): (src, to)
                       for src, to in all_pairs}
            for future in as_completed(futures):
                try:
                    if future.result():
                        ok += 1
                    else:
                        fail += 1
                except Exception as e:
                    src, to = futures[future]
                    log.debug(f"Place failed: {to} <- {src}: {e}")
                    fail += 1
        with self._stats_lock:
            self.stats['ok'] += ok
            self.stats['fail'] += fail
        if label:
            log.debug(f"  {label}: {ok} placed, {fail} failed")

    def install(self, skip_download: bool = False, download_types: list[str] | None = None, dry_run: bool = False) -> None:
        log.info(f"\n{'='*60}")
        log.info(f"Installing: {self.ml.name} {self.ml.version}")
        log.info(f"Output:     {self.output}")
        log.info(f"Downloads:  {self.downloads}")
        log.info(f"Game:       {self.game_dir}")
        log.info(f"Workers:    {self.workers}")
        log.info(f"Verify:     {self.verify_hashes}")
        log.info(f"Cache:      {self.cache_dir}")
        log.info(f"{'='*60}\n")

        if not skip_download:
            log.info("=== Step 1: Downloading missing archives ===")
            self.download_all(types=download_types, dry_run=dry_run)
            if dry_run:
                return
        else:
            log.info("=== Step 1: Skipping downloads (--skip-download) ===")

        log.info("\n=== Step 2: Analyzing directives ===")
        groups, inlines, patched, bsas = self._group_directives_by_archive()
        log.info(f"  {len(groups)} unique archives, {sum(len(v) for v in groups.values())} FromArchive")
        log.info(f"  {len(inlines)} inline, {len(patched)} patched, {len(bsas)} BSA")

        # Release raw directive list (~2-4 GB for 651K directives) -- grouped data is sufficient
        if hasattr(self.ml, '_modlist') and self.ml._modlist:
            self.ml._modlist.pop('Directives', None)
            import gc; gc.collect()

        log.info("\n=== Step 3: Extracting inline data ===")
        self.ml.extract_all_inline(self.inline_dir)

        log.info("\n=== Step 4: Extracting archives & placing files ===")
        self.state.phase = 'placing'
        all_hashes = list(groups.keys())
        batch_size = 200
        total_d = sum(len(v) for v in groups.values())
        done_hashes = self.state.completed_hashes

        # Skip already-completed batches on resume
        skipped_batches = 0
        for batch_start in range(0, len(all_hashes), batch_size):
            batch = all_hashes[batch_start:batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (len(all_hashes) + batch_size - 1) // batch_size

            # Check if entire batch was already completed (resume)
            if all(h in done_hashes for h in batch):
                skipped_batches += 1
                continue

            if skipped_batches and batch_num == skipped_batches + 1:
                log.info(f"  Resumed: skipped {skipped_batches} completed batches")

            log.info(f"\n  Batch {batch_num}/{total_batches}")
            self._batch_extract_archives(batch)

            all_pairs = []
            for h in batch:
                if h in done_hashes:
                    continue  # Skip individual completed hashes
                pairs, fail_count = self._resolve_directive_sources(h, groups[h])
                all_pairs.extend(pairs)
                self.stats['fail'] += fail_count
            self._place_batch_parallel(all_pairs, f"Batch {batch_num}")

            # Mark batch hashes as completed
            for h in batch:
                self.state.mark_hash_done(h)
            self.state.update_stats(self.stats['ok'], self.stats['fail'])
            log.info(f"  Progress: {self.stats['ok']}/{total_d} placed, {self.stats['fail']} failed")

        log.info(f"\n=== Step 5: Installing {len(inlines)} inline files ===")
        inline_pairs = []
        remapped_count = 0
        for d in inlines:
            source_id = d.get('SourceDataID', '')
            src = self.inline_dir / source_id
            if not src.exists():
                self.stats['fail'] += 1
                continue
            # RemappedInlineFile: replace path magic strings before placing
            if d.get('$type') == 'RemappedInlineFile':
                try:
                    data = src.read_bytes()
                    remapped = self._remap_inline_content(data)
                    if remapped is not data:
                        src.write_bytes(remapped)
                        remapped_count += 1
                except OSError as e:
                    log.warning(f"  Remap failed for {source_id}: {e}")
            inline_pairs.append((src, d.get('To', '')))
        if remapped_count:
            log.info(f"  Remapped {remapped_count} inline files with actual paths")
        self._place_batch_parallel(inline_pairs, "Inline files")

        log.info(f"\n=== Step 6: Applying {len(patched)} patched files ===")
        from .octodiff import apply_delta
        patch_ok = 0
        patch_fallback = 0
        for d in patched:
            ahp = d.get('ArchiveHashPath', [])
            if not ahp:
                self.stats['fail'] += 1
                continue
            archive_hash = ahp[0]
            internal_path = '\\'.join(ahp[1:]) if len(ahp) > 1 else ''
            info = self.archive_by_hash.get(archive_hash)
            if not info:
                self.stats['fail'] += 1
                continue
            src = None
            if internal_path:
                src = self.archive_cache.find_file(info['Name'], internal_path)
            if not src:
                src = self.find_archive_path(archive_hash)
            if not src or not src.exists():
                self.stats['fail'] += 1
                continue

            to_field = d.get('To', '')
            patch_id = d.get('PatchID', '')
            dest = self.output / to_field.replace('\\', '/')

            if patch_id:
                # Apply OctoDiff delta: basis + patch -> output
                delta_path = self.inline_dir / patch_id
                if delta_path.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if apply_delta(src, delta_path, dest):
                        patch_ok += 1
                        continue
                    else:
                        log.warning(f"  Delta failed for {to_field}, falling back to base copy")

            # Fallback: copy base file (patch data missing or failed)
            if self._place_file(src, to_field):
                patch_fallback += 1
            else:
                self.stats['fail'] += 1

        log.info(f"  Patched: {patch_ok} applied, {patch_fallback} base-copy fallback, "
                 f"{self.stats['fail']} failed")

        if bsas:
            log.info(f"\n=== Step 7: BSA creation ({len(bsas)} archives) ===")
            bsa_ok = 0
            bsa_fail = 0
            for d in bsas:
                dest_name = d.get('To', 'unknown.bsa')
                file_states = d.get('FileStates', [])
                bsa_state = d.get('State', {})
                dest_path = self.output / dest_name.replace('\\', '/')

                log.info(f"  BSA: {dest_name} ({len(file_states)} files)")

                # Stage files for BSA creation
                staging, count = stage_bsa_files(d, self.archive_cache, str(self.output), str(self.cache_dir))
                if staging and count > 0:
                    if create_bsa(staging, str(dest_path), bsa_state):
                        bsa_ok += 1
                    else:
                        bsa_fail += 1
                        log.warning(f"    BSA creation failed: {dest_name}")
                else:
                    bsa_fail += 1
                    log.warning(f"    No files staged for BSA: {dest_name}")
                self.stats['bsa'] += 1

            log.info(f"  BSA: {bsa_ok} created, {bsa_fail} failed")

        log.info("\n=== Step 8: MO2 setup ===")
        self._setup_mo2()

        log.info("\n=== Step 9: Saving config ===")
        self.config.update_from_install(self)

        # Mark installation complete
        self.state.update_stats(self.stats['ok'], self.stats['fail'])
        self.state.mark_complete()

        pct = self.stats['ok'] / max(1, self.stats['ok'] + self.stats['fail']) * 100
        if HAS_RICH:
            print_install_complete(self.stats, self.hash_mismatches)
        else:
            log.info(f"\n{'='*60}")
            log.info(f"Installation complete: {self.ml.name}")
            log.info(f"  Files placed:     {self.stats['ok']}")
            log.info(f"  Failed:           {self.stats['fail']}")
            log.info(f"  BSAs needed:      {self.stats['bsa']}")
            log.info(f"  Extracted:        {self.stats['archives_extracted']}")
            log.info(f"  Success rate:     {pct:.1f}%")
            if self.hash_mismatches:
                log.warning(f"  Hash mismatches:  {len(self.hash_mismatches)}")
            log.info(f"{'='*60}")
