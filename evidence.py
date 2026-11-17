"""Evidence collection and citation verification — deterministic, no LLM.

Collectors (all free, no API keys):
  web        ddgs metasearch (tries several backends)       -> snippets + fetched page sentences
  hn         Hacker News Algolia API                          -> discussion threads (demand/competitor signal)
  wikipedia  MediaWiki API                                    -> reference context
  worldbank  World Bank Indicators API                        -> local constraints (internet use, income)

Every passage is stored in a source ledger with URL, title, domain, fetch time,
SHA-256 of the fetched text, collector type and evidence category. Models only
see source keys (S1..Sn), never URLs. `verify_claims` then checks that each
claim's quote really appears in a passage of a source it cites; claims that
fail are downgraded to ASSUMPTION.

Set HATCHAI_OFFLINE=1 to disable all network access (tests use this).
"""
from __future__ import annotations

import difflib
import hashlib
import html
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urlparse

from models import Claim, Source

log = logging.getLogger(__name__)

CATEGORIES = ("demand", "competitors", "pricing", "local_constraints", "channels")
UA = "HatchAI-research/1.0 (open-source venture builder; +https://github.com/)"
_WEB_BACKENDS = ("yahoo", "duckduckgo", "brave", "mojeek", "startpage")

STOPWORDS = set("""a an the and or for to of in on with by from at as is are be this that it its i we you
want build app tool platform based help helps using use who what how my our your their them they
digital online product service people users user should can will would have has which into about
than then also more most very just only some any all not no yes support focused focus""".split())

# ISO-2 codes for the World Bank API (subset; extend as needed)
COUNTRIES = {
    "egypt": "EG", "saudi": "SA", "saudi arabia": "SA", "uae": "AE", "united arab emirates": "AE",
    "jordan": "JO", "morocco": "MA", "tunisia": "TN", "algeria": "DZ", "lebanon": "LB", "kuwait": "KW",
    "qatar": "QA", "nigeria": "NG", "kenya": "KE", "south africa": "ZA", "ghana": "GH", "india": "IN",
    "pakistan": "PK", "bangladesh": "BD", "indonesia": "ID", "philippines": "PH", "vietnam": "VN",
    "brazil": "BR", "mexico": "MX", "argentina": "AR", "colombia": "CO", "turkey": "TR",
    "united kingdom": "GB", "uk": "GB", "germany": "DE", "france": "FR", "spain": "ES", "italy": "IT",
    "united states": "US", "usa": "US", "canada": "CA", "australia": "AU", "japan": "JP",
}

WB_INDICATORS = {
    "IT.NET.USER.ZS": "Individuals using the Internet (% of population)",
    "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
}


def offline() -> bool:
    return os.environ.get("HATCHAI_OFFLINE", "").lower() in ("1", "true", "yes")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def keywords(text: str, limit: int = 8) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower())
    out: list[str] = []
    for w in words:
        if w not in STOPWORDS and w not in out:
            out.append(w)
    return out[:limit]


def detect_country(geography: str) -> tuple[str, str] | None:
    g = geography.lower()
    for name in sorted(COUNTRIES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", g):
            return name.title() if len(name) > 3 else name.upper(), COUNTRIES[name]
    return None


def domain_of(url: str) -> str:
    net = urlparse(url).netloc.lower()
    return net[4:] if net.startswith("www.") else net


def _is_ad(url: str) -> bool:
    return any(t in url for t in ("aclick?", "bing.com/", "/ads/", "doubleclick", "googleadservices"))


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clean_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if 40 <= len(p.strip()) <= 320]


# Strip instruction-like content from fetched pages (prompt-injection hygiene).
_INJECTION = re.compile(r"(?i)(ignore (all|previous|the above)|system prompt|you are (now )?an? (ai|assistant)|disregard)")


def sanitise(text: str) -> str:
    return "" if _INJECTION.search(text) else text


def rank_sentences(sentences: list[str], terms: list[str], k: int = 3) -> list[str]:
    scored = []
    for s in sentences:
        low = s.lower()
        score = sum(1 for t in terms if t in low) + (0.5 if re.search(r"\d", s) else 0)
        if score >= 2:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:k]]


# ---------------------------------------------------------------------------
# Collectors — each returns a list of raw dicts {url,title,passages,collector}
# ---------------------------------------------------------------------------

