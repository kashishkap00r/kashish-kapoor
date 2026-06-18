// Sync video metadata for the /work page.
//
// Reads the curated list of YouTube URLs from src/data/sources.json and
// resolves each into { url, videoId, title, thumbnail, author } using YouTube's
// public oEmbed endpoint. Titles/thumbnails are fetched automatically so the
// owner only ever maintains a list of links.
//
// Reuses the previous videos.json so only NEW urls hit oEmbed (rate-limit
// friendly). On failure it keeps the prior entry, or falls back to a stub with
// a thumbnail derived from the video id. No third-party dependencies.

import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCES = join(ROOT, 'src/data/sources.json');
const OUT = join(ROOT, 'src/data/videos.json');

const UA = 'Mozilla/5.0 (kashishkapoor.com content sync)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseVideoId(url) {
  try {
    const u = new URL(url);
    if (u.hostname === 'youtu.be') return u.pathname.slice(1).split('/')[0] || null;
    if (u.searchParams.get('v')) return u.searchParams.get('v');
    const parts = u.pathname.split('/').filter(Boolean); // /shorts/<id>, /embed/<id>, /live/<id>
    const i = parts.findIndex((p) => ['shorts', 'embed', 'live', 'v'].includes(p));
    if (i >= 0 && parts[i + 1]) return parts[i + 1];
    return null;
  } catch {
    return null;
  }
}

const thumbFor = (id) => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;

async function fetchOEmbed(url) {
  const endpoint = `https://www.youtube.com/oembed?url=${encodeURIComponent(url)}&format=json`;
  const res = await fetch(endpoint, { headers: { 'user-agent': UA } });
  if (!res.ok) throw new Error(`oEmbed ${res.status}`);
  return res.json();
}

async function readJson(path, fallback) {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch {
    return fallback;
  }
}

async function main() {
  const sources = await readJson(SOURCES, { videos: [] });
  const urls = Array.isArray(sources.videos) ? sources.videos : [];
  const prev = await readJson(OUT, []);
  const prevByUrl = new Map(prev.map((v) => [v.url, v]));

  const out = [];
  for (const url of urls) {
    const videoId = parseVideoId(url);
    // Reuse prior metadata if we already resolved a title (fewer oEmbed calls).
    const existing = prevByUrl.get(url);
    if (existing && existing.title && existing.title !== '(title unavailable)') {
      out.push(existing);
      continue;
    }
    try {
      const j = await fetchOEmbed(url);
      out.push({
        url,
        videoId,
        title: j.title,
        thumbnail: videoId ? thumbFor(videoId) : j.thumbnail_url,
        author: j.author_name ?? null,
        fetchedAt: new Date().toISOString(),
      });
      console.log(`✓ ${j.title}`);
    } catch (err) {
      console.warn(`! ${url} — ${err.message}; using fallback`);
      out.push(
        existing ?? {
          url,
          videoId,
          title: '(title unavailable)',
          thumbnail: videoId ? thumbFor(videoId) : null,
          author: null,
          fetchedAt: new Date().toISOString(),
        }
      );
    }
    await sleep(250);
  }

  await writeFile(OUT, JSON.stringify(out, null, 2) + '\n');
  console.log(`Wrote ${out.length} video(s) → src/data/videos.json`);
}

main().catch((err) => {
  console.error('sync-videos failed:', err);
  process.exit(1);
});
