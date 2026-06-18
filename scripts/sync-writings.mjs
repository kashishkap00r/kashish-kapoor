// Sync the owner's published writing for the /work page.
//
// The Daily Brief and The Chatter (Substack) publish everything under a single
// "Zerodha" byline, so there is no author field to filter on. Instead, editions
// credit authors in the body footer, e.g. "...written by Manie and Kashish."
// This script paginates each publication's archive, fetches each edition's full
// body, and detects the owner's first name near a "written by" phrase.
//
// It is INCREMENTAL: a committed cache (writings-cache.json) holds a per-pub
// high-water mark (latest post_date scanned) plus a per-post verdict keyed by
// canonical_url. Each run only fetches editions newer than the high-water mark.
//
// Manual overrides in sources.json (manualInclude / exclude) are the source of
// truth for completeness — the scan is best-effort.
//
// Fetched body HTML is ONLY regex-scanned here; it is never written to the page
// (the page renders title/subtitle/date/url/cover only). No injection surface,
// no third-party dependencies.

import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCES = join(ROOT, 'src/data/sources.json');
const CACHE = join(ROOT, 'src/data/writings-cache.json');
const OUT = join(ROOT, 'src/data/writings.json');

const UA = 'Mozilla/5.0 (kashishkapoor.com content sync)';
const PAGE = 25;          // archive page size
const SAFETY_MAX = 2000;  // pagination guard (offset ceiling)
const REQ_DELAY = 150;    // ms between per-post fetches (politeness)
const MAX_POSTS = Number(process.env.SYNC_MAX_POSTS || 0); // 0 = unlimited; cap for testing

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const stripTags = (html) => (html || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');

async function readJson(path, fallback) {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch {
    return fallback;
  }
}

async function fetchJson(url, { retries = 3 } = {}) {
  let lastErr;
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url, { headers: { 'user-agent': UA } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      lastErr = err;
      await sleep(400 * (i + 1));
    }
  }
  throw lastErr;
}

