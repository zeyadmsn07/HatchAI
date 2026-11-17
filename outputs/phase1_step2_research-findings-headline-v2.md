# Phase 1 — Research findings (round 1)

> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v2 (relevance: brief-specific user / problem / local terms)

> **Evidence mode: REPLAY** — sources loaded from snapshot evidence_snapshots/strong_v2_scenario.json (captured 2026-11-17T20:51:46+00:00). Nothing was collected in this run; fetch times and hashes below are the ORIGINAL capture values.
> Synthesis mode: **extractive** (no LLM: claims are verbatim passages from fetched sources).
> Every claim cites a fetched source whose text contains the quoted passage, or is labelled ASSUMPTION.

## Claims

- **demand** — Egypt steps up pre-university education reform, expands ... reports: "8 hours ago · The study noted that students enrolled in pre-university education account for more than 25% of Egypt's population, ranging from kindergarten to general secondary education and its equivalents. This reflects the scale of the s" (VERIFIED — [S12](https://mena.org.eg/en/news/egypt-steps-preuniversity-education-reform-8d66b432-4e89-4bf6-89c4-ab0f287930de))
- **competitors** — Best study apps for university students (2026) - memmo.org reports: "Apr 16, 2026 · The best study apps for university students in 2026 — compared. From AI-powered platforms and flashcard tools to note-taking apps and focus timers." (VERIFIED — [S13](https://www.memmo.org/en/magazine/studyapps))
- **competitors** — Best Study Apps for College Students in 2026 - notehive.app reports: "The best AI study apps for college students in 2026 include NoteHive AI for lecture recording, notes, flashcards, and quizzes in one place; Anki for spaced repetition; Forest for focus sessions; and Wolfram Alpha for STEM coursework." (VERIFIED — [S16](https://notehive.app/blog/best-study-apps-for-college-students-2026))
- **local_constraints** — World Bank — Individuals using the Internet (% of population), Egypt, Arab Rep. reports: "Individuals using the Internet (% of population) for Egypt, Arab Rep. in 2024: 74.6." (VERIFIED — [S3](https://data.worldbank.org/indicator/IT.NET.USER.ZS?locations=EG))
- **local_constraints** — World Bank — GDP per capita (current US$), Egypt, Arab Rep. reports: "GDP per capita (current US$) for Egypt, Arab Rep. in 2025: 3,085.8." (VERIFIED — [S4](https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=EG))
- **channels** — Marketing and Social Media Consulting | The American ... reports: "Reach out to us for consultations on marketing strategies and social media activity on your pages, and we will direct your efforts so that you can achieve your goals more efficiently and ensure you are abiding by University guidelines and f" (VERIFIED — [S24](https://www.aucegypt.edu/services/communications/marketing))
- **channels** — Studying in Egypt : r/Egypt - Reddit reports: "I would suggest searching social media and/or LinkedIn for current foreign students in Egypt in general, and AlAzhar more specifically to have the most relevant insights that everyday Egyptians can miss. Listening to someone with similar ba" (VERIFIED — [S9](https://www.reddit.com/r/Egypt/comments/szb3p4/studying_in_egypt/))
- **pricing** — ASSUMPTION: no verified evidence found for 'pricing'. (**ASSUMPTION**)

## Opportunity angles

- Narrow the idea to university students in Egypt: Narrow the idea to university students in Egypt: An AI-powered flashcard and spaced-repeti
- ASSUMPTION: differentiate from the incumbents in the competitor evidence via Arabic/English localisation for university students
- ASSUMPTION: B2B version — sell to institutions that serve university students

## Evidence score: 83.9 / 100

| Component | Points |
|---|---|
| category coverage | 32.0 |
| verified ratio | 21.9 |
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
| Dated (publication date found) | 86% |
| Fresh (≤ 18 months) | 56% |
| Independent (not a vendor writing about its own market) | 71% |
| Quotes taken from a search snippet rather than the page | 56% |
| Categories backed by independent, non-stale evidence | channels, demand, local_constraints |
| Categories backed only by vendor or stale evidence | competitors |

| Category | Source | Domain | Who is speaking | Published | Freshness | Quote origin |
|---|---|---|---|---|---|---|
| demand | S12 | mena.org.eg | independent-web | 2026-11-17 (snippet-date (relative)) | fresh (0 d) | search-snippet |
| competitors | S13 | memmo.org | vendor (self-interested) | 2026-04-16 (page-meta) | fresh (215 d) | search-snippet |
| competitors | S16 | notehive.app | vendor (self-interested) | 2026-04-05 (page-meta) | fresh (226 d) | page |
| local_constraints | S3 | data.worldbank.org | official-statistics | 2024 (api (data year)) | aging (686 d) | api |
| local_constraints | S4 | data.worldbank.org | official-statistics | 2025 (api (data year)) | fresh (321 d) | api |
| channels | S24 | aucegypt.edu | academic | 2015-09-09 (page-meta) | stale (4087 d) | search-snippet |
| channels | S9 | reddit.com | community | undated | undated | search-snippet |

**Warnings**

- ⚠ channels: S24 (aucegypt.edu) is older than 3 years (2015-09-09).

## Source ledger (24 sources, 20 domains)

- `S1` [HN: Ask HN: US-based non-enterprise programming conferences?](https://news.ycombinator.com/item?id=35576335) — hn, demand, community, published 2023-04-15, fetched 2026-11-17T20:51:45+00:00, sha256:8572358a96a982fb
- `S2` [HN: Show HN: Telescope – Find the right people in seconds](https://news.ycombinator.com/item?id=41130993) — hn, demand, community, published 2024-08-01, fetched 2026-11-17T20:51:45+00:00, sha256:5ee882300a987afa
- `S3` [World Bank — Individuals using the Internet (% of population), Egypt, Arab Rep.](https://data.worldbank.org/indicator/IT.NET.USER.ZS?locations=EG) — worldbank, local_constraints, official-statistics, published 2024, fetched 2026-11-17T20:51:45+00:00, sha256:faf656f908089c33
- `S4` [World Bank — GDP per capita (current US$), Egypt, Arab Rep.](https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=EG) — worldbank, local_constraints, official-statistics, published 2025, fetched 2026-11-17T20:51:45+00:00, sha256:a517d2c9627f30b0
- `S5` [(PDF) The Development of Higher Education in Egypt - ResearchGate](https://www.researchgate.net/publication/390306214_The_Development_of_Higher_Education_in_Egypt) — web:yahoo, demand, academic, published 2025-03-30, fetched 2026-11-17T20:51:45+00:00, sha256:cd1c4e97c54087a2
- `S6` [Egyptian Higher Education System: Core Challenges and Reform ...](https://www.ijnrd.org/papers/IJNRD2504556.pdf) — web:yahoo, demand, independent-web, published undated, fetched 2026-11-17T20:51:45+00:00, sha256:2880fe0676c8d59d
- `S7` [The Development of Higher Education in Egypt](https://papers.iafor.org/wp-content/uploads/papers/ece2024/ECE2024_82382.pdf) — web:yahoo, demand, independent-web, published undated, fetched 2026-11-17T20:51:45+00:00, sha256:44d6b5e014aae927
- `S8` [Egypt: Declining Funding Undermines Education | Human Rights ...](https://www.hrw.org/news/2025/01/27/egypt-declining-funding-undermines-education) — web:yahoo, demand, independent-web, published 2025-01-27, fetched 2026-11-17T20:51:45+00:00, sha256:fe28de802eb61dca
- `S9` [Studying in Egypt : r/Egypt - Reddit](https://www.reddit.com/r/Egypt/comments/szb3p4/studying_in_egypt/) — web:yahoo, demand, community, published undated, fetched 2026-11-17T20:51:45+00:00, sha256:e3d79dcffaacba3e
- `S10` [Coming to study in Egypt : r/Egypt - Reddit](https://www.reddit.com/r/Egypt/comments/p13ywx/coming_to_study_in_egypt/) — web:yahoo, demand, community, published undated, fetched 2026-11-17T20:51:45+00:00, sha256:ef1df83334307e48
- `S11` [After university crackdown, Egyptian students fear for their ...](https://www.reuters.com/investigates/special-report/egypt-students/) — web:yahoo, demand, independent-web, published 2016-06-01, fetched 2026-11-17T20:51:45+00:00, sha256:ad8f45486ec78b4c
- `S12` [Egypt steps up pre-university education reform, expands ...](https://mena.org.eg/en/news/egypt-steps-preuniversity-education-reform-8d66b432-4e89-4bf6-89c4-ab0f287930de) — web:yahoo, demand, independent-web, published 2026-11-17, fetched 2026-11-17T20:51:45+00:00, sha256:4c7685f77b7294f3
- `S13` [Best study apps for university students (2026) - memmo.org](https://www.memmo.org/en/magazine/studyapps) — web:yahoo, competitors, vendor (self-interested), published 2026-04-16, fetched 2026-11-17T20:51:45+00:00, sha256:b5616b2950f51516
- `S14` [24 Best Education Apps in Egypt (2026) – Liners](https://liners.com/best/edtech/egypt) — web:yahoo, competitors, vendor (self-interested), published undated, fetched 2026-11-17T20:51:45+00:00, sha256:d182bccbb29ddef4
- `S15` [Best Study Apps in 2026: 24 Tested, Every Price Dated](https://www.mindomax.com/best-study-apps-for-students) — web:yahoo, competitors, independent-web, published 2026-06-07, fetched 2026-11-17T20:51:45+00:00, sha256:e57f0f459e221405
- `S16` [Best Study Apps for College Students in 2026 - notehive.app](https://notehive.app/blog/best-study-apps-for-college-students-2026) — web:yahoo, competitors, vendor (self-interested), published 2026-04-05, fetched 2026-11-17T20:51:45+00:00, sha256:47f28eddf72c31e9
- `S17` [Narrow pricing — TechBloat](https://www.techbloat.com/software/narrow/pricing/) — web:yahoo, pricing, vendor (self-interested), published undated, fetched 2026-11-17T20:51:45+00:00, sha256:996a7f440248ba86
- `S18` [Notion Pricing Plans: Free, Plus, Business, & Enterprise.](https://www.notion.com/pricing) — web:yahoo, pricing, vendor (self-interested), published undated, fetched 2026-11-17T20:51:45+00:00, sha256:0f040a4712c37708
- `S19` [Home - IDEA - An Online Higher Education Alliance](https://www.idea.edu/) — web:yahoo, pricing, academic, published undated, fetched 2026-11-17T20:51:45+00:00, sha256:e3851cc058d06d45
- `S20` [Free JetBrains Student Pack](https://www.jetbrains.com/academy/student-pack/) — web:yahoo, pricing, vendor (self-interested), published undated, fetched 2026-11-17T20:51:45+00:00, sha256:9fc2a07a49edda79
- `S21` [E-Payments in Egypt's Education Sector (2026 Guide) | XPay](https://xpay.app/blog/epayments-education-sector-egypt) — web:yahoo, local_constraints, vendor (self-interested), published 2026-04-16, fetched 2026-11-17T20:51:45+00:00, sha256:3b8cf2b0d3d4fff8
- `S22` [Welcome to Online Payment Tool - aucegypt.edu](https://www3.aucegypt.edu/OnlinePayment/Default.aspx) — web:yahoo, local_constraints, academic, published undated, fetched 2026-11-17T20:51:45+00:00, sha256:b5e6e5e0bec730f2
- `S23` [Steps for E-Payment - The American University in Cairo](https://www.aucegypt.edu/academics/registrar/steps-e-payment) — web:yahoo, local_constraints, academic, published 2016-02-25, fetched 2026-11-17T20:51:45+00:00, sha256:a1c17176e73bc371
- `S24` [Marketing and Social Media Consulting | The American ...](https://www.aucegypt.edu/services/communications/marketing) — web:yahoo, channels, academic, published 2015-09-09, fetched 2026-11-17T20:51:45+00:00, sha256:0c5a133d5d375930
