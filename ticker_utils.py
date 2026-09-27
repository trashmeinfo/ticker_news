"""
Resolve an NSE ticker (e.g. 'TCS', 'RELIANCE') to its full company name.

Uses Yahoo Finance's lightweight autocomplete/search endpoint directly via
requests (fast, free, no API key). We deliberately avoid yfinance's heavy
Ticker(...).info call here -- that endpoint is aggressively rate-limited by
Yahoo and can hang indefinitely instead of failing cleanly.
"""

import requests

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
REQUEST_TIMEOUT_SECONDS = 6
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def normalize_nse_ticker(raw_ticker: str) -> str:
    """Clean up user input into a bare NSE symbol, e.g. ' tcs ' -> 'TCS'."""
    ticker = raw_ticker.strip().upper()
    ticker = ticker.replace(".NS", "").replace(".NSE", "")
    return ticker


def get_company_name(ticker: str) -> str | None:
    """
    Returns the company's name for a given NSE ticker using Yahoo's search
    endpoint, or None if it can't be resolved within the timeout.

    A timeout or any request failure returns None rather than hanging --
    callers should treat None as "couldn't confirm the name" and may choose
    to fall back to using the raw ticker symbol instead of hard-failing.
    """
    symbol = normalize_nse_ticker(ticker)

    try:
        resp = requests.get(
            SEARCH_URL,
            params={"q": symbol, "quotesCount": 5, "newsCount": 0},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    quotes = data.get("quotes", [])
    for quote in quotes:
        # Prefer an exact NSE match (symbol looks like 'RELIANCE.NS')
        if quote.get("symbol", "").upper() == f"{symbol}.NS":
            return quote.get("longname") or quote.get("shortname")

    # Fall back to the first result if no exact .NS match was found
    if quotes:
        return quotes[0].get("longname") or quotes[0].get("shortname")

    return None
