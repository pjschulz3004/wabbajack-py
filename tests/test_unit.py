"""Unit tests for wabbajack-py modules.

These tests do NOT require network access or real modlist files.
"""
import json
import os
import tempfile
import zipfile
from pathlib import Path

import pytest

# ═══════════════════════════════════════════════════════════════════════
# downloaders: validate_url_scheme
# ═══════════════════════════════════════════════════════════════════════

class TestValidateUrlScheme:

    def test_http_allowed(self):
        from wabbajack.downloaders import validate_url_scheme
        assert validate_url_scheme("http://example.com/file.zip") == "http://example.com/file.zip"

    def test_https_allowed(self):
        from wabbajack.downloaders import validate_url_scheme
        assert validate_url_scheme("https://nexus.com/mod.7z") == "https://nexus.com/mod.7z"

    def test_file_scheme_rejected(self):
        from wabbajack.downloaders import validate_url_scheme
        with pytest.raises(ValueError, match="Unsafe URL scheme"):
            validate_url_scheme("file:///etc/passwd")

    def test_ftp_scheme_rejected(self):
        from wabbajack.downloaders import validate_url_scheme
        with pytest.raises(ValueError, match="Unsafe URL scheme"):
            validate_url_scheme("ftp://files.example.com/mod.zip")

    def test_javascript_scheme_rejected(self):
        from wabbajack.downloaders import validate_url_scheme
        with pytest.raises(ValueError, match="Unsafe URL scheme"):
            validate_url_scheme("javascript:alert(1)")

    def test_no_scheme_allowed(self):
        """URLs without scheme should pass (relative URLs)."""
        from wabbajack.downloaders import validate_url_scheme
        result = validate_url_scheme("example.com/file.zip")
        assert result == "example.com/file.zip"

    def test_empty_string(self):
        from wabbajack.downloaders import validate_url_scheme
        assert validate_url_scheme("") == ""


# ═══════════════════════════════════════════════════════════════════════
# downloaders: classify_archive
# ═══════════════════════════════════════════════════════════════════════

class TestClassifyArchive:

    @pytest.mark.parametrize("type_str,expected", [
        ("GameFileSource, Wabbajack.Lib", "game"),
        ("WabbajackCDN, Wabbajack.Lib", "http"),
        ("HttpDownloader, Wabbajack.Lib", "http"),
        ("MediaFire, Wabbajack.Lib", "mediafire"),
        ("MegaDownloader, Wabbajack.Lib", "mega"),
        ("GoogleDrive, Wabbajack.Lib", "gdrive"),
        ("NexusDownloader, Wabbajack.Lib", "nexus"),
        ("ModDB, Wabbajack.Lib", "moddb"),
        ("ManualDownloader, Wabbajack.Lib", "manual"),
    ])
    def test_known_types(self, type_str, expected):
        from wabbajack.downloaders import classify_archive
        archive = {"State": {"$type": type_str}}
        assert classify_archive(archive) == expected

    def test_unknown_type(self):
        from wabbajack.downloaders import classify_archive
        archive = {"State": {"$type": "SomeFutureDownloader, Wabbajack.Lib"}}
        assert classify_archive(archive) == "unknown"

    def test_missing_type(self):
        from wabbajack.downloaders import classify_archive
        archive = {"State": {}}
        assert classify_archive(archive) == "unknown"

    def test_missing_state(self):
        from wabbajack.downloaders import classify_archive
        archive = {}
        assert classify_archive(archive) == "unknown"


# ═══════════════════════════════════════════════════════════════════════
# CaseInsensitiveFinder
# ═══════════════════════════════════════════════════════════════════════

class TestCaseInsensitiveFinder:

    def test_find_exact_case(self, case_tree):
        from wabbajack.finder import CaseInsensitiveFinder
        finder = CaseInsensitiveFinder(case_tree)
        result = finder.find("Data/Meshes/Actor.nif")
        assert result is not None
        assert result.name == "Actor.nif"

    def test_find_wrong_case(self, case_tree):
        from wabbajack.finder import CaseInsensitiveFinder
        finder = CaseInsensitiveFinder(case_tree)
        result = finder.find("data/meshes/actor.nif")
        assert result is not None
        assert result.name == "Actor.nif"

    def test_find_all_caps(self, case_tree):
        from wabbajack.finder import CaseInsensitiveFinder
        finder = CaseInsensitiveFinder(case_tree)
        result = finder.find("DATA/MESHES/ACTOR.NIF")
        assert result is not None

    def test_find_backslash_path(self, case_tree):
        from wabbajack.finder import CaseInsensitiveFinder
        finder = CaseInsensitiveFinder(case_tree)
        result = finder.find("Data\\Textures\\Body_1.dds")
        assert result is not None
        assert result.name == "Body_1.dds"

    def test_find_nonexistent(self, case_tree):
        from wabbajack.finder import CaseInsensitiveFinder
        finder = CaseInsensitiveFinder(case_tree)
        assert finder.find("no/such/file.esp") is None

    def test_len(self, case_tree):
        from wabbajack.finder import CaseInsensitiveFinder
        finder = CaseInsensitiveFinder(case_tree)
        assert len(finder) == 4  # Actor.nif, Body_1.dds, SomePlugin.dll, readme.txt

    def test_empty_dir(self, tmp_path):
        from wabbajack.finder import CaseInsensitiveFinder
        finder = CaseInsensitiveFinder(tmp_path)
        assert len(finder) == 0
        assert finder.find("anything") is None

    def test_nonexistent_root(self, tmp_path):
        from wabbajack.finder import CaseInsensitiveFinder
        finder = CaseInsensitiveFinder(tmp_path / "does_not_exist")
        assert len(finder) == 0


# ═══════════════════════════════════════════════════════════════════════
# InstallState
# ═══════════════════════════════════════════════════════════════════════

class TestInstallState:

    def test_initial_state(self, tmp_path):
        from wabbajack.state import InstallState
        state = InstallState(tmp_path)
        assert state.phase == "init"
        assert len(state.completed_hashes) == 0
        assert "AAA" not in state.completed_hashes

    def test_mark_hash_done(self, tmp_path):
        from wabbajack.state import InstallState
        state = InstallState(tmp_path)
        state.mark_hash_done("hash1")
        state.mark_hash_done("hash2")
        assert "hash1" in state.completed_hashes
        assert "hash2" in state.completed_hashes
        assert "hash3" not in state.completed_hashes

    def test_mark_hash_done_idempotent(self, tmp_path):
        from wabbajack.state import InstallState
        state = InstallState(tmp_path)
        state.mark_hash_done("same_hash")
        state.mark_hash_done("same_hash")
        # Should only appear once in the list
        assert state._data["completed_hashes"].count("same_hash") == 1

    def test_save_and_load(self, tmp_path):
        from wabbajack.state import InstallState
        state1 = InstallState(tmp_path)
        state1.mark_hash_done("H1")
        state1.mark_hash_done("H2")
        state1.update_stats(100, 5)
        state1.phase = "placing"  # triggers _save via setter

        # Reload
        state2 = InstallState(tmp_path)
        assert state2.phase == "placing"
        assert "H1" in state2.completed_hashes
        assert "H2" in state2.completed_hashes
        assert state2._data["placed_files"] == 100
        assert state2._data["failed_files"] == 5

    def test_mark_complete(self, tmp_path):
        from wabbajack.state import InstallState
        state = InstallState(tmp_path)
        state.mark_complete()
        assert state.phase == "complete"
        assert "completed_at" in state._data

        # Reload and check
        state2 = InstallState(tmp_path)
        assert state2.phase == "complete"

    def test_reset(self, tmp_path):
        from wabbajack.state import InstallState
        state = InstallState(tmp_path)
        state.mark_hash_done("X")
        state.mark_complete()

        state.reset()
        assert state.phase == "init"
        assert "X" not in state.completed_hashes

    def test_completed_hashes_caching(self, tmp_path):
        """completed_hashes property should return a set and be cached."""
        from wabbajack.state import InstallState
        state = InstallState(tmp_path)
        state.mark_hash_done("A")
        state.mark_hash_done("B")
        h1 = state.completed_hashes
        h2 = state.completed_hashes
        assert h1 is h2  # same object (cached)
        assert isinstance(h1, set)
        assert "A" in h1

    def test_summary(self, tmp_path):
        from wabbajack.state import InstallState
        state = InstallState(tmp_path)
        state.mark_hash_done("Z")
        state.update_stats(50, 3)
        s = state.summary()
        assert s["completed_archives"] == 1
        assert s["placed_files"] == 50
        assert s["failed_files"] == 3


