# Phase 1 — Research findings (round 1)

> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v1 (relevance: any idea keyword + category vocabulary)

> **Evidence mode: REPLAY** — sources loaded from snapshot evidence_snapshots/weak_scenario.json (captured 2026-11-17T15:53:01+00:00). Nothing was collected in this run; fetch times and hashes below are the ORIGINAL capture values.
> Synthesis mode: **extractive** (no LLM: claims are verbatim passages from fetched sources).
> Every claim cites a fetched source whose text contains the quoted passage, or is labelled ASSUMPTION.

## Claims

- **demand** — HN: Maker of EpiPen to Sell Generic Version for Half the Price reports: "Maker of EpiPen to Sell Generic Version for Half the Price — Hacker News thread with 1 points and 1 comments, posted 2016-08-29." (VERIFIED — [S1](https://news.ycombinator.com/item?id=12382737))
- **demand** — HN: Mylan to Sell Generic EpiPen at Half the Price of Original reports: "Mylan to Sell Generic EpiPen at Half the Price of Original — Hacker News thread with 1 points and 0 comments, posted 2016-12-16." (VERIFIED — [S2](https://news.ycombinator.com/item?id=13195588))
- **competitors** — Best Study Notes App 2026: 11 Tools for Students Compared reports: "Jun 2, 2026 · Quick comparison: 11 best study notes apps for 2026 ... The rest of this guide breaks each app down: pricing, what it does well, where it falls short, and which student profile it actually fits." (VERIFIED — [S3](https://www.screensnap.pro/blog/best-study-notes-app))
- **competitors** — The 15 best free note-taking apps for students in 2026 reports: "Goodnotes Content Team View related posts Study Tips The 15 best free note-taking apps for students in 2026 Goodnotes Content Team A roundup comparing the free plans of 15 note-taking apps (Goodnotes, Apple Notes, Freenotes, Notion, Obsidia" (VERIFIED — [S5](https://www.goodnotes.com/blog/best-free-note-taking-apps-for-students-2026))
- **pricing** — Sell Study Notes and Class Notes Online (2026) | RichTactic reports: "Apr 1, 2026 · Selling Study Notes offers higher income potential (reported $300-$3K/month) and location freedom compared to most jobs, but requires self-motivation and involves more uncertainty." (VERIFIED — [S8](https://richtactic.com/tactic/study-notes-selling))
- **pricing** — Pricing for Individuals - Compare plans and unlock better ... reports: "Monthly Subscribe to Genio Notes Annual Save up to 20% with multi-year plans Genio Notes for individuals From £12 per month Start improving your learning experience with powerful, all-in-one study notes that are easy to learn from." (VERIFIED — [S10](https://genio.co/pricing/individuals))
- **local_constraints** — Studyrift — High-quality Study Notes, Summaries & Exam Prep reports: "Swap it for free Written by students who passed Immediately available after payment Read online or as PDF 4.6 Trustpilot Trusted by 50,000+ Students Worldwide High-quality Study Notes, Summaries & Exam Prep Buy and sell the best university " (VERIFIED — [S7](https://studyrift.com/))
- **local_constraints** — Sell Study Notes and Class Notes Online (2026) | RichTactic reports: "Apr 1, 2026 · Selling Study Notes offers higher income potential (reported $300-$3K/month) and location freedom compared to most jobs, but requires self-motivation and involves more uncertainty." (VERIFIED — [S8](https://richtactic.com/tactic/study-notes-selling))
- **channels** — The 15 best free note-taking apps for students in 2026 reports: "Work with classmates: The Free plan supports comments and up to 10 external guests, which can be useful for shared study notes or group projects." (VERIFIED — [S5](https://www.goodnotes.com/blog/best-free-note-taking-apps-for-students-2026))
- **channels** — Studyrift — High-quality Study Notes, Summaries & Exam Prep reports: "56 pages Start browsing 📚 Browse textbooks ❓ Homework Q&A 🎯 AI practice quizzes 💬 Community 💰 Sell study notes How it works → ✨ NEW — AI POWERED Practice Quizzes, Built by AI 20 exam-style questions per set, generated from real study docume" (VERIFIED — [S7](https://studyrift.com/))

## Opportunity angles

- Narrow the idea to a narrower, named user group in one specific country: An app that sells generic study notes.
- ASSUMPTION: differentiate from the incumbents in the competitor evidence via English localisation for a narrower, named user group
- ASSUMPTION: B2B version — sell to institutions that serve a narrower, named user group

## Evidence score: 95.0 / 100

| Component | Points |
|---|---|
| category coverage | 40.0 |
| verified ratio | 25.0 |
| domain diversity | 20.0 |
| source type triangulation | 10.0 |

## Evidence quality audit (advisory: shown to the founder, not part of the E score)

A quote that matches its source proves **where** a sentence came from, not that it is **true**. This audit
shows who is speaking, how old the source is, and whether the quote came from the fetched page or only from
the search engine's snippet. Freshness: fresh ≤ 18 months, aging ≤ 36 months, stale > 36 months (age measured
at fetch time).

| Metric | Value |
|---|---|
| Cited sources | 7 |
| Dated (publication date found) | 71% |
| Fresh (≤ 18 months) | 43% |
| Independent (not a vendor writing about its own market) | 43% |
| Quotes taken from a search snippet rather than the page | 30% |
| Categories backed by independent, non-stale evidence | competitors |
| Categories backed only by vendor or stale evidence | channels, demand, local_constraints, pricing |

| Category | Source | Domain | Who is speaking | Published | Freshness | Quote origin |
|---|---|---|---|---|---|---|
| demand | S1 | news.ycombinator.com | community | 2016-08-29 (api) | stale (3732 d) | api |
| demand | S2 | news.ycombinator.com | community | 2016-12-16 (api) | stale (3623 d) | api |
| competitors | S3 | screensnap.pro | independent-web | 2026-06-02 (snippet-date) | fresh (168 d) | search-snippet |
| competitors | S5 | goodnotes.com | vendor (self-interested) | 2026-09-11 (snippet-date) | fresh (67 d) | page |
| pricing | S8 | richtactic.com | vendor (self-interested) | 2026-04-01 (snippet-date) | fresh (230 d) | search-snippet |
| pricing | S10 | genio.co | vendor (self-interested) | undated | undated | page |
| local_constraints | S7 | studyrift.com | vendor (self-interested) | undated | undated | page |
| local_constraints | S8 | richtactic.com | vendor (self-interested) | 2026-04-01 (snippet-date) | fresh (230 d) | search-snippet |
| channels | S5 | goodnotes.com | vendor (self-interested) | 2026-09-11 (snippet-date) | fresh (67 d) | page |
| channels | S7 | studyrift.com | vendor (self-interested) | undated | undated | page |

**Warnings**

- ⚠ demand: S1 (news.ycombinator.com) is older than 3 years (2016-08-29).
- ⚠ demand: S2 (news.ycombinator.com) is older than 3 years (2016-12-16).
- ⚠ pricing: S10 (genio.co) is a vendor writing about its own market — treat as a claim, not independent evidence.
- ⚠ pricing: S8 (richtactic.com) is a vendor writing about its own market — treat as a claim, not independent evidence.

## Source ledger (10 sources, 9 domains)

- `S1` [HN: Maker of EpiPen to Sell Generic Version for Half the Price](https://news.ycombinator.com/item?id=12382737) — hn, demand, community, published 2016-08-29, fetched 2026-11-17T15:53:00+00:00, sha256:8a7fb949e4c422bf
- `S2` [HN: Mylan to Sell Generic EpiPen at Half the Price of Original](https://news.ycombinator.com/item?id=13195588) — hn, demand, community, published 2016-12-16, fetched 2026-11-17T15:53:00+00:00, sha256:d353c165c9ae593e
- `S3` [Best Study Notes App 2026: 11 Tools for Students Compared](https://www.screensnap.pro/blog/best-study-notes-app) — web:yahoo, competitors, independent-web, published 2026-06-02, fetched 2026-11-17T15:53:00+00:00, sha256:79ffc32cc879d406
- `S4` [8 Best Note-Taking Apps for Students 2026 - savemyexams.com](https://www.savemyexams.com/learning-hub/useful-resources/best-note-taking-apps-for-students/) — web:yahoo, competitors, vendor (self-interested), published 2026-09-08, fetched 2026-11-17T15:53:00+00:00, sha256:728ddabb17eb8ac3
- `S5` [The 15 best free note-taking apps for students in 2026](https://www.goodnotes.com/blog/best-free-note-taking-apps-for-students-2026) — web:yahoo, competitors, vendor (self-interested), published 2026-09-11, fetched 2026-11-17T15:53:00+00:00, sha256:91e920ec0e978688
- `S6` [Best Study Apps in 2026: 24 Tested, Every Price Dated](https://www.mindomax.com/best-study-apps-for-students) — web:yahoo, competitors, independent-web, published 2026-06-07, fetched 2026-11-17T15:53:00+00:00, sha256:3df91af4ab7e0052
- `S7` [Studyrift — High-quality Study Notes, Summaries & Exam Prep](https://studyrift.com/) — web:yahoo, pricing, vendor (self-interested), published undated, fetched 2026-11-17T15:53:00+00:00, sha256:f620d7aaeb49654a
- `S8` [Sell Study Notes and Class Notes Online (2026) | RichTactic](https://richtactic.com/tactic/study-notes-selling) — web:yahoo, pricing, vendor (self-interested), published 2026-04-01, fetched 2026-11-17T15:53:00+00:00, sha256:53d5b58e94ef06ae
- `S9` [Sell Study Notes Online: 5 Best Platforms (2026)](https://www.researchprospect.com/platforms-to-sell-study-notes-online/) — web:yahoo, pricing, independent-web, published 2026-02-24, fetched 2026-11-17T15:53:00+00:00, sha256:e12baaebd13138e3
- `S10` [Pricing for Individuals - Compare plans and unlock better ...](https://genio.co/pricing/individuals) — web:yahoo, pricing, vendor (self-interested), published undated, fetched 2026-11-17T15:53:00+00:00, sha256:bd3c64aa97feb446