const slugFromUrl = (url) => {
  const m = String(url).match(/\/p\/([^/?#]+)/);
  return m ? m[1] : null;
};

// Owner-name detection. Anchored ("written by ... Kashish") = high confidence.
function classify(bodyHtml, firstName) {
  const text = stripTags(bodyHtml);
  const writtenBy = new RegExp(`written by[^.]{0,160}\\b${firstName}\\b`, 'i');
  const nameOnly = new RegExp(`\\b${firstName}\\b`, 'i');
  if (writtenBy.test(text)) return 'written-by';
  if (nameOnly.test(text)) return 'name-only';
  return 'none';
}

async function scanPublication(pub, cache, firstName, budget) {
  const pubCache = cache[pub.name] || { lastScannedDate: null, posts: {} };
  const highWater = pubCache.lastScannedDate;
  let newHighWater = highWater;
  let scanned = 0;
  let reused = 0;
  let offset = 0;
  // `completed` stays true only if we walk the archive all the way down to the
  // previous high-water (or the end). If we bail early (cap / fetch error) there
  // is a gap, so we must NOT advance the high-water — the next run resumes.
  let completed = true;

  outer: while (offset < SAFETY_MAX) {
    let page;
    try {
      page = await fetchJson(`${pub.base}/api/v1/archive?sort=new&limit=${PAGE}&offset=${offset}`);
    } catch (err) {
      console.warn(`! ${pub.name}: archive fetch failed at offset ${offset} (${err.message}) — keeping cache`);
      completed = false;
      break;
    }
    if (!Array.isArray(page) || page.length === 0) break;

    for (const post of page) {
      if (highWater && post.post_date <= highWater) break outer; // reached known territory
      if (!newHighWater || post.post_date > newHighWater) newHighWater = post.post_date;

      // Reuse a prior verdict if we already scanned this edition — makes re-runs
      // and resumed-after-interruption runs cheap (no re-fetch of the body).
      const cached = pubCache.posts[post.canonical_url];
      if (cached && cached.matchKind) {
        reused++;
        continue;
      }

      const slug = post.slug || slugFromUrl(post.canonical_url);
      let matchKind = 'none';
      try {
        const full = await fetchJson(`${pub.base}/api/v1/posts/${slug}`);
        matchKind = classify(full.body_html, firstName);
      } catch (err) {
        console.warn(`  ? ${pub.name}/${slug}: body fetch failed (${err.message})`);
      }

      pubCache.posts[post.canonical_url] = {
        title: post.title,
        subtitle: post.subtitle || '',
        post_date: post.post_date,
        cover_image: post.cover_image || null,
        canonical_url: post.canonical_url,
        matched: matchKind === 'written-by',
        matchKind,
        scannedAt: new Date().toISOString(),
      };
      if (matchKind === 'written-by') console.log(`  ✓ ${pub.name}: ${post.title}`);

      scanned++;
      budget.count++;
      await sleep(REQ_DELAY);
      if (MAX_POSTS && budget.count >= MAX_POSTS) {
        console.warn(`  (hit SYNC_MAX_POSTS=${MAX_POSTS}, stopping early — high-water not advanced)`);
        completed = false;
        break outer;
      }
    }

    // Advance by the actual page size — Substack's first page can be short
    // (pinned-post dedup), so never treat a short page as the end; only an
    // empty page (checked at the top of the loop) ends pagination.
    offset += page.length;
  }

  // Only advance the high-water mark when the scan completed without a gap.
  if (completed) pubCache.lastScannedDate = newHighWater;
  cache[pub.name] = pubCache;
  console.log(
    `${pub.name}: scanned ${scanned} new, reused ${reused}; ` +
    `high-water = ${pubCache.lastScannedDate}${completed ? '' : ' (unchanged — run incomplete)'}`
  );
}

// Fetch metadata for a manually-included URL (when the scan missed it).
async function fetchMeta(url, pubName) {
  const slug = slugFromUrl(url);
  const base = new URL(url).origin;
  const full = await fetchJson(`${base}/api/v1/posts/${slug}`);
  return {
    title: full.title,
    subtitle: full.subtitle || '',
    date: full.post_date,
    url: full.canonical_url || url,
    coverImage: full.cover_image || null,
    publication: pubName,
    source: 'manual',
  };
}

async function main() {
  const sources = await readJson(SOURCES, {});
  const cfg = sources.writings || {};
  const firstName = cfg.ownerFirstName || 'Kashish';
  const publications = cfg.publications || [];
  const manualInclude = cfg.manualInclude || [];
  const exclude = new Set(cfg.exclude || []);

  const cache = await readJson(CACHE, {});
  const budget = { count: 0 };

  for (const pub of publications) {
    await scanPublication(pub, cache, firstName, budget);
  }

  // Build the published list from cached "written-by" hits (minus excludes).
  const pubByBase = publications.map((p) => ({ ...p, origin: new URL(p.base).origin }));
  const results = [];
  const seen = new Set();
  for (const [pubName, pubCache] of Object.entries(cache)) {
    for (const post of Object.values(pubCache.posts || {})) {
      if (!post.matched) continue;
      if (exclude.has(post.canonical_url)) continue;
      results.push({
        title: post.title,
        subtitle: post.subtitle || '',
        date: post.post_date,
        url: post.canonical_url,
        coverImage: post.cover_image || null,
        publication: pubName,
        source: 'scan',
      });
      seen.add(post.canonical_url);
    }
  }

  // Manual includes the scan missed.
  for (const url of manualInclude) {
    if (exclude.has(url) || seen.has(url)) continue;
    const match = pubByBase.find((p) => url.startsWith(p.origin));
    try {
      const meta = await fetchMeta(url, match ? match.name : '');
      results.push(meta);
      seen.add(meta.url);
      console.log(`  + manual: ${meta.title}`);
    } catch (err) {
      console.warn(`! manualInclude ${url} — ${err.message}`);
    }
  }

  results.sort((a, b) => new Date(b.date).valueOf() - new Date(a.date).valueOf());

  await writeFile(OUT, JSON.stringify(results, null, 2) + '\n');
  await writeFile(CACHE, JSON.stringify(cache, null, 2) + '\n');
  console.log(`Wrote ${results.length} writing(s) → src/data/writings.json`);
}

main().catch((err) => {
  console.error('sync-writings failed:', err);
  process.exit(1);
});