def search_web(query: str, max_results: int = 4, errors: list | None = None) -> list[dict]:
    if offline():
        return []
    try:
        from ddgs import DDGS  # type: ignore
    except ImportError:
        log.warning("ddgs not installed; web search skipped")
        if errors is not None:
            errors.append("web: ddgs not installed")
        return []
    failures = []
    for backend in _WEB_BACKENDS:
        try:
            with DDGS() as d:
                results = list(d.text(query, max_results=max_results, backend=backend))
            if results:
                return [
                    {"url": r.get("href", ""), "title": r.get("title", ""),
                     "passages": [sanitise(r.get("body", ""))], "collector": f"web:{backend}"}
                    for r in results if r.get("href")
                ]
        except Exception as exc:
            log.debug("ddgs backend %s failed: %s", backend, exc)
            if "no results" in str(exc).lower():
                continue                            # ddgs raises on an empty result page: not a tool failure
            failures.append(f"web:{backend}: {type(exc).__name__}: {str(exc)[:80]}")
    if errors is not None and failures and len(failures) == len(_WEB_BACKENDS):
        errors.append(failures[-1])                 # every backend raised: a tool failure, not "no results"
    return []


def search_hn(query: str, max_results: int = 3, errors: list | None = None) -> list[dict]:
    if offline():
        return []
    try:
        import httpx
        r = httpx.get("https://hn.algolia.com/api/v1/search",
                      params={"query": query, "tags": "story", "hitsPerPage": max_results},
                      headers={"User-Agent": UA}, timeout=8)
        r.raise_for_status()
        out = []
        for h in r.json().get("hits", []):
            title = h.get("title") or ""
            if not title:
                continue
            passage = (f"{title} — Hacker News thread with {h.get('points', 0)} points and "
                       f"{h.get('num_comments', 0)} comments, posted {str(h.get('created_at', ''))[:10]}.")
            out.append({"url": f"https://news.ycombinator.com/item?id={h['objectID']}",
                        "title": f"HN: {title}", "passages": [passage], "collector": "hn"})
        return out
    except Exception as exc:
        log.warning("HN search failed: %s", exc)
        if errors is not None:
            errors.append(f"hn: {type(exc).__name__}: {str(exc)[:80]}")
        return []


def search_wikipedia(query: str, max_results: int = 1, errors: list | None = None) -> list[dict]:
    if offline():
        return []
    try:
        import httpx
        params = {"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": max_results}
        r = httpx.get("https://en.wikipedia.org/w/api.php", params=params, headers={"User-Agent": UA}, timeout=8)
        if r.status_code == 429:  # polite single retry
            import time
            time.sleep(2)
            r = httpx.get("https://en.wikipedia.org/w/api.php", params=params, headers={"User-Agent": UA}, timeout=8)
        r.raise_for_status()
        out = []
        for hit in r.json().get("query", {}).get("search", []):
            title = hit["title"]
            e = httpx.get("https://en.wikipedia.org/w/api.php",
                          params={"action": "query", "prop": "extracts", "exintro": 1,
                                  "explaintext": 1, "titles": title, "format": "json"},
                          headers={"User-Agent": UA}, timeout=8).json()
            page = next(iter(e.get("query", {}).get("pages", {}).values()), {})
            text = page.get("extract", "")
            out.append({"url": f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}",
                        "title": f"Wikipedia: {title}", "passages": _sentences(text)[:4],
                        "collector": "wikipedia"})
        return out
    except Exception as exc:
        log.warning("Wikipedia search failed: %s", exc)
        if errors is not None:
            errors.append(f"wikipedia: {type(exc).__name__}: {str(exc)[:80]}")
        return []


def worldbank_indicators(iso2: str, errors: list | None = None) -> list[dict]:
    if offline():
        return []
    out = []
    try:
        import httpx
        for code, label in WB_INDICATORS.items():
            r = httpx.get(f"https://api.worldbank.org/v2/country/{iso2}/indicator/{code}",
                          params={"format": "json", "mrnev": 1}, headers={"User-Agent": UA}, timeout=10)
            r.raise_for_status()
            data = r.json()
            if len(data) < 2 or not data[1]:
                continue
            row = data[1][0]
            val = row.get("value")
            if val is None:
                continue
            country = row.get("country", {}).get("value", iso2)
            passage = f"{label} for {country} in {row.get('date')}: {round(float(val), 1):,}."
            out.append({"url": f"https://data.worldbank.org/indicator/{code}?locations={iso2}",
                        "title": f"World Bank — {label}, {country}", "passages": [passage],
                        "collector": "worldbank"})
    except Exception as exc:
        log.warning("World Bank API failed: %s", exc)
        if errors is not None:
            errors.append(f"worldbank: {type(exc).__name__}: {str(exc)[:80]}")
    return out