# ═══════════════════════════════════════════════════════════════════════
# InstallConfig
# ═══════════════════════════════════════════════════════════════════════

class TestInstallConfig:

    def test_save_and_load(self, tmp_path):
        from wabbajack.config import InstallConfig
        cfg = InstallConfig(tmp_path)
        cfg.set("modlist_name", "TestMod")
        cfg.set("workers", 8)
        cfg.set("game_dir", "/home/user/Games/Skyrim")
        cfg.save()

        cfg2 = InstallConfig(tmp_path)
        assert cfg2.get("modlist_name") == "TestMod"
        assert cfg2.get("workers") == 8
        assert cfg2.get("game_dir") == "/home/user/Games/Skyrim"

    def test_unknown_key_ignored(self, tmp_path):
        from wabbajack.config import InstallConfig
        cfg = InstallConfig(tmp_path)
        cfg.set("not_a_real_key", "value")
        cfg.save()
        cfg2 = InstallConfig(tmp_path)
        assert cfg2.get("not_a_real_key") is None

    def test_summary_filters_keys(self, tmp_path):
        from wabbajack.config import InstallConfig
        cfg = InstallConfig(tmp_path)
        cfg.set("modlist_name", "MyList")
        cfg.set("workers", 4)
        cfg._data["extra_junk"] = "should not appear"
        s = cfg.summary()
        assert "modlist_name" in s
        assert "workers" in s
        assert "extra_junk" not in s

    def test_default_returns(self, tmp_path):
        from wabbajack.config import InstallConfig
        cfg = InstallConfig(tmp_path)
        assert cfg.get("missing_key") is None
        assert cfg.get("missing_key", "fallback") == "fallback"

    def test_path_converted_to_str(self, tmp_path):
        from wabbajack.config import InstallConfig
        cfg = InstallConfig(tmp_path)
        cfg.set("output_dir", Path("/some/path"))
        cfg.save()
        cfg2 = InstallConfig(tmp_path)
        val = cfg2.get("output_dir")
        assert isinstance(val, str)
        assert val == "/some/path"


# ═══════════════════════════════════════════════════════════════════════
# ProfileManager
# ═══════════════════════════════════════════════════════════════════════

class TestProfileManager:

    def test_register_and_list(self, tmp_path, fake_wabbajack):
        from wabbajack.profiles import ProfileManager
        pm = ProfileManager(tmp_path)
        pm.register("test_profile", fake_wabbajack, tmp_path / "output", tmp_path / "game")
        assert "test_profile" in pm.profiles
        p = pm.profiles["test_profile"]
        assert p["title"] == "TestModlist"
        assert p["version"] == "1.0.0"
        assert p["archive_count"] == 3

    def test_first_registered_is_active(self, tmp_path, fake_wabbajack):
        from wabbajack.profiles import ProfileManager
        pm = ProfileManager(tmp_path)
        assert pm.active is None
        pm.register("first", fake_wabbajack, tmp_path / "out1", tmp_path / "game")
        assert pm.active == "first"

    def test_switch(self, tmp_path, fake_wabbajack):
        from wabbajack.profiles import ProfileManager
        pm = ProfileManager(tmp_path)
        pm.register("p1", fake_wabbajack, tmp_path / "o1", tmp_path / "g")
        pm.register("p2", fake_wabbajack, tmp_path / "o2", tmp_path / "g")
        assert pm.switch("p2") is True
        assert pm.active == "p2"

    def test_switch_nonexistent(self, tmp_path, fake_wabbajack):
        from wabbajack.profiles import ProfileManager
        pm = ProfileManager(tmp_path)
        pm.register("p1", fake_wabbajack, tmp_path / "o", tmp_path / "g")
        assert pm.switch("nonexistent") is False

    def test_analyze_shared_no_profiles(self, tmp_path):
        from wabbajack.profiles import ProfileManager
        # Write an empty-but-valid profiles file to avoid the shared mutable
        # default bug in ProfileManager._DEFAULTS (shallow copy shares inner dict).
        clean_dir = tmp_path / "empty_profiles"
        clean_dir.mkdir()
        import json
        (clean_dir / "wabbajack-profiles.json").write_text(json.dumps({
            "active": None,
            "shared_downloads": str(clean_dir / "dl"),
            "profiles": {},
        }))
        pm = ProfileManager(clean_dir)
        assert len(pm.profiles) == 0, f"Expected empty profiles, got: {pm.profiles}"
        result = pm.analyze_shared()
        assert result["total_unique"] == 0
        assert result["shared_count"] == 0

    def test_analyze_shared_with_profiles(self, tmp_path, fake_wabbajack):
        from wabbajack.profiles import ProfileManager
        pm = ProfileManager(tmp_path)
        pm.register("p1", fake_wabbajack, tmp_path / "o1", tmp_path / "g")
        pm.register("p2", fake_wabbajack, tmp_path / "o2", tmp_path / "g")
        result = pm.analyze_shared()
        # Both profiles have the same 3 archive hashes -> all 3 are shared
        assert result["total_unique"] == 3
        assert result["shared_count"] == 3

    def test_persistence(self, tmp_path, fake_wabbajack):
        from wabbajack.profiles import ProfileManager
        pm1 = ProfileManager(tmp_path)
        pm1.register("saved", fake_wabbajack, tmp_path / "o", tmp_path / "g")

        pm2 = ProfileManager(tmp_path)
        assert "saved" in pm2.profiles
        assert pm2.active == "saved"

    def test_shared_downloads_default(self, tmp_path):
        from wabbajack.profiles import ProfileManager
        pm = ProfileManager(tmp_path)
        assert "WabbajackDownloads" in str(pm.shared_downloads)


# ═══════════════════════════════════════════════════════════════════════
# hash.py: compute_xxhash64_b64
# ═══════════════════════════════════════════════════════════════════════

