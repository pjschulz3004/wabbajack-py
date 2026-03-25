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
from . import USER_AGENT, CHUNK_SIZE, DOWNLOAD_TIMEOUT, MAX_RETRIES

log = logging.getLogger(__name__)


def download_wabbajack_cdn(base_url, dest_path):
    """Download a file from WabbajackCDN using chunked protocol. Returns True on success."""
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
    downloaded = 0
    start = time.time()
    try:
        with open(dest_path, 'wb') as f:
            for part in parts:
                part_url = f"{base_url}/parts/{part['Index']}"
                part_ok = False
                for attempt in range(MAX_RETRIES):
                    try:
                        req = Request(part_url, headers={'User-Agent': USER_AGENT})
                        resp = urlopen(req, timeout=DOWNLOAD_TIMEOUT)
                        part_bytes = 0
                        while True:
                            chunk = resp.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            part_bytes += len(chunk)

                        expected_part = part.get('Size', 0)
                        if expected_part and part_bytes != expected_part:
                            log.debug(f"    Part {part['Index']} size mismatch, retrying...")
                            f.seek(part.get('Offset', downloaded - part_bytes))
                            downloaded -= part_bytes
                            continue

                        part_ok = True
                        break
                    except (HTTPError, URLError, OSError, TimeoutError) as e:
                        if attempt < MAX_RETRIES - 1:
                            log.debug(f"    Part {part['Index']} attempt {attempt+1} failed: {e}")
                            time.sleep(1)
                            f.seek(part.get('Offset', downloaded))
                            downloaded = part.get('Offset', downloaded)
                        else:
                            log.error(f"    Part {part['Index']} failed: {type(e).__name__}: {e}")

                if not part_ok:
                    dest_path.unlink(missing_ok=True)
                    return False

                elapsed = time.time() - start
                speed = downloaded / elapsed if elapsed > 0 else 0
                pct = downloaded / total_size * 100 if total_size > 0 else 0
                print(f"\r    {pct:.0f}% {downloaded/1048576:.1f}/{total_size/1048576:.1f} MB "
                      f"({speed/1048576:.1f} MB/s)  ", end="", flush=True)

    except (OSError, IOError) as e:
        log.error(f"    CDN write error ({type(e).__name__}): {e}")
        dest_path.unlink(missing_ok=True)
        return False

    elapsed = time.time() - start
    speed = downloaded / elapsed if elapsed > 0 else 0
    print(f"\r    Done: {downloaded/1048576:.1f} MB ({speed/1048576:.1f} MB/s)       ")

    actual = dest_path.stat().st_size
    if total_size > 0 and actual != total_size:
        log.error(f"    Size mismatch (got {actual}, expected {total_size})")
        dest_path.unlink(missing_ok=True)
        return False
    return True
