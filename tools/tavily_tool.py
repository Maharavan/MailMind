"""tools/tavily_tool.py — Tavily web search integration."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Run a Tavily search and return a list of result dicts with keys:
    title, url, content (snippet).

    Returns empty list if Tavily key is missing or the call fails.
    """
    try:
        from tavily import TavilyClient
        from config.settings import settings

        api_key = getattr(settings, "TAVILY_API_KEY", None)
        if not api_key:
            logger.warning("TAVILY_API_KEY not set — skipping web search")
            return []

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=False,
        )
        results = response.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            }
            for r in results
        ]
    except ImportError:
        logger.warning("tavily-python not installed — run: pip install tavily-python")
        return []
    except Exception as e:
        logger.warning("Tavily search failed for query '%s': %s", query, e)
        return []


def format_results_for_llm(results: list[dict]) -> str:
    """Format Tavily results into a compact block for LLM consumption."""
    if not results:
        return "No web results available."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}\nURL: {r['url']}\n{r['content'][:400]}")
    return "\n\n".join(lines)
