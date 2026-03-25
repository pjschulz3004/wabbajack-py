"""WabbajackCDN chunked download protocol.

Files on authored-files.wabbajack.org are stored as multiple 2MB parts:
  {url}/definition.json.gz   -- gzipped JSON manifest with part list
  {url}/parts/{index}        -- raw bytes for each part

HEAD returns 404 (Cloudflare quirk), only GET works.
No authentication required.
"""
import gzip, json, time, logging
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import USER_AGENT, DOWNLOAD_TIMEOUT, MAX_RETRIES

log = logging.getLogger(__name__)

CDN_PARALLEL_PARTS = 4


def _download_part(base_url, part):
    """Download a single CDN part. Returns (index, offset, data) or (index, offset, None)."""
    part_url = f"{base_url}/parts/{part['Index']}"
    for attempt in range(MAX_RETRIES):
        try:
            req = Request(part_url, headers={'User-Agent': USER_AGENT})
            resp = urlopen(req, timeout=DOWNLOAD_TIMEOUT)
            data = resp.read()
            expected = part.get('Size', 0)
            if expected and len(data) != expected:
                log.debug(f"    Part {part['Index']} size mismatch ({len(data)} vs {expected}), retrying...")
                continue
            return part['Index'], part.get('Offset', 0), data
        except (HTTPError, URLError, OSError, TimeoutError) as e:
            if attempt < MAX_RETRIES - 1:
                log.debug(f"    Part {part['Index']} attempt {attempt+1} failed: {e}")
                time.sleep(1)
            else:
                log.error(f"    Part {part['Index']} failed: {type(e).__name__}: {e}")
    return part['Index'], part.get('Offset', 0), None


def download_wabbajack_cdn(base_url, dest_path):
    """Download a file from WabbajackCDN using chunked protocol with parallel parts."""
    def_url = f"{base_url}/definition.json.gz"
    req = Request(def_url, headers={'User-Agent': USER_AGENT})

    try:
        resp = urlopen(req, timeout=30)
        raw = resp.read()
        definition = json.loads(gzip.decompress(raw))
    except HTTPError as e:
        log.error(f"    CDN definition HTTP {e.code}: {def_url}")
        return False
    except (URLError, OSError, TimeoutError) as e:
        log.error(f"    CDN definition connection failed ({type(e).__name__}): {def_url}")
        return False
    except (gzip.BadGzipFile, json.JSONDecodeError, ValueError) as e:
        log.error(f"    CDN definition parse failed ({type(e).__name__}: {e}): {def_url}")
        return False

    parts = sorted(definition.get('Parts', []), key=lambda p: p['Index'])
    total_size = definition.get('Size', 0)
    orig_name = definition.get('OriginalFileName', '?')
    log.info(f"    CDN: {orig_name} ({total_size/1048576:.1f} MB, {len(parts)} parts)")

    if not parts:
        log.error(f"    CDN definition has no parts: {def_url}")
        return False

    dest_path = Path(dest_path)
    start = time.time()

    # Download parts in parallel, then write sequentially by offset
    workers = min(CDN_PARALLEL_PARTS, len(parts))
    part_data = {}
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_download_part, base_url, p): p for p in parts}
            for future in as_completed(futures):
                idx, offset, data = future.result()
                if data is None:
                    dest_path.unlink(missing_ok=True)
                    return False
                part_data[idx] = (offset, data)

        # Write in order
        with open(dest_path, 'wb') as f:
            for part in parts:
                offset, data = part_data[part['Index']]
                f.write(data)

    except (OSError, IOError) as e:
        log.error(f"    CDN write error ({type(e).__name__}): {e}")
        dest_path.unlink(missing_ok=True)
        return False

    elapsed = time.time() - start
    actual = dest_path.stat().st_size
    speed = actual / elapsed if elapsed > 0 else 0
    print(f"\r    Done: {actual/1048576:.1f} MB ({speed/1048576:.1f} MB/s)       ")

    if total_size > 0 and actual != total_size:
        log.error(f"    Size mismatch (got {actual}, expected {total_size})")
        dest_path.unlink(missing_ok=True)
        return False
    return True
