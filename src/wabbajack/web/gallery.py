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

            # Fetch all repos in parallel
            import asyncio
            async def fetch_repo(url):
                try:
                    r = await client.get(url, timeout=15)
                    data = r.json()
                    return data if isinstance(data, list) else []
                except Exception:
                    return []

            results = await asyncio.gather(
                *[fetch_repo(repo["url"]) for repo in repos]
            )
            all_lists = [item for sublist in results for item in sublist]

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
