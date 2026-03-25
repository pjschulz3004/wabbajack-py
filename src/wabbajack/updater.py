"""Self-update logic for wabbajack-py."""
import logging, os, platform, shutil, subprocess, sys, tempfile
from pathlib import Path
from packaging.version import Version

from . import __version__

log = logging.getLogger(__name__)

GITHUB_REPO = "wabbajack-tools/wabbajack-py"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CURRENT_VERSION = __version__


def _is_frozen() -> bool:
    """Running as PyInstaller bundle?"""
    return getattr(sys, 'frozen', False)


def _is_pip_install() -> bool:
    """Installed via pip (not dev/editable)?"""
    try:
        from importlib.metadata import distribution
        dist = distribution('wabbajack-py')
        return dist is not None
    except Exception:
        return False


def get_install_type() -> str:
    if _is_frozen():
        return 'binary'
    if _is_pip_install():
        return 'pip'
    return 'dev'


def check_for_update(timeout: int = 10) -> dict:
    """Check GitHub releases for a newer version.

    Returns dict with: current, latest, update_available, download_url, release_url, changelog
    """
    import requests

    result = {
        'current': CURRENT_VERSION,
        'latest': CURRENT_VERSION,
        'update_available': False,
        'install_type': get_install_type(),
        'download_url': None,
        'release_url': None,
        'changelog': '',
    }

    try:
        resp = requests.get(GITHUB_API, timeout=timeout, headers={
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': f'wabbajack-py/{CURRENT_VERSION}',
        })
        if resp.status_code == 404:
            # No releases yet
            return result
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.debug(f"Update check failed: {e}")
        result['error'] = str(e)
        return result

    tag = data.get('tag_name', '').lstrip('v')
    if not tag:
        return result

    result['latest'] = tag
    result['release_url'] = data.get('html_url', '')
    result['changelog'] = data.get('body', '')[:2000]

    try:
        if Version(tag) > Version(CURRENT_VERSION):
            result['update_available'] = True

            # Find matching asset for this platform
            system = platform.system().lower()
            assets = data.get('assets', [])
            for asset in assets:
                name = asset['name'].lower()
                if system == 'linux' and ('linux' in name or 'appimage' in name):
                    result['download_url'] = asset['browser_download_url']
                    break
                elif system == 'windows' and ('windows' in name or '.exe' in name):
                    result['download_url'] = asset['browser_download_url']
                    break
                elif system == 'darwin' and ('macos' in name or 'darwin' in name):
                    result['download_url'] = asset['browser_download_url']
                    break
    except Exception:
        pass

    return result


def apply_update(info: dict | None = None) -> dict:
    """Apply an available update. Returns status dict."""
    if info is None:
        info = check_for_update()

    if not info.get('update_available'):
        return {'success': False, 'message': 'Already up to date'}

    install_type = info['install_type']

    if install_type == 'pip':
        return _update_pip()
    elif install_type == 'binary':
        if info.get('download_url'):
            return _update_binary(info['download_url'])
        return {'success': False, 'message': 'No binary available for this platform'}
    else:
        return {'success': False, 'message': 'Dev install -- use git pull instead'}


def _update_pip() -> dict:
    """Update via pip."""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'wabbajack-py'],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return {
                'success': True,
                'message': 'Updated via pip. Restart to use new version.',
                'restart_required': True,
            }
        return {'success': False, 'message': f'pip upgrade failed: {result.stderr[:500]}'}
    except Exception as e:
        return {'success': False, 'message': str(e)}


def _update_binary(download_url: str) -> dict:
    """Download and replace the running binary."""
    import requests

    current_exe = Path(sys.executable)
    if not current_exe.exists():
        return {'success': False, 'message': 'Cannot find current executable'}

    try:
        # Download to temp file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=current_exe.suffix, dir=current_exe.parent)
        log.info(f"Downloading update from {download_url}")

        with requests.get(download_url, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                tmp.write(chunk)
        tmp.close()

        # Make executable
        os.chmod(tmp.name, 0o755)

        # Swap: current -> .old, new -> current
        backup = current_exe.with_suffix(current_exe.suffix + '.old')  # type: Path
        backup.unlink(missing_ok=True)
        current_exe.rename(backup)
        shutil.move(tmp.name, str(current_exe))

        return {
            'success': True,
            'message': 'Binary updated. Restart to use new version.',
            'restart_required': True,
        }
    except Exception as e:
        # Restore backup if swap failed
        try:
            if backup.exists() and not current_exe.exists():
                backup.rename(current_exe)
        except Exception:
            pass
        return {'success': False, 'message': f'Binary update failed: {e}'}
