"""
Discovers recent news for an NSE-listed company and pulls full article text.

Discovery uses Google News RSS (a public, intentionally-syndicated feed —
no scraping, no auth) restricted with site: filters to the publishers you
care about (LiveMint, Moneycontrol, Economic Times, DSIJ). This sidesteps
each site's own search/anti-bot layer while still surfacing their articles.

Full-text extraction does ONE polite HTTP GET per article link (not bulk
crawling) and uses trafilatura to pull clean article text. If a fetch is
blocked, throttled, or fails, we fall back to the RSS snippet so the
pipeline still produces a summary — just from thinner material.
"""

import time
from urllib.parse import quote_plus

import feedparser
import requests
import trafilatura

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Publishers you asked for, mapped to Google News 'site:' filters.
SOURCE_SITES = [
    "livemint.com",
    "moneycontrol.com",
    "economictimes.indiatimes.com",
    "dsij.in",
]

REQUEST_TIMEOUT_SECONDS = 8
MAX_ARTICLES = 6


def build_google_news_rss_url(company_name: str, ticker: str) -> str:
    site_filter = " OR ".join(f"site:{s}" for s in SOURCE_SITES)
    query = f'"{company_name}" OR "{ticker}" ({site_filter})'
    encoded = quote_plus(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"


def discover_articles(company_name: str, ticker: str) -> list[dict]:
    """Returns a de-duplicated list of {title, link, published, snippet}."""
    url = build_google_news_rss_url(company_name, ticker)
    feed = feedparser.parse(url)

    seen_titles = set()
    articles = []
    for entry in feed.entries:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if not title or not link or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        articles.append(
            {
                "title": title,
                "link": link,
                "published": getattr(entry, "published", ""),
                "snippet": getattr(entry, "summary", ""),
            }
        )
        if len(articles) >= MAX_ARTICLES:
            break

    return articles


def fetch_full_text(url: str) -> str | None:
    """One respectful GET + extraction. Returns None on any failure."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        if resp.status_code != 200 or not resp.text:
            return None
        text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
        return text.strip() if text else None
    except Exception:
        return None


def gather_content_for_ticker(company_name: str, ticker: str) -> list[dict]:
    """
    Full pipeline step: discover articles, then try to enrich each with
    full article text. Falls back to the RSS snippet per-article on failure.
    Returns list of {title, link, published, text, source_quality}.
    """
    articles = discover_articles(company_name, ticker)
    enriched = []

    for article in articles:
        full_text = fetch_full_text(article["link"])
        enriched.append(
            {
                "title": article["title"],
                "link": article["link"],
                "published": article["published"],
                "text": full_text or article["snippet"],
                "source_quality": "full_article" if full_text else "snippet_only",
            }
        )
        time.sleep(0.5)  # small courtesy delay between requests

    return enriched
