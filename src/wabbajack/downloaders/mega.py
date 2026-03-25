"""Mega.nz downloader using megadl CLI."""
import subprocess, logging
from . import MAX_RETRIES

log = logging.getLogger(__name__)


def download_mega_files(archives, downloads_dir, is_present_fn, register_fn, failed_list):
    """Download archives from Mega using megadl CLI."""
    if not archives:
        return
    log.info(f"\n--- Downloading {len(archives)} Mega files ---")
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

        try:
            result = subprocess.run(
                ['megadl', '--path', str(downloads_dir), '--', url],
                capture_output=True, timeout=3600
            )
            if result.returncode != 0:
                err = result.stderr.decode(errors='replace')[:200]
                log.error(f"    megadl exit {result.returncode}: {err}")
                failed_list.append(a)
                continue
            if is_present_fn(a):
                register_fn(a)
                ok += 1
            else:
                log.warning(f"    megadl succeeded but file not found at expected name")
                failed_list.append(a)
        except FileNotFoundError:
            log.error("    megadl not installed (pip install megatools / yay -S megatools)")
            failed_list.append(a)
            break
        except subprocess.TimeoutExpired:
            log.error(f"    Mega download timed out (1 hour): {url}")
            failed_list.append(a)
        except (OSError, subprocess.SubprocessError) as e:
            log.error(f"    Mega {type(e).__name__} for {url}: {e}")
            failed_list.append(a)

    log.info(f"  Mega: {ok}/{len(archives)} downloaded")
