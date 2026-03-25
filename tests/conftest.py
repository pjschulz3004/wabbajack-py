"""Shared fixtures for wabbajack-py tests."""
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

# Ensure src/ is on sys.path so wabbajack imports work
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ── Paths ────────────────────────────────────────────────────────────

WABBAJACK_FILE = Path.home() / "Jackify/downloaded_mod_lists/WakingDreams_@@_TwistedSkyrim.wabbajack.bak"
DOWNLOADS_DIR = Path.home() / "Games/TwistedSkyrim/downloads"


def _have_real_wabbajack():
    return WABBAJACK_FILE.exists()


def _have_downloads_dir():
    return DOWNLOADS_DIR.is_dir()


# Skip markers
requires_wabbajack = pytest.mark.skipif(
    not _have_real_wabbajack(),
    reason=f"Real .wabbajack file not found: {WABBAJACK_FILE}",
)
requires_downloads = pytest.mark.skipif(
    not _have_downloads_dir(),
    reason=f"Downloads directory not found: {DOWNLOADS_DIR}",
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a clean temporary directory."""
    return tmp_path


@pytest.fixture
def case_tree(tmp_path):
    """Create a small directory tree with mixed-case files for CaseInsensitiveFinder."""
    (tmp_path / "Data").mkdir()
    (tmp_path / "Data" / "Meshes").mkdir()
    (tmp_path / "Data" / "Meshes" / "Actor.nif").write_bytes(b"nif data")
    (tmp_path / "Data" / "Textures").mkdir()
    (tmp_path / "Data" / "Textures" / "Body_1.dds").write_bytes(b"dds data")
    (tmp_path / "SKSE").mkdir()
    (tmp_path / "SKSE" / "Plugins").mkdir()
    (tmp_path / "SKSE" / "Plugins" / "SomePlugin.dll").write_bytes(b"dll data")
    (tmp_path / "readme.txt").write_text("hello")
    return tmp_path


@pytest.fixture
def sample_modlist_json():
    """Minimal modlist JSON structure for unit tests."""
    return {
        "Name": "TestModlist",
        "Version": "1.0.0",
        "Author": "Tester",
        "GameType": "SkyrimSpecialEdition",
        "IsNSFW": False,
        "Archives": [
            {
                "Hash": "AAAA",
                "Name": "mod_a.7z",
                "Size": 1024,
                "State": {"$type": "NexusDownloader, Wabbajack.Lib", "ModID": 1, "FileID": 100, "GameName": "skyrimspecialedition"},
            },
            {
                "Hash": "BBBB",
                "Name": "mod_b.zip",
                "Size": 2048,
                "State": {"$type": "HttpDownloader, Wabbajack.Lib", "Url": "https://example.com/mod_b.zip"},
            },
            {
                "Hash": "CCCC",
                "Name": "Skyrim - Meshes0.bsa",
                "Size": 4096,
                "State": {"$type": "GameFileSource, Wabbajack.Lib", "GameFile": "Data/Skyrim - Meshes0.bsa"},
            },
        ],
        "Directives": [
            {"$type": "FromArchive", "To": "mods/ModA/plugin.esp", "ArchiveHashPath": ["AAAA", "plugin.esp"]},
            {"$type": "InlineFile", "To": "profiles/Default/modlist.txt", "SourceDataID": "abc123"},
            {"$type": "RemappedInlineFile", "To": "ModOrganizer.ini", "SourceDataID": "def456"},
        ],
    }


@pytest.fixture
def fake_wabbajack(tmp_path, sample_modlist_json):
    """Create a minimal .wabbajack ZIP file for unit testing."""
    wj_path = tmp_path / "test.wabbajack"
    with zipfile.ZipFile(wj_path, "w") as zf:
        zf.writestr("modlist", json.dumps(sample_modlist_json))
        zf.writestr("modlist-image.png", b"fakepng")
        zf.writestr("abc123", b"inline content here")
        zf.writestr("def456", b"[General]\ndownload_directory={--||DOWNLOAD_PATH_MAGIC_FORWARD||--}")
    return wj_path


@pytest.fixture
def real_modlist():
    """Open the real .wabbajack file. Requires the file to exist on disk."""
    if not _have_real_wabbajack():
        pytest.skip(f"Real .wabbajack not found: {WABBAJACK_FILE}")
    from wabbajack.modlist import WabbajackModlist
    ml = WabbajackModlist(WABBAJACK_FILE)
    yield ml
    ml.close()
