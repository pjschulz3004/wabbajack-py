"""MediaFire downloader -- scrapes direct link from page HTML."""
import re, time, logging
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import download_with_progress, USER_AGENT, MAX_RETRIES

log = logging.getLogger(__name__)

MEDIAFIRE_PARALLEL = 3


def scrape_mediafire_link(url):
    """Extract direct download link from a MediaFire page."""
    url = url.replace('%255B', '[').replace('%255D', ']')
    req = Request(url, headers={'User-Agent': USER_AGENT})
    try:
        html = urlopen(req, timeout=30).read().decode()
    except HTTPError as e:
        log.error(f"    MediaFire page HTTP {e.code}: {url}")
        return None
    except (URLError, OSError) as e:
        log.error(f"    MediaFire page unreachable ({type(e).__name__}: {e}): {url}")
        return None
    match = re.search(r'href="(https://download\d*\.mediafire\.com/[^"]+)"', html)
    if not match:
        log.debug(f"    No direct link found in MediaFire HTML ({len(html)} bytes): {url}")
    return match.group(1) if match else None


def _download_one_mediafire(archive, downloads_dir):
    """Download a single MediaFire archive. Returns (archive, success)."""
    url = archive['State'].get('Url', '')
    dest = downloads_dir / archive['Name']

    if dest.exists() and dest.stat().st_size > 0:
        return archive, True

    for attempt in range(MAX_RETRIES):
        try:
            direct = scrape_mediafire_link(url)
            if direct and download_with_progress(direct, dest, quiet=True):
                return archive, True
        except (HTTPError, URLError, OSError, TimeoutError, ValueError):
            pass
        if attempt < MAX_RETRIES - 1:
            time.sleep(3)
    return archive, False


def download_mediafire_files(archives, downloads_dir, register_fn, failed_list):
    """Download archives from MediaFire with parallel scraping."""
    if not archives:
        return
    log.info(f"\n--- Downloading {len(archives)} MediaFire files ({MEDIAFIRE_PARALLEL} parallel) ---")
    ok = 0
    completed = 0

    with ThreadPoolExecutor(max_workers=MEDIAFIRE_PARALLEL) as pool:
        futures = {pool.submit(_download_one_mediafire, a, downloads_dir): a for a in archives}
        for future in as_completed(futures):
            completed += 1
            archive, success = future.result()
            if success:
                register_fn(archive)
                ok += 1
                log.info(f"  [{completed}/{len(archives)}] OK: {archive['Name'][:70]}")
            else:
                failed_list.append(archive)
                log.warning(f"  [{completed}/{len(archives)}] FAIL: {archive['Name'][:70]}")

    log.info(f"  MediaFire: {ok}/{len(archives)} downloaded")
