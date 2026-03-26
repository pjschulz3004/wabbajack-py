"""Nexus Mods SSO authentication via WebSocket."""
import uuid, json, logging, asyncio
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_nexus_token: Optional[str] = None
_nexus_username: Optional[str] = None
_nexus_premium: Optional[bool] = None

# File-based token storage (keyring fallback — keyring often fails on Linux)
_TOKEN_FILE = Path.home() / ".config" / "wabbajack-py" / "nexus_token.json"


def get_nexus_status():
    """Return current Nexus auth status."""
    return {
        "logged_in": _nexus_token is not None,
        "username": _nexus_username,
        "premium": _nexus_premium,
    }


def get_nexus_token():
    """Get stored Nexus API token."""
    return _nexus_token


def set_nexus_token(token: str):
    """Store Nexus API token and validate it."""
    global _nexus_token, _nexus_username, _nexus_premium
    _nexus_token = token

    # Validate token
    import requests
    try:
        resp = requests.get(
            "https://api.nexusmods.com/v1/users/validate.json",
            headers={"apikey": token, "accept": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            _nexus_username = data.get("name", "?")
            _nexus_premium = data.get("is_premium", False)
            log.info(f"Nexus: logged in as {_nexus_username} (Premium: {_nexus_premium})")
        else:
            log.warning(f"Nexus: token validation failed (HTTP {resp.status_code})")
            _nexus_token = None
    except Exception as e:
        log.warning(f"Nexus: validation error: {e}")
        _nexus_token = None


def logout():
    """Clear Nexus credentials from memory, file, and keyring."""
    global _nexus_token, _nexus_username, _nexus_premium
    _nexus_token = None
    _nexus_username = None
    _nexus_premium = None

    # Clear file
    try:
        _TOKEN_FILE.unlink(missing_ok=True)
    except OSError:
        pass

    # Clear keyring
    try:
        import keyring
        keyring.delete_password("wabbajack-py", "nexus_api_key")
    except Exception:
        pass


def load_saved_token():
    """Try to load Nexus token from file, keyring, or env var."""
    global _nexus_token

    # Try file first (most reliable on Linux)
    try:
        if _TOKEN_FILE.exists():
            data = json.loads(_TOKEN_FILE.read_text())
            token = data.get("api_key")
            if token:
                set_nexus_token(token)
                return
    except (json.JSONDecodeError, OSError) as e:
        log.debug(f"Could not load token file: {e}")

    # Try keyring
    try:
        import keyring
        token = keyring.get_password("wabbajack-py", "nexus_api_key")
        if token:
            set_nexus_token(token)
            return
    except Exception:
        pass

    # Fallback: check environment
    import os
    token = os.environ.get("NEXUS_API_KEY")
    if token:
        set_nexus_token(token)


def save_token(token: str):
    """Validate token with Nexus API, then persist to file and keyring."""
    # Validate FIRST — don't persist invalid tokens
    set_nexus_token(token)
    if _nexus_token is None:
        log.warning("Token validation failed — not saving to disk")
        return

    # Only persist after successful validation
    try:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(json.dumps({"api_key": token}))
        _TOKEN_FILE.chmod(0o600)
    except OSError as e:
        log.warning(f"Could not save token file: {e}")

    try:
        import keyring
        keyring.set_password("wabbajack-py", "nexus_api_key", token)
    except Exception:
        pass


async def initiate_sso():
    """Start Nexus SSO flow. Returns the authorization URL for the user to visit.

    The SSO flow uses Nexus's WebSocket-based SSO:
    1. Connect to wss://sso.nexusmods.com
    2. Send our UUID + app ID
    3. Return URL for user to authorize
    4. Wait for token on the WebSocket
    """
    request_id = str(uuid.uuid4())

    try:
        import websockets
    except ImportError:
        log.error("websockets package required for Nexus SSO (pip install websockets)")
        return None, None

    # Nexus SSO requires a registered application slug. 'vortex' is the only
    # publicly accepted value (used by Vortex, MO2, and other modding tools).
    # Custom app names like 'wabbajack-py' get rejected with "application ID was invalid".
    auth_url = f"https://www.nexusmods.com/sso?id={request_id}&application=vortex"

    async def wait_for_token():
        try:
            async with websockets.connect("wss://sso.nexusmods.com") as ws:
                await ws.send(json.dumps({
                    "id": request_id,
                    "token": None,
                    "protocol": 2,
                }))

                # Wait for Nexus to send back the API key (up to 5 minutes)
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=300)
                    data = json.loads(response)
                    if data.get("success") and isinstance(data.get("data"), dict):
                        token = data["data"].get("api_key", "")
                        # Validate token format (Nexus API keys are alphanumeric)
                        if token and len(token) > 10 and token.isascii():
                            save_token(token)
                            log.info("Nexus SSO: authorization received")
                            return token
                        else:
                            log.warning("Nexus SSO: received invalid token format")
                except asyncio.TimeoutError:
                    log.warning("Nexus SSO: timed out waiting for authorization")
        except Exception as e:
            log.error(f"Nexus SSO error: {e}")
        return None

    return auth_url, wait_for_token
