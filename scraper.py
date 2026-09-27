"""
Discovers recent news for an NSE-listed company and pulls full article text.

Discovery uses Google News RSS (a public, intentionally-syndicated feed --
no scraping, no auth) restricted with site: filters to the publishers you
care about. This sidesteps each site's own search/anti-bot layer while
still surfacing their articles.

IMPORTANT: Google News RSS links don't point straight at the article --
they point at a news.google.com redirect page that resolves to the real
URL via client-side JavaScript. A plain HTTP request never executes that
JS, so it lands on Google's shell page instead of the actual article --
which is why full-text extraction can silently fail for every source at
once, regardless of which publisher it is. We decode the real URL first
using the `googlenewsdecoder` library (replicates Google's internal
resolution call) before attempting to fetch the article.

Full-text extraction then does ONE polite HTTP GET per resolved article
link (not bulk crawling) and uses trafilatura to pull clean article text.
If a fetch is still blocked, throttled, or fails, we fall back to the RSS
snippet so the pipeline still produces a summary -- just from thinner
material.
"""

import time
from urllib.parse import quote_plus

import feedparser
import requests
import trafilatura
from googlenewsdecoder import gnewsdecoder

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
    "reuters.com",
    "business-standard.com",
    "ndtvprofit.com",
    "cnbctv18.com",
    "financialexpress.com",
    "zeebiz.com",
]

REQUEST_TIMEOUT_SECONDS = 8
MAX_ARTICLES = 8


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


def resolve_real_urls(google_links: list[str]) -> list[str | None]:
    """
    Decodes Google News redirect links into the actual publisher URLs.
    Returns a list the same length as google_links; an entry is None if
    that particular link couldn't be decoded (caller should fall back to
    the RSS snippet for that article).
    """
    if not google_links:
        return []

    try:
        results = gnewsdecoder(google_links, interval=1)
    except Exception:
        return [None] * len(google_links)

    # gnewsdecoder returns a single dict if given a single string, and a
    # list of dicts if given a list -- we always pass a list, but guard
    # anyway in case the library's behavior changes.
    if isinstance(results, dict):
        results = [results]

    resolved = []
    for result in results:
        if isinstance(result, dict) and result.get("success"):
            resolved.append(result.get("decoded_url"))
        else:
            resolved.append(None)
    return resolved


def fetch_full_text(url: str) -> str | None:
    """One respectful GET + extraction against the REAL article URL. Returns None on any failure."""
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
    Full pipeline step: discover articles, decode their real URLs, then try
    to enrich each with full article text. Falls back to the RSS snippet
    per-article on failure. Returns list of
    {title, link, published, text, source_quality}.
    """
    articles = discover_articles(company_name, ticker)
    if not articles:
        return []

    real_urls = resolve_real_urls([a["link"] for a in articles])

    enriched = []
    for article, real_url in zip(articles, real_urls):
        full_text = fetch_full_text(real_url) if real_url else None
        enriched.append(
            {
                "title": article["title"],
                # Show the real publisher link when we have it -- nicer
                # for the person reading, not a Google tracking wrapper.
                "link": real_url or article["link"],
                "published": article["published"],
                "text": full_text or article["snippet"],
                "source_quality": "full_article" if full_text else "snippet_only",
            }
        )
        time.sleep(0.5)  # small courtesy delay between requests

    return enriched
