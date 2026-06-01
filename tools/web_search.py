"""
Web search via local SearxNG instance.

Stand-alone usage:
    from tools.web_search import web_search
    results = web_search("python async best practices")

ReAct agent tool spec in web_search_tool_spec.
"""

import httpx

SEARXNG_URL = "http://localhost:8888"
DEFAULT_MAX_RESULTS = 5


def web_search(query: str, max_results: int = DEFAULT_MAX_RESULTS,
               searxng_url: str = SEARXNG_URL) -> list[dict]:
    """Query local SearxNG and return a list of result dicts.

    Each dict has: title, url, content (snippet).
    Raises on HTTP errors; returns [] if no results.
    """
    resp = httpx.get(
        f"{searxng_url}/search",
        params={"q": query, "format": "json"},
        timeout=15,
        headers={"User-Agent": "qwen-agent/1.0 (local)"},
    )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for r in data.get("results", [])[:max_results]:
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", r.get("snippet", "")),
        })
    return results


def web_search_formatted(query: str, max_results: int = DEFAULT_MAX_RESULTS,
                         searxng_url: str = SEARXNG_URL) -> str:
    """Return search results as a plain-text string (for LLM context)."""
    try:
        results = web_search(query, max_results=max_results, searxng_url=searxng_url)
    except Exception as e:
        return f"Search error: {e}"

    if not results:
        return f"No results found for: {query}"

    lines = [f"Web search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}")
        lines.append(f"    URL: {r['url']}")
        if r["content"]:
            lines.append(f"    {r['content'][:300]}")
        lines.append("")
    return "\n".join(lines)


# ── ReAct agent tool spec ─────────────────────────────────────────────────────

def _handler(params: dict) -> str:
    query = params.get("query", "")
    max_results = int(params.get("max_results", DEFAULT_MAX_RESULTS))
    return web_search_formatted(query, max_results=max_results)


web_search_tool_spec = {
    "name": "web_search",
    "description": (
        "Search the web via local SearxNG (private meta-search engine). "
        "Returns titles, URLs, and snippets. Use for current information, "
        "facts, documentation, or anything not in the local codebase."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (default 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    "handler": _handler,
}


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "Python asyncio tutorial"
    print(web_search_formatted(q))
