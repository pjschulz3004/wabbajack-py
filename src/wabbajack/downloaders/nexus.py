"""Nexus Mods downloader using the v1 API. Requires Premium for auto-download."""
import re, json, time, logging, threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import download_with_progress, USER_AGENT, MAX_RETRIES

log = logging.getLogger(__name__)

NEXUS_RATE_DELAY = 0.3


class NexusClient:
    """Nexus Mods API client for Premium download links."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.is_premium = None
        self.daily_remaining = None
        self.username = None

    def check_premium(self):
        data = self._request('users/validate.json')
        if data:
            self.is_premium = data.get('is_premium', False)
            self.username = data.get('name', '?')
            log.info(f"  Nexus user: {self.username} (Premium: {self.is_premium})")
            return self.is_premium
        return False

    def _request(self, endpoint):
        url = f"https://api.nexusmods.com/v1/{endpoint}"
        req = Request(url)
        req.add_header("apikey", self.api_key)
        req.add_header("accept", "application/json")
        for attempt in range(MAX_RETRIES):
            try:
                resp = urlopen(req, timeout=30)
                remaining = resp.headers.get('X-RL-Daily-Remaining')
                if remaining:
                    self.daily_remaining = int(remaining)
                return json.loads(resp.read())
            except HTTPError as e:
                if e.code == 429:
                    wait = min(30, 2 ** (attempt + 1))
                    log.warning(f"    Nexus rate limited on {endpoint}, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                log.debug(f"    Nexus HTTP {e.code} on {endpoint}: {e.reason}")
                return None
            except URLError as e:
                log.debug(f"    Nexus connection error on {endpoint}: {e.reason}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)
                    continue
                return None
            except (OSError, TimeoutError) as e:
                log.debug(f"    Nexus request failed on {endpoint}: {type(e).__name__}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)
                    continue
                return None
        return None

    def download_link(self, game, mod_id, file_id):
        game = game.lower()
        data = self._request(f"games/{game}/mods/{mod_id}/files/{file_id}/download_link.json")
        if data and isinstance(data, list) and data:
            return data[0].get('URI')
        return None


NEXUS_PARALLEL_DOWNLOADS = 4  # Concurrent download threads (API calls stay serialized)


def _nexus_download_one(archive, downloads_dir, nexus_client, api_lock):
    """Download a single Nexus archive. Returns (archive, success)."""
    state = archive['State']
    game = state.get('GameName', 'skyrimspecialedition')
    mod_id = state.get('ModID', 0)
    file_id = state.get('FileID', 0)

    meta = archive.get('Meta', '')
    if not mod_id:
        m = re.search(r'modID=(\d+)', meta)
        if m: mod_id = int(m.group(1))
    if not file_id:
        m = re.search(r'fileID=(\d+)', meta)
        if m: file_id = int(m.group(1))

    if not mod_id or not file_id:
        log.warning(f"    No ModID/FileID for {archive['Name']}, skipping")
        return archive, False

    dest = downloads_dir / archive['Name']
    for attempt in range(MAX_RETRIES):
        # Serialize API calls (rate-limited), parallelize actual downloads
        with api_lock:
            dl_url = nexus_client.download_link(game, mod_id, file_id)
            time.sleep(NEXUS_RATE_DELAY)
        if dl_url:
            if download_with_progress(dl_url, dest, quiet=True):
                return archive, True
        else:
            log.warning(f"    Could not get download link for {game}/mods/{mod_id}/files/{file_id}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(NEXUS_RATE_DELAY * (attempt + 2))
    return archive, False


def download_nexus_files(archives, downloads_dir, nexus_client, register_fn, failed_list):
    """Download archives from Nexus using Premium API with parallel downloads."""
    if not archives:
        return
    if not nexus_client:
        log.warning(f"SKIP {len(archives)} Nexus files (no API key)")
        failed_list.extend(archives)
        return

    if nexus_client.is_premium is None:
        nexus_client.check_premium()

    if not nexus_client.is_premium:
        log.error(f"Nexus account is NOT Premium -- cannot auto-download {len(archives)} files")
        urls_file = downloads_dir / 'nexus-manual-downloads.txt'
        with open(urls_file, 'w') as f:
            for a in archives:
                state = a['State']
                game = state.get('GameName', 'skyrimspecialedition').lower()
                mod_id = state.get('ModID', 0)
                file_id = state.get('FileID', 0)
                f.write(f"{a['Name']}\thttps://www.nexusmods.com/{game}/mods/{mod_id}"
                        f"?tab=files&file_id={file_id}\n")
        log.error(f"  Manual download URLs written to: {urls_file}")
        failed_list.extend(archives)
        return

    total_size = sum(a.get('Size', 0) for a in archives)
    log.info(f"\n--- Downloading {len(archives)} Nexus files (~{total_size/1073741824:.1f} GB) ---")
    log.info(f"  Using {NEXUS_PARALLEL_DOWNLOADS} parallel download threads")

    api_lock = threading.Lock()
    ok = 0
    completed = 0

    with ThreadPoolExecutor(max_workers=NEXUS_PARALLEL_DOWNLOADS) as pool:
        futures = {
            pool.submit(_nexus_download_one, a, downloads_dir, nexus_client, api_lock): a
            for a in archives
        }
        for future in as_completed(futures):
            completed += 1
            archive, success = future.result()
            if success:
                register_fn(archive)
                ok += 1
                size_mb = archive.get('Size', 0) / 1048576
                log.info(f"  [{completed}/{len(archives)}] OK: {archive['Name'][:70]} ({size_mb:.1f} MB)")
            else:
                failed_list.append(archive)
                log.warning(f"  [{completed}/{len(archives)}] FAIL: {archive['Name'][:70]}")

            if completed % 200 == 0:
                log.info(f"\n  === Checkpoint: {ok}/{completed} downloaded, {len(failed_list)} failed ===")
                if nexus_client.daily_remaining is not None:
                    log.info(f"  === API calls remaining: {nexus_client.daily_remaining} ===\n")

    log.info(f"  Nexus: {ok}/{len(archives)} downloaded")
