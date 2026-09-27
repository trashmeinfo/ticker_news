# NSE Stock News Summarizer

Type an NSE ticker (TCS, RELIANCE, INFY, etc.) and get a 4-5 line crux
summary of recent news about that company, drawn from LiveMint,
Moneycontrol, Economic Times, and DSIJ.

## How it actually works (read this before deploying)

1. **Ticker → company name**: uses `yfinance` (free, no key) to resolve
   the NSE symbol to a company name.
2. **Discovery**: queries Google News RSS — a public syndication feed,
   not a scrape — restricted with `site:` filters to livemint.com,
   moneycontrol.com, economictimes.indiatimes.com, and dsij.in.
3. **Full-text extraction**: does one polite HTTP request per article
   link and pulls clean text with `trafilatura`. If a site blocks or
   throttles the request, that article silently falls back to just its
   RSS snippet — the pipeline never hard-fails on this.
4. **Summarization**: sends the gathered material to Google's Gemini
   API (free tier) with a prompt tuned for a tight, fact-dense 4-5
   line brief — not a generic rephrase.

### Known limitations, honestly
- Twitter/X is **not** included — there's no reliable free way to pull
  tweets by ticker anymore (X's free API access was discontinued).
- Any of the four news sites can start blocking/throttling automated
  requests at any time without notice. When that happens for a given
  article, you'll see a lower-quality "snippet only" summary rather
  than a crash.
- `yfinance` occasionally rate-limits; if ticker lookups start failing
  in bulk, wait a few minutes.
- This scrapes only what's needed per user request (not bulk/scheduled
  crawling) — keep it that way if you extend it, to stay a good citizen
  of these sites' infrastructure.

## Local setup

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # then paste in your Gemini key
export $(cat .env | xargs)     # Windows: set env vars manually
python app.py
```

Visit http://localhost:5000

## Getting a free Gemini API key

1. Go to https://ai.google.dev
2. Sign in with a Google account → "Get API key" → create a key
3. Free tier is generous enough for personal/light use; put the key in
   `.env` as `GEMINI_API_KEY`

## Deploying for free so anyone can use it

**Render.com (recommended, easiest free tier):**
1. Push this folder to a GitHub repo
2. On Render: New → Web Service → connect the repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variable `GEMINI_API_KEY` in the dashboard
6. Deploy — Render gives you a public URL

**Railway.app** works the same way and also has a free tier.

Note: free tiers on both platforms "sleep" the app after inactivity —
the first request after idling takes a few extra seconds to wake up.
That's normal, not a bug.

## Extending later
- Swap/add more `site:` filters in `scraper.py` → `SOURCE_SITES`
- Swap Gemini for Groq (also free tier) in `summarizer.py` if you hit
  Gemini quota limits
- Add simple caching (e.g. Redis or even an in-memory dict with a TTL)
  if the same tickers get queried repeatedly, to reduce load on the
  news sites and speed up repeat lookups
