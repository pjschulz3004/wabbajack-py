"""Fetch modlist gallery from Wabbajack's GitHub-hosted repositories."""
import time, logging

log = logging.getLogger(__name__)

REPOS_URL = "https://raw.githubusercontent.com/wabbajack-tools/mod-lists/master/repositories.json"
CACHE_TTL = 3600

_cache = {"data": None, "fetched_at": 0}


async def fetch_gallery():
    """Fetch and cache the full modlist gallery."""
    now = time.time()
    if _cache["data"] and now - _cache["fetched_at"] < CACHE_TTL:
        return _cache["data"]

    try:
        import httpx
    except ImportError:
        log.warning("httpx not installed -- gallery unavailable (pip install httpx)")
        return []
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        try:
            resp = await client.get(REPOS_URL)
            repos = resp.json()

            all_lists = []
            for repo in repos:
                try:
                    r = await client.get(repo["url"], timeout=15)
                    lists = r.json()
                    if isinstance(lists, list):
                        all_lists.extend(lists)
                except Exception:
                    continue

            _cache["data"] = all_lists
            _cache["fetched_at"] = now
            log.info(f"Gallery: {len(all_lists)} modlists from {len(repos)} repos")
            return all_lists

        except Exception as e:
            log.warning(f"Gallery fetch failed: {e}")
            return _cache["data"] or []


async def fetch_gallery_item(machine_url: str):
    """Find a single modlist by machineURL."""
    gallery = await fetch_gallery()
    for item in gallery:
        if item.get("links", {}).get("machineURL") == machine_url:
            return item
    return None
