from flask import Flask, render_template, request

from scraper import gather_content_for_ticker
from summarizer import summarize
from ticker_utils import get_company_name, normalize_nse_ticker

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", result=None, error=None, ticker="")


@app.route("/summarize", methods=["POST"])
def summarize_ticker():
    raw_ticker = request.form.get("ticker", "")
    ticker = normalize_nse_ticker(raw_ticker)

    if not ticker:
        return render_template("index.html", result=None, error="Please enter an NSE ticker.", ticker="")

    company_name = get_company_name(ticker)
    if not company_name:
        # Name lookup failed (timeout, rate-limit, or genuinely unknown
        # ticker) -- don't hard-block the user, just search using the raw
        # symbol instead. Slightly less precise, but keeps the app working.
        company_name = ticker

    articles = gather_content_for_ticker(company_name, ticker)
    summary_text = summarize(company_name, ticker, articles)

    result = {
        "ticker": ticker,
        "company_name": company_name,
        "summary": summary_text,
        "sources": articles,
    }
    return render_template("index.html", result=result, error=None, ticker=raw_ticker)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
