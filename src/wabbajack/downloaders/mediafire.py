"""MediaFire downloader -- scrapes direct link from page HTML."""
import re, time, logging
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from . import download_with_progress, USER_AGENT, MAX_RETRIES

log = logging.getLogger(__name__)


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


def download_mediafire_files(archives, downloads_dir, register_fn, failed_list):
    """Download archives from MediaFire by scraping direct links."""
    if not archives:
        return
    log.info(f"\n--- Downloading {len(archives)} MediaFire files ---")
    ok = 0
    for i, a in enumerate(archives):
        url = a['State'].get('Url', '')
        dest = downloads_dir / a['Name']
        log.info(f"  [{i+1}/{len(archives)}] {a['Name']}")

        success = False
        for attempt in range(MAX_RETRIES):
            try:
                direct = scrape_mediafire_link(url)
                if direct and download_with_progress(direct, dest):
                    register_fn(a)
                    ok += 1
                    success = True
                    break
                elif not direct:
                    log.warning(f"    Could not scrape direct link from: {url}")
            except (HTTPError, URLError, OSError, TimeoutError, ValueError) as e:
                log.error(f"    MediaFire error for {url}: {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES - 1:
                log.info(f"    Retry {attempt+2}/{MAX_RETRIES}...")
                time.sleep(3)
        if not success:
            failed_list.append(a)

    log.info(f"  MediaFire: {ok}/{len(archives)} downloaded")
