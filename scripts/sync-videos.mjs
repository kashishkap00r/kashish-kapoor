// Sync video metadata for the /work page.
//
// Reads grouped YouTube links from src/data/sources.json → videos:
//   { documentaries: [url], interviews: [url],
//     course: { playlist: url, firstVideo: url } }
// and resolves titles via YouTube's public oEmbed endpoint into
// src/data/videos.json with the same groups.
//
// Titles are cleaned to the part before the first " | " so channel names
// ("Subtext by Zerodha", "Markets by Zerodha"…) never show on the site.
// Thumbnails are NOT linked from YouTube: scripts/sync-images.mjs downloads
// them to public/images/videos/<videoId>.jpg and the page checks they exist.
//
// Reuses the previous videos.json so only NEW urls hit oEmbed. On failure it
// keeps the prior entry, or writes a stub titled "(title unavailable)".
// No third-party dependencies.

import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCES = join(ROOT, 'src/data/sources.json');
const OUT = join(ROOT, 'src/data/videos.json');

const UA = 'Mozilla/5.0 (kashishkapoor.com content sync)';
const GROUPS = ['documentaries', 'interviews'];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function parseVideoId(url) {
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

export const cleanTitle = (t) => (t || '').split(' | ')[0].replace(/\s+/g, ' ').trim();

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

// One resolved entry per url, reusing prior titles where we have them.
async function resolve(url, prevByUrl) {
  const videoId = parseVideoId(url);
  const existing = prevByUrl.get(url);
  if (existing && existing.title && existing.title !== '(title unavailable)') return existing;
  try {
    const j = await fetchOEmbed(url);
    console.log(`✓ ${cleanTitle(j.title)}`);
    await sleep(250);
    return { url, videoId, title: cleanTitle(j.title), fetchedAt: new Date().toISOString() };
  } catch (err) {
    console.warn(`! ${url} — ${err.message}; using fallback`);
    return existing ?? { url, videoId, title: '(title unavailable)', fetchedAt: new Date().toISOString() };
  }
}

async function main() {
  const sources = await readJson(SOURCES, { videos: {} });
  const v = sources.videos && !Array.isArray(sources.videos) ? sources.videos : {};
  const prev = await readJson(OUT, {});
  const prevEntries = [
    ...GROUPS.flatMap((g) => (Array.isArray(prev[g]) ? prev[g] : [])),
    ...(prev.course ? [prev.course] : []),
  ];
  const prevByUrl = new Map(prevEntries.map((e) => [e.url, e]));

  const out = {};
  for (const g of GROUPS) {
    out[g] = [];
    for (const url of Array.isArray(v[g]) ? v[g] : []) out[g].push(await resolve(url, prevByUrl));
  }

  // Course: a playlist. Title comes from the playlist; the thumbnail from its first video.
  out.course = null;
  if (v.course && v.course.playlist) {
    const entry = await resolve(v.course.playlist, prevByUrl);
    out.course = { ...entry, videoId: parseVideoId(v.course.firstVideo || '') };
  }

  await writeFile(OUT, JSON.stringify(out, null, 2) + '\n');
  const n = GROUPS.reduce((s, g) => s + out[g].length, 0) + (out.course ? 1 : 0);
  console.log(`Wrote ${n} video entr${n === 1 ? 'y' : 'ies'} → src/data/videos.json`);
}

// Only run when executed directly (lets check-site import the helpers).
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main().catch((err) => {
    console.error('sync-videos failed:', err);
    process.exit(1);
  });
}
