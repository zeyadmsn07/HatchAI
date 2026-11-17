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
from datetime import datetime, timezone
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

def search_web(query: str, max_results: int = 4) -> list[dict]:
    if offline():
        return []
    try:
        from ddgs import DDGS  # type: ignore
    except ImportError:
        log.warning("ddgs not installed; web search skipped")
        return []
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
    return []


def search_hn(query: str, max_results: int = 3) -> list[dict]:
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
        return []


def search_wikipedia(query: str, max_results: int = 1) -> list[dict]:
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
        return []


def worldbank_indicators(iso2: str) -> list[dict]:
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
    return out


def enrich_with_page_text(item: dict, terms: list[str]) -> dict:
    """Fetch the page and add up to 3 keyword-ranked sentences as extra passages."""
    if offline() or not item["collector"].startswith("web"):
        return item
    try:
        import httpx
        r = httpx.get(item["url"], headers={"User-Agent": UA}, timeout=6, follow_redirects=True)
        if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
            sents = [sanitise(s) for s in _sentences(_clean_html(r.text[:400_000]))]
            item["passages"] = [p for p in item["passages"] if p] + [s for s in rank_sentences(sents, terms) if s]
    except Exception:
        pass
    return item


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
            "demand": [("web", f"{kw} {user} problem need {geo}"), ("hn", " ".join(keywords(idea, 2)))],
            "competitors": [("web", f"best {kw} apps alternatives"), ("wikipedia", kw)],
            "pricing": [("web", f"{kw} app pricing per month subscription")],
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
            existing: list[Source] | None = None) -> tuple[list[Source], dict[str, str]]:
    """Run all collectors and return (sources, category_by_source_key)."""
    existing = existing or []
    sources: list[Source] = list(existing)
    category_of: dict[str, str] = {}
    seen_urls = {s.url for s in sources}
    terms = keywords(f"{idea} {target_user}", 10)

    jobs: list[tuple[str, str, str]] = []
    for cat, qs in plan_queries(idea, target_user, geography, round_no).items():
        for collector, q in qs:
            jobs.append((cat, collector, q))

    def run_job(job):
        cat, collector, q = job
        fn = {"web": search_web, "hn": search_hn, "wikipedia": search_wikipedia}[collector]
        return cat, fn(q)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run_job, jobs))

    country = detect_country(geography)
    if country and round_no == 1:
        results.append(("local_constraints", worldbank_indicators(country[1])))

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
        enriched = list(pool.map(lambda ci: (ci[0], enrich_with_page_text(ci[1], terms)), raw[:20]))

    for cat, it in enriched:
        passages = [p for p in it["passages"] if p]
        if not passages:
            continue
        key = f"S{len(sources) + 1}"
        text = " ".join(passages)
        sources.append(Source(key=key, url=it["url"], title=it["title"][:160], domain=domain_of(it["url"]),
                              fetch_time=now_iso(), text_hash=_hash(text), passages=passages[:5],
                              collector=it["collector"], category=cat))
        category_of[key] = cat
    return sources, category_of


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


def extractive_claims(sources: list[Source], idea: str, target_user: str) -> list[Claim]:
    """No-LLM synthesis: up to 2 verbatim passages per category, each a verified quote.

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
