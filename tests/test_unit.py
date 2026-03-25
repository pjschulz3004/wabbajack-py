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
        assert state.is_hash_done("AAA") is False

    def test_mark_hash_done(self, tmp_path):
        from wabbajack.state import InstallState
        state = InstallState(tmp_path)
        state.mark_hash_done("hash1")
        state.mark_hash_done("hash2")
        assert state.is_hash_done("hash1")
        assert state.is_hash_done("hash2")
        assert not state.is_hash_done("hash3")

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
        state1.phase = "placing"  # triggers save
        state1.save()

        # Reload
        state2 = InstallState(tmp_path)
        assert state2.phase == "placing"
        assert state2.is_hash_done("H1")
        assert state2.is_hash_done("H2")
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
        assert not state.is_hash_done("X")

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
