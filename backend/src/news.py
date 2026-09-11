import logging
import os
import re
import ssl
from datetime import datetime, timezone

import httpx
import truststore
from llm import LLMError, generate_news_synthesis

logger = logging.getLogger(__name__)

WORLD_NEWS_API_KEY = os.getenv("WORLD_NEWS_API_KEY")
TOP_NEWS_URL = "https://api.worldnewsapi.com/top-news"
SEARCH_NEWS_URL = "https://api.worldnewsapi.com/search-news"

# Common French function words / filler verbs from natural-language prompts
# (e.g. the example chat prompts), stripped out when building a search query.
_STOPWORDS = {
    "le", "la", "les", "l", "de", "des", "du", "un", "une", "et", "ou", "a", "au", "aux",
    "sur", "dans", "pour", "que", "qui", "quoi", "ce", "cette", "ces", "son", "sa", "ses",
    "mon", "ma", "mes", "ton", "ta", "tes", "notre", "nos", "votre", "vos", "leur", "leurs",
    "moi", "toi", "nous", "vous", "il", "elle", "ils", "elles", "je", "tu", "on",
    "resume", "resumez", "genere", "generez", "donne", "donnez", "dis", "parle", "parlez",
    "quelles", "quels", "quelle", "quel", "sont", "est", "sujet", "specifique",
    "semaine", "jour", "aujourd", "hui", "actualite", "actualites",
    "nouvelles", "informations", "info", "infos",
}


def _strip_accents(text: str) -> str:
    replacements = str.maketrans("àâäéèêëïîôöùûüçÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ", "aaaeeeeiioouuucAAAEEEEIIOOUUUC")
    return text.translate(replacements)


def _build_search_query(theme: str) -> str:
    """World News API's `text` param expects ALL words to match by default,
    so a natural-language phrase (e.g. an example chat prompt typed in as a
    theme) almost never matches any article. Keep only the significant
    (non-filler) words, in their original accented form, and OR them
    together so matching any one of them is enough."""
    original_words = re.findall(r"[^\W\d_]+", theme, flags=re.UNICODE)
    significant = [
        word
        for word in original_words
        if len(_strip_accents(word.lower())) >= 3
        and _strip_accents(word.lower()) not in _STOPWORDS
    ]

    if not significant:
        return theme.strip()
    if len(significant) == 1:
        return significant[0]
    return " OR ".join(dict.fromkeys(significant[:6]))


class NewsError(Exception):
    """Raised when news cannot be fetched from World News API or synthesized."""


def _get(url: str, params: dict) -> dict:
    if not WORLD_NEWS_API_KEY:
        logger.error("WORLD_NEWS_API_KEY is not configured")
        raise NewsError("WORLD_NEWS_API_KEY is not configured")

    try:
        response = httpx.get(
            url,
            params=params,
            headers={"x-api-key": WORLD_NEWS_API_KEY},
            timeout=20,
            # The system's default cert store isn't reachable through this
            # network's TLS setup; fall back to the OS trust store.
            verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        logger.exception(
            "World News API request failed: %s %s -> %s %s",
            url,
            params,
            error.response.status_code,
            error.response.text[:500],
        )
        raise NewsError("World News API request failed") from error
    except httpx.HTTPError as error:
        logger.exception("World News API request failed: %s %s", url, params)
        raise NewsError("World News API request failed") from error

    return response.json()


def fetch_top_news(source_country: str = "fr", language: str = "fr") -> list[dict]:
    """Fetch today's top news and return one {"title", "summary"} entry per
    story cluster (the lead article), skipping the redundant same-story
    coverage from other outlets that the API groups alongside it."""
    data = _get(TOP_NEWS_URL, {"source-country": source_country, "language": language})

    articles = []
    for cluster in data.get("top_news", []):
        news = cluster.get("news") or []
        if not news:
            continue
        lead = news[0]
        title = (lead.get("title") or "").strip()
        if not title:
            continue
        articles.append({"title": title, "summary": (lead.get("summary") or "").strip()})

    return articles


def search_news(theme: str, date: str | None = None, language: str = "fr", number: int = 20) -> list[dict]:
    """Search World News API for articles matching a theme/topic, published
    on the given date (YYYY-MM-DD, defaults to today)."""
    target_date = date or datetime.now(timezone.utc).date().isoformat()
    query = _build_search_query(theme)

    data = _get(
        SEARCH_NEWS_URL,
        {
            "text": query,
            "language": language,
            "number": number,
            "sort": "publish-time",
            "sort-direction": "DESC",
            "earliest-publish-date": f"{target_date} 00:00:00",
            "latest-publish-date": f"{target_date} 23:59:59",
        },
    )

    articles = []
    for article in data.get("news", []):
        title = (article.get("title") or "").strip()
        url = article.get("url")
        if not title or not url:
            continue
        articles.append(
            {
                "title": title,
                "summary": (article.get("summary") or "").strip(),
                "text": (article.get("text") or "").strip(),
                "image": article.get("image"),
                "url": url,
                "publish_date": article.get("publish_date"),
            }
        )

    return articles


async def build_news_digest(synthesis_prompt: str) -> str:
    """Fetch today's top news and condense it into a short digest via the LLM."""
    articles = fetch_top_news()

    try:
        return await generate_news_synthesis(articles, synthesis_prompt)
    except LLMError as error:
        logger.exception("News digest synthesis failed")
        raise NewsError("News synthesis failed") from error


def search_news_tool(query: str) -> list[dict]:
    """Search recent news articles about a topic to get more detail or
    up-to-date information than what is already known. Use this when the
    user asks to know more about a subject, wants recent articles on a
    theme, or asks a question about current events not already covered.

    Args:
        query: The topic or keywords to search news for, e.g. "elections
            presidentielles" or "intelligence artificielle".

    Returns:
        A list of up to 5 recent articles, each with just a "title" and a
        short "summary" (kept minimal so the agent isn't flooded with the
        full raw World News API response).
    """
    articles = search_news(query, number=5)
    return [
        {"title": article["title"], "summary": article["summary"] or article["text"][:300]}
        for article in articles
    ]
