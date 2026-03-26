"""Fetch modlist gallery from Wabbajack's GitHub-hosted repositories."""
import time, logging

log = logging.getLogger(__name__)

REPOS_URL = "https://raw.githubusercontent.com/wabbajack-tools/mod-lists/master/repositories.json"
CACHE_TTL = 3600

_cache = {"data": None, "fetched_at": 0}


async def fetch_gallery():
    """Fetch and cache the full modlist gallery from all Wabbajack repositories."""
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
            repos_data = resp.json()

            # repositories.json is a dict: {"name": "url", ...}
            if isinstance(repos_data, dict):
                repo_urls = list(repos_data.values())
            elif isinstance(repos_data, list):
                repo_urls = [r.get("url", r) if isinstance(r, dict) else r for r in repos_data]
            else:
                repo_urls = []

            import asyncio
            async def fetch_repo(url):
                try:
                    r = await client.get(url, timeout=15)
                    data = r.json()
                    return data if isinstance(data, list) else []
                except Exception:
                    return []

            results = await asyncio.gather(*[fetch_repo(url) for url in repo_urls])
            all_lists = []
            seen = set()
            for sublist in results:
                for item in sublist:
                    # Deduplicate by title+author
                    key = (item.get('title', ''), item.get('author', ''))
                    if key not in seen:
                        seen.add(key)
                        all_lists.append(item)

            _cache["data"] = all_lists
            _cache["fetched_at"] = now
            log.info(f"Gallery: {len(all_lists)} modlists from {len(repo_urls)} repos")
            return all_lists

        except Exception as e:
            log.warning(f"Gallery fetch failed: {e}")
            return _cache["data"] or []


async def search_gallery(query: str = '', game: str = '', tags: list[str] | None = None,
                         nsfw: bool = False) -> list[dict]:
    """Search the gallery with filters."""
    gallery = await fetch_gallery()
    results = gallery

    if query:
        q = query.lower()
        results = [m for m in results if
                   q in (m.get('title', '') or '').lower() or
                   q in (m.get('author', '') or '').lower() or
                   q in (m.get('description', '') or '').lower() or
                   any(q in t.lower() for t in m.get('tags', []))]

    if game:
        g = game.lower()
        results = [m for m in results if (m.get('game', '') or '').lower() == g]

    if tags:
        tag_set = {t.lower() for t in tags}
        results = [m for m in results if
                   tag_set & {t.lower() for t in m.get('tags', [])}]

    if not nsfw:
        results = [m for m in results if not m.get('nsfw')]

    return results


async def fetch_gallery_item(machine_url: str):
    """Find a single modlist by machineURL."""
    gallery = await fetch_gallery()
    for item in gallery:
        links = item.get("links", {})
        if isinstance(links, dict) and links.get("machineURL") == machine_url:
            return item
    return None