def enrich_with_page_text(item: dict, terms: list[str]) -> dict:
    """Fetch the page; add up to 3 keyword-ranked sentences as extra passages and record the page's
    own publication date (HTML metadata) when it states one. Passage origins are tracked so that a
    search-engine snippet is never presented as text read from the page."""
    if item["collector"].startswith("web"):
        item["origins"] = ["search-snippet"] * len([p for p in item["passages"] if p])
    else:
        item["origins"] = ["api"] * len([p for p in item["passages"] if p])
    if offline() or not item["collector"].startswith("web"):
        return item
    try:
        import httpx
        r = httpx.get(item["url"], headers={"User-Agent": UA}, timeout=6, follow_redirects=True)
        if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
            raw = r.text[:400_000]
            pub = published_from_html(raw)
            if pub:
                item["published"], item["published_from"] = pub, "page-meta"
            sents = [sanitise(s) for s in _sentences(_clean_html(raw))]
            page = [s for s in rank_sentences(sents, terms) if s]
            item["passages"] = [p for p in item["passages"] if p] + page
            item["origins"] = item["origins"] + ["page"] * len(page)
    except Exception:
        pass
    return item


# ---------------------------------------------------------------------------
# Freshness and source credibility (reported to the founder and in every findings file;
# not part of the E score, so replays of earlier captures keep their exact gate outcomes)
# ---------------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
                                       "oct", "nov", "dec"), start=1)}
_META_DATE = re.compile(
    r"""(?is)(?:property|name|itemprop)\s*=\s*["'](?:article:published_time|og:published_time|datePublished|"""
    r"""date|dc\.date|pubdate|publish-date|article:modified_time|dateModified)["'][^>]*?content\s*=\s*["']"""
    r"""(\d{4}-\d{2}-\d{2})""")
_META_DATE_REV = re.compile(
    r"""(?is)content\s*=\s*["'](\d{4}-\d{2}-\d{2})[^"']*["'][^>]*?(?:property|name|itemprop)\s*=\s*["']"""
    r"""(?:article:published_time|datePublished|date|pubdate|dateModified)["']""")
_JSONLD_DATE = re.compile(r'"date(?:Published|Modified)"\s*:\s*"(\d{4}-\d{2}-\d{2})')
_TIME_TAG = re.compile(r'(?is)<time[^>]+datetime\s*=\s*["\'](\d{4}-\d{2}-\d{2})')
_SNIPPET_DATE = re.compile(r"^\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}), (\d{4})\b")
_RELATIVE_DATE = re.compile(r"^\s*(\d{1,3}) (minute|hour|day|week|month|year)s? ago\b", re.I)
_HN_DATE = re.compile(r"posted (\d{4}-\d{2}-\d{2})")
_WB_YEAR = re.compile(r" in (\d{4}): ")


def published_from_html(raw: str) -> str | None:
    for rx in (_META_DATE, _META_DATE_REV, _JSONLD_DATE, _TIME_TAG):
        m = rx.search(raw)
        if m:
            return m.group(1)
    return None


