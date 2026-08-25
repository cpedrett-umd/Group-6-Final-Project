"""Review-insight layer -- "What real customers say".

Three parts, in the order a reader needs them:

  1. Plain-language definitions of technical terms in the ad. An ad that leans
     on enzyme names is doing authority manipulation: the words are the tactic.
     Explaining them plainly is the direct counter, and it is a definition task
     rather than a claim about the product, so nothing is at stake if the ad
     itself is nonsense.
  2. A summary of what people report, built ONLY from retrieved passages.
  3. The sources themselves, ranked by how independent of the advertiser they
     are.

The hard rule: every sentence shown to the user traces to a URL that was
actually fetched. A model asked "what do people say about X" will produce
fluent, plausible complaints about a real product that nobody ever made. That is
worse than showing nothing, because the audience is people deciding whether to
spend money.

Retrieval is Tavily; needs TAVILY_API_KEY. Summary and glossary are OpenAI;
needs OPENAI_API_KEY. Any failure falls back to the sample data with
``"mock": True`` intact, so the visible "sample data" badge behaves exactly as
it did before this layer existed.
"""
from __future__ import annotations

import os
import re

NOT_BUILT_NOTICE = "Sample data — the review-insight layer is not built yet."

LIVE_NOTICE = "Retrieved from public web sources. Informational only."

NOTHING_FOUND_NOTICE = (
    "We could not find independent discussion of this product."
)

NO_ENTITY_NOTICE = (
    "This ad names no company or product we could look up."
)

# Illustrative only: written to demonstrate the panel's layout, not scraped from
# any real listing. Returned whenever retrieval is unavailable or finds nothing.
SAMPLE_REVIEWS = [
    {
        "source": "Trustpilot",
        "rating": "2.1★",
        "quote": "Auto-billed monthly. Six calls to cancel.",
    },
    {
        "source": "Reddit · r/scams",
        "rating": None,
        "quote": "14 threads report this seller since March.",
    },
]

# --------------------------------------------------------------------------
# Source independence
#
# Testing surfaced two contaminants a naive pipeline would present as evidence:
# a page hosted on the advertiser's own subdomain, and a blog carrying an
# affiliate discount code. Neither is independent. The first is excluded
# outright; the second is kept but flagged, because it is sometimes the most
# candid source available.
# --------------------------------------------------------------------------

TIER_1 = {  # regulators and consumer protection
    "bbb.org", "ftc.gov", "consumer.ftc.gov", "gov.uk", "which.co.uk",
    "trustpilot.com", "ripoffreport.com", "consumeraffairs.com",
    "citizensadvice.org.uk",
}

TIER_2 = {  # verified-purchase retail
    "amazon.com", "walmart.com", "target.com", "costco.com", "ebay.com",
    "bestbuy.com",
}

TIER_3 = {  # user forums
    "reddit.com", "quora.com", "stackexchange.com", "trustradius.com",
}

AFFILIATE_CUES = [
    r"\bsave \d+%", r"\bdiscount code\b", r"\buse code\b", r"\baffiliate\b",
    r"[?&](?:ref|aff|utm_source|tag)=", r"\bcommission\b", r"\bmy link\b",
    r"\bsponsored\b", r"\bpartner link\b",
]

TIER_LABELS = {
    1: "Consumer protection",
    2: "Verified purchases",
    3: "Public forum",
    4: "Web",
}


def _domain(url: str) -> str:
    match = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return match.group(1).lower() if match else ""


def _root(domain: str) -> str:
    return ".".join(domain.split(".")[-2:]) if domain else ""


def _is_advertiser(domain: str, brand: str | None) -> bool:
    """Whether this domain belongs to the advertiser itself."""
    if not brand or not domain:
        return False
    slug = re.sub(r"[^a-z0-9]", "", brand.lower())
    return bool(slug) and slug in domain.replace("-", "").replace(".", "")


