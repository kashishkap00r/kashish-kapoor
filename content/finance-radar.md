+++
title = "FinanceRadar"
description = "A lightweight tool I built to clean news noise and speed up financial research."
+++

[FinanceRadar](http://financeradar.kashishkapoor.com) is a small internal tool I built for myself.

I wanted a way to track financial and business news for my job @ Zerodha without:
- doomscrolling
- duplicate headlines
- low-signal content

So I vibe-coded a system that pulls from 50+ credible sources, cleans the feed, and throws out what should actually matter.

---

## What it does (today)

FinanceRadar is **V1**.

Right now, it:
- aggregates news from curated, high-quality sources
- removes repetition and obvious noise (read: stock price movement)
- presents everything in a clean, fast, scrollable view

It’s not a product.  
It’s a **workflow tool** — built to make idea generation for my writings (slightly) faster and (a lot) calmer.

---

## What’s coming next

In **V2**, I plan to layer in AI-driven filtering and prioritisation.

The idea is not “AI summaries for everything”, but:
- better clustering of similar stories
- more contextual ranking
- clearer signals on *what’s actually worth deeper work*

Still early, still experimental — but directionally focused on improving signal, not volume.

---

## How it’s built (lightly)

FinanceRadar is built on top of:
- **[Miniflux](https://miniflux.app/)**, an open-source RSS reader
- hosted on a **VPS via [DigitalOcean](https://cloud.digitalocean.com/)**
- with custom logic on top to clean, filter, and present the feed

Nothing fancy. Just open-source tools stitched together to solve a very real personal problem.

---

## Try it

You can explore the live dashboard here:

[Open FinanceRadar →](https://financeradar.kashishkapoor.com)

---

*This is an evolving tool. I keep it deliberately simple.*
