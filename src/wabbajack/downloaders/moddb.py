"""ModDB downloader -- scrapes mirror list from download page."""
import re, time, logging
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from . import download_with_progress, USER_AGENT, MAX_RETRIES

log = logging.getLogger(__name__)


def _scrape_moddb_mirrors(url):
    """Extract mirror download links from a ModDB download page."""
    # ModDB download pages redirect to a mirror selection page
    req = Request(url, headers={'User-Agent': USER_AGENT})
    try:
        html = urlopen(req, timeout=30).read().decode('utf-8', errors='replace')
    except HTTPError as e:
        log.error(f"    ModDB page HTTP {e.code}: {url}")
        return []
    except (URLError, OSError) as e:
        log.error(f"    ModDB page unreachable ({type(e).__name__}: {e}): {url}")
        return []

    # Look for mirror links -- ModDB uses /downloads/mirror/<id>/ pattern
    mirrors = re.findall(r'href="(https?://(?:www\.)?moddb\.com/downloads/mirror/[^"]+)"', html)
    if not mirrors:
        # Fallback: look for direct download links
        mirrors = re.findall(r'href="(https?://(?:www\.)?moddb\.com/mods/[^"]*download[^"]*)"', html)
    if not mirrors:
        # Try meta refresh or redirect patterns
        meta = re.search(r'<meta[^>]*url=(https?://[^"\'>\s]+)', html, re.IGNORECASE)
        if meta:
            mirrors = [meta.group(1)]
    return mirrors


def _follow_moddb_mirror(mirror_url):
    """Follow a ModDB mirror URL to get the actual download link."""
    req = Request(mirror_url, headers={'User-Agent': USER_AGENT})
    try:
        resp = urlopen(req, timeout=30)
        # ModDB mirrors redirect to the actual file URL
        return resp.url
    except (HTTPError, URLError, OSError) as e:
        log.debug(f"    Mirror redirect failed: {mirror_url}: {type(e).__name__}: {e}")
        return None


def download_moddb_files(archives, downloads_dir, register_fn, failed_list):
    """Download archives from ModDB by scraping mirror links."""
    if not archives:
        return
    log.info(f"\n--- Downloading {len(archives)} ModDB files ---")
    ok = 0
    for i, a in enumerate(archives):
        url = a['State'].get('Url', '')
        dest = downloads_dir / a['Name']
        log.info(f"  [{i+1}/{len(archives)}] {a['Name']}")

        if dest.exists() and dest.stat().st_size > 0:
            log.info(f"    Already exists ({dest.stat().st_size/1048576:.1f} MB)")
            register_fn(a)
            ok += 1
            continue

        success = False
        for attempt in range(MAX_RETRIES):
            mirrors = _scrape_moddb_mirrors(url)
            if not mirrors:
                log.warning(f"    No mirrors found for: {url}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(3)
                continue

            # Try each mirror until one works
            for mirror in mirrors[:3]:  # Try up to 3 mirrors
                direct = _follow_moddb_mirror(mirror)
                if direct and download_with_progress(direct, dest):
                    register_fn(a)
                    ok += 1
                    success = True
                    break
            if success:
                break
            if attempt < MAX_RETRIES - 1:
                log.info(f"    Retry {attempt+2}/{MAX_RETRIES}...")
                time.sleep(3)

        if not success:
            log.warning(f"    FAILED: {a['Name']} -- download manually from: {url}")
            failed_list.append(a)

    log.info(f"  ModDB: {ok}/{len(archives)} downloaded")