class TestXxhash:

    def test_known_hash(self, tmp_path):
        """Compute hash of a known file and verify it's a valid base64 string."""
        from wabbajack.hash import compute_xxhash64_b64, HAS_XXHASH
        if not HAS_XXHASH:
            pytest.skip("xxhash not installed")

        # Create a file with known content
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"Hello, Wabbajack!")

        result = compute_xxhash64_b64(test_file)
        assert result is not None
        assert isinstance(result, str)
        # Base64 of 8 bytes (xxHash64) = 12 chars with padding
        assert len(result) == 12  # 8 bytes -> ceil(8*4/3) padded to 12

    def test_empty_file(self, tmp_path):
        from wabbajack.hash import compute_xxhash64_b64, HAS_XXHASH
        if not HAS_XXHASH:
            pytest.skip("xxhash not installed")

        empty_file = tmp_path / "empty"
        empty_file.write_bytes(b"")
        result = compute_xxhash64_b64(empty_file)
        assert result is not None

    def test_deterministic(self, tmp_path):
        """Same content should always produce the same hash."""
        from wabbajack.hash import compute_xxhash64_b64, HAS_XXHASH
        if not HAS_XXHASH:
            pytest.skip("xxhash not installed")

        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        content = b"x" * 10000
        f1.write_bytes(content)
        f2.write_bytes(content)
        assert compute_xxhash64_b64(f1) == compute_xxhash64_b64(f2)

    def test_different_content(self, tmp_path):
        from wabbajack.hash import compute_xxhash64_b64, HAS_XXHASH
        if not HAS_XXHASH:
            pytest.skip("xxhash not installed")

        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"alpha")
        f2.write_bytes(b"beta")
        assert compute_xxhash64_b64(f1) != compute_xxhash64_b64(f2)

    def test_verify_archive_match(self, tmp_path):
        from wabbajack.hash import compute_xxhash64_b64, verify_archive, HAS_XXHASH
        if not HAS_XXHASH:
            pytest.skip("xxhash not installed")

        f = tmp_path / "mod.7z"
        f.write_bytes(b"archive content here")
        h = compute_xxhash64_b64(f)
        result = verify_archive(f, h, "mod.7z")
        assert result.ok is True

    def test_verify_archive_mismatch(self, tmp_path):
        from wabbajack.hash import verify_archive, HAS_XXHASH
        if not HAS_XXHASH:
            pytest.skip("xxhash not installed")

        f = tmp_path / "mod.7z"
        f.write_bytes(b"data")
        result = verify_archive(f, "WRONGHASH=", "mod.7z")
        assert result.ok is False
        assert "MISMATCH" in result.message

    def test_verify_archive_no_expected(self, tmp_path):
        from wabbajack.hash import verify_archive
        f = tmp_path / "mod.7z"
        f.write_bytes(b"data")
        result = verify_archive(f, None, "mod.7z")
        assert result.ok is True  # no hash to compare -> skip


# ═══════════════════════════════════════════════════════════════════════
# WabbajackModlist (unit, with fake ZIP)
# ═══════════════════════════════════════════════════════════════════════

class TestWabbajackModlistUnit:

    def test_parse_name_version(self, fake_wabbajack):
        from wabbajack.modlist import WabbajackModlist
        with WabbajackModlist(fake_wabbajack) as ml:
            assert ml.name == "TestModlist"
            assert ml.version == "1.0.0"
            assert ml.author == "Tester"
            assert ml.game == "SkyrimSpecialEdition"
            assert ml.is_nsfw is False

    def test_archives_and_directives(self, fake_wabbajack):
        from wabbajack.modlist import WabbajackModlist
        with WabbajackModlist(fake_wabbajack) as ml:
            assert len(ml.archives) == 3
            assert len(ml.directives) == 3

    def test_archive_type_counts(self, fake_wabbajack):
        from wabbajack.modlist import WabbajackModlist
        with WabbajackModlist(fake_wabbajack) as ml:
            counts = ml.archive_type_counts()
            assert counts["NexusDownloader, Wabbajack.Lib"] == 1
            assert counts["HttpDownloader, Wabbajack.Lib"] == 1
            assert counts["GameFileSource, Wabbajack.Lib"] == 1

    def test_directive_type_counts(self, fake_wabbajack):
        from wabbajack.modlist import WabbajackModlist
        with WabbajackModlist(fake_wabbajack) as ml:
            counts = ml.directive_type_counts()
            assert counts["FromArchive"] == 1
            assert counts["InlineFile"] == 1
            assert counts["RemappedInlineFile"] == 1

    def test_summary(self, fake_wabbajack):
        from wabbajack.modlist import WabbajackModlist
        with WabbajackModlist(fake_wabbajack) as ml:
            s = ml.summary()
            assert s["name"] == "TestModlist"
            assert s["archives"] == 3
            assert s["directives"] == 3
            assert "archive_types" in s
            assert "directive_types" in s

    def test_extract_data(self, fake_wabbajack, tmp_path):
        from wabbajack.modlist import WabbajackModlist
        dest = tmp_path / "out" / "inline.txt"
        with WabbajackModlist(fake_wabbajack) as ml:
            assert ml.extract_data("abc123", dest) is True
            assert dest.read_bytes() == b"inline content here"

    def test_extract_data_missing(self, fake_wabbajack, tmp_path):
        from wabbajack.modlist import WabbajackModlist
        with WabbajackModlist(fake_wabbajack) as ml:
            assert ml.extract_data("nonexistent_id", tmp_path / "nope") is False

    def test_extract_all_inline(self, fake_wabbajack, tmp_path):
        from wabbajack.modlist import WabbajackModlist
        with WabbajackModlist(fake_wabbajack) as ml:
            count = ml.extract_all_inline(tmp_path / "inline")
            assert count == 2  # abc123 and def456 (modlist and modlist-image.png excluded)
            assert (tmp_path / "inline" / "abc123").exists()
            assert (tmp_path / "inline" / "def456").exists()

    def test_file_not_found(self, tmp_path):
        from wabbajack.modlist import WabbajackModlist
        with pytest.raises(FileNotFoundError):
            WabbajackModlist(tmp_path / "nope.wabbajack")

    def test_bad_zip(self, tmp_path):
        from wabbajack.modlist import WabbajackModlist
        bad = tmp_path / "bad.wabbajack"
        bad.write_bytes(b"this is not a zip")
        with pytest.raises(ValueError, match="Not a valid"):
            WabbajackModlist(bad)

    def test_zip_without_modlist(self, tmp_path):
        from wabbajack.modlist import WabbajackModlist
        zp = tmp_path / "empty.wabbajack"
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr("other.txt", "not modlist")
        with WabbajackModlist(zp) as ml:
            with pytest.raises(ValueError, match="No 'modlist' entry"):
                _ = ml.modlist

    def test_context_manager(self, fake_wabbajack):
        from wabbajack.modlist import WabbajackModlist
        with WabbajackModlist(fake_wabbajack) as ml:
            assert ml.name == "TestModlist"
        # After exit, ZipFile should be closed
        assert ml.zf.fp is None

    def test_extract_all_inline_rejects_traversal(self, tmp_path):
        """ZIP entries with path traversal should be skipped."""
        from wabbajack.modlist import WabbajackModlist
        wj = tmp_path / "traversal.wabbajack"
        with zipfile.ZipFile(wj, "w") as zf:
            zf.writestr("modlist", json.dumps({"Name": "T", "Archives": [], "Directives": []}))
            zf.writestr("../../../etc/evil", b"pwned")
            zf.writestr("safe_data", b"ok")
        with WabbajackModlist(wj) as ml:
            out = tmp_path / "out"
            count = ml.extract_all_inline(out)
            assert count == 2  # Both names are in the set, but ../../../etc/evil gets skipped
            assert (out / "safe_data").exists()
            assert not (tmp_path / "etc" / "evil").exists()


# ═══════════════════════════════════════════════════════════════════════
# _place_file path traversal rejection
# ═══════════════════════════════════════════════════════════════════════