def score_source(url: str, title: str, snippet: str, brand: str | None) -> dict:
    domain = _domain(url)
    flags = []

    if _is_advertiser(domain, brand):
        return {
            "url": url, "title": title, "snippet": snippet, "domain": domain,
            "tier": 9, "independent": False,
            "flags": ["the advertiser's own site"],
        }

    blob = f"{title} {snippet} {url}"
    independent = True

    if any(re.search(cue, blob, re.I) for cue in AFFILIATE_CUES):
        flags.append("earns commission on sales")
        independent = False

    root = _root(domain)
    tier = 1 if root in TIER_1 else 2 if root in TIER_2 else 3 if root in TIER_3 else 4

    return {
        "url": url, "title": title, "snippet": snippet, "domain": domain,
        "tier": tier, "independent": independent, "flags": flags,
    }


# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------

def _tavily_available() -> bool:
    if not os.environ.get("TAVILY_API_KEY"):
        return False
    try:
        import tavily  # noqa: F401
    except ImportError:
        return False
    return True


def _search(query: str, max_results: int = 6) -> list[dict]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="basic",
    )
    return response.get("results", []) or []


def _queries(brand: str, tactic: str | None, claim_query: str | None) -> list[str]:
    """What to search, ordered by expected value.

    The tactic the classifier found selects the kind of scrutiny. An
    exaggerated claim is checked against evidence; pressure tactics correlate
    with billing and cancellation problems, so those are checked against
    conduct. Complaint-shaped queries consistently returned better sources than
    review-shaped ones in testing -- a review query surfaces affiliate listicles,
    a complaint query surfaces regulator records.
    """
    queries = []

    if claim_query:
        queries.append(claim_query)

    if tactic in {"Exaggerated Claims", "Authority Manipulation"}:
        queries.append(f"{brand} evidence does it work review")
    elif tactic in {"Urgency", "Scarcity", "FOMO"}:
        queries.append(f"{brand} cancel subscription refund problem")

    queries.append(f"{brand} complaints reddit")

    seen, ordered = set(), []
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            ordered.append(q)

    return ordered[:3]


# --------------------------------------------------------------------------
# Glossary and summary -- both grounded in text we already have
# --------------------------------------------------------------------------

GLOSSARY_PROMPT = """The text below is from an advertisement. Find the terms it
uses to sound more authoritative than the claim behind them warrants.

Include a term when it is:
- technical vocabulary from any field -- biology, medicine, finance,
  engineering, law -- used to make a claim sound established
- a word that sounds regulated, tested or verified when no such standard exists
  behind it
- a figure, ratio or comparison stated without its basis

Exclude anything a general reader already understands from daily life.

For each term, output one line:
TERM: <term> -- <what it actually means, and what an ad using it does not tell you>

Rules:
- Two short sentences at most. Plain words a 70-year-old would use.
- Explain the term itself, in general. Do not say whether this ad's claim is
  true or false -- that is what the retrieved sources are for.
- Where a term's real meaning is narrower than it sounds, say so plainly.
- At most four terms, the ones carrying the most weight in the ad.
- If the ad uses no such terms, output NONE.

Advertisement text:
"""

SUMMARY_PROMPT = """Below are passages retrieved from public web pages about a
product, each with its source.

Write two or three short sentences describing what these passages report about
people's experience with the product.

Rules:
- Use ONLY what is stated in the passages. Add nothing from your own knowledge.
- If the passages disagree, say so.
- If they contain no substantive user experience, write NOTHING.
- Name the source when you report something specific ("Better Business Bureau
  records describe...").
- Plain language for a general reader. No marketing words.
- Do not tell the reader what to do.

Passages:
"""


