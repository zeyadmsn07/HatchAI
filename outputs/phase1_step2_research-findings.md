# Phase 1 — Research findings (round 1)

> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v1 (relevance: any idea keyword + category vocabulary)

> **Evidence mode: REPLAY** — sources loaded from snapshot evidence_snapshots/strong_scenario.json (captured 2026-11-17T15:52:54+00:00). Nothing was collected in this run; fetch times and hashes below are the ORIGINAL capture values.
> Synthesis mode: **extractive** (no LLM: claims are verbatim passages from fetched sources).
> Every claim cites a fetched source whose text contains the quoted passage, or is labelled ASSUMPTION.

## Claims

- **demand** — Memdora: Designing Cognitively-Grounded Flashcard ... reports: "This preparation burden is so significant that it deters sustained adoption: a recent study of AI flashcard systems found that students reported spending more energy preparing cards than actually studying them ( 18 ) ." (VERIFIED — [S6](https://arxiv.org/html/2607.25096v1))
- **demand** — Active Recall & Spaced Repetition: Evidence & Effectiveness reports: "Retention Improvement Comparative research from Johns Hopkins University demonstrated that students using AI-optimized spaced repetition retained 92% of material after 6 months, compared to 23% for traditional study methods." (VERIFIED — [S7](https://studycardsai.com/blog/spaced-repetition-science-ai-optimization))
- **competitors** — Best Flashcard Apps for University Students in 2026 ... reports: "Jul 29, 2026 · Compare the best flashcard apps for university students in 2026: Motown AI, Anki, Quizlet, and more. Side-by-side feature comparison for active recall, spaced repetition, and exam prep." (VERIFIED — [S11](https://www.motownai.com/blog/best-flashcard-apps-university-students-2026))
- **competitors** — 7 Best Spaced Repetition Apps in 2026: Hands-On Comparison reports: "Aug 26, 2026 · A hands-on comparison of 7 spaced repetition apps. Laxu AI, Anki, Quizlet, Brainscape, RemNote, StudyFetch, and Knowt on SRS algorithm, free-tier limits, platforms, and price — every figure checked against each vendor's own s" (VERIFIED — [S9](https://laxuai.com/blog/best-spaced-repetition-apps-2026))
- **pricing** — 7 Best Spaced Repetition Apps in 2026: Hands-On Comparison reports: "Laxu AI is the best spaced repetition app for most students in 2026, combining AI-powered flashcard generation from PDFs, images, and audio with a built-in SM-2-adapted scheduling algorithm at $4.99/month or $39.99/year." (VERIFIED — [S9](https://laxuai.com/blog/best-spaced-repetition-apps-2026))
- **pricing** — 5 Best Flashcard Apps for Students in 2026 | Laxu AI reports: "Turbo AI - Another $20/month option Turbo AI is similar to StudyFetch: AI flashcards, quizzes and a lecture notetaker in one app." (VERIFIED — [S15](https://laxuai.com/blog/best-flashcard-apps-for-students-2026))
- **local_constraints** — World Bank — Individuals using the Internet (% of population), Egypt, Arab Rep. reports: "Individuals using the Internet (% of population) for Egypt, Arab Rep. in 2024: 74.6." (VERIFIED — [S3](https://data.worldbank.org/indicator/IT.NET.USER.ZS?locations=EG))
- **local_constraints** — World Bank — GDP per capita (current US$), Egypt, Arab Rep. reports: "GDP per capita (current US$) for Egypt, Arab Rep. in 2025: 3,085.8." (VERIFIED — [S4](https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=EG))
- **channels** — Higher Education Marketing: The Complete 2026 Guide - LeadSquared reports: "Oct 23, 2026 · Whether you work at a 2-year or 4-year institution, focus on traditional or non-traditional students, serve in-house or at an agency specializing in education marketing, or hold a role as a university administrator or enrollm" (VERIFIED — [S19](https://www.leadsquared.com/industries/education/higher-education-marketing-guide/))
- **channels** — Best AI Spaced Repetition Flashcard App | Studyboost reports: "Feb 28, 2026 · It generates flashcards from your own PDFs, slides, docs, YouTube lectures and audio, then schedules every review with FSRS, a modern spaced repetition algorithm. Studyboost Pro costs $10 a month or $90 a year ($7.50 a month)" (VERIFIED — [S13](https://studyboost.org/blog/best-spaced-repetition-app/))

## Opportunity angles

- Narrow the idea to university students in Egypt: An AI-powered flashcard and spaced-repetition study tool for university students in Egypt,
- ASSUMPTION: differentiate from the incumbents in the competitor evidence via Arabic/English localisation for university students
- ASSUMPTION: B2B version — sell to institutions that serve university students

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
| Cited sources | 9 |
| Dated (publication date found) | 100% |
| Fresh (≤ 18 months) | 89% |
| Independent (not a vendor writing about its own market) | 33% |
| Quotes taken from a search snippet rather than the page | 40% |
| Categories backed by independent, non-stale evidence | demand, local_constraints |
| Categories backed only by vendor or stale evidence | channels, competitors, pricing |

| Category | Source | Domain | Who is speaking | Published | Freshness | Quote origin |
|---|---|---|---|---|---|---|
| demand | S6 | arxiv.org | academic | 2026-07-27 (snippet-date) | fresh (113 d) | page |
| demand | S7 | studycardsai.com | vendor (self-interested) | 2026-04-12 (snippet-date) | fresh (219 d) | page |
| competitors | S11 | motownai.com | vendor (self-interested) | 2026-07-29 (snippet-date) | fresh (111 d) | search-snippet |
| competitors | S9 | laxuai.com | vendor (self-interested) | 2026-08-26 (snippet-date) | fresh (83 d) | search-snippet |
| pricing | S9 | laxuai.com | vendor (self-interested) | 2026-08-26 (snippet-date) | fresh (83 d) | page |
| pricing | S15 | laxuai.com | vendor (self-interested) | 2026-10-18 (snippet-date) | fresh (30 d) | page |
| local_constraints | S3 | data.worldbank.org | official-statistics | 2024 (api (data year)) | aging (686 d) | api |
| local_constraints | S4 | data.worldbank.org | official-statistics | 2025 (api (data year)) | fresh (321 d) | api |
| channels | S19 | leadsquared.com | vendor (self-interested) | 2026-10-23 (snippet-date) | fresh (25 d) | search-snippet |
| channels | S13 | studyboost.org | vendor (self-interested) | 2026-02-28 (snippet-date) | fresh (262 d) | search-snippet |

**Warnings**

- ⚠ demand: S7 (studycardsai.com) is a vendor writing about its own market — treat as a claim, not independent evidence.
- ⚠ pricing: S15 (laxuai.com) is a vendor writing about its own market — treat as a claim, not independent evidence.
- ⚠ pricing: S9 (laxuai.com) is a vendor writing about its own market — treat as a claim, not independent evidence.

## Source ledger (19 sources, 15 domains)

- `S1` [HN: Show HN: I Tried Coolify to Self-Host My AI-Powered Anki Flashcard Generator](https://news.ycombinator.com/item?id=40626452) — hn, demand, community, published 2024-06-09, fetched 2026-11-17T15:52:51+00:00, sha256:66e7e5d12dc3caa3
- `S2` [HN: Show HN: Keepmind – AI-powered flashcards and quizzes from your notes](https://news.ycombinator.com/item?id=44491043) — hn, demand, community, published 2025-07-07, fetched 2026-11-17T15:52:51+00:00, sha256:33586c8a190f1e79
- `S3` [World Bank — Individuals using the Internet (% of population), Egypt, Arab Rep.](https://data.worldbank.org/indicator/IT.NET.USER.ZS?locations=EG) — worldbank, local_constraints, official-statistics, published 2024, fetched 2026-11-17T15:52:51+00:00, sha256:faf656f908089c33
- `S4` [World Bank — GDP per capita (current US$), Egypt, Arab Rep.](https://data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=EG) — worldbank, local_constraints, official-statistics, published 2025, fetched 2026-11-17T15:52:51+00:00, sha256:a517d2c9627f30b0
- `S5` [Memdora: Designing Cognitively-Grounded Flashcard ...](https://arxiv.org/pdf/2607.25096) — web:yahoo, demand, academic, published undated, fetched 2026-11-17T15:52:51+00:00, sha256:01f51d3060616694
- `S6` [Memdora: Designing Cognitively-Grounded Flashcard ...](https://arxiv.org/html/2607.25096v1) — web:yahoo, demand, academic, published 2026-07-27, fetched 2026-11-17T15:52:51+00:00, sha256:e4c59da47594adab
- `S7` [Active Recall & Spaced Repetition: Evidence & Effectiveness](https://studycardsai.com/blog/spaced-repetition-science-ai-optimization) — web:yahoo, demand, vendor (self-interested), published 2026-04-12, fetched 2026-11-17T15:52:51+00:00, sha256:b8656f9530e6d883
- `S8` [The Science Behind AI-Generated Flashcards - notiq.study](https://notiq.study/blog/flashcards-spaced-repetition-science) — web:yahoo, demand, vendor (self-interested), published 2026-05-29, fetched 2026-11-17T15:52:51+00:00, sha256:dd37c93efc5283eb
- `S9` [7 Best Spaced Repetition Apps in 2026: Hands-On Comparison](https://laxuai.com/blog/best-spaced-repetition-apps-2026) — web:yahoo, competitors, vendor (self-interested), published 2026-08-26, fetched 2026-11-17T15:52:51+00:00, sha256:04e5d148dd3bc418
- `S10` [Best Spaced Repetition Apps (2026) · Free Anki Alternatives](https://www.mintdeck.app/blog/best-spaced-repetition-apps-2026) — web:yahoo, competitors, vendor (self-interested), published 2026-01-08, fetched 2026-11-17T15:52:51+00:00, sha256:c9529c858fea86b7
- `S11` [Best Flashcard Apps for University Students in 2026 ...](https://www.motownai.com/blog/best-flashcard-apps-university-students-2026) — web:yahoo, competitors, vendor (self-interested), published 2026-07-29, fetched 2026-11-17T15:52:51+00:00, sha256:8bc99d792e24a6fb
- `S12` [Best Spaced Repetition Apps 2026: FSRS vs SM-2 Ranked](https://studyglen.com/guides/best-spaced-repetition-apps) — web:yahoo, competitors, vendor (self-interested), published 2026-11-03, fetched 2026-11-17T15:52:51+00:00, sha256:b69225e6dc48cb53
- `S13` [Best AI Spaced Repetition Flashcard App | Studyboost](https://studyboost.org/blog/best-spaced-repetition-app/) — web:yahoo, pricing, vendor (self-interested), published 2026-02-28, fetched 2026-11-17T15:52:51+00:00, sha256:dd12a712028df757
- `S14` [RemNote Pricing - Free, Pro, and EDU Plans](https://www.remnote.com/pricing) — web:yahoo, pricing, vendor (self-interested), published undated, fetched 2026-11-17T15:52:51+00:00, sha256:cb5735bb9c89e28c
- `S15` [5 Best Flashcard Apps for Students in 2026 | Laxu AI](https://laxuai.com/blog/best-flashcard-apps-for-students-2026) — web:yahoo, pricing, vendor (self-interested), published 2026-10-18, fetched 2026-11-17T15:52:51+00:00, sha256:c1d35cba3ebe4137
- `S16` [Marketing and Social Media Consulting | The American ...](https://www.aucegypt.edu/services/communications/marketing) — web:yahoo, channels, academic, published undated, fetched 2026-11-17T15:52:51+00:00, sha256:44eb9aa5d5e5676a
- `S17` [School of Marketing - FacebookStudent Acquisition Strategy in Egypt - 23HubLabHigher Education Marketing: The Complete 2026 Guide - LeadSquaredDigital marketing](https://www.facebook.com/SchoolOfMarketing.CO/) — web:yahoo, channels, community, published undated, fetched 2026-11-17T15:52:51+00:00, sha256:74ab4789a3bd381c
- `S18` [Student Acquisition Strategy in Egypt - 23HubLab](https://23hublab.com/student-acquisition-strategy-in-egypt/) — web:yahoo, channels, vendor (self-interested), published undated, fetched 2026-11-17T15:52:51+00:00, sha256:5b932d0a8c3c2ff0
- `S19` [Higher Education Marketing: The Complete 2026 Guide - LeadSquared](https://www.leadsquared.com/industries/education/higher-education-marketing-guide/) — web:yahoo, channels, vendor (self-interested), published 2026-10-23, fetched 2026-11-17T15:52:51+00:00, sha256:ae10d0a3d91922e6