def source_date(s: Source) -> tuple[str | None, str]:
    """(date, how it was found). Uses the stored page date, else what the stored text itself states."""
    if s.published:
        return s.published, s.published_from or "page-meta"
    first = s.passages[0] if s.passages else ""
    if s.collector == "hn":
        m = _HN_DATE.search(first)
        return (m.group(1), "api") if m else (None, "")
    if s.collector == "worldbank":
        m = _WB_YEAR.search(first)
        return (m.group(1), "api (data year)") if m else (None, "")
    m = _RELATIVE_DATE.match(first)
    if m:   # "8 hours ago · …": relative to when the snippet was fetched
        n, unit = int(m.group(1)), m.group(2).lower()
        days = n * {"minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}[unit]
        try:
            fetched = datetime.fromisoformat(s.fetch_time.replace("Z", "+00:00")).date()
            return (fetched - timedelta(days=days)).isoformat(), "snippet-date (relative)"
        except ValueError:
            return None, ""
    m = _SNIPPET_DATE.match(first)
    if m:
        mon, day, year = _MONTHS[m.group(1).lower()[:3]], int(m.group(2)), int(m.group(3))
        return f"{year:04d}-{mon:02d}-{day:02d}", "snippet-date"
    return None, ""


def freshness(s: Source) -> tuple[str, int | None]:
    """('fresh' ≤ 18 months | 'aging' ≤ 36 | 'stale' | 'undated', age in days at fetch time)."""
    d, _ = source_date(s)
    if not d:
        return "undated", None
    try:
        fetched = datetime.fromisoformat(s.fetch_time.replace("Z", "+00:00")).date()
        pub = datetime.strptime(d if len(d) == 10 else f"{d}-12-31", "%Y-%m-%d").date()
    except ValueError:
        return "undated", None
    age = max(0, (fetched - pub).days)
    return ("fresh" if age <= 548 else "aging" if age <= 1096 else "stale"), age


_COMMUNITY = ("news.ycombinator.com", "reddit.com", "facebook.com", "quora.com", "stackexchange.com",
              "stackoverflow.com", "x.com", "twitter.com", "linkedin.com", "youtube.com", "tiktok.com")
_ACADEMIC = ("arxiv.org", "doi.org", "ncbi.nlm.nih.gov", "sciencedirect.com", "springer.com",
             "researchgate.net", "jstor.org", "nature.com", "frontiersin.org", "mdpi.com", "eric.ed.gov")
_OFFICIAL = ("worldbank.org", "data.worldbank.org", "oecd.org", "un.org", "unesco.org", "itu.int",
             "imf.org", "statista.com", "pewresearch.org", "gsma.com", "datareportal.com")


def credibility(s: Source) -> str:
    """Who is speaking. 'vendor' = the site sells a product it is writing about (self-interested)."""
    d = s.domain
    if s.collector == "worldbank" or any(d == o or d.endswith("." + o) for o in _OFFICIAL) \
            or re.search(r"\.(gov|gob|gouv)(\.[a-z]{2})?$", d):
        return "official-statistics"
    if s.collector == "wikipedia":
        return "reference"
    if any(d == a or d.endswith("." + a) for a in _ACADEMIC) or re.search(r"\.(edu|ac)(\.[a-z]{2})?$", d):
        return "academic"
    if s.collector == "hn" or any(d == c or d.endswith("." + c) for c in _COMMUNITY):
        return "community"
    brand = re.sub(r"[^a-z0-9]", "", d.split(".")[-2] if d.count(".") >= 1 else d)
    text = re.sub(r"[^a-z0-9]", "", (s.title + " " + " ".join(s.passages)).lower())
    if "/pricing" in s.url.lower() or (len(brand) >= 4 and brand in text):
        return "vendor (self-interested)"
    if _product_brand(brand, text) and re.search(r"/(blog|features?|product|app|learn|resources)\b", s.url.lower()):
        # e.g. studycardsai.com/blog/...: a domain made of the product's own words, writing on its blog
        return "vendor (self-interested)"
    return "independent-web"


_BRAND_SUFFIX = ("ai", "app", "hq", "io", "ly", "go")


def _product_brand(brand: str, text: str) -> bool:
    """True when the domain label splits into 2+ words that all occur in the page text (each 4+ letters,
    or a common product suffix such as 'ai' / 'app'), e.g. 'studycardsai' -> study + cards + ai."""
    if len(brand) < 6:
        return False

    def split(rest: str, parts: int) -> bool:
        if not rest:
            return parts >= 2
        for i in range(len(rest), 1, -1):
            seg = rest[:i]
            if (seg in _BRAND_SUFFIX or (len(seg) >= 4 and seg in text)) and split(rest[i:], parts + 1):
                return True
        return False
    return split(brand, 0)


def quality_report(sources: list[Source], claims: list[Claim]) -> dict:
    """Freshness, credibility and passage-origin summary of the evidence the claims actually rely on."""
    by_key = {s.key: s for s in sources}
    rows, warnings = [], []
    strong_cats: set[str] = set()
    for c in claims:
        if not c.verified:
            continue
        for k in c.source_keys:
            s = by_key.get(k)
            if not s:
                continue
            fresh, age = freshness(s)
            cred = credibility(s)
            idx = next((i for i, p in enumerate(s.passages) if quote_matches(c.quote, p)), 0)
            origin = (s.passage_origins[idx] if idx < len(s.passage_origins) else
                      "api" if s.collector in ("hn", "worldbank", "wikipedia") else
                      "search-snippet" if idx == 0 else "page")
            date, how = source_date(s)
            rows.append({"category": c.category, "key": k, "domain": s.domain, "credibility": cred,
                         "published": date, "date_from": how, "freshness": fresh, "age_days": age,
                         "origin": origin})
            if not cred.startswith("vendor") and fresh != "stale":
                strong_cats.add(c.category)
            if cred.startswith("vendor") and c.category in ("demand", "pricing"):
                warnings.append(f"{c.category}: {k} ({s.domain}) is a vendor writing about its own market — "
                                "treat as a claim, not independent evidence.")
            if fresh == "stale":
                warnings.append(f"{c.category}: {k} ({s.domain}) is older than 3 years ({date}).")
    cited = {r["key"]: r for r in rows}.values()
    n = len(cited) or 1
    summary = {
        "cited_sources": len(cited),
        "dated_share": round(sum(1 for r in cited if r["freshness"] != "undated") / n, 2),
        "fresh_share": round(sum(1 for r in cited if r["freshness"] == "fresh") / n, 2),
        "independent_share": round(sum(1 for r in cited if not r["credibility"].startswith("vendor")) / n, 2),
        "snippet_quote_share": round(sum(1 for r in rows if r["origin"] == "search-snippet") / (len(rows) or 1), 2),
        "categories_with_independent_non_stale_evidence": sorted(strong_cats),
        "categories_only_vendor_or_stale": sorted({r["category"] for r in rows} - strong_cats),
    }
    return {"rows": rows, "warnings": sorted(set(warnings)), "summary": summary}


# ---------------------------------------------------------------------------
# Query planning and ledger
# ---------------------------------------------------------------------------

def plan_queries(idea: str, target_user: str, geography: str, round_no: int = 1) -> dict[str, list[tuple[str, str]]]:
    """Return {category: [(collector, query), ...]}. Round 2 broadens the phrasing."""
    kw = " ".join(keywords(idea, 5))
    user = " ".join(keywords(target_user, 3))
    geo = "" if geography.upper().startswith(("ASSUMPTION", "UNKNOWN")) else geography
    if round_no == 1:
        plan = {
            # Demand: a first-hand community query (Reddit threads are people describing their own
            # problem) plus a problem query that names the user and the place.
            "demand": [("web", f"{kw} {user} problem need {geo}"), ("hn", " ".join(keywords(idea, 2))),
                       ("web", f"reddit {' '.join(keywords(idea, 3))} {user} {geo}".strip())],
            "competitors": [("web", f"best {kw} apps alternatives"), ("wikipedia", kw)],
            # Pricing: vendor pricing pages state real prices (they are labelled vendor sources).
            "pricing": [("web", f"{kw} app pricing per month subscription"),
                        ("web", f"{' '.join(keywords(idea, 3))} pricing plans free premium")],
            "local_constraints": [("web", f"{user} {geo} digital tools online payments")],
            "channels": [("web", f"how to reach {user} {geo} marketing community")],
        }
    else:
        short = " ".join(keywords(idea, 3))
        plan = {
            "demand": [("web", f"{short} survey statistics {user}"), ("hn", f"{short} {user}".strip())],
            "competitors": [("web", f"{short} software comparison review")],
            "pricing": [("web", f"{short} subscription price comparison")],
            "local_constraints": [("web", f"{geo} {short} market adoption".strip())],
            "channels": [("web", f"{user} online communities forums {geo}".strip())],
        }
    return plan


def collect(idea: str, target_user: str, geography: str, round_no: int = 1,
            existing: list[Source] | None = None,
            health: dict | None = None) -> tuple[list[Source], dict[str, str]]:
    """Run all collectors and return (sources, category_by_source_key).

    health: optional dict filled with how the research tools behaved this round
    ({"jobs", "ok", "empty", "failed", "errors", "new_sources"}). A job "failed" when its tool raised
    (HTTP 429, timeout, DNS...), which is different from a search that worked and found nothing."""
    existing = existing or []
    sources: list[Source] = list(existing)
    category_of: dict[str, str] = {}
    seen_urls = {s.url for s in sources}
    terms = keywords(f"{idea} {target_user}", 10)

    jobs: list[tuple[str, str, str]] = []
    for cat, qs in plan_queries(idea, target_user, geography, round_no).items():
        for collector, q in qs:
            jobs.append((cat, collector, q))

    status: list[tuple[str, int, list]] = []          # (collector, n_results, errors) per job

    def run_job(job):
        cat, collector, q = job
        fn = {"web": search_web, "hn": search_hn, "wikipedia": search_wikipedia}[collector]
        errs: list = []
        items = fn(q, errors=errs)
        status.append((collector, len(items), errs))
        return cat, items

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run_job, jobs))

    country = detect_country(geography)
    if country and round_no == 1:
        errs: list = []
        wb = worldbank_indicators(country[1], errors=errs)
        status.append(("worldbank", len(wb), errs))
        results.append(("local_constraints", wb))

    raw: list[tuple[str, dict]] = []
    per_domain: dict[str, int] = {}
    # Structured sources first so the cap below never drops them.
    flat = [(cat, it) for cat, items in results for it in items]
    flat.sort(key=lambda ci: 0 if not ci[1]["collector"].startswith("web") else 1)
    for cat, it in flat:
        if True:
            if not it["url"] or it["url"] in seen_urls or _is_ad(it["url"]):
                continue
            d = domain_of(it["url"])
            if per_domain.get(d, 0) >= 2:
                continue
            per_domain[d] = per_domain.get(d, 0) + 1
            seen_urls.add(it["url"])
            raw.append((cat, it))

    with ThreadPoolExecutor(max_workers=6) as pool:
        enriched = list(pool.map(lambda ci: (ci[0], enrich_with_page_text(ci[1], terms)), raw[:24]))

    for cat, it in enriched:
        passages = [p for p in it["passages"] if p]
        if not passages:
            continue
        key = f"S{len(sources) + 1}"
        text = " ".join(passages)
        origins = (it.get("origins") or [])[:len(passages)]
        sources.append(Source(key=key, url=it["url"], title=it["title"][:160], domain=domain_of(it["url"]),
                              fetch_time=now_iso(), text_hash=_hash(text), passages=passages[:5],
                              collector=it["collector"], category=cat,
                              published=it.get("published"), published_from=it.get("published_from", ""),
                              passage_origins=origins[:5]))
        category_of[key] = cat
    if health is not None:
        health.update(tool_health(status, len(sources) - len(existing)))
    return sources, category_of