def _openai_text(prompt: str, max_tokens: int = 400) -> str | None:
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI

        response = OpenAI(timeout=20).chat.completions.create(
            model=os.environ.get("ADINSIGHT_VLM_MODEL", "gpt-4o-mini"),
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return None


def _glossary(text: str) -> list[dict]:
    """Plain-language definitions for technical terms in the ad."""
    if not text or len(text.split()) < 5:
        return []

    raw = _openai_text(GLOSSARY_PROMPT + text[:3000], max_tokens=400)

    if not raw or raw.strip().upper().startswith("NONE"):
        return []

    terms = []
    for line in raw.splitlines():
        if not line.upper().startswith("TERM:"):
            continue
        body = line.split(":", 1)[1].strip()
        if "--" in body:
            term, _, meaning = body.partition("--")
        elif "—" in body:
            term, _, meaning = body.partition("—")
        else:
            continue
        term, meaning = term.strip(), meaning.strip()
        if term and meaning:
            terms.append({"term": term, "meaning": meaning})

    return terms[:5]


def _summarise(sources: list[dict]) -> str | None:
    """Summarise retrieved passages, using nothing outside them."""
    usable = [s for s in sources if s["independent"] and s.get("snippet")]

    if len(usable) < 2:
        return None

    passages = "\n\n".join(
        f"[{s['domain']}] {s['snippet'][:400]}" for s in usable[:6]
    )

    summary = _openai_text(SUMMARY_PROMPT + passages, max_tokens=300)

    if not summary or summary.strip().upper().startswith("NOTHING"):
        return None

    return summary


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def _mock(notice: str = NOT_BUILT_NOTICE) -> dict:
    return {"mock": True, "notice": notice, "items": SAMPLE_REVIEWS,
            "glossary": [], "summary": None}


def fetch(text: str, brand: str | None = None, tactic: str | None = None,
          claim_query: str | None = None) -> dict:
    """Review evidence for an ad.

    `text` is the ad's extracted text. `brand`, `tactic` and `claim_query` come
    from the VLM claim extractor and the classifier when available; without a
    brand there is nothing to search for, which is itself reportable.

    Never raises: server.py calls this inside the analyse route, so an exception
    here would turn a working analysis into a 500.
    """
    try:
        glossary = _glossary(text)

        if not brand:
            return {
                "mock": False,
                "notice": NO_ENTITY_NOTICE,
                "items": [],
                "glossary": glossary,
                "summary": None,
                "no_entity": True,
            }

        if not _tavily_available():
            result = _mock()
            result["glossary"] = glossary
            return result

        queries = _queries(brand, tactic, claim_query)
        print(f"[reviews] brand={brand!r} tactic={tactic!r}")
        print(f"[reviews] claim_query={claim_query!r}")
        print(f"[reviews] queries={queries}")

        scored = []
        seen = set()


        for query in _queries(brand, tactic, claim_query):
            try:
                hits = _search(query)
            except Exception:
                continue

            for hit in hits:
                url = hit.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                scored.append(
                    score_source(url, hit.get("title", ""),
                                 hit.get("content", ""), brand)
                )

        # Advertiser-owned pages are dropped entirely; affiliate content is kept
        # but sorted below independent sources and flagged in the UI.
        usable = [s for s in scored if s["tier"] != 9]
        usable.sort(key=lambda s: (s["tier"], not s["independent"]))

        if not usable:
            result = _mock(NOTHING_FOUND_NOTICE)
            result["glossary"] = glossary
            return result

        top = usable[:4]

        items = [
            {
                "source": f"{TIER_LABELS.get(s['tier'], 'Web')} · {s['domain']}",
                "rating": None,
                "quote": (s["snippet"] or s["title"])[:220],
                "url": s["url"],
                "flags": s["flags"],
            }
            for s in top
        ]

        return {
            "mock": False,
            "notice": LIVE_NOTICE,
            "items": items,
            "glossary": glossary,
            "summary": _summarise(top),
            "no_entity": False,
        }

    except Exception:
        # Anything unexpected degrades to the sample data rather than breaking
        # the analysis the user actually asked for.
        return _mock()