"""Google Drive downloader -- gdown CLI preferred, urllib fallback."""
import re, subprocess, time, logging
from pathlib import Path
from urllib.request import build_opener, HTTPCookieProcessor
from urllib.error import HTTPError, URLError
from http.cookiejar import CookieJar
from . import download_with_progress, USER_AGENT, CHUNK_SIZE, DOWNLOAD_TIMEOUT

log = logging.getLogger(__name__)


def _download_gdrive_urllib(file_id, dest_path):
    """Download from Google Drive with virus scan confirmation handling."""
    url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
    cj = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cj))
    opener.addheaders = [('User-Agent', USER_AGENT)]

    try:
        resp = opener.open(url, timeout=DOWNLOAD_TIMEOUT)
        content_type = resp.headers.get('Content-Type', '')

        if 'text/html' in content_type:
            html = resp.read().decode('utf-8', errors='replace')
            match = re.search(r'action="([^"]+)"', html)
            if match:
                action = match.group(1).replace('&amp;', '&')
                if not action.startswith('http'):
                    action = 'https://drive.google.com' + action
                resp = opener.open(action, timeout=DOWNLOAD_TIMEOUT)
            else:
                match = re.search(r'confirm=([a-zA-Z0-9_-]+)', html)
                if match:
                    resp = opener.open(
                        f"https://drive.google.com/uc?export=download&id={file_id}&confirm={match.group(1)}",
                        timeout=DOWNLOAD_TIMEOUT
                    )
                else:
                    return False

        total = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        start = time.time()
        dest_path = Path(dest_path)
        with open(dest_path, 'wb') as f:
            while True:
                chunk = resp.read(CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                elapsed = time.time() - start
                speed = downloaded / elapsed if elapsed > 0 else 0
                if total > 0:
                    pct = downloaded / total * 100
                    print(f"\r    {pct:.0f}% {downloaded/1048576:.1f}/{total/1048576:.1f} MB "
                          f"({speed/1048576:.1f} MB/s)  ", end="", flush=True)
                else:
                    print(f"\r    {downloaded/1048576:.1f} MB ({speed/1048576:.1f} MB/s)  ",
                          end="", flush=True)
        print()
        return dest_path.exists() and dest_path.stat().st_size > 1000
    except (HTTPError, URLError, OSError) as e:
        log.error(f"    Google Drive urllib failed for id={file_id}: {type(e).__name__}: {e}")
        return False


def download_gdrive_files(archives, downloads_dir, register_fn, failed_list):
    """Download archives from Google Drive via gdown or urllib fallback."""
    if not archives:
        return
    log.info(f"\n--- Downloading {len(archives)} Google Drive files ---")
    ok = 0
    for i, a in enumerate(archives):
        file_id = a['State'].get('Id', '')
        dest = downloads_dir / a['Name']
        size_mb = a.get('Size', 0) / 1048576
        log.info(f"  [{i+1}/{len(archives)}] {a['Name']} ({size_mb:.1f} MB)")

        if dest.exists() and dest.stat().st_size > 0:
            log.info(f"    Already exists")
            register_fn(a)
            ok += 1
            continue

        # Try gdown first
        success = False
        try:
            result = subprocess.run(
                ['gdown', '--id', file_id, '-O', str(dest)],
                timeout=600
            )
            if result.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
                register_fn(a)
                ok += 1
                success = True
        except FileNotFoundError:
            log.debug("    gdown not installed, trying urllib fallback")
        except subprocess.TimeoutExpired:
            log.warning(f"    gdown timed out for id={file_id}")
        except (OSError, subprocess.SubprocessError) as e:
            log.debug(f"    gdown failed for id={file_id}: {type(e).__name__}: {e}")

        if success:
            continue

        # Fallback: urllib
        log.info("    Trying direct download...")
        if _download_gdrive_urllib(file_id, dest):
            register_fn(a)
            ok += 1
        else:
            log.warning(f"    FAILED -- download manually: gdown --id {file_id} -O '{dest}'")
            failed_list.append(a)

    log.info(f"  Google Drive: {ok}/{len(archives)} downloaded")
