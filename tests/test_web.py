"""Tests for wabbajack-py FastAPI web API."""
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from wabbajack.web import create_app, SESSION_TOKEN


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a TestClient with session token for authenticated requests."""
    return TestClient(app, headers={"X-Session-Token": SESSION_TOKEN})


# ── GET /api/games ──────────────────────────────────────────────────


def test_get_games_returns_list(client):
    """GET /api/games returns installed games, not_found, and total_supported."""
    with patch("wabbajack.platform.find_steam_libraries", return_value=[]):
        resp = client.get("/api/games")
    assert resp.status_code == 200
    data = resp.json()
    assert "libraries" in data
    assert "games" in data
    assert "not_found" in data
    assert "total_supported" in data
    assert isinstance(data["games"], list)
    assert isinstance(data["not_found"], list)
    # With no libraries, all games should be in not_found
    assert len(data["games"]) == 0
    assert len(data["not_found"]) == data["total_supported"]


def test_get_games_with_installed_game(client, tmp_path):
    """A game shows installed=True when its directory exists."""
    # Create a fake steam library with a Skyrim SE directory
    fake_lib = tmp_path / "steamapps" / "common"
    (fake_lib / "Skyrim Special Edition").mkdir(parents=True)

    with patch("wabbajack.platform.find_steam_libraries", return_value=[fake_lib]):
        resp = client.get("/api/games")
    data = resp.json()
    sse = [g for g in data["games"] if g["id"] == "SkyrimSpecialEdition"]
    assert len(sse) == 1
    assert sse[0]["installed"] is True
    assert sse[0]["path"] is not None


# ── GET /api/gallery ────────────────────────────────────────────────


def test_get_gallery_returns_list(client):
    """GET /api/gallery returns a list (may be empty if no network)."""
    with patch("wabbajack.web.gallery.fetch_gallery", return_value=[]):
        resp = client.get("/api/gallery")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── GET /api/settings ──────────────────────────────────────────────


def test_get_settings_returns_dict(client, tmp_path):
    """GET /api/settings returns a dict (config summary)."""
    with patch("wabbajack.web.api.Path") as mock_path:
        mock_path.home.return_value = tmp_path
        resp = client.get("/api/settings")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


# ── GET /api/profiles ──────────────────────────────────────────────


def test_get_profiles_returns_expected_keys(client, tmp_path):
    """GET /api/profiles returns dict with 'active', 'profiles' keys."""
    with patch("wabbajack.profiles.ProfileManager") as MockPM:
        pm = MockPM.return_value
        pm.active = None
        pm.shared_downloads = tmp_path / "Downloads"
        pm.profiles = {}
        resp = client.get("/api/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert "active" in data
    assert "profiles" in data
    assert isinstance(data["profiles"], dict)


# ── GET /api/install/status ────────────────────────────────────────


def test_install_status_not_running(client):
    """GET /api/install/status returns running=false when no install is active."""
    resp = client.get("/api/install/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"running": False}


# ── GET /api/auth/nexus/status ─────────────────────────────────────


def test_nexus_status_returns_logged_in_key(client):
    """GET /api/auth/nexus/status returns dict with 'logged_in' key."""
    with patch("wabbajack.web.auth.get_nexus_status", return_value={
        "logged_in": False, "username": None, "premium": None,
    }), patch("wabbajack.web.auth.load_saved_token"):
        resp = client.get("/api/auth/nexus/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "logged_in" in data
    assert isinstance(data["logged_in"], bool)


# ── POST /api/modlist/open (validation) ────────────────────────────


def test_open_modlist_invalid_path(client):
    """POST /api/modlist/open with nonexistent path returns 400 or 404."""
    resp = client.post(
        "/api/modlist/open",
        params={"wabbajack_path": "/nonexistent/fake.wabbajack"},
    )
    assert resp.status_code in (400, 404)


def test_open_modlist_traversal_path(client):
    """POST /api/modlist/open with '..' traversal returns 400."""
    resp = client.post(
        "/api/modlist/open",
        params={"wabbajack_path": "/tmp/../etc/passwd.wabbajack"},
    )
    assert resp.status_code == 400


def test_open_modlist_wrong_extension(client):
    """POST /api/modlist/open with non-.wabbajack extension returns 400."""
    resp = client.post(
        "/api/modlist/open",
        params={"wabbajack_path": "/tmp/somefile.zip"},
    )
    assert resp.status_code == 400


# ── POST /api/install/start (validation) ──────────────────────────


def test_install_start_workers_too_high(client):
    """POST /api/install/start with workers > 64 returns 422."""
    resp = client.post("/api/install/start", json={
        "wabbajack_path": "/tmp/test.wabbajack",
        "output_dir": "/tmp/out",
        "downloads_dir": "/tmp/dl",
        "game_dir": "/tmp/game",
        "workers": 100,
    })
    assert resp.status_code == 422


def test_install_start_workers_zero(client):
    """POST /api/install/start with workers=0 returns 422."""
    resp = client.post("/api/install/start", json={
        "wabbajack_path": "/tmp/test.wabbajack",
        "output_dir": "/tmp/out",
        "downloads_dir": "/tmp/dl",
        "game_dir": "/tmp/game",
        "workers": 0,
    })
    assert resp.status_code == 422


def test_install_start_null_byte_in_path(client):
    """POST /api/install/start with null byte in path returns 422."""
    resp = client.post("/api/install/start", json={
        "wabbajack_path": "/tmp/test\x00.wabbajack",
        "output_dir": "/tmp/out",
        "downloads_dir": "/tmp/dl",
        "game_dir": "/tmp/game",
        "workers": 4,
    })
    assert resp.status_code == 422


def test_install_start_path_traversal_rejected(client):
    """POST /api/install/start with '..' in path returns 422."""
    resp = client.post("/api/install/start", json={
        "wabbajack_path": "/tmp/../etc/shadow",
        "output_dir": "/tmp/out",
        "downloads_dir": "/tmp/dl",
        "game_dir": "/tmp/game",
        "workers": 4,
    })
    assert resp.status_code == 422


# ── WebSocket /ws ──────────────────────────────────────────────────


def test_websocket_connect_accepted(client):
    """WebSocket connection to /ws is accepted."""
    with client.websocket_connect(f"/ws?token={SESSION_TOKEN}") as ws:
        # Connection was accepted if we get here without exception
        assert ws is not None


def test_websocket_valid_command(client):
    """Sending a valid 'cancel' command does not crash."""
    with client.websocket_connect(f"/ws?token={SESSION_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "cancel"}))
        # No error means success -- the server silently processes it


def test_websocket_invalid_command_type(client):
    """Sending an unknown command type does not crash the server."""
    with client.websocket_connect(f"/ws?token={SESSION_TOKEN}") as ws:
        ws.send_text(json.dumps({"type": "bogus_command"}))
        # Server should silently drop it, no crash


def test_websocket_malformed_json(client):
    """Sending non-JSON text does not crash the server."""
    with client.websocket_connect(f"/ws?token={SESSION_TOKEN}") as ws:
        ws.send_text("this is not json {{{")
        # Server should silently drop it


def test_websocket_oversized_message(client):
    """Sending an oversized message (>4096 bytes) is silently dropped."""
    with client.websocket_connect(f"/ws?token={SESSION_TOKEN}") as ws:
        huge = json.dumps({"type": "cancel", "padding": "x" * 5000})
        ws.send_text(huge)
        # Server should drop it, no crash


# ── Security: Unauthenticated access ─────────────────────────────


@pytest.fixture
def unauth_client(app):
    """TestClient without session token — for testing 403 responses."""
    return TestClient(app)


def test_post_without_token_returns_403(unauth_client):
    """POST to mutating endpoint without session token returns 403."""
    resp = unauth_client.post("/api/install/start", json={
        "wabbajack_path": "/tmp/test.wabbajack",
        "output_dir": "/tmp/out",
        "downloads_dir": "/tmp/dl",
        "game_dir": "/tmp/game",
    })
    assert resp.status_code == 403


def test_websocket_without_token_rejected(unauth_client):
    """WebSocket connection without token is rejected."""
    try:
        with unauth_client.websocket_connect("/ws") as ws:
            pytest.fail("Should have been rejected")
    except Exception:
        pass  # Expected: connection refused or closed


def test_websocket_wrong_token_rejected(unauth_client):
    """WebSocket connection with wrong token is rejected."""
    try:
        with unauth_client.websocket_connect("/ws?token=wrong") as ws:
            pytest.fail("Should have been rejected")
    except Exception:
        pass  # Expected: connection refused or closed


# ── Security: DNS Rebinding / TrustedHost ────────────────────────


def test_untrusted_host_rejected(app):
    """Requests with non-localhost Host header are rejected by TrustedHostMiddleware."""
    evil_client = TestClient(app, headers={"Host": "evil.example.com"})
    resp = evil_client.get("/api/install/status")
    assert resp.status_code == 400


# ── Games endpoint: installed vs not_found ────────────────────────


def test_installed_game_in_games_not_not_found(client, tmp_path):
    """Installed game appears in 'games' list, not in 'not_found'."""
    fake_lib = tmp_path / "steamapps" / "common"
    (fake_lib / "Skyrim Special Edition").mkdir(parents=True)

    with patch("wabbajack.platform.find_steam_libraries", return_value=[fake_lib]):
        resp = client.get("/api/games")
    data = resp.json()
    game_ids = [g["id"] for g in data["games"]]
    not_found_ids = [g["id"] for g in data["not_found"]]
    assert "SkyrimSpecialEdition" in game_ids
    assert "SkyrimSpecialEdition" not in not_found_ids
