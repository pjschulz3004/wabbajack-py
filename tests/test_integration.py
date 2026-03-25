"""Integration tests using the real TwistedSkyrim .wabbajack file.

These tests require:
  - /home/paul/Jackify/downloaded_mod_lists/WakingDreams_@@_TwistedSkyrim.wabbajack.bak
  - /home/paul/Games/TwistedSkyrim/downloads/
"""
import pytest
from pathlib import Path
from tests.conftest import requires_wabbajack, requires_downloads, WABBAJACK_FILE, DOWNLOADS_DIR


# ═══════════════════════════════════════════════════════════════════════
# Parsing the real modlist
# ═══════════════════════════════════════════════════════════════════════

@requires_wabbajack
class TestRealModlistParsing:

    def test_name_and_version(self, real_modlist):
        assert real_modlist.name == "Twisted Skyrim"
        assert real_modlist.version is not None
        assert len(real_modlist.version) > 0

    def test_game_type(self, real_modlist):
        assert real_modlist.game == "SkyrimSpecialEdition"

    def test_archives_count(self, real_modlist):
        """The modlist should have ~5667 archives per project memory."""
        count = len(real_modlist.archives)
        assert count > 5000, f"Expected ~5667 archives, got {count}"
        assert count < 7000

    def test_directives_count(self, real_modlist):
        """The modlist should have ~651462 directives per project memory."""
        count = len(real_modlist.directives)
        assert count > 600000, f"Expected ~651462 directives, got {count}"
        assert count < 800000

    def test_archive_type_counts(self, real_modlist):
        counts = real_modlist.archive_type_counts()
        # Should have at least Nexus and HTTP archives
        found_nexus = any("Nexus" in k for k in counts)
        found_http = any("Http" in k or "WabbajackCDN" in k for k in counts)
        assert found_nexus, f"No Nexus archives found in types: {list(counts.keys())}"
        assert found_http, f"No HTTP archives found in types: {list(counts.keys())}"
        # Total should match archives count
        assert sum(counts.values()) == len(real_modlist.archives)

    def test_directive_type_counts(self, real_modlist):
        counts = real_modlist.directive_type_counts()
        found_from_archive = any("FromArchive" in k for k in counts)
        assert found_from_archive, f"No FromArchive directives: {list(counts.keys())}"
        assert sum(counts.values()) == len(real_modlist.directives)

    def test_summary_structure(self, real_modlist):
        s = real_modlist.summary()
        assert s["name"] == "Twisted Skyrim"
        assert isinstance(s["archives"], int)
        assert isinstance(s["directives"], int)
        assert isinstance(s["archive_types"], dict)
        assert isinstance(s["directive_types"], dict)

    def test_archives_have_required_fields(self, real_modlist):
        """Every archive should have Hash, Name, and State.$type."""
        for i, a in enumerate(real_modlist.archives[:100]):  # spot check first 100
            assert "Hash" in a, f"Archive {i} missing Hash"
            assert "Name" in a, f"Archive {i} missing Name"
            assert "State" in a, f"Archive {i} missing State"
            assert "$type" in a["State"], f"Archive {i} State missing $type"

    def test_directives_have_required_fields(self, real_modlist):
        for i, d in enumerate(real_modlist.directives[:100]):
            assert "$type" in d, f"Directive {i} missing $type"
            assert "To" in d, f"Directive {i} missing To"

    def test_author(self, real_modlist):
        author = real_modlist.author
        assert isinstance(author, str)
        assert len(author) > 0


# ═══════════════════════════════════════════════════════════════════════
# Archive presence checking with real downloads directory
# ═══════════════════════════════════════════════════════════════════════

@requires_wabbajack
@requires_downloads
class TestArchivePresence:

    def _make_installer(self, real_modlist, tmp_path):
        from wabbajack.installer import ModlistInstaller
        output = tmp_path / "output"
        game = tmp_path / "game"
        output.mkdir()
        game.mkdir()
        return ModlistInstaller(
            real_modlist, output, DOWNLOADS_DIR, game, workers=1,
        )

    def test_downloads_index_populated(self, real_modlist, tmp_path):
        inst = self._make_installer(real_modlist, tmp_path)
        assert len(inst.downloads_index) > 0

    def test_some_archives_present(self, real_modlist, tmp_path):
        inst = self._make_installer(real_modlist, tmp_path)
        present = sum(1 for a in real_modlist.archives if inst._is_archive_present(a))
        total = len(real_modlist.archives)
        assert present > 0, "Expected at least some archives to be present in downloads"
        # Log what we found for informational purposes
        print(f"\n  Archives present: {present}/{total} ({present/total*100:.1f}%)")

    def test_known_file_found(self, real_modlist, tmp_path):
        """At least one archive with a matching name should exist in downloads."""
        inst = self._make_installer(real_modlist, tmp_path)
        # Find any archive whose name exists in downloads
        found_any = False
        for a in real_modlist.archives[:500]:
            name = a["Name"]
            dl_path = DOWNLOADS_DIR / name
            if dl_path.exists():
                assert inst._is_archive_present(a), f"{name} exists on disk but _is_archive_present returned False"
                found_any = True
                break
        assert found_any, "No archives from the modlist found in the downloads directory"

    def test_classify_real_archives(self, real_modlist):
        """classify_archive should handle all archive types in the real modlist."""
        from wabbajack.downloaders import classify_archive
        results = {}
        for a in real_modlist.archives:
            cat = classify_archive(a)
            results[cat] = results.get(cat, 0) + 1
        print(f"\n  Archive categories: {results}")
        # Should have no crashes and at least 2 categories
        assert len(results) >= 2
