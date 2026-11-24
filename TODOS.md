# TODOS

## LinkedIn notes on the site
- **What:** Show selected LinkedIn posts on /work as a "Lately, on LinkedIn" strip.
- **Why:** Most short-form writing lives on LinkedIn ("I would want my LinkedIn writings to also show up here").
- **Pros:** More variety; the site feels current.
- **Cons:** LinkedIn has no public feed for personal posts, so links are hand-pasted.
- **Context:** Follow the videos pattern: a `linkedin` list in `src/data/sources.json`, a small sync step for titles if possible, cards on /work. Keep images self-hosted and run `npm run check`.
- **Depends on:** the redesign merged.
