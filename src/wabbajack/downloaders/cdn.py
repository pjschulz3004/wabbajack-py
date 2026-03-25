"""WabbajackCDN chunked download protocol.

Files on authored-files.wabbajack.org are stored as multiple 2MB parts:
  {url}/definition.json.gz   -- gzipped JSON manifest with part list
  {url}/parts/{index}        -- raw bytes for each part

HEAD returns 404 (Cloudflare quirk), only GET works.
No authentication required.
"""
import gzip, json, time, logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import USER_AGENT, DOWNLOAD_TIMEOUT, MAX_RETRIES, _get_session

log = logging.getLogger(__name__)

CDN_PARALLEL_PARTS = 4


def _download_part(base_url, part):
    """Download a single CDN part. Returns (index, offset, data) or (index, offset, None).

    Uses requests.Session for HTTP connection reuse (avoids TCP+TLS handshake per part).
    """
    part_url = f"{base_url}/parts/{part['Index']}"
    session = _get_session()
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(part_url, timeout=DOWNLOAD_TIMEOUT)
            resp.raise_for_status()
            data = resp.content
            expected = part.get('Size', 0)
            if expected and len(data) != expected:
                log.debug(f"    Part {part['Index']} size mismatch ({len(data)} vs {expected}), retrying...")
                continue
            return part['Index'], part.get('Offset', 0), data
        except (OSError, TimeoutError, Exception) as e:
            if attempt < MAX_RETRIES - 1:
                log.debug(f"    Part {part['Index']} attempt {attempt+1} failed: {e}")
                time.sleep(1)
            else:
                log.error(f"    Part {part['Index']} failed: {type(e).__name__}: {e}")
    return part['Index'], part.get('Offset', 0), None


def download_wabbajack_cdn(base_url, dest_path):
    """Download a file from WabbajackCDN using chunked protocol with parallel parts."""
    def_url = f"{base_url}/definition.json.gz"
    session = _get_session()

    try:
        resp = session.get(def_url, timeout=30)
        resp.raise_for_status()
        definition = json.loads(gzip.decompress(resp.content))
    except Exception as e:
        if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
            log.error(f"    CDN definition HTTP {e.response.status_code}: {def_url}")
        else:
            log.error(f"    CDN definition failed ({type(e).__name__}): {def_url}")
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

    # Pre-allocate output file, write parts directly at their offsets
    # This avoids holding all part data in memory (was O(file_size), now O(chunk_size * workers))
    import threading as _thr
    write_lock = _thr.Lock()
    failed = False

    def _download_and_write(part, f):
        nonlocal failed
        if failed:
            return
        _idx, _offset, data = _download_part(base_url, part)
        if data is None:
            failed = True
            return
        with write_lock:
            f.seek(part.get('Offset', 0))
            f.write(data)

    workers = min(CDN_PARALLEL_PARTS, len(parts))
    try:
        with open(dest_path, 'wb') as f:
            # Pre-allocate file size
            if total_size > 0:
                f.seek(total_size - 1)
                f.write(b'\0')
                f.seek(0)

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_download_and_write, p, f) for p in parts]
                for fut in as_completed(futures):
                    fut.result()  # Propagate exceptions

        if failed:
            dest_path.unlink(missing_ok=True)
            return False

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
