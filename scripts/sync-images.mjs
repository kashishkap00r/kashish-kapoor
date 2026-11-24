// Download the few images the site shows, so pages load them from our own
// domain (no Substack or YouTube requests from visitors' browsers).
//
//   covers  — curated pieces (src/data/curation.json) → public/images/covers/<slug>.jpg
//             fetched from Substack's image CDN at 640px wide, JPEG.
//   videos  — every video in src/data/videos.json  → public/images/videos/<videoId>.jpg
//             YouTube's hqdefault (480x360; pages crop it to 16:9).
//
// Existing files are kept (runs are incremental). A failed download only warns:
// pages check the file exists at build time and fall back to a plain tile.
// No third-party dependencies.

import { readFile, writeFile, mkdir, access } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const UA = 'Mozilla/5.0 (kashishkapoor.com content sync)';

export const coverSlug = (url) => new URL(url).pathname.split('/').filter(Boolean).pop();

// Substack fetch URLs look like .../image/fetch/$s_!x!,f_auto,q_auto:good,.../<encoded original>
// Ask the CDN for a 640px-wide JPEG instead of the 1536px original.
export function sizedCover(src) {
  if (!src) return null;
  if (src.includes('/image/fetch/') && src.includes(',f_auto,')) return src.replace(',f_auto,', ',w_640,c_limit,f_jpg,');
  return src;
}

const exists = (p) => access(p).then(() => true, () => false);

async function download(url, dest) {
  if (await exists(dest)) return 'kept';
  const res = await fetch(url, { headers: { 'user-agent': UA } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const type = res.headers.get('content-type') || '';
  if (!type.startsWith('image/')) throw new Error(`not an image (${type})`);
  await writeFile(dest, Buffer.from(await res.arrayBuffer()));
  return 'saved';
}

async function main() {
  const read = async (p) => JSON.parse(await readFile(join(ROOT, p), 'utf8'));
  const curation = await read('src/data/curation.json');
  const writings = await read('src/data/writings.json');
  const videos = await read('src/data/videos.json');

  const coversDir = join(ROOT, 'public/images/covers');
  const videosDir = join(ROOT, 'public/images/videos');
  await mkdir(coversDir, { recursive: true });
  await mkdir(videosDir, { recursive: true });

  const byUrl = new Map(writings.map((w) => [w.url, w]));
  const picks = [...new Set([...(curation.home || []), ...(curation.bestOf || [])])];
  const jobs = [];
  for (const url of picks) {
    const w = byUrl.get(url);
    if (!w || !w.coverImage) continue; // check-site reports missing picks
    jobs.push([sizedCover(w.coverImage), join(coversDir, `${coverSlug(url)}.jpg`)]);
  }
  const vids = [...(videos.documentaries || []), ...(videos.interviews || []), ...(videos.product || [])];
  if (videos.course) vids.push(videos.course);
  for (const v of vids) {
    if (v.videoId) jobs.push([`https://i.ytimg.com/vi/${v.videoId}/hqdefault.jpg`, join(videosDir, `${v.videoId}.jpg`)]);
  }

  let saved = 0, kept = 0, failed = 0;
  for (const [url, dest] of jobs) {
    try {
      (await download(url, dest)) === 'saved' ? saved++ : kept++;
    } catch (err) {
      failed++;
      console.warn(`! ${url} — ${err.message}`);
    }
  }
  console.log(`Images: ${saved} saved, ${kept} kept, ${failed} failed`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main().catch((err) => {
    console.error('sync-images failed:', err);
    process.exit(1);
  });
}
