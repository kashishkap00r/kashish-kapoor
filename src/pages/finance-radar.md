---
layout: ../layouts/LongForm.astro
title: "FinanceRadar"
description: "FinanceRadar is a free news dashboard Kashish Kapoor built to cut the noise in Indian markets, policy and business news: hourly feeds, an AI shortlist twice a day."
kicker: "Built · FinanceRadar"
heading: "FinanceRadar."
headingEm: "A bullshit detector for financial news."
lead: "A small hobby project I built for myself, so I spend less time collecting news and more time understanding it. It's free, it's live, and I open it every morning."
heroImage:
  src: "/images/financeradar.jpg"
  srcset: "/images/financeradar.jpg 1x, /images/financeradar@2x.jpg 2x"
  alt: "FinanceRadar homepage"
  href: "https://financeradar.news"
notes:
  - label: "Live at"
    text: "financeradar.news →"
    href: "https://financeradar.news"
  - label: "Feeds refresh"
    text: "Every hour"
  - label: "AI shortlist"
    text: "Twice a day"
  - label: "Reads"
    text: "News, reports, Telegram, YouTube, X"
  - label: "Runs on"
    text: "A static site and scheduled jobs. Low maintenance by design."
---

[FinanceRadar](https://financeradar.news) is a small hobby project I built for myself.

There is no grand end goal here.
I just had a practical problem: I was wasting too much time jumping across sources, seeing the same story repeated, and still missing what actually mattered.

So I built a setup that gives me a cleaner research feed.

---

## The problem I was trying to solve

When you track business and market news seriously, the bottleneck is rarely access.
It is signal.

Too much noise, too many repeats, too many low-value updates, and too much context-switching.

I wanted one place that helps me:
- scan faster
- avoid duplicate headlines
- spend more time on analysis than collection

---

## What FinanceRadar does now

Today, it is a lightweight workflow tool that:

- pulls from a broad set of finance/business sources on an hourly cycle
- filters obvious low-signal items and removes duplicates
- groups things in a way that makes scanning easier
- adds an AI-ranked shortlist of stories worth paying attention to, twice a day
- pulls public brokerage-report updates from selected Telegram channels

It is still intentionally simple.
No dashboards for the sake of dashboards. Just a cleaner pipeline.

---

## How I use it

My flow is straightforward:

1. Open FinanceRadar and do a quick top-level scan
2. Check the AI shortlist for prioritization
3. Open only the stories that look worth deeper reading
4. Save items I want to come back to while writing

That is it.
The tool exists to reduce friction in this loop.

---

## Current setup (behind the scenes)

The project runs as a static site with automated refresh jobs:
- feed aggregation refreshes hourly
- AI ranking runs twice a day
- output is published to `financeradar.news`

So maintenance stays low, and the workflow stays reliable.

If you are curious, you can check it here:

[Open FinanceRadar →](https://financeradar.news)
