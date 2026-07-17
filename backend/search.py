import time
from urllib.parse import urlparse
from ddgs import DDGS
from ddgs.exceptions import DDGSException
import trafilatura

# Known wire/syndication and corporate-family clusters so we don't treat
# five reprints of one AP story as five independent sources.
PUBLISHER_CLUSTERS = {
    "apnews.com": "ap-wire",
    "reuters.com": "reuters-wire",
    "yahoo.com": "reuters-wire",  # often re-syndicates reuters/ap
    "nytimes.com": "nyt",
    "wsj.com": "dowjones",
    "marketwatch.com": "dowjones",
    "barrons.com": "dowjones",
}

PRIMARY_DOMAINS = ("sec.gov", "epa.gov", "courtlistener.com", ".gov", "who.int", "europa.eu")
TERTIARY_DOMAINS = ("wikipedia.org", "medium.com", "reddit.com", "quora.com")


def classify_source(url: str) -> tuple[str, str, float]:
    """Return (publisher_cluster, reliability_tier, reliability_score)."""
    domain = urlparse(url).netloc.replace("www.", "")
    cluster = PUBLISHER_CLUSTERS.get(domain, domain)

    if any(domain.endswith(d) for d in PRIMARY_DOMAINS):
        return cluster, "primary", 0.95
    if any(domain.endswith(d) for d in TERTIARY_DOMAINS):
        return cluster, "tertiary", 0.35
    return cluster, "secondary", 0.65


def web_search(query: str, max_results: int = 6, retries: int = 4) -> list[dict]:
    results: list[dict] = []
    delay = 2.0
    for attempt in range(retries):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results, backend="duckduckgo"))
            if results:
                break
        except DDGSException:
            pass
        if attempt < retries - 1:
            time.sleep(delay)
            delay *= 2
    out = []
    for r in results:
        url = r.get("href") or r.get("url") or ""
        if not url:
            continue
        domain = urlparse(url).netloc.replace("www.", "")
        cluster, tier, score = classify_source(url)
        out.append(
            {
                "url": url,
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "domain": domain,
                "publisher_cluster": cluster,
                "reliability_tier": tier,
                "reliability_score": score,
            }
        )
    return out


def fetch_full_text(url: str, max_chars: int = 3000) -> str:
    try:
        downloaded = trafilatura.fetch_url(url, timeout=8)
        if not downloaded:
            return ""
        text = trafilatura.extract(downloaded) or ""
        return text[:max_chars]
    except Exception:
        return ""
