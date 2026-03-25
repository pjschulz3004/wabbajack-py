"""Click CLI for wabbajack-py."""
import sys, logging
from pathlib import Path
import click

from . import __version__
from .modlist import WabbajackModlist
from .platform import detect_game_dir, find_steam_libraries, GAME_DIRS
from .hash import compute_xxhash64_b64, HAS_XXHASH, verify_archive
from .installer import ModlistInstaller
from .profiles import ProfileManager
from .downloaders import classify_archive

log = logging.getLogger('wabbajack')


def setup_logging(log_file=None, verbose=False):
    log.setLevel(logging.DEBUG)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter('%(message)s'))
    log.addHandler(console)
    if log_file:
        fh = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)-5s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        log.addHandler(fh)


@click.group()
@click.version_option(__version__, prog_name='wabbajack-py')
@click.option('-v', '--verbose', is_flag=True, help='Verbose console output')
@click.option('--log-file', type=click.Path(), help='Write detailed log to file')
@click.pass_context
def main(ctx, verbose, log_file):
    """Cross-platform Wabbajack modlist installer.

    Handles all archive sources: Nexus, MediaFire, Mega, Google Drive,
    WabbajackCDN, HTTP, and game files. Works on Windows, macOS, and Linux.
    """
    ctx.ensure_object(dict)
    setup_logging(log_file=log_file, verbose=verbose)


