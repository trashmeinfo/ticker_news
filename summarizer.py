"""
Summarizes gathered articles into a tight, high-signal 4-5 line brief
using Google's Gemini API (free tier available at ai.google.dev).
"""

import os

import google.generativeai as genai

MODEL_NAME = "gemini-2.0-flash"

PROMPT_TEMPLATE = """You are a sharp equity research analyst briefing a busy portfolio manager.

Below are recent news articles about {company_name} ({ticker}, NSE). Some are full
articles, some are only short snippets (marked accordingly) — weight full articles
more heavily and use snippets only to corroborate.

Write a summary that is EXACTLY 4 to 5 lines, following these rules strictly:
- Lead with the single most material development (earnings, deal, regulatory action,
  management change, price-sensitive news) — not generic company description.
- Every line must carry a distinct, concrete fact (numbers, dates, names) — no filler,
  no throat-clearing, no "the company continues to focus on...".
- If the articles disagree or one is stale/rumor-only, note that briefly rather than
  ignoring it.
- If the material is genuinely thin (all snippet-only, low information), say so plainly
  in 1-2 lines rather than padding — do not invent specifics that aren't in the source
  text.
- No preamble, no headers, no bullet points — just the 4-5 lines of prose.

ARTICLES:
{articles_block}
"""


def _format_articles_block(articles: list[dict]) -> str:
    blocks = []
    for i, art in enumerate(articles, start=1):
        tag = "[FULL ARTICLE]" if art["source_quality"] == "full_article" else "[SNIPPET ONLY]"
        blocks.append(
            f"{i}. {tag} {art['title']} ({art['published']})\n{art['text'][:3000]}"
        )
    return "\n\n".join(blocks)


def summarize(company_name: str, ticker: str, articles: list[dict]) -> str:
    if not articles:
        return "No recent news was found for this ticker across the tracked sources."

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return (
            "Summarization is not configured: set the GEMINI_API_KEY environment "
            "variable (get a free key at https://ai.google.dev) to enable this step."
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    prompt = PROMPT_TEMPLATE.format(
        company_name=company_name,
        ticker=ticker,
        articles_block=_format_articles_block(articles),
    )

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        return f"Summarization failed: {exc}"
