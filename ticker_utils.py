"""
Resolve an NSE ticker (e.g. 'TCS', 'RELIANCE') to its full company name.
Uses yfinance (free, no API key) against the '.NS' (NSE) suffix on Yahoo Finance.
"""

import yfinance as yf


def normalize_nse_ticker(raw_ticker: str) -> str:
    """Clean up user input into a bare NSE symbol, e.g. ' tcs ' -> 'TCS'."""
    ticker = raw_ticker.strip().upper()
    ticker = ticker.replace(".NS", "").replace(".NSE", "")
    return ticker


def get_company_name(ticker: str) -> str | None:
    """
    Returns the company's long/short name for a given NSE ticker, or None
    if the ticker can't be resolved (likely invalid/delisted symbol).
    """
    symbol = normalize_nse_ticker(ticker)
    yf_symbol = f"{symbol}.NS"

    try:
        info = yf.Ticker(yf_symbol).info
    except Exception:
        return None

    if not info or info.get("regularMarketPrice") is None and not info.get("longName"):
        # yfinance sometimes returns a near-empty dict for invalid tickers
        name = info.get("longName") or info.get("shortName") if info else None
        return name

    return info.get("longName") or info.get("shortName")