def tool_health(status: list[tuple[str, int, list]], new_sources: int) -> dict:
    """Summarise collector outcomes. `outage` is True when most research calls raised errors and too
    little came back to judge the market: Gate 1 then says 'research tools unavailable, retry' instead
    of scoring the (missing) evidence as weak."""
    jobs = len(status)
    failed = sum(1 for _, n, e in status if e and n == 0)
    ok = sum(1 for _, n, _ in status if n > 0)
    errors = sorted({e for _, _, es in status for e in es})[:8]
    outage = jobs > 0 and (failed / jobs >= 0.5) and new_sources < 6
    return {"jobs": jobs, "ok": ok, "empty": jobs - ok - failed, "failed": failed,
            "new_sources": new_sources, "errors": errors, "outage": outage}


# ---------------------------------------------------------------------------
# Evidence replay (reproducible runs from a captured snapshot)
# ---------------------------------------------------------------------------

SNAPSHOT_VERSION = 1


class ReplayMissError(LookupError):
    """The snapshot has no captured round for this request. Replay never falls back to live search."""


def replay_round(snapshot: dict, idea: str, round_no: int) -> dict:
    for r in snapshot.get("rounds", []):
        if r["round"] == round_no and r["idea"] == idea:
            return r
    raise ReplayMissError(f"snapshot has no captured evidence for round {round_no} of idea {idea[:80]!r}")


