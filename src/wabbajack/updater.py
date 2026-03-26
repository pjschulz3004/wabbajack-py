"""Self-update logic for wabbajack-py."""
import logging, os, platform, re, shutil, subprocess, sys, tempfile
from pathlib import Path

from . import __version__

log = logging.getLogger(__name__)

GITHUB_REPO = "pjschulz3004/wabbajack-py"
GITHUB_API_RELEASES = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_API_COMMITS = f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"
CURRENT_VERSION = __version__

# Strict pattern for git refspecs: alphanumeric, dots, slashes, hyphens, underscores
_SAFE_REFSPEC = re.compile(r'^[A-Za-z0-9._/\-]{1,200}$')


def _sanitize_upstream(upstream: str) -> str:
    """Validate and sanitize a git upstream refspec. Falls back to origin/master."""
    upstream = upstream.strip()
    if not upstream or not _SAFE_REFSPEC.match(upstream) or upstream.startswith('-'):
        return 'origin/master'
    return upstream


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


def _find_git_root() -> Path | None:
    """Find the git root of the project (for dev installs)."""
    # Walk up from the package source
    pkg_dir = Path(__file__).resolve().parent  # src/wabbajack/
    for parent in [pkg_dir, pkg_dir.parent, pkg_dir.parent.parent]:
        if (parent / '.git').exists():
            return parent
    return None


def get_install_type() -> str:
    if _is_frozen():
        return 'binary'
    if _find_git_root():
        return 'dev'
    if _is_pip_install():
        return 'pip'
    return 'dev'


def check_for_update(timeout: int = 10) -> dict:
    """Check for updates. For dev installs, checks git commits. For releases, checks GitHub releases."""
    install_type = get_install_type()

    if install_type == 'dev':
        return _check_dev_update(timeout)
    return _check_release_update(timeout)


def _check_dev_update(timeout: int) -> dict:
    """Check if there are new commits on the remote."""
    git_root = _find_git_root()
    result = {
        'current': CURRENT_VERSION,
        'latest': CURRENT_VERSION,
        'update_available': False,
        'install_type': 'dev',
        'download_url': None,
        'release_url': f'https://github.com/{GITHUB_REPO}',
        'changelog': '',
        'git_root': str(git_root) if git_root else None,
    }

    if not git_root:
        result['error'] = 'Cannot find git root directory'
        return result

    try:
        # Get local HEAD commit
        local = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, timeout=5, cwd=git_root,
        )
        local_sha = local.stdout.strip()[:7]

        # Detect tracking branch
        tracking = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'],
            capture_output=True, text=True, timeout=5, cwd=git_root,
        )
        upstream = _sanitize_upstream(
            tracking.stdout if tracking.returncode == 0 else 'origin/master'
        )

        # Fetch remote (use -- to prevent argument injection)
        remote = upstream.split('/')[0] if '/' in upstream else 'origin'
        subprocess.run(
            ['git', 'fetch', '--', remote],
            capture_output=True, timeout=timeout, cwd=git_root,
        )

        # Compare local vs remote
        # NOTE: '--' separates paths from revisions in rev-list/log.
        # Placing it BEFORE the revision range breaks the command (treats range as path).
        # _sanitize_upstream() already prevents argument injection via regex + startswith('-') check.
        behind = subprocess.run(
            ['git', 'rev-list', '--count', f'HEAD..{upstream}'],
            capture_output=True, text=True, timeout=5, cwd=git_root,
        )
        behind_count = int(behind.stdout.strip()) if behind.returncode == 0 else 0

        result['current'] = f'{CURRENT_VERSION} ({local_sha})'

        if behind_count > 0:
            result['update_available'] = True
            result['latest'] = f'{behind_count} new commits'
            # Get commit log for changelog
            changelog = subprocess.run(
                ['git', 'log', '--oneline', '--max-count=20', f'HEAD..{upstream}'],
                capture_output=True, text=True, timeout=5, cwd=git_root,
            )
            result['changelog'] = changelog.stdout.strip()
        else:
            result['latest'] = f'{CURRENT_VERSION} (up to date)'

    except Exception as e:
        result['error'] = str(e)

    return result


def _check_release_update(timeout: int) -> dict:
    """Check GitHub releases for a newer version."""
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
        resp = requests.get(GITHUB_API_RELEASES, timeout=timeout, headers={
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': f'wabbajack-py/{CURRENT_VERSION}',
        })
        if resp.status_code == 404:
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
        from packaging.version import Version
    except ImportError:
        log.debug("packaging not installed; skipping version comparison")
        return result

    try:
        if Version(tag) > Version(CURRENT_VERSION):
            result['update_available'] = True
            system = platform.system().lower()
            for asset in data.get('assets', []):
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
    except Exception as e:
        log.warning(f"Version comparison failed (tag={tag!r}): {e}")
        result['error'] = str(e)

    return result


def apply_update(info: dict | None = None, progress_fn=None) -> dict:
    """Apply an available update. Returns status dict.

    progress_fn: Optional callback(step: str, message: str, pct: int) for progress reporting.
    """
    if info is None:
        info = check_for_update()

    if not info.get('update_available'):
        return {'success': False, 'message': 'Already up to date'}

    install_type = info.get('install_type', get_install_type())

    if install_type == 'dev':
        return _update_dev(progress_fn=progress_fn)
    elif install_type == 'pip':
        return _update_pip(progress_fn=progress_fn)
    elif install_type == 'binary':
        if info.get('download_url'):
            return _update_binary(info['download_url'], progress_fn=progress_fn)
        return {'success': False, 'message': 'No binary available for this platform'}
    return {'success': False, 'message': f'Unknown install type: {install_type}'}


