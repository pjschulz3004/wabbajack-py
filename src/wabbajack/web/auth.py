"""Nexus Mods SSO authentication via WebSocket."""
import uuid, json, logging, asyncio
from typing import Optional

log = logging.getLogger(__name__)

_nexus_token: Optional[str] = None
_nexus_username: Optional[str] = None
_nexus_premium: Optional[bool] = None


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
    """Clear Nexus credentials."""
    global _nexus_token, _nexus_username, _nexus_premium
    _nexus_token = None
    _nexus_username = None
    _nexus_premium = None

    # Try to clear from keyring
    try:
        import keyring
        keyring.delete_password("wabbajack-py", "nexus_api_key")
    except Exception:
        pass


def load_saved_token():
    """Try to load Nexus token from keyring or config."""
    global _nexus_token

    # Try keyring first
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
    """Save token to keyring (or fallback)."""
    try:
        import keyring
        keyring.set_password("wabbajack-py", "nexus_api_key", token)
    except Exception:
        pass
    set_nexus_token(token)


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

    auth_url = f"https://www.nexusmods.com/sso?id={request_id}&application=wabbajack-py"

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
                    if data.get("success") and data.get("data", {}).get("api_key"):
                        token = data["data"]["api_key"]
                        save_token(token)
                        log.info("Nexus SSO: authorization received")
                        return token
                except asyncio.TimeoutError:
                    log.warning("Nexus SSO: timed out waiting for authorization")
        except Exception as e:
            log.error(f"Nexus SSO error: {e}")
        return None

    return auth_url, wait_for_token