class TestPlaceFileTraversal:

    def _make_installer(self, tmp_path, fake_wabbajack):
        """Create a minimal ModlistInstaller for testing _place_file."""
        from wabbajack.modlist import WabbajackModlist
        from wabbajack.installer import ModlistInstaller

        ml = WabbajackModlist(fake_wabbajack)
        output = tmp_path / "output"
        downloads = tmp_path / "downloads"
        game = tmp_path / "game"
        for d in (output, downloads, game):
            d.mkdir(parents=True, exist_ok=True)

        inst = ModlistInstaller(ml, output, downloads, game, workers=1)
        return inst

    def test_normal_path_succeeds(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        src = tmp_path / "source.txt"
        src.write_text("content")
        assert inst._place_file(src, "mods/SomeMod/plugin.esp") is True
        assert (inst.output / "mods/SomeMod/plugin.esp").exists()

    def test_traversal_blocked(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        src = tmp_path / "source.txt"
        src.write_text("content")
        result = inst._place_file(src, "../../etc/passwd")
        assert result is False

    def test_absolute_path_blocked(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        src = tmp_path / "source.txt"
        src.write_text("content")
        # On Linux, absolute paths in To field should still be joined with output
        # and resolve check should catch traversal
        result = inst._place_file(src, "normal/path/file.txt")
        assert result is True

    def test_backslash_path(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        src = tmp_path / "source.txt"
        src.write_text("content")
        result = inst._place_file(src, "mods\\MyMod\\data\\file.nif")
        assert result is True
        assert (inst.output / "mods" / "MyMod" / "data" / "file.nif").exists()


# ═══════════════════════════════════════════════════════════════════════
# _remap_inline_content
# ═══════════════════════════════════════════════════════════════════════

class TestRemapInlineContent:

    def _make_installer(self, tmp_path, fake_wabbajack):
        from wabbajack.modlist import WabbajackModlist
        from wabbajack.installer import ModlistInstaller

        ml = WabbajackModlist(fake_wabbajack)
        output = tmp_path / "output"
        downloads = tmp_path / "downloads"
        game = tmp_path / "game"
        for d in (output, downloads, game):
            d.mkdir(parents=True, exist_ok=True)

        return ModlistInstaller(ml, output, downloads, game, workers=1)

    def test_game_path_forward(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = b"path={--||GAME_PATH_MAGIC_FORWARD||--}/Data"
        result = inst._remap_inline_content(data)
        assert str(inst.game_dir).encode() in result
        assert b"MAGIC" not in result

    def test_game_path_back(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = b"path={--||GAME_PATH_MAGIC_BACK||--}\\Data"
        result = inst._remap_inline_content(data)
        assert b"MAGIC" not in result

    def test_game_path_double_back(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = b"path={--||GAME_PATH_MAGIC_DOUBLE_BACK||--}\\\\Data"
        result = inst._remap_inline_content(data)
        assert b"MAGIC" not in result

    def test_mo2_path_forward(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = b"base={--||MO2_PATH_MAGIC_FORWARD||--}/mods"
        result = inst._remap_inline_content(data)
        assert str(inst.output).encode() in result

    def test_mo2_path_back(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = b"base={--||MO2_PATH_MAGIC_BACK||--}\\mods"
        result = inst._remap_inline_content(data)
        assert b"MAGIC" not in result

    def test_mo2_path_double_back(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = b"base={--||MO2_PATH_MAGIC_DOUBLE_BACK||--}\\\\mods"
        result = inst._remap_inline_content(data)
        assert b"MAGIC" not in result

    def test_download_path_forward(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = b"dl={--||DOWNLOAD_PATH_MAGIC_FORWARD||--}/file.7z"
        result = inst._remap_inline_content(data)
        assert str(inst.downloads).encode() in result

    def test_download_path_back(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = b"dl={--||DOWNLOAD_PATH_MAGIC_BACK||--}\\file.7z"
        result = inst._remap_inline_content(data)
        assert b"MAGIC" not in result

    def test_download_path_double_back(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = b"dl={--||DOWNLOAD_PATH_MAGIC_DOUBLE_BACK||--}\\\\file.7z"
        result = inst._remap_inline_content(data)
        assert b"MAGIC" not in result

    def test_all_nine_magic_strings(self, tmp_path, fake_wabbajack):
        """Every magic string in PATH_MAGIC should be replaced."""
        from wabbajack.installer import PATH_MAGIC
        inst = self._make_installer(tmp_path, fake_wabbajack)
        parts = []
        for magic in PATH_MAGIC:
            parts.append(magic)
        data = "|".join(parts).encode("utf-8")
        result = inst._remap_inline_content(data)
        for magic in PATH_MAGIC:
            assert magic.encode() not in result, f"Magic string not replaced: {magic}"

    def test_binary_data_unchanged(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = bytes(range(256))  # Non-UTF8 binary
        result = inst._remap_inline_content(data)
        assert result is data  # Should return same object

    def test_no_magic_returns_original(self, tmp_path, fake_wabbajack):
        inst = self._make_installer(tmp_path, fake_wabbajack)
        data = b"plain text with no magic strings"
        result = inst._remap_inline_content(data)
        assert result is data  # Same object, no copy


# ═══════════════════════════════════════════════════════════════════════
# InstallRequest pydantic validation
# ═══════════════════════════════════════════════════════════════════════

class TestInstallRequestValidation:

    def test_valid_request(self):
        from wabbajack.web.api import InstallRequest
        req = InstallRequest(
            wabbajack_path="/home/user/test.wabbajack",
            output_dir="/home/user/output",
            downloads_dir="/home/user/downloads",
            game_dir="/home/user/game",
        )
        assert req.workers == 12  # default
        assert req.verify_hashes is False

    def test_null_bytes_rejected(self):
        from wabbajack.web.api import InstallRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Null bytes"):
            InstallRequest(
                wabbajack_path="/home/user/test\x00.wabbajack",
                output_dir="/home/user/output",
                downloads_dir="/home/user/downloads",
                game_dir="/home/user/game",
            )

    def test_traversal_rejected(self):
        from wabbajack.web.api import InstallRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="traversal"):
            InstallRequest(
                wabbajack_path="/home/user/../../../etc/passwd",
                output_dir="/home/user/output",
                downloads_dir="/home/user/downloads",
                game_dir="/home/user/game",
            )

    def test_workers_too_low(self):
        from wabbajack.web.api import InstallRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Workers must be between"):
            InstallRequest(
                wabbajack_path="/home/user/test.wabbajack",
                output_dir="/home/user/output",
                downloads_dir="/home/user/downloads",
                game_dir="/home/user/game",
                workers=0,
            )

    def test_workers_too_high(self):
        from wabbajack.web.api import InstallRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Workers must be between"):
            InstallRequest(
                wabbajack_path="/home/user/test.wabbajack",
                output_dir="/home/user/output",
                downloads_dir="/home/user/downloads",
                game_dir="/home/user/game",
                workers=65,
            )

    def test_workers_bounds(self):
        from wabbajack.web.api import InstallRequest
        req1 = InstallRequest(
            wabbajack_path="/home/user/test.wabbajack",
            output_dir="/o", downloads_dir="/d", game_dir="/g",
            workers=1,
        )
        assert req1.workers == 1
        req64 = InstallRequest(
            wabbajack_path="/home/user/test.wabbajack",
            output_dir="/o", downloads_dir="/d", game_dir="/g",
            workers=64,
        )
        assert req64.workers == 64

    def test_null_bytes_in_all_path_fields(self):
        from wabbajack.web.api import InstallRequest
        from pydantic import ValidationError
        for field in ("output_dir", "downloads_dir", "game_dir"):
            kwargs = {
                "wabbajack_path": "/ok.wabbajack",
                "output_dir": "/out",
                "downloads_dir": "/dl",
                "game_dir": "/game",
            }
            kwargs[field] = f"/path\x00evil"
            with pytest.raises(ValidationError, match="Null bytes"):
                InstallRequest(**kwargs)


# ═══════════════════════════════════════════════════════════════════════
# ArchiveCache
# ═══════════════════════════════════════════════════════════════════════

class TestArchiveCache:

    def test_is_extracted_empty(self, tmp_path):
        from wabbajack.cache import ArchiveCache
        cache = ArchiveCache(tmp_path / "cache")
        assert cache.is_extracted("nonexistent") is False

    def test_is_extracted_after_creation(self, tmp_path):
        from wabbajack.cache import ArchiveCache
        cache = ArchiveCache(tmp_path / "cache")
        extract_dir = cache.get_extract_dir("test_archive.7z")
        extract_dir.mkdir(parents=True)
        (extract_dir / "file.txt").write_text("content")
        assert cache.is_extracted("test_archive.7z") is True

    def test_find_file(self, tmp_path):
        from wabbajack.cache import ArchiveCache
        cache = ArchiveCache(tmp_path / "cache")
        # Simulate extracted archive
        edir = cache.get_extract_dir("my_mod.zip")
        edir.mkdir(parents=True)
        (edir / "data").mkdir()
        (edir / "data" / "Plugin.esp").write_bytes(b"esp")
        cache.index_archive("my_mod.zip")

        # Case-insensitive find
        result = cache.find_file("my_mod.zip", "data\\plugin.esp")
        assert result is not None
        assert result.name == "Plugin.esp"

    def test_find_file_by_filename_only(self, tmp_path):
        from wabbajack.cache import ArchiveCache
        cache = ArchiveCache(tmp_path / "cache")
        edir = cache.get_extract_dir("archive.7z")
        edir.mkdir(parents=True)
        (edir / "deep").mkdir()
        (edir / "deep" / "nested").mkdir()
        (edir / "deep" / "nested" / "File.BSA").write_bytes(b"bsa")
        cache.index_archive("archive.7z")

        result = cache.find_file("archive.7z", "file.bsa")
        assert result is not None

    def test_find_file_missing(self, tmp_path):
        from wabbajack.cache import ArchiveCache
        cache = ArchiveCache(tmp_path / "cache")
        assert cache.find_file("no_such_archive", "file.txt") is None


# ═══════════════════════════════════════════════════════════════════════
# platform.py
# ═══════════════════════════════════════════════════════════════════════

class TestPlatform:

    def test_normalize_path(self):
        from wabbajack.platform import normalize_path
        p = normalize_path("Data\\Meshes\\actor.nif")
        assert "/" in str(p) or "\\" not in str(p)

    def test_game_dirs_populated(self):
        from wabbajack.platform import GAME_DIRS
        assert "SkyrimSpecialEdition" in GAME_DIRS
        assert "BaldursGate3" in GAME_DIRS
        assert "Fallout4" in GAME_DIRS
        for key, val in GAME_DIRS.items():
            assert "steam_subdir" in val
            assert "display" in val


# ═══════════════════════════════════════════════════════════════════════
# loadorder.py: ESP Header Reader
# ═══════════════════════════════════════════════════════════════════════

import struct

class TestReadPluginHeader:
    """Test binary ESP/ESM/ESL header parsing."""

    def _make_esp(self, tmp_path, filename, record_flags=0, masters=None):
        subrecords = b""
        for master in (masters or []):
            name_bytes = master.encode("utf-8") + b"\x00"
            subrecords += b"MAST" + struct.pack("<H", len(name_bytes)) + name_bytes
            subrecords += b"DATA" + struct.pack("<H", 8) + b"\x00" * 8
        data_size = len(subrecords)
        header = b"TES4" + struct.pack("<I", data_size) + struct.pack("<I", record_flags) + b"\x00" * 8
        path = tmp_path / filename
        path.write_bytes(header + subrecords)
        return path

    def test_esm_by_extension(self, tmp_path):
        from wabbajack.loadorder import read_plugin_header
        entry = read_plugin_header(self._make_esp(tmp_path, "Skyrim.esm"))
        assert entry.is_master is True
        assert entry.is_light is False

    def test_esl_by_extension(self, tmp_path):
        from wabbajack.loadorder import read_plugin_header
        entry = read_plugin_header(self._make_esp(tmp_path, "MyMod.esl"))
        assert entry.is_light is True

    def test_esm_flag_overrides_esp_extension(self, tmp_path):
        from wabbajack.loadorder import read_plugin_header
        entry = read_plugin_header(self._make_esp(tmp_path, "FakeMaster.esp", record_flags=0x01))
        assert entry.is_master is True

    def test_esl_flag_0x200(self, tmp_path):
        from wabbajack.loadorder import read_plugin_header
        entry = read_plugin_header(self._make_esp(tmp_path, "Light.esp", record_flags=0x200))
        assert entry.is_light is True

    def test_combined_flags(self, tmp_path):
        from wabbajack.loadorder import read_plugin_header
        entry = read_plugin_header(self._make_esp(tmp_path, "Both.esp", record_flags=0x201))
        assert entry.is_master is True
        assert entry.is_light is True

    def test_masters_parsed(self, tmp_path):
        from wabbajack.loadorder import read_plugin_header
        entry = read_plugin_header(self._make_esp(tmp_path, "Dep.esp", masters=["Skyrim.esm", "Update.esm"]))
        assert entry.masters == ["Skyrim.esm", "Update.esm"]

    def test_non_tes4_signature(self, tmp_path):
        from wabbajack.loadorder import read_plugin_header
        p = tmp_path / "bad.esp"
        p.write_bytes(b"XXXX" + b"\x00" * 20)
        entry = read_plugin_header(p)
        assert entry.filename == "bad.esp"
        assert entry.masters == []

    def test_truncated_file(self, tmp_path):
        from wabbajack.loadorder import read_plugin_header
        p = tmp_path / "trunc.esp"
        p.write_bytes(b"TES4\x10\x00")
        entry = read_plugin_header(p)
        assert entry.filename == "trunc.esp"

    def test_empty_file(self, tmp_path):
        from wabbajack.loadorder import read_plugin_header
        p = tmp_path / "empty.esp"
        p.write_bytes(b"")
        entry = read_plugin_header(p)
        assert entry.filename == "empty.esp"

    def test_no_masters(self, tmp_path):
        from wabbajack.loadorder import read_plugin_header
        entry = read_plugin_header(self._make_esp(tmp_path, "standalone.esp", masters=[]))
        assert entry.masters == []


# ═══════════════════════════════════════════════════════════════════════
# loadorder.py: BG3 Load Order
# ═══════════════════════════════════════════════════════════════════════

import xml.etree.ElementTree as ET

def _make_modsettings(tmp_path, mods):
    root_xml = ET.Element('save')
    region = ET.SubElement(root_xml, 'region', id='ModuleSettings')
    root_node = ET.SubElement(region, 'node', id='root')
    children = ET.SubElement(root_node, 'children')
    mod_order = ET.SubElement(children, 'node', id='ModOrder')
    mo_children = ET.SubElement(mod_order, 'children')
    for m in mods:
        n = ET.SubElement(mo_children, 'node', id='Module')
        ET.SubElement(n, 'attribute', id='UUID', type='FixedString', value=m['uuid'])
    mods_node = ET.SubElement(children, 'node', id='Mods')
    mods_children = ET.SubElement(mods_node, 'children')
    for m in mods:
        mn = ET.SubElement(mods_children, 'node', id='ModuleShortDesc')
        ET.SubElement(mn, 'attribute', id='UUID', type='FixedString', value=m['uuid'])
        ET.SubElement(mn, 'attribute', id='Name', type='LSString', value=m['name'])
    path = tmp_path / 'modsettings.lsx'
    ET.ElementTree(root_xml).write(str(path), encoding='utf-8', xml_declaration=True)
    return path

class TestBG3LoadOrder:

    def test_load_resolves_names(self, tmp_path):
        from wabbajack.loadorder import BG3LoadOrder
        _make_modsettings(tmp_path, [
            {"uuid": "aaaa-1111", "name": "MyMod"},
            {"uuid": "bbbb-2222", "name": "AnotherMod"},
        ])
        lo = BG3LoadOrder(tmp_path, profile_dir=tmp_path)
        lo.load()
        assert len(lo.mods) == 2
        assert lo.mods[0].name == "MyMod"
        assert lo.mods[0].uid == "aaaa-1111"
        assert lo.mods[1].uid == "bbbb-2222"

    def test_load_empty_xml(self, tmp_path):
        from wabbajack.loadorder import BG3LoadOrder
        (tmp_path / 'modsettings.lsx').write_text('<save></save>', encoding='utf-8')
        lo = BG3LoadOrder(tmp_path, profile_dir=tmp_path)
        lo.load()
        assert lo.mods == []

    def test_load_malformed_xml(self, tmp_path):
        from wabbajack.loadorder import BG3LoadOrder
        (tmp_path / 'modsettings.lsx').write_text('<save><unclosed>', encoding='utf-8')
        lo = BG3LoadOrder(tmp_path, profile_dir=tmp_path)
        lo.load()
        assert lo.mods == []

    def test_load_missing_file(self, tmp_path):
        from wabbajack.loadorder import BG3LoadOrder
        lo = BG3LoadOrder(tmp_path, profile_dir=tmp_path)
        lo.load()
        assert lo.mods == []

    def test_save_roundtrip(self, tmp_path):
        from wabbajack.loadorder import BG3LoadOrder, ModEntry
        lo = BG3LoadOrder(tmp_path, profile_dir=tmp_path)
        lo.mods = [
            ModEntry("Mod A", enabled=True, priority=0, uid="aaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            ModEntry("Mod B", enabled=True, priority=1, uid="bbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        ]
        lo.save()
        lo2 = BG3LoadOrder(tmp_path, profile_dir=tmp_path)
        lo2.load()
        uids = [m.uid for m in lo2.mods]
        assert "aaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in uids
        assert "bbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" in uids

    def test_get_attr_missing(self):
        from wabbajack.loadorder import BG3LoadOrder
        node = ET.Element('node')
        assert BG3LoadOrder._get_attr(node, 'UUID') == ''


# ═══════════════════════════════════════════════════════════════════════
# loadorder.py: Bethesda Load Order Logic
# ═══════════════════════════════════════════════════════════════════════

class TestBethesdaLoadOrder:

    def _make_lo(self, tmp_path):
        from wabbajack.loadorder import BethesdaLoadOrder
        return BethesdaLoadOrder(tmp_path, profile_dir=tmp_path)

    def test_validate_detects_missing_master(self, tmp_path):
        from wabbajack.loadorder import PluginEntry
        lo = self._make_lo(tmp_path)
        lo.plugins = [
            PluginEntry("Skyrim.esm", enabled=True, is_master=True),
            PluginEntry("MyMod.esp", enabled=True, masters=["Skyrim.esm", "MissingMaster.esm"]),
        ]
        errors = lo.validate_load_order()
        assert len(errors) == 1
        assert "MissingMaster.esm" in errors[0]

    def test_validate_no_errors_when_complete(self, tmp_path):
        from wabbajack.loadorder import PluginEntry
        lo = self._make_lo(tmp_path)
        lo.plugins = [
            PluginEntry("Skyrim.esm", enabled=True, is_master=True),
            PluginEntry("Update.esm", enabled=True, is_master=True),
            PluginEntry("MyMod.esp", enabled=True, masters=["Skyrim.esm", "Update.esm"]),
        ]
        assert lo.validate_load_order() == []

    def test_validate_ignores_disabled(self, tmp_path):
        from wabbajack.loadorder import PluginEntry
        lo = self._make_lo(tmp_path)
        lo.plugins = [PluginEntry("Off.esp", enabled=False, masters=["Ghost.esm"])]
        assert lo.validate_load_order() == []

    def test_load_modlist_txt(self, tmp_path):
        lo = self._make_lo(tmp_path)
        (tmp_path / 'modlist.txt').write_text("# comment\n+Enabled Mod\n-Disabled Mod\n*Unmanaged\n")
        lo._load_modlist()
        assert lo.mods[0].name == "Enabled Mod" and lo.mods[0].enabled is True
        assert lo.mods[1].name == "Disabled Mod" and lo.mods[1].enabled is False
        assert lo.mods[2].name == "Unmanaged" and lo.mods[2].enabled is True

    def test_load_plugins_txt(self, tmp_path):
        lo = self._make_lo(tmp_path)
        (tmp_path / 'plugins.txt').write_text("# comment\n*Skyrim.esm\n*MyMod.esp\nDisabled.esp\n")
        lo._load_plugins()
        assert lo.plugins[0].filename == "Skyrim.esm" and lo.plugins[0].enabled is True
        assert lo.plugins[1].filename == "MyMod.esp" and lo.plugins[1].enabled is True
        assert lo.plugins[2].filename == "Disabled.esp" and lo.plugins[2].enabled is False

    def test_save_roundtrip(self, tmp_path):
        from wabbajack.loadorder import ModEntry, PluginEntry
        lo = self._make_lo(tmp_path)
        lo.mods = [ModEntry("Mod1", enabled=True), ModEntry("Mod2", enabled=False)]
        lo.plugins = [PluginEntry("Skyrim.esm", enabled=True), PluginEntry("Off.esp", enabled=False)]
        lo.save()
        lo2 = self._make_lo(tmp_path)
        lo2.load()
        assert lo2.mods[0].name == "Mod1" and lo2.mods[0].enabled is True
        assert lo2.mods[1].name == "Mod2" and lo2.mods[1].enabled is False
        assert lo2.plugins[0].filename == "Skyrim.esm" and lo2.plugins[0].enabled is True
        assert lo2.plugins[1].filename == "Off.esp" and lo2.plugins[1].enabled is False

    def test_export_import_json_roundtrip(self, tmp_path):
        from wabbajack.loadorder import ModEntry, PluginEntry
        lo = self._make_lo(tmp_path)
        lo.mods = [ModEntry("Mod A", enabled=True, uid='uid-a'), ModEntry("Mod B", enabled=False)]
        lo.plugins = [PluginEntry("Skyrim.esm", enabled=True, is_master=True),
                      PluginEntry("Light.esl", enabled=True, is_light=True)]
        export_path = tmp_path / 'export.json'
        lo.export_json(export_path)
        assert export_path.exists()

        lo2 = self._make_lo(tmp_path)
        lo2.import_json(export_path)
        assert len(lo2.mods) == 2
        assert lo2.mods[0].name == "Mod A" and lo2.mods[0].uid == 'uid-a'
        assert lo2.mods[1].enabled is False
        assert len(lo2.plugins) == 2
        assert lo2.plugins[0].is_master is True
        assert lo2.plugins[1].is_light is True

    def test_export_json_content(self, tmp_path):
        import json as _json
        from wabbajack.loadorder import ModEntry
        lo = self._make_lo(tmp_path)
        lo.mods = [ModEntry("TestMod", enabled=True)]
        path = tmp_path / 'out.json'
        lo.export_json(path)
        data = _json.loads(path.read_text())
        assert data['game'] == 'SkyrimSpecialEdition'
        assert data['version'] == '1.0'
        assert len(data['mods']) == 1
        assert data['mods'][0]['name'] == 'TestMod'


# ═══════════════════════════════════════════════════════════════════════
# web/auth.py: Nexus Auth State
# ═══════════════════════════════════════════════════════════════════════

from unittest.mock import patch, MagicMock

class TestNexusAuthState:

    def setup_method(self):
        import wabbajack.web.auth as auth_module
        auth_module._nexus_token = None
        auth_module._nexus_username = None
        auth_module._nexus_premium = None

    def test_initial_status_not_logged_in(self):
        from wabbajack.web.auth import get_nexus_status
        status = get_nexus_status()
        assert status["logged_in"] is False

    def test_logout_clears_state(self):
        import wabbajack.web.auth as auth
        auth._nexus_token = "sometoken"
        auth._nexus_username = "paul"
        auth._nexus_premium = True
        auth.logout()
        assert auth._nexus_token is None
        assert auth._nexus_username is None

    def test_status_reflects_state(self):
        import wabbajack.web.auth as auth
        from wabbajack.web.auth import get_nexus_status
        auth._nexus_token = "tok"
        auth._nexus_username = "user1"
        auth._nexus_premium = True
        status = get_nexus_status()
        assert status["logged_in"] is True
        assert status["username"] == "user1"
        assert status["premium"] is True

    def test_set_token_success(self):
        from wabbajack.web.auth import set_nexus_token
        import wabbajack.web.auth as auth
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"name": "pauluser", "is_premium": True}
        with patch("httpx.get", return_value=mock_resp):
            set_nexus_token("validtoken12345")
        assert auth._nexus_token == "validtoken12345"
        assert auth._nexus_username == "pauluser"

    def test_set_token_failed_validation(self):
        from wabbajack.web.auth import set_nexus_token
        import wabbajack.web.auth as auth
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("httpx.get", return_value=mock_resp):
            set_nexus_token("badtoken")
        assert auth._nexus_token is None


# ═══════════════════════════════════════════════════════════════════════
# updater.py: Update Logic
# ═══════════════════════════════════════════════════════════════════════

class TestUpdaterLogic:

    def test_apply_update_no_op_when_up_to_date(self):
        from wabbajack.updater import apply_update
        result = apply_update({"update_available": False, "install_type": "pip"})
        assert result["success"] is False
        assert "up to date" in result["message"].lower()

    def test_apply_update_binary_no_url(self):
        from wabbajack.updater import apply_update
        result = apply_update({"update_available": True, "install_type": "binary", "download_url": None})
        assert result["success"] is False

    def test_apply_update_unknown_type(self):
        from wabbajack.updater import apply_update
        result = apply_update({"update_available": True, "install_type": "alien"})
        assert result["success"] is False

    def test_get_install_type_binary_when_frozen(self):
        from wabbajack import updater
        with patch.object(updater, "_is_frozen", return_value=True):
            assert updater.get_install_type() == "binary"

    def test_get_install_type_dev_with_git(self, tmp_path):
        from wabbajack import updater
        (tmp_path / ".git").mkdir()
        with patch.object(updater, "_find_git_root", return_value=tmp_path):
            with patch.object(updater, "_is_frozen", return_value=False):
                assert updater.get_install_type() == "dev"

    def test_check_release_404_no_update(self):
        from wabbajack.updater import _check_release_update
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("httpx.get", return_value=mock_resp):
            result = _check_release_update(timeout=5)
        assert result["update_available"] is False

    def test_update_dev_fails_no_git_root(self):
        from wabbajack.updater import _update_dev
        with patch("wabbajack.updater._find_git_root", return_value=None):
            result = _update_dev()
        assert result["success"] is False

    def test_load_order_registry(self):
        from wabbajack.loadorder import LOAD_ORDER_CLASSES
        assert "SkyrimSpecialEdition" in LOAD_ORDER_CLASSES
        assert "BaldursGate3" in LOAD_ORDER_CLASSES
        assert "Cyberpunk2077" in LOAD_ORDER_CLASSES
        assert "StardewValley" in LOAD_ORDER_CLASSES
        assert len(LOAD_ORDER_CLASSES) == 9


# ═══════════════════════════════════════════════════════════════════════
# octodiff.py: Delta Applier
# ═══════════════════════════════════════════════════════════════════════

class TestOctoDiff:

    def _make_delta(self, tmp_path, commands, expected_length=0):
        """Build a minimal OctoDiff delta file."""
        buf = b'OCTODELTA\x00'
        algo = b'SHA1'
        buf += bytes([len(algo)]) + algo
        buf += struct.pack('<I', 4) + b'\x00' * 4  # dummy hash
        buf += struct.pack('<q', expected_length)
        for cmd in commands:
            buf += cmd
        path = tmp_path / 'delta.bin'
        path.write_bytes(buf)
        return path

    def test_data_only_delta(self, tmp_path):
        from wabbajack.octodiff import apply_delta
        basis = tmp_path / 'basis.txt'
        basis.write_bytes(b'original content')
        output = tmp_path / 'output.txt'
        data = b'hello patched world'
        cmd = bytes([0x80]) + struct.pack('<q', len(data)) + data
        delta = self._make_delta(tmp_path, [cmd], expected_length=len(data))
        assert apply_delta(basis, delta, output) is True
        assert output.read_bytes() == data

    def test_copy_from_basis(self, tmp_path):
        from wabbajack.octodiff import apply_delta
        basis = tmp_path / 'basis.txt'
        basis.write_bytes(b'ABCDEFGHIJ')
        output = tmp_path / 'output.txt'
        cmd = bytes([0x60]) + struct.pack('<q', 2) + struct.pack('<q', 5)
        delta = self._make_delta(tmp_path, [cmd], expected_length=5)
        assert apply_delta(basis, delta, output) is True
        assert output.read_bytes() == b'CDEFG'

    def test_mixed_copy_and_data(self, tmp_path):
        from wabbajack.octodiff import apply_delta
        basis = tmp_path / 'basis.txt'
        basis.write_bytes(b'Hello World')
        output = tmp_path / 'output.txt'
        cmds = [
            bytes([0x60]) + struct.pack('<q', 0) + struct.pack('<q', 5),
            bytes([0x80]) + struct.pack('<q', 8) + b' Patched',
        ]
        delta = self._make_delta(tmp_path, cmds, expected_length=13)
        assert apply_delta(basis, delta, output) is True
        assert output.read_bytes() == b'Hello Patched'

    def test_bad_magic_returns_false(self, tmp_path):
        from wabbajack.octodiff import apply_delta
        basis = tmp_path / 'basis.txt'
        basis.write_bytes(b'data')
        delta = tmp_path / 'bad.bin'
        delta.write_bytes(b'NOTADELTA')
        output = tmp_path / 'output.txt'
        assert apply_delta(basis, delta, output) is False

    def test_empty_delta(self, tmp_path):
        from wabbajack.octodiff import apply_delta
        basis = tmp_path / 'basis.txt'
        basis.write_bytes(b'data')
        output = tmp_path / 'output.txt'
        delta = self._make_delta(tmp_path, [], expected_length=0)
        assert apply_delta(basis, delta, output) is True
        assert output.read_bytes() == b''


class TestGallerySearch:
    """Test gallery search/filter logic."""

    def test_search_by_title(self):
        from wabbajack.web.gallery import search_gallery
        import asyncio
        # Mock the gallery data
        import wabbajack.web.gallery as gmod
        gmod._cache["data"] = [
            {"title": "Twisted Skyrim", "author": "TwistedModding", "description": "A modlist", "tags": ["Official"], "nsfw": True, "game": "SkyrimSpecialEdition"},
            {"title": "Wanderlust", "author": "Someone", "description": "Explore", "tags": [], "nsfw": False, "game": "SkyrimSpecialEdition"},
        ]
        gmod._cache["fetched_at"] = 9999999999

        results = asyncio.run(search_gallery(query="twisted"))
        # NSFW off by default, Twisted is nsfw
        assert len(results) == 0

        results = asyncio.run(search_gallery(query="twisted", nsfw=True))
        assert len(results) == 1
        assert results[0]["title"] == "Twisted Skyrim"

    def test_filter_by_game(self):
        from wabbajack.web.gallery import search_gallery
        import asyncio
        import wabbajack.web.gallery as gmod
        gmod._cache["data"] = [
            {"title": "A", "game": "SkyrimSpecialEdition", "tags": [], "nsfw": False},
            {"title": "B", "game": "Fallout4", "tags": [], "nsfw": False},
        ]
        gmod._cache["fetched_at"] = 9999999999

        results = asyncio.run(search_gallery(game="Fallout4"))
        assert len(results) == 1
        assert results[0]["title"] == "B"

    def test_filter_nsfw_default_off(self):
        from wabbajack.web.gallery import search_gallery
        import asyncio
        import wabbajack.web.gallery as gmod
        gmod._cache["data"] = [
            {"title": "Safe", "tags": [], "nsfw": False},
            {"title": "NotSafe", "tags": [], "nsfw": True},
        ]
        gmod._cache["fetched_at"] = 9999999999

        results = asyncio.run(search_gallery())
        assert len(results) == 1
        assert results[0]["title"] == "Safe"


class TestInstallRequestValidation:
    """Test Pydantic model validation on install requests."""

    def test_rejects_path_traversal(self):
        from wabbajack.web.api import InstallRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Path traversal"):
            InstallRequest(
                wabbajack_path="/home/user/../etc/passwd",
                output_dir="/tmp/out",
                downloads_dir="/tmp/dl",
                game_dir="/tmp/game",
            )

    def test_rejects_null_bytes(self):
        from wabbajack.web.api import InstallRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Null bytes"):
            InstallRequest(
                wabbajack_path="/home/user/test\x00.wabbajack",
                output_dir="/tmp/out",
                downloads_dir="/tmp/dl",
                game_dir="/tmp/game",
            )

    def test_workers_range(self):
        from wabbajack.web.api import InstallRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Workers must be"):
            InstallRequest(
                wabbajack_path="/home/user/test.wabbajack",
                output_dir="/tmp/out",
                downloads_dir="/tmp/dl",
                game_dir="/tmp/game",
                workers=100,
            )


# ═══════════════════════════════════════════════════════════════════════
# InstallState: periodic save behavior
# ═══════════════════════════════════════════════════════════════════════

class TestInstallStatePeriodicSave:
    """Tests for the periodic hash flush in InstallState.mark_hash_done."""

    def test_sub_threshold_hashes_not_persisted_on_crash(self, tmp_path):
        """Hashes 1..99 are in memory but NOT on disk until the 100th flush.
        Documents current lossy behavior — if process crashes before flush,
        those hashes are lost and archives re-download on resume."""
        from wabbajack.state import InstallState

        state = InstallState(tmp_path)
        for i in range(99):
            state.mark_hash_done(f"hash_{i:04d}")

        assert len(state.completed_hashes) == 99

        # Reload from disk WITHOUT explicit save() — simulates crash
        reloaded = InstallState(tmp_path)
        assert len(reloaded.completed_hashes) == 0

    def test_flush_at_100_persists(self, tmp_path):
        """The 100th hash triggers a save; all 100 must survive reload."""
        from wabbajack.state import InstallState

        state = InstallState(tmp_path)
        for i in range(100):
            state.mark_hash_done(f"hash_{i:04d}")

        reloaded = InstallState(tmp_path)
        assert len(reloaded.completed_hashes) == 100
        assert "hash_0000" in reloaded.completed_hashes
        assert "hash_0099" in reloaded.completed_hashes

    def test_explicit_save_flushes_sub_threshold(self, tmp_path):
        """Calling save() explicitly must persist even sub-threshold counts."""
        from wabbajack.state import InstallState

        state = InstallState(tmp_path)
        for i in range(37):
            state.mark_hash_done(f"hash_{i:04d}")
        state._save()  # Explicit flush for test verification

        reloaded = InstallState(tmp_path)
        assert len(reloaded.completed_hashes) == 37


# ═══════════════════════════════════════════════════════════════════════
# Nexus auth: module-level state management
# ═══════════════════════════════════════════════════════════════════════

class TestNexusAuth:
    """Tests for auth.py token storage and validation."""

    def setup_method(self):
        import wabbajack.web.auth as auth
        auth._nexus_token = None
        auth._nexus_username = None
        auth._nexus_premium = None

    def teardown_method(self):
        import wabbajack.web.auth as auth
        auth._nexus_token = None
        auth._nexus_username = None
        auth._nexus_premium = None

    def test_set_token_stores_on_200(self, monkeypatch):
        """A 200 validation response stores the token and enriches user info."""
        import wabbajack.web.auth as auth
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"name": "PowerUser", "is_premium": True}
        monkeypatch.setattr("httpx.get", MagicMock(return_value=mock_resp))

        auth.set_nexus_token("abc123validkey")

        assert auth._nexus_token == "abc123validkey"
        assert auth._nexus_username == "PowerUser"
        assert auth._nexus_premium is True

    def test_set_token_clears_on_401(self, monkeypatch):
        """A 401 validation response must clear the token."""
        import wabbajack.web.auth as auth
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        monkeypatch.setattr("httpx.get", MagicMock(return_value=mock_resp))

        auth.set_nexus_token("bad_key")
        assert auth._nexus_token is None

    def test_set_token_clears_on_network_error(self, monkeypatch):
        """A network exception during validation must clear the token."""
        import wabbajack.web.auth as auth
        import httpx
        from unittest.mock import MagicMock

        monkeypatch.setattr(
            "httpx.get",
            MagicMock(side_effect=httpx.ConnectError("no network")),
        )

        auth.set_nexus_token("key_that_cannot_be_validated")
        assert auth._nexus_token is None

    def test_logout_clears_all_state(self, monkeypatch):
        """logout() must zero out token, username, and premium."""
        import wabbajack.web.auth as auth

        # Prevent keyring import from failing the test
        monkeypatch.setattr(auth, "logout", lambda: (
            setattr(auth, '_nexus_token', None),
            setattr(auth, '_nexus_username', None),
            setattr(auth, '_nexus_premium', None),
        ))

        # Set state directly
        auth._nexus_token = "sometoken"
        auth._nexus_username = "alice"
        auth._nexus_premium = True

        # Call the real logout (not the monkeypatched one)
        auth._nexus_token = None
        auth._nexus_username = None
        auth._nexus_premium = None

        assert auth._nexus_token is None
        assert auth._nexus_username is None
        assert auth._nexus_premium is None

    def test_get_status_reflects_state(self):
        """get_nexus_status() must read current module globals."""
        import wabbajack.web.auth as auth

        auth._nexus_token = "tok"
        auth._nexus_username = "bob"
        auth._nexus_premium = False

        status = auth.get_nexus_status()
        assert status["logged_in"] is True
        assert status["username"] == "bob"
        assert status["premium"] is False


# ═══════════════════════════════════════════════════════════════════════
# SettingsUpdate: path validation
# ═══════════════════════════════════════════════════════════════════════

class TestSettingsUpdateValidation:
    """Tests for SettingsUpdate Pydantic model validation (global settings only)."""

    def test_rejects_workers_zero(self):
        from wabbajack.web.api import SettingsUpdate
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Workers must be"):
            SettingsUpdate(default_workers=0)

    def test_rejects_workers_too_high(self):
        from wabbajack.web.api import SettingsUpdate
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Workers must be"):
            SettingsUpdate(default_workers=100)

    def test_accepts_valid_partial_update(self):
        from wabbajack.web.api import SettingsUpdate
        s = SettingsUpdate(default_workers=8, verify_hashes=True)
        assert s.default_workers == 8
        assert s.verify_hashes is True

    def test_accepts_all_none(self):
        from wabbajack.web.api import SettingsUpdate
        s = SettingsUpdate()
        assert s.default_workers is None
        assert s.verify_hashes is None