def _update_dev(progress_fn=None) -> dict:
    """Update dev install: git pull + pip install -e . + rebuild frontend."""
    git_root = _find_git_root()
    if not git_root:
        return {'success': False, 'message': 'Cannot find git root directory'}

    def progress(step, message, pct):
        if progress_fn:
            progress_fn(step, message, pct)

    try:
        # Fetch remote
        progress("fetch", "Fetching from GitHub...", 10)
        tracking = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'],
            capture_output=True, text=True, timeout=5, cwd=git_root,
        )
        upstream = _sanitize_upstream(
            tracking.stdout if tracking.returncode == 0 else 'origin/master'
        )
        remote = upstream.split('/')[0] if '/' in upstream else 'origin'

        subprocess.run(
            ['git', 'fetch', '--', remote],
            capture_output=True, timeout=30, cwd=git_root,
        )

        # Pull changes
        progress("pull", "Pulling changes...", 30)
        pull = subprocess.run(
            ['git', 'pull', '--ff-only'],
            capture_output=True, text=True, timeout=30, cwd=git_root,
        )
        if pull.returncode != 0:
            return {'success': False, 'message': f'git pull failed: {pull.stderr[:500]}'}

        # Reinstall in editable mode
        progress("install", "Installing dependencies...", 50)
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-e', str(git_root), '--quiet'],
            capture_output=True, text=True, timeout=120, cwd=git_root,
        )

        # Rebuild frontend
        progress("build", "Building frontend...", 70)
        frontend_dir = git_root / 'frontend'
        if frontend_dir.exists() and (frontend_dir / 'package.json').exists():
            subprocess.run(
                ['npm', 'install', '--silent'],
                capture_output=True, timeout=60, cwd=frontend_dir,
            )
            subprocess.run(
                ['npx', 'vite', 'build', '--quiet'],
                capture_output=True, timeout=120, cwd=frontend_dir,
            )
            # Copy built files to static dir for serving
            static_dir = git_root / 'src' / 'wabbajack' / 'web' / 'static'
            static_dir.mkdir(parents=True, exist_ok=True)
            dist_dir = frontend_dir / 'dist'
            if dist_dir.exists():
                for item in dist_dir.iterdir():
                    dest = static_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest)

        progress("done", "Update complete!", 100)

        commits = pull.stdout.strip()
        return {
            'success': True,
            'message': f'Updated successfully. {commits}',
            'restart_required': True,
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}


def _update_pip(progress_fn=None) -> dict:
    """Update via pip."""
    if progress_fn:
        progress_fn("install", "Upgrading via pip...", 50)
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'wabbajack-py'],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            if progress_fn:
                progress_fn("done", "Update complete!", 100)
            return {
                'success': True,
                'message': 'Updated via pip.',
                'restart_required': True,
            }
        return {'success': False, 'message': f'pip upgrade failed: {result.stderr[:500]}'}
    except Exception as e:
        return {'success': False, 'message': str(e)}


def _update_binary(download_url: str, progress_fn=None) -> dict:
    """Download and replace the running binary."""
    import requests

    if progress_fn:
        progress_fn("download", "Downloading binary...", 30)

    current_exe = Path(sys.executable)
    if not current_exe.exists():
        return {'success': False, 'message': 'Cannot find current executable'}

    backup = None
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=current_exe.suffix, dir=current_exe.parent)
        log.info(f"Downloading update from {download_url}")

        import hashlib
        sha256 = hashlib.sha256()
        with requests.get(download_url, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                tmp.write(chunk)
                sha256.update(chunk)
        tmp.close()
        actual_hash = sha256.hexdigest()

        # Verify checksum against .sha256 sidecar file
        sha_url = download_url + '.sha256'
        try:
            sha_resp = requests.get(sha_url, timeout=10)
            if sha_resp.status_code == 200:
                expected_hash = sha_resp.text.strip().split()[0]
                if actual_hash != expected_hash:
                    return {'success': False, 'message': f'Checksum mismatch: expected {expected_hash[:16]}..., got {actual_hash[:16]}...'}
                log.info(f"Checksum verified: {actual_hash[:16]}...")
            else:
                log.warning("No .sha256 sidecar file found — refusing to install unverified binary")
                return {'success': False, 'message': 'No checksum file available to verify download integrity'}
        except Exception as e:
            log.warning(f"Could not verify checksum: {e}")
            return {'success': False, 'message': f'Checksum verification failed: {e}'}

        os.chmod(tmp.name, 0o755)

        backup = current_exe.with_suffix(current_exe.suffix + '.old')
        backup.unlink(missing_ok=True)
        current_exe.rename(backup)
        shutil.move(tmp.name, str(current_exe))

        return {
            'success': True,
            'message': 'Binary updated. Restart to use new version.',
            'restart_required': True,
        }
    except Exception as e:
        if tmp:
            try:
                Path(tmp.name).unlink(missing_ok=True)
            except Exception:
                pass
        if backup and backup.exists() and not current_exe.exists():
            try:
                backup.rename(current_exe)
            except Exception:
                pass
        return {'success': False, 'message': f'Binary update failed: {e}'}


def restart_server():
    """Restart the server process using os.execv (replaces current process)."""
    from .web import _serve_restart_cmd
    cmd = _serve_restart_cmd
    if not cmd:
        log.warning("No serve command stored, cannot auto-restart")
        return False
    log.info(f"Restarting server: {' '.join(cmd)}")
    os.execv(cmd[0], cmd)
