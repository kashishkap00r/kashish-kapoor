# TODOS

## Illustrated avatar
- **What:** Replace the photo avatar (`public/images/avatar.jpg`) with an illustrated avatar drawn from the original photo (`assets/originals/profile.jpg`).
- **Why:** The interview wish was "Top image I'd ideally want it to be an illustrated avatar of me." The photo went in first (eng review D3) so the homepage did not ship a placeholder.
- **Pros:** Matches the original wish; more distinctive than a photo.
- **Cons:** Needs an illustrator or a working image-generation path (the gstack design binary failed on this machine with "Gemini returned image/jpeg, not a PNG").
- **Context:** The avatar slot on the homepage reads one file. Swap `public/images/avatar.jpg` (600×600, under ~80 KB, no EXIF) and nothing else changes.
- **Depends on:** the redesign merged.

## LinkedIn notes on the site
- **What:** Show selected LinkedIn posts on /work as a "Lately, on LinkedIn" strip.
- **Why:** Most short-form writing lives on LinkedIn ("I would want my LinkedIn writings to also show up here").
- **Pros:** More variety; the site feels current.
- **Cons:** LinkedIn has no public feed for personal posts, so links are hand-pasted.
- **Context:** Follow the videos pattern: a `linkedin` list in `src/data/sources.json`, a small sync step for titles if possible, cards on /work. Keep images self-hosted and run `npm run check`.
- **Depends on:** the redesign merged.
