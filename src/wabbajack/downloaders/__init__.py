"""Download handlers for all Wabbajack archive source types."""
import logging, time
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

log = logging.getLogger(__name__)

USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0'
CHUNK_SIZE = 256 * 1024
DOWNLOAD_TIMEOUT = 600
MAX_RETRIES = 3

# Per-thread sessions for HTTP connection reuse (thread-safe)
import threading as _thr
_thread_local = _thr.local()


def _get_session():
    """Get or create a per-thread requests.Session with connection pooling."""
    session = getattr(_thread_local, 'session', None)
    if session is None:
        try:
            import requests
            from requests.adapters import HTTPAdapter
            session = requests.Session()
            session.headers['User-Agent'] = USER_AGENT
            adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            _thread_local.session = session
        except ImportError:
            return None
    return session


def validate_url_scheme(url):
    """Reject non-HTTP(S) URLs to prevent SSRF (file://, ftp://, etc.)."""
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme.lower() not in ('http', 'https'):
        raise ValueError(f"Unsafe URL scheme '{parsed.scheme}': {url}")
    return url


def download_with_progress(url, dest_path, timeout=DOWNLOAD_TIMEOUT, quiet=False):
    """Download a URL to a file with progress bar and connection reuse."""
    validate_url_scheme(url)

    if '%' not in url:
        parsed = urlparse(url)
        encoded_path = quote(parsed.path, safe='/:@!$&\'()*+,;=-._~[]')
        url = urlunparse(parsed._replace(path=encoded_path))

    session = _get_session()

    # Try requests first (connection reuse), fall back to urllib
    if session is not None:
        return _download_requests(session, url, dest_path, timeout, quiet)
    return _download_urllib(url, dest_path, timeout, quiet)


def _download_requests(session, url, dest_path, timeout, quiet):
    """Download using requests.Session with resume support and connection pooling."""
    dest = Path(dest_path)
    headers = {}
    mode = 'wb'
    resume_offset = 0

    # Resume partial download if .part file exists
    part_path = dest.with_suffix(dest.suffix + '.part')
    if part_path.exists():
        resume_offset = part_path.stat().st_size
        if resume_offset > 0:
            headers['Range'] = f'bytes={resume_offset}-'
            mode = 'ab'
            if not quiet:
                log.debug(f"    Resuming from {resume_offset/1048576:.1f} MB")

    try:
        resp = session.get(url, stream=True, timeout=timeout, allow_redirects=True,
                           headers=headers)
        resp.raise_for_status()

        # Handle resume response
        if resp.status_code == 206:  # Partial content -- resume worked
            total = int(resp.headers.get('Content-Range', '').split('/')[-1] or 0)
        else:
            total = int(resp.headers.get('Content-Length', 0))
            resume_offset = 0  # Server doesn't support resume
            mode = 'wb'

        downloaded = resume_offset
        start = time.time()
        with open(part_path, mode) as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if not quiet:
                        elapsed = time.time() - start
                        speed = (downloaded - resume_offset) / elapsed if elapsed > 0 else 0
                        if total > 0:
                            pct = downloaded / total * 100
                            eta = (total - downloaded) / speed if speed > 0 else 0
                            print(f"\r    {pct:.0f}% {downloaded/1048576:.1f}/{total/1048576:.1f} MB "
                                  f"({speed/1048576:.1f} MB/s, ETA {eta:.0f}s)  ", end="", flush=True)
                        else:
                            print(f"\r    {downloaded/1048576:.1f} MB ({speed/1048576:.1f} MB/s)  ",
                                  end="", flush=True)

        # Rename .part to final name on success
        part_path.rename(dest)
        if not quiet:
            elapsed = time.time() - start
            speed = (downloaded - resume_offset) / elapsed if elapsed > 0 else 0
            print(f"\r    Done: {downloaded/1048576:.1f} MB ({speed/1048576:.1f} MB/s)       ")
        return True
    except Exception as e:
        if not quiet:
            status = getattr(getattr(e, 'response', None), 'status_code', '')
            if status:
                log.error(f"    Download HTTP {status}: {url}")
            else:
                log.error(f"    Download {type(e).__name__}: {e} -- {url}")
        # Keep .part file for resume on retry -- only delete if empty
        if part_path.exists() and part_path.stat().st_size == 0:
            part_path.unlink(missing_ok=True)
        return False


def _download_urllib(url, dest_path, timeout, quiet):
    """Fallback download using urllib (no connection reuse)."""
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError

    req = Request(url, headers={'User-Agent': USER_AGENT})
    try:
        resp = urlopen(req, timeout=timeout)
        total = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        start = time.time()
        with open(dest_path, 'wb') as f:
            while True:
                chunk = resp.read(CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if not quiet:
                    elapsed = time.time() - start
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    if total > 0:
                        pct = downloaded / total * 100
                        eta = (total - downloaded) / speed if speed > 0 else 0
                        print(f"\r    {pct:.0f}% {downloaded/1048576:.1f}/{total/1048576:.1f} MB "
                              f"({speed/1048576:.1f} MB/s, ETA {eta:.0f}s)  ", end="", flush=True)
                    else:
                        print(f"\r    {downloaded/1048576:.1f} MB ({speed/1048576:.1f} MB/s)  ",
                              end="", flush=True)
        if not quiet:
            elapsed = time.time() - start
            speed = downloaded / elapsed if elapsed > 0 else 0
            print(f"\r    Done: {downloaded/1048576:.1f} MB ({speed/1048576:.1f} MB/s)       ")
        return True
    except HTTPError as e:
        if not quiet:
            log.error(f"    Download HTTP {e.code} ({e.reason}): {url}")
        Path(dest_path).unlink(missing_ok=True)
        return False
    except URLError as e:
        if not quiet:
            log.error(f"    Download connection error ({e.reason}): {url}")
        Path(dest_path).unlink(missing_ok=True)
        return False
    except (OSError, TimeoutError) as e:
        if not quiet:
            log.error(f"    Download {type(e).__name__}: {e} -- {url}")
        try:
            p = Path(dest_path)
            if p.exists() and p.stat().st_size == 0:
                p.unlink()
        except OSError:
            pass
        return False


# Convenience type-dispatch mapping (downloader $type -> handler key)
TYPE_MAP = {
    'GameFileSource': 'game',
    'WabbajackCDN': 'http',
    'HttpDownloader': 'http',
    'MediaFire': 'mediafire',
    'MegaDownloader': 'mega',
    'GoogleDrive': 'gdrive',
    'NexusDownloader': 'nexus',
    'ModDB': 'moddb',
    'ManualDownloader': 'manual',
}


def classify_archive(archive):
    """Return the handler key for an archive based on its State.$type."""
    state_type = archive.get('State', {}).get('$type', '')
    for key, handler in TYPE_MAP.items():
        if key in state_type:
            return handler
    return 'unknown'
