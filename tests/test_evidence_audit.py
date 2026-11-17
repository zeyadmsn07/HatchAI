"""Evidence quality audit: publication dates, freshness, who is speaking, passage origin."""
import json

import evidence
import orchestrator
from models import Claim, Source


def _src(key="S1", url="https://example.org/a", title="Example", passages=None, collector="web:yahoo",
         fetch="2026-11-17T12:00:00+00:00", **kw):
    return Source(key=key, url=url, title=title, domain=evidence.domain_of(url), fetch_time=fetch,
                  text_hash="0" * 16, passages=passages or ["A sufficiently long passage about something."],
                  collector=collector, **kw)


def test_dates_from_page_meta_snippet_relative_and_api():
    assert evidence.published_from_html('<meta property="article:published_time" content="2025-03-04T10:00">') == "2025-03-04"
    assert evidence.published_from_html('<script>{"datePublished": "2024-01-02"}</script>') == "2024-01-02"
    assert evidence.source_date(_src(passages=["Jul 29, 2026 · Compare the best flashcard apps for students."]))[0] == "2026-07-29"
    assert evidence.source_date(_src(passages=["8 hours ago · Egypt expands education reform for students."]))[0] == "2026-11-17"
    assert evidence.source_date(_src(passages=["3 days ago · Egypt expands education reform for students."]))[0] == "2026-11-14"
    hn = _src(collector="hn", url="https://news.ycombinator.com/item?id=1",
              passages=["Thread — Hacker News thread with 5 points and 2 comments, posted 2019-05-01."])
    assert evidence.source_date(hn)[0] == "2019-05-01"
    assert evidence.freshness(hn)[0] == "stale"
    assert evidence.freshness(_src())[0] == "undated"


def test_credibility_classes():
    assert evidence.credibility(_src(url="https://data.worldbank.org/x", collector="worldbank")) == "official-statistics"
    assert evidence.credibility(_src(url="https://arxiv.org/abs/1")) == "academic"
    assert evidence.credibility(_src(url="https://www.reddit.com/r/Egypt/x")) == "community"
    assert evidence.credibility(_src(url="https://laxuai.com/blog/best",
                                     passages=["Laxu AI is the best app at $4.99/month for students."])).startswith("vendor")
    assert evidence.credibility(_src(url="https://www.remnote.com/pricing")).startswith("vendor")
    assert evidence.credibility(_src(url="https://independent-review.org/x")) == "independent-web"


def test_quality_report_flags_vendor_pricing_and_snippet_quotes():
    s = _src(url="https://laxuai.com/blog/best", passages=["Laxu AI is the best app at $4.99/month for students."])
    c = Claim(category="pricing", text="x", source_keys=["S1"], quote=s.passages[0], verified=True, is_assumption=False)
    q = evidence.quality_report([s], [c])
    assert q["summary"]["independent_share"] == 0.0
    assert q["summary"]["snippet_quote_share"] == 1.0
    assert q["summary"]["categories_only_vendor_or_stale"] == ["pricing"]
    assert any("vendor" in w for w in q["warnings"])


def test_old_snapshots_still_load_and_new_capture_records_provenance():
    old = json.loads((orchestrator.SNAPSHOTS / "strong_scenario.json").read_text(encoding="utf-8"))
    Source(**old["rounds"][0]["sources"][0])                      # pre-audit snapshot: defaults apply
    new = json.loads((orchestrator.SNAPSHOTS / "strong_v2_scenario.json").read_text(encoding="utf-8"))
    srcs = [Source(**s) for r in new["rounds"] for s in r["sources"]]
    assert new["scoring_version"] == "v2"
    assert any(s.passage_origins for s in srcs)
    assert all(len(s.passage_origins) == len(s.passages) for s in srcs if s.passage_origins)