@main.command()
@click.option('--port', default=6969, help='Port for web UI')
@click.option('--no-browser', is_flag=True, help='Do not open browser on start')
@click.option('--host', default='127.0.0.1', help='Bind address')
def serve(port, no_browser, host):
    """Launch the web GUI."""
    import uvicorn
    from .web import create_app

    app = create_app()

    if not no_browser:
        import threading, webbrowser, time as _time
        def open_browser():
            _time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")
        threading.Thread(target=open_browser, daemon=True).start()

    log.info(f"Starting wabbajack-py web UI on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


@main.command()
@click.argument('wabbajack', type=click.Path(exists=True))
def info(wabbajack):
    """Show modlist details."""
    from .progress import print_modlist_info, HAS_RICH
    with WabbajackModlist(wabbajack) as ml:
        s = ml.summary()
    if HAS_RICH:
        print_modlist_info(s)
    else:
        log.info(f"Name:       {s['name']}")
        log.info(f"Version:    {s['version']}")
        log.info(f"Author:     {s['author']}")
        log.info(f"Game:       {s['game']}")
        log.info(f"NSFW:       {s['nsfw']}")
        log.info(f"Archives:   {s['archives']}")
        log.info(f"Directives: {s['directives']}")
        log.info(f"\nDirective types:")
        for t, c in sorted(s['directive_types'].items(), key=lambda x: -x[1]):
            log.info(f"  {c:>8}  {t}")
        log.info(f"\nArchive sources:")
        for t, c in sorted(s['archive_types'].items(), key=lambda x: -x[1]):
            log.info(f"  {c:>6}  {t}")


@main.command()
@click.argument('wabbajack', type=click.Path(exists=True))
@click.option('-d', '--downloads', required=True, type=click.Path(), help='Downloads directory')
@click.option('-k', '--nexus-key', envvar='NEXUS_API_KEY', help='Nexus API key (or set NEXUS_API_KEY env var)')
@click.option('-g', '--game-dir', type=click.Path(exists=True), help='Game install directory')
@click.option('--dry-run', is_flag=True, help='Show what would be downloaded')
@click.option('--verify', is_flag=True, help='Verify hashes after download (warn only)')
@click.option('--type', 'types', multiple=True,
              type=click.Choice(['game', 'http', 'mediafire', 'mega', 'gdrive', 'moddb', 'nexus']),
              help='Only download specific types')
def download(wabbajack, downloads, nexus_key, game_dir, dry_run, verify, types):
    """Download missing archives for a modlist."""
    ml = WabbajackModlist(wabbajack)  # Stays open for installer use
    log.info(f"{ml.name} v{ml.version} by {ml.author}")

    gdir = Path(game_dir) if game_dir else detect_game_dir(ml.game)
    if not gdir or not gdir.exists():
        log.error(f"Game directory not found. Use -g to specify.")
        raise SystemExit(1)

    import tempfile
    with tempfile.TemporaryDirectory(prefix='wj-dl-') as tmpdir:
        inst = ModlistInstaller(ml, tmpdir, downloads, gdir,
                                nexus_key=nexus_key, verify_hashes=verify)
        inst.download_all(types=list(types) if types else None, dry_run=dry_run)


@main.command()
@click.argument('wabbajack', type=click.Path(exists=True))
@click.option('-o', '--output', required=True, type=click.Path(), help='Output directory')
@click.option('-d', '--downloads', required=True, type=click.Path(), help='Downloads directory')
@click.option('-g', '--game-dir', type=click.Path(exists=True), help='Game install directory')
@click.option('-k', '--nexus-key', envvar='NEXUS_API_KEY', help='Nexus API key (or NEXUS_API_KEY env)')
@click.option('-j', '--workers', default=12, help='Parallel extraction workers')
@click.option('--cache-dir', type=click.Path(), help='Archive extraction cache directory')
@click.option('--skip-download', is_flag=True, help='Skip download phase')
@click.option('--dry-run', is_flag=True, help='Show plan without executing')
@click.option('--verify', is_flag=True, help='Verify hashes (warn only)')
@click.option('--profile', help='Register as named profile after install')
@click.option('--type', 'types', multiple=True, help='Only download specific types')
def install(wabbajack, output, downloads, game_dir, nexus_key, workers,
            cache_dir, skip_download, dry_run, verify, profile, types):
    """Full install: download + extract + place files."""
    ml = WabbajackModlist(wabbajack)
    log.info(f"{ml.name} v{ml.version} by {ml.author}")

    gdir = Path(game_dir) if game_dir else detect_game_dir(ml.game)
    if not gdir or not gdir.exists():
        log.error(f"Game directory not found. Use -g to specify.")
        raise SystemExit(1)

    inst = ModlistInstaller(
        ml, output, downloads, gdir,
        nexus_key=nexus_key, workers=workers,
        cache_dir=cache_dir, verify_hashes=verify
    )
    inst.install(
        skip_download=skip_download,
        download_types=list(types) if types else None,
        dry_run=dry_run
    )
    if profile:
        pm = ProfileManager()
        pm.register(profile, wabbajack, output, gdir)


@main.command()
@click.argument('output_dir', type=click.Path(exists=True))
@click.option('--skip-download', is_flag=True, help='Skip download phase')
@click.option('-k', '--nexus-key', envvar='NEXUS_API_KEY', help='Nexus API key')
def reinstall(output_dir, skip_download, nexus_key):
    """Re-run install from saved config (resumes where it left off)."""
    from .config import InstallConfig
    from .state import InstallState

    config = InstallConfig(output_dir)
    state = InstallState(output_dir)

    wj_path = config.get('wabbajack_path')
    if not wj_path or not Path(wj_path).exists():
        log.error(f"No saved config in {output_dir} or .wabbajack file missing")
        log.error(f"  Run 'wabbajack-py install' first to create the config")
        raise SystemExit(1)

    cfg = config.summary()
    log.info(f"Resuming: {cfg.get('modlist_name', '?')} v{cfg.get('modlist_version', '?')}")
    log.info(f"  State: {state.phase} ({state.summary()['completed_archives']} archives done)")

    ml = WabbajackModlist(wj_path)
    inst = ModlistInstaller(
        ml, output_dir, cfg['downloads_dir'], cfg['game_dir'],
        nexus_key=nexus_key,
        workers=int(cfg.get('workers', 12)),
        cache_dir=cfg.get('cache_dir'),
        verify_hashes=cfg.get('verify_hashes', False)
    )
    inst.install(skip_download=skip_download)


@main.command()
@click.option('--base', type=click.Path(), help='Base directory for profiles')
def profiles(base):
    """List installed modlist profiles."""
    pm = ProfileManager(base)
    if not pm.profiles:
        log.info("No profiles registered. Use 'install --profile <name>' to create one.")
        return
    log.info(f"\nModlist Profiles (base: {pm.base})")
    log.info(f"Shared downloads: {pm.shared_downloads}")
    log.info(f"{'='*60}")
    for name, p in sorted(pm.profiles.items()):
        active = ' [ACTIVE]' if name == pm.active else ''
        exists = Path(p['output']).exists()
        log.info(f"\n  {name}{active}")
        log.info(f"    {p['title']} v{p['version']} ({p['game']})")
        log.info(f"    Output: {p['output']} {'(ok)' if exists else '(missing)'}")
        log.info(f"    Archives: {p['archive_count']} | Installed: {p.get('installed_at', '?')}")


@main.command()
@click.argument('name')
@click.option('--base', type=click.Path(), help='Base directory for profiles')
def switch(name, base):
    """Switch active modlist profile."""
    pm = ProfileManager(base)
    if not pm.switch(name):
        raise SystemExit(1)


@main.command()
@click.option('--base', type=click.Path(), help='Base directory for profiles')
@click.option('--new', 'new_wabbajack', type=click.Path(exists=True),
              help='.wabbajack file to check reuse against')
def shared(base, new_wabbajack):
    """Analyze download sharing between modlists."""
    pm = ProfileManager(base)
    result = pm.analyze_shared(new_wabbajack)

    log.info(f"\nDownload Sharing Analysis")
    log.info(f"  Total unique archives: {result['total_unique']}")
    log.info(f"  Shared by 2+ profiles: {result['shared_count']}")

    if 'new_title' in result:
        log.info(f"\n  New modlist: {result['new_title']} v{result['new_version']}")
        log.info(f"    Total needed:       {result['new_total']}")
        log.info(f"    Already downloaded:  {result['reusable']} ({result['reusable_size']/1073741824:.1f} GB)")
        log.info(f"    Need to download:   {result['new_only']} ({result['new_size']/1073741824:.1f} GB)")
        log.info(f"    Savings:            {result['savings_pct']:.0f}%")


@main.command('list-games')
def list_games():
    """List detected game installations."""
    libraries = find_steam_libraries()
    log.info(f"Steam libraries: {len(libraries)}")
    for lib in libraries:
        log.info(f"  {lib}")

    log.info(f"\nSupported games ({len(GAME_DIRS)}):")
    found = 0
    for game_type, info in sorted(GAME_DIRS.items()):
        for lib in libraries:
            game_path = lib / info['steam_subdir']
            if game_path.exists():
                log.info(f"  [FOUND] {info['display']:30s}  {game_path}")
                found += 1
                break
        else:
            log.info(f"  [     ] {info['display']}")
    log.info(f"\n{found}/{len(GAME_DIRS)} games detected")


@main.command('load-order')
@click.argument('game_type')
@click.option('--game-dir', type=click.Path(exists=True), help='Game install directory')
@click.option('--profile', type=click.Path(), help='MO2 profile directory')
@click.option('--validate', is_flag=True, help='Check for missing masters')
def load_order(game_type, game_dir, profile, validate):
    """Show or validate mod load order for a game.

    GAME_TYPE: SkyrimSpecialEdition, BaldursGate3, Cyberpunk2077, StardewValley, etc.
    """
    from .loadorder import get_load_order, LOAD_ORDER_CLASSES

    if game_type == 'list':
        log.info("Supported games for load order management:")
        for gt in sorted(LOAD_ORDER_CLASSES.keys()):
            log.info(f"  {gt}")
        return

    if not game_dir:
        game_dir = detect_game_dir(game_type)
        if not game_dir:
            log.error(f"Could not auto-detect {game_type}. Pass --game-dir.")
            raise SystemExit(1)

    lo = get_load_order(game_type, Path(game_dir), Path(profile) if profile else None)
    lo.load()
    s = lo.summary()

    log.info(f"\n{game_type} Load Order")
    log.info(f"  Mods:    {s['enabled_mods']}/{s['total_mods']} enabled")
    log.info(f"  Plugins: {s['enabled_plugins']}/{s['total_plugins']} enabled")

    if lo.mods:
        log.info(f"\n  Mod Priority (asset override order):")
        for m in lo.mods[:50]:
            state = '+' if m.enabled else '-'
            log.info(f"    {state} {m.name}")
        if len(lo.mods) > 50:
            log.info(f"    ... and {len(lo.mods) - 50} more")

    if lo.plugins:
        log.info(f"\n  Plugin Load Order:")
        for p in lo.plugins[:50]:
            flags = ''
            if p.is_master:
                flags += ' [ESM]'
            if p.is_light:
                flags += ' [ESL]'
            state = '*' if p.enabled else ' '
            log.info(f"    {state} {p.filename}{flags}")
        if len(lo.plugins) > 50:
            log.info(f"    ... and {len(lo.plugins) - 50} more")

    if validate and hasattr(lo, 'validate_load_order'):
        errors = lo.validate_load_order()
        if errors:
            log.warning(f"\n  Validation Issues ({len(errors)}):")
            for err in errors:
                log.warning(f"    ! {err}")
        else:
            log.info(f"\n  Validation: OK (no missing masters)")


@main.command('check-update')
def check_update():
    """Check for available updates."""
    from .updater import check_for_update
    info = check_for_update()
    if info.get('error'):
        log.warning(f"Update check failed: {info['error']}")
        raise SystemExit(1)
    log.info(f"Current version:  {info['current']}")
    log.info(f"Latest version:   {info['latest']}")
    log.info(f"Install type:     {info['install_type']}")
    if info['update_available']:
        log.info(f"\nUpdate available! Run 'wabbajack-py update' to install.")
        if info.get('changelog'):
            log.info(f"\nChangelog:\n{info['changelog'][:500]}")
    else:
        log.info("\nYou're up to date.")


@main.command()
def update():
    """Update wabbajack-py to the latest version."""
    from .updater import check_for_update, apply_update
    log.info("Checking for updates...")
    info = check_for_update()
    if info.get('error'):
        log.error(f"Update check failed: {info['error']}")
        raise SystemExit(1)
    if not info['update_available']:
        log.info(f"Already at latest version ({info['current']})")
        return
    log.info(f"Updating {info['current']} -> {info['latest']} ({info['install_type']})")
    result = apply_update(info)
    if result['success']:
        log.info(f"  {result['message']}")
    else:
        log.error(f"  {result['message']}")
        raise SystemExit(1)


@main.command('hash-file')
@click.argument('file_path', type=click.Path(exists=True))
def hash_file(file_path):
    """Compute xxHash64 of a file (Wabbajack format)."""
    if not HAS_XXHASH:
        log.error("xxhash not installed (pip install xxhash)")
        raise SystemExit(1)
    import os
    size = os.path.getsize(file_path)
    log.info(f"File: {file_path} ({size/1048576:.1f} MB)")
    result = compute_xxhash64_b64(file_path)
    log.info(f"xxHash64 (base64): {result}")


@main.command('verify')
@click.argument('wabbajack', type=click.Path(exists=True))
@click.option('-d', '--downloads', required=True, type=click.Path(exists=True), help='Downloads directory')
def verify(wabbajack, downloads):
    """Verify downloaded archive hashes against modlist."""
    if not HAS_XXHASH:
        log.error("xxhash not installed (pip install xxhash)")
        raise SystemExit(1)

    ml = WabbajackModlist(wabbajack)
    log.info(f"{ml.name} v{ml.version} -- verifying {len(ml.archives)} archives")

    downloads_dir = Path(downloads)
    ok = 0
    mismatch = 0
    missing = 0
    skipped = 0

    for i, a in enumerate(ml.archives):
        name = a['Name']
        expected = a.get('Hash', '')
        path = downloads_dir / name
        if not path.exists():
            path_lower = downloads_dir / name.lower()
            if path_lower.exists():
                path = path_lower
            else:
                missing += 1
                continue

        if not expected:
            skipped += 1
            continue

        result = verify_archive(path, expected, name)
        if result.ok:
            ok += 1
        else:
            mismatch += 1
            log.warning(f"  {result.message}")

        if (i + 1) % 500 == 0:
            log.info(f"  Progress: {i+1}/{len(ml.archives)} checked...")

    log.info(f"\nVerification complete:")
    log.info(f"  OK:         {ok}")
    log.info(f"  Mismatch:   {mismatch}")
    log.info(f"  Missing:    {missing}")
    log.info(f"  Skipped:    {skipped}")
    if mismatch:
        log.warning(f"\n{mismatch} hash mismatches found. Re-download affected files.")


@main.command('list-downloads')
@click.argument('wabbajack', type=click.Path(exists=True))
@click.option('-d', '--downloads', type=click.Path(exists=True), help='Downloads directory to check against')
def list_downloads(wabbajack, downloads):
    """List all archives in a modlist with download status."""
    ml = WabbajackModlist(wabbajack)
    log.info(f"{ml.name} v{ml.version} -- {len(ml.archives)} archives\n")

    downloads_dir = Path(downloads) if downloads else None
    by_type = {}
    present = 0
    total_size = 0
    present_size = 0

    for a in ml.archives:
        t = classify_archive(a)
        by_type.setdefault(t, []).append(a)
        size = a.get('Size', 0)
        total_size += size

        if downloads_dir:
            path = downloads_dir / a['Name']
            if path.exists() and path.stat().st_size > 0:
                present += 1
                present_size += size

    for t in sorted(by_type.keys()):
        items = by_type[t]
        size = sum(a.get('Size', 0) for a in items) / 1073741824
        log.info(f"  {t:>12}: {len(items):>5} files ({size:.2f} GB)")

    log.info(f"\n  Total: {len(ml.archives)} archives ({total_size/1073741824:.1f} GB)")
    if downloads_dir:
        log.info(f"  Present: {present}/{len(ml.archives)} ({present_size/1073741824:.1f} GB)")
        log.info(f"  Missing: {len(ml.archives) - present} ({(total_size - present_size)/1073741824:.1f} GB)")


@main.command('extract')
@click.argument('wabbajack', type=click.Path(exists=True))
@click.option('-o', '--output', required=True, type=click.Path(), help='Output directory for inline data')
def extract(wabbajack, output):
    """Extract all inline/patch data from a .wabbajack file."""
    with WabbajackModlist(wabbajack) as ml:
        log.info(f"{ml.name} v{ml.version}")
        count = ml.extract_all_inline(output)
        log.info(f"Extracted {count} files to {output}")


@main.command('status')
@click.argument('wabbajack', type=click.Path(exists=True))
@click.option('-d', '--downloads', type=click.Path(exists=True), help='Downloads directory')
@click.option('-o', '--output', type=click.Path(exists=True), help='Output/install directory')
def status(wabbajack, downloads, output):
    """Show installation status and readiness."""
    with WabbajackModlist(wabbajack) as ml:
        s = ml.summary()
        log.info(f"{s['name']} v{s['version']} by {s['author']}")
        log.info(f"Game: {s['game']} | Archives: {s['archives']} | Directives: {s['directives']}")

        if downloads:
            dl_dir = Path(downloads)
            present = 0
            present_size = 0
            total_size = 0
            for a in ml.archives:
                size = a.get('Size', 0)
                total_size += size
                path = dl_dir / a['Name']
                if path.exists() and path.stat().st_size > 0:
                    present += 1
                    present_size += size
            pct = present / max(1, len(ml.archives)) * 100
            log.info(f"\nDownloads: {present}/{len(ml.archives)} ({pct:.0f}%)")
            log.info(f"  Downloaded: {present_size/1073741824:.1f} GB / {total_size/1073741824:.1f} GB")
            remaining = total_size - present_size
            if remaining > 0:
                log.info(f"  Remaining:  {remaining/1073741824:.1f} GB")

            by_type = {}
            missing = []
            for a in ml.archives:
                path = dl_dir / a['Name']
                if not (path.exists() and path.stat().st_size > 0):
                    t = classify_archive(a)
                    by_type.setdefault(t, []).append(a)
                    missing.append(a)
            if missing:
                log.info(f"\n  Missing by type:")
                for t in sorted(by_type.keys()):
                    items = by_type[t]
                    size = sum(a.get('Size', 0) for a in items) / 1073741824
                    log.info(f"    {t:>12}: {len(items):>5} ({size:.1f} GB)")

        if output:
            out_dir = Path(output)
            file_count = sum(1 for _ in out_dir.rglob('*') if _.is_file())
            dir_size = sum(f.stat().st_size for f in out_dir.rglob('*') if f.is_file())
            portable = (out_dir / 'portable.txt').exists()
            mo2_ini = (out_dir / 'ModOrganizer.ini').exists()
            log.info(f"\nInstallation: {out_dir}")
            log.info(f"  Files: {file_count}")
            log.info(f"  Size:  {dir_size/1073741824:.1f} GB")
            log.info(f"  MO2 portable: {'yes' if portable else 'no'}")
            log.info(f"  MO2 config:   {'yes' if mo2_ini else 'no'}")