def replay_collect(snapshot: dict, idea: str, round_no: int,
                   existing: list[Source] | None = None) -> tuple[list[Source], dict]:
    """Return (existing + captured sources for this round, round record). No network access."""
    rnd = replay_round(snapshot, idea, round_no)
    existing = list(existing or [])
    new = [Source(**s) for s in rnd["sources"]]
    expected = [f"S{len(existing) + i + 1}" for i in range(len(new))]
    if [s.key for s in new] != expected:
        raise ReplayMissError(f"snapshot source keys {[s.key for s in new]} do not continue the ledger {expected}")
    return existing + new, rnd


# ---------------------------------------------------------------------------
# Citation verifier
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[^a-z0-9%$.,' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def quote_matches(quote: str, passage: str, threshold: float = 0.9) -> bool:
    q, p = _norm(quote), _norm(passage)
    if len(q) < 12:
        return False
    if q in p:
        return True
    n = len(q)
    best = 0.0
    step = max(1, n // 6)
    for i in range(0, max(1, len(p) - n + 1), step):
        r = difflib.SequenceMatcher(None, q, p[i:i + n]).ratio()
        best = max(best, r)
        if best >= threshold:
            return True
    return False


def verify_claims(claims: list[Claim], sources: list[Source]) -> list[Claim]:
    """Downgrade claims whose citations don't hold up. Mutates and returns claims."""
    by_key = {s.key: s for s in sources}
    for c in claims:
        c.source_keys = [k for k in c.source_keys if k in by_key]  # unknown keys rejected
        ok = bool(c.source_keys) and bool(c.quote) and any(
            quote_matches(c.quote, p) for k in c.source_keys for p in by_key[k].passages
        )
        c.verified = ok
        c.is_assumption = not ok
        if not ok and not c.text.startswith("ASSUMPTION"):
            c.text = f"ASSUMPTION (citation not verified): {c.text}"
    return claims


CATEGORY_TERMS = {
    "demand": ("problem", "struggl", "need", "survey", "adoption", "%", "percent", "points and", "burden",
               "demand", "pain", "difficult", "spend", "frustrat", "looking for", "wish"),
    "competitors": ("anki", "quizlet", "alternative", "compare", "comparison", "best", "vs", "competitor",
                    "app", "apps", "tool", "platform", "features", "leading"),
    "pricing": ("$", "price", "pricing", "per month", "/month", "subscription", "premium", "free tier", "free plan"),
    "local_constraints": ("internet", "payment", "gdp", "income", "mobile", "smartphone", "language", "%",
                          "regulation", "access"),
    "channels": ("facebook", "tiktok", "instagram", "youtube", "whatsapp", "telegram", "community", "group",
                 "forum", "marketing", "reach", "social media", "word of mouth", "ambassador"),
}


def _looks_like_navigation(p: str) -> bool:
    return p.count("·") >= 3 or p.count("|") >= 4 or len(re.findall(r"[A-Z][a-z]+ [A-Z][a-z]+", p)) > 12


def _mostly_latin(p: str) -> bool:
    letters = [ch for ch in p if ch.isalpha()]
    return bool(letters) and sum(1 for ch in letters if ch.isascii()) / len(letters) > 0.9


def passage_relevance(p: str, cat: str, terms: list[str], collector: str = "") -> tuple[int, int]:
    """(idea-term hits, category-term hits) for a passage."""
    low = p.lower()
    return sum(1 for t in terms if t in low), sum(1 for t in CATEGORY_TERMS[cat] if t in low)


SCORING_VERSIONS = ("v1", "v2")
DEFAULT_LIVE_SCORING = "v2"           # new live runs; replays default to the snapshot's own version


def extractive_claims(sources: list[Source], idea: str, target_user: str, scoring: str = "v1",
                      geography: str = "", language: str = "") -> list[Claim]:
    """Dispatch to the relevance rule of the given scoring version (v1 unchanged, v2 brief-specific)."""
    if scoring == "v1":
        return extractive_claims_v1(sources, idea, target_user)
    if scoring == "v2":
        return extractive_claims_v2(sources, idea, target_user, geography, language)
    raise ValueError(f"unknown scoring version {scoring!r}; expected one of {SCORING_VERSIONS}")


# ---------------------------------------------------------------------------
# v2 relevance: a passage must match the brief's OWN terms, not just category vocabulary
# ---------------------------------------------------------------------------

# Words that describe "a product" in general and say nothing about this brief's problem.
GENERIC_PRODUCT_WORDS = set("""ai ai-powered smart simple easy new best sells sell selling generic build
built make want app apps tool tools platform service website web mobile online digital solution system
software product products based focused""".split())
# Aggregate market figures are background context, never demand evidence for this brief.
AGGREGATE_STATS = re.compile(r"\b(million|billion|trillion|statistics|market size|industry|worldwide|global)\b", re.I)
DEMAND_TERMS_V2 = tuple(t for t in CATEGORY_TERMS["demand"] if t != "points and")   # HN metadata is not demand


def _known(v: str) -> str:
    return "" if not v or v.upper().startswith(("UNKNOWN", "ASSUMPTION")) else v


def brief_terms(idea: str, target_user: str, geography: str, language: str) -> dict[str, list[str]]:
    """The brief's specific terms: user (stated target user), local (stated geography + non-English
    language), product (idea keywords minus generic product words, user and local terms)."""
    user = keywords(_known(target_user), 6)
    local = keywords(_known(geography), 4)
    for lang in re.split(r"[/,\s]+", _known(language).lower()):
        if lang and lang != "english" and lang not in local:
            local.append(lang)
    product = [w for w in keywords(idea, 12)
               if w not in GENERIC_PRODUCT_WORDS and w not in user and w not in local]
    return {"user": user, "local": local, "product": product}


def _hits(terms: list[str], low: str) -> int:
    """Whole-word-prefix matches; hyphenated terms also match with a space ('spaced repetition')."""
    n = 0
    for t in terms:
        pat = r"[- ]".join(re.escape(part) for part in t.split("-"))
        if re.search(rf"\b{pat}", low):
            n += 1
    return n


def _vocab(cat_terms: tuple, low: str) -> int:
    return sum(1 for t in cat_terms if t in low)


def relevant_v2(p: str, cat: str, s: Source, bt: dict[str, list[str]]) -> int:
    """Return a ranking score > 0 if passage p counts for category `cat` under v2, else 0."""
    low = p.lower()
    u, loc, pr = _hits(bt["user"], low), _hits(bt["local"], low), _hits(bt["product"], low)
    about_product = pr >= 2 or (pr >= 1 and u >= 1)
    if s.collector == "worldbank":
        # Indicator rows are fetched for the brief's own country only; they are local context.
        return 4 if cat == "local_constraints" and bt["local"] and loc >= 1 else 0
    if cat == "demand":
        v = _vocab(DEMAND_TERMS_V2, low)
        ok = u >= 1 and pr >= 1 and loc >= 1 and v >= 1 and not AGGREGATE_STATS.search(low)
    elif cat == "competitors":
        v = _vocab(CATEGORY_TERMS["competitors"], low)
        ok = v >= 1 and about_product
    elif cat == "pricing":
        v = _vocab(CATEGORY_TERMS["pricing"], low)
        ok = v >= 1 and about_product
    elif cat == "local_constraints":
        v = _vocab(CATEGORY_TERMS["local_constraints"], low)
        ok = v >= 1 and loc >= 1
    else:  # channels
        v = _vocab(CATEGORY_TERMS["channels"], low)
        ok = v >= 1 and (u >= 1 or loc >= 1)
    return (u + loc + pr + v) if ok else 0


def extractive_claims_v2(sources: list[Source], idea: str, target_user: str, geography: str,
                         language: str) -> list[Claim]:
    """v2: same verbatim-quote synthesis as v1 (top 2 per category), stricter relevance."""
    bt = brief_terms(idea, target_user, geography, language)
    claims: list[Claim] = []
    for cat in CATEGORIES:
        cands = []
        for s in sources:
            for p in s.passages:
                if len(p) < 30 or _looks_like_navigation(p[:240]) or not _mostly_latin(p[:240]):
                    continue
                score = relevant_v2(p, cat, s, bt)
                if score:
                    cands.append((score + (1 if s.category == cat else 0), s, p))
        cands.sort(key=lambda x: -x[0])
        used = set()
        for _, s, p in cands:
            if s.key in used:
                continue
            used.add(s.key)
            quote = p[:240]
            claims.append(Claim(category=cat, text=f'{s.title} reports: "{quote}"', source_keys=[s.key],
                                quote=quote, verified=True, is_assumption=False))
            if len(used) >= 2:
                break
    return claims


def extractive_claims_v1(sources: list[Source], idea: str, target_user: str) -> list[Claim]:
    """v1 (unchanged): No-LLM synthesis: up to 2 verbatim passages per category, each a verified quote.

    A passage qualifies only if it mentions the idea/target user AND the category's
    vocabulary, and is not navigation chrome. World Bank indicator rows qualify for
    local_constraints by construction.
    """
    terms = keywords(f"{idea} {target_user}", 10)
    claims: list[Claim] = []
    for cat in CATEGORIES:
        cands = []
        for s in sources:
            for p in s.passages:
                if len(p) < 30 or _looks_like_navigation(p[:240]) or not _mostly_latin(p[:240]):
                    continue
                idea_hits, cat_hits = passage_relevance(p, cat, terms)
                if s.collector == "worldbank":
                    if cat != "local_constraints":
                        continue
                    idea_hits, cat_hits = idea_hits + 3, cat_hits + 1
                if idea_hits < 1 or cat_hits < 1:
                    continue
                home = 1 if s.category == cat else 0
                score = idea_hits + cat_hits + home + (1 if re.search(r"\d", p) else 0)
                cands.append((score, s, p))
        cands.sort(key=lambda x: -x[0])
        used = set()
        for score, s, p in cands:
            if s.key in used:
                continue
            used.add(s.key)
            quote = p[:240]
            claims.append(Claim(category=cat, text=f'{s.title} reports: "{quote}"', source_keys=[s.key],
                                quote=quote, verified=True, is_assumption=False))
            if len(used) >= 2:
                break
    return claims


# ---------------------------------------------------------------------------
# Pain signals: what the verified evidence says hurts (input to the Advisor's gap analysis)
# ---------------------------------------------------------------------------

PAIN_CUES = ("burden", "struggl", "difficult", "hard to", "time-consuming", "spend", "spending", "frustrat",
             "overwhelm", "stress", "expensive", "can't afford", "cannot afford", "lack", "waste", "deter",
             "problem", "challenge", "barrier", "pain", "tedious", "confus", "forget", "drop out", "abandon")
_PAIN_STOP = STOPWORDS | set("""than more such so very even still being been were was there these those when
while because whether through across within reported recent found study studies report percent""".split())


def pain_signals(claims: list[Claim], idea: str = "", target_user: str = "") -> list[dict]:
    """Pull the problem wording out of verified demand claims.

    For every pain cue ('burden', 'struggle', 'spend', ...) in a verified demand quote, keep the clause
    around it and its content words. Words that only restate the idea or the target user (e.g.
    'flashcards', 'students') are removed, so what is left describes the pain, not the product.
    Returns [{"key", "cue", "phrase", "terms"}], deterministic and in claim order."""
    known = set(keywords(f"{idea} {target_user}", 30))
    out: list[dict] = []
    for c in claims:
        if c.category != "demand" or not c.verified or c.is_assumption or not c.quote:
            continue
        low = c.quote.lower()
        for clause in re.split(r"[.;:!?()]|\s[—–-]\s", low):
            cue = next((q for q in PAIN_CUES if q in clause), None)
            if not cue:
                continue
            words = re.findall(r"[a-z][a-z\-]{3,}", clause)
            terms = [w for w in words if w not in _PAIN_STOP and w not in known
                     and not any(w.startswith(k[:6]) for k in known if len(k) >= 6)]
            terms = list(dict.fromkeys(terms))[:8]
            if not terms:
                continue
            phrase = " ".join(clause.split()[:28]).strip(" ,")
            out.append({"key": c.source_keys[0], "cue": cue, "phrase": phrase, "terms": terms})
            break                                   # one pain per claim keeps the memo readable
    return out
