import httpx
import json
import os
import time
from crawler.pipeline.types import OperatorInfo, SearchResult
from rapidfuzz import fuzz
from unidecode import unidecode
import tldextract
import re
from urllib.parse import quote_plus, urlparse
from publicsuffix2 import get_sld

_AGGREGATOR_DOMAINS = {
    "wikipedia",
    "wikivoyage",
    "tripadvisor",
    "viator",
    "getyourguide",
    "klook",
    "booking",
    "airbnb",
    "expedia",
    "lonelyplanet",
    "yelp",
    "facebook",
    "instagram",
    "twitter",
    "x",
    "linkedin",
    "tiktok",
    "youtube",
    "youtu",
    "pinterest",
    "reddit",
    "trustpilot",
    "foursquare",
    "opentable",
    "google",
    "goo",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", unidecode(s).lower())


def _score(operator: str, title: str, link: str, search_rank: int = 0) -> float:
    ext = tldextract.extract(link)
    domain = ext.domain

    operator_n = _norm(operator)
    title_n = _norm(title)
    domain_n = _norm(domain)

    s_title = fuzz.token_set_ratio(operator_n, title_n)
    s_domain = fuzz.partial_ratio(operator_n, domain_n)

    return 0.55 * s_domain + 0.35 * s_title + (10 - search_rank)


def _validate_url(link: str) -> bool:
    p = urlparse(link)
    host = p.netloc.lower().split(":")[0]
    sld = get_sld(host)
    sld_name = sld.split(".", 1)[0]

    if sld_name in _AGGREGATOR_DOMAINS:
        return False

    return True


def search(operator: OperatorInfo, trace) -> SearchResult:
    headers = {
        "Authorization": f"Bearer {os.environ['BRIGHTDATA_SERP_API_KEY']}",
        "Content-Type": "application/json",
    }
    data = {
        "zone": "arival_crawler",
        "url": f"https://www.google.com/search?q={quote_plus(operator.name)}",
        "format": "raw",
    }

    # three attempts
    attempt_results = []
    for attempt in range(3):
        attempt_start = time.perf_counter()
        try:
            response = httpx.post(
                "https://api.brightdata.com/request",
                json=data,
                headers=headers,
                timeout=30,
            )
            attempt_results.append(
                {
                    "attempt": attempt + 1,
                    "result": "response",
                    "latency": round(time.perf_counter() - attempt_start, 3),
                }
            )
            break
        except httpx.RequestError as e:
            attempt_results.append(
                {"attempt": attempt + 1, "result": type(e).__name__, "message": str(e), "latency": round(time.perf_counter() - attempt_start, 3)}
            )
            response = None

    if response is None:
        trace.add("search", ok=False, message="SERP Request Error", attempts=attempt_results)
        return SearchResult(ok=False, message="SERP Request Error")

    try:
        results = json.loads(response.text)
    except json.JSONDecodeError:
        trace.add("search", ok=False, message="SERP provided invalid JSON", attempts=attempt_results)
        return SearchResult(ok=False, message="SERP provided invalid JSON")

    best: str = ""
    best_score: float = -99999

    try:
        candidates = results["organic"]

        for i, c in enumerate(candidates):
            link = c.get("link", "")
            title = c.get("title", "")
            if not link or not title:
                continue

            score = _score(
                operator=operator.name, title=title, link=link, search_rank=i
            )
            if score > best_score:
                best_score = score
                best = link

    except Exception:
        trace.add("search", ok=False, message="SERP provided invalid JSON schema", attempts=attempt_results)
        return SearchResult(ok=False, message="SERP provided invalid JSON schema")

    if not _validate_url(best):
        trace.add("search", ok=False, message="Found social/aggregator URL", attempts=attempt_results)
        return SearchResult(ok=False, url=best, message="Found social/aggregator URL")

    trace.add("search", ok=True, attempts=attempt_results)
    return SearchResult(ok=True, url=best)
