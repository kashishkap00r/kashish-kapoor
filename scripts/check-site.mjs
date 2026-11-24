// Post-build checks for dist/. Run with `npm run check` after `npm run build`.
// deploy.yml and sync-content.yml run it before every deploy; any failure
// blocks the deploy. No third-party dependencies.
//
// Guards (from the 2026-11-24 eng review):
//   1. No third-party resource requests (fonts, images, scripts, styles).
//      Plain <a href> links to other sites are fine; they are navigation.
//   2. Every local resource referenced by HTML/CSS exists in dist/.
//   3. All personal posts still build at /writings/<slug>/, RSS lists them,
//      and /writings/ is served only by the 301 in _redirects.
//   4. _redirects carries the expected 301s.
//   5. Curated picks render on / and /work/.
//   6. Pages are never hidden until JavaScript runs.

import { readFile, readdir, access } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(ROOT, 'dist');
const errors = [];
const fail = (msg) => errors.push(msg);
const exists = (p) => access(p).then(() => true, () => false);

async function walk(dir) {
  const out = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...(await walk(p)));
    else out.push(p);
  }
  return out;
}

// Resource references (things the browser fetches without a click).
function resourceRefs(file, text) {
  const refs = [];
  if (file.endsWith('.html')) {
    for (const m of text.matchAll(/<(?:img|script|source|iframe|video|audio)\b[^>]*?\ssrc="([^"]+)"/gi)) refs.push(m[1]);
    for (const m of text.matchAll(/\ssrcset="([^"]+)"/gi)) for (const part of m[1].split(',')) refs.push(part.trim().split(/\s+/)[0]);
    for (const m of text.matchAll(/<link\b([^>]*)>/gi)) {
      const attrs = m[1];
      const rel = (attrs.match(/\srel="([^"]+)"/i) || [])[1] || '';
      const href = (attrs.match(/\shref="([^"]+)"/i) || [])[1];
      if (href && /\b(stylesheet|preload|icon|modulepreload|prefetch|preconnect|dns-prefetch)\b/i.test(rel)) refs.push(href);
    }
    for (const m of text.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)) refs.push(...cssUrls(m[1]));
    for (const m of text.matchAll(/\sstyle="([^"]*)"/gi)) refs.push(...cssUrls(m[1]));
  } else if (file.endsWith('.css')) {
    refs.push(...cssUrls(text));
  }
  return refs;
}

function cssUrls(css) {
  const out = [];
  for (const m of css.matchAll(/url\(\s*(['"]?)([^'")]+)\1\s*\)/gi)) out.push(m[2]);
  for (const m of css.matchAll(/@import\s+(['"])([^'"]+)\1/gi)) out.push(m[2]);
  return out;
}

async function main() {
  if (!(await exists(DIST))) {
    console.error('dist/ not found. Run `npm run build` first.');
    process.exit(1);
  }
  const files = await walk(DIST);
  const texts = new Map();
  for (const f of files.filter((f) => /\.(html|css)$/.test(f))) texts.set(f, await readFile(f, 'utf8'));

  // 1 + 2: third-party and missing local resources.
  for (const [file, text] of texts) {
    const rel = relative(DIST, file);
    for (const ref of resourceRefs(file, text)) {
      if (/^(data:|#|about:|mailto:)/i.test(ref)) continue;
      if (/^(https?:)?\/\//i.test(ref)) {
        fail(`${rel}: third-party resource ${ref}`);
        continue;
      }
      const clean = decodeURIComponent(ref.split(/[?#]/)[0]);
      const target = clean.startsWith('/') ? join(DIST, clean) : join(dirname(file), clean);
      if (!(await exists(target))) fail(`${rel}: missing local resource ${ref}`);
    }
  }

  // 3: personal posts, RSS, /writings/ index gone.
  const mdDir = join(ROOT, 'src/content/writings');
  const mds = [];
  for (const f of (await readdir(mdDir)).filter((f) => f.endsWith('.md'))) {
    const src = await readFile(join(mdDir, f), 'utf8');
    if (!/^draft:\s*true\s*$/m.test(src.split('---')[1] || '')) mds.push(f.replace(/\.md$/, ''));
  }
  for (const slug of mds) {
    if (!(await exists(join(DIST, 'writings', slug, 'index.html')))) fail(`missing post page /writings/${slug}/`);
  }
  if (await exists(join(DIST, 'writings', 'index.html'))) {
    fail('dist/writings/index.html exists; /writings/ must be served only by the 301 in _redirects (remove src/pages/writings/index.astro)');
  }
  const rssPath = join(DIST, 'rss.xml');
  if (await exists(rssPath)) {
    const items = ((await readFile(rssPath, 'utf8')).match(/<item>/g) || []).length;
    if (items !== mds.length) fail(`rss.xml has ${items} items, expected ${mds.length}`);
  } else fail('rss.xml missing');

  // 4: redirects.
  const redirectsPath = join(DIST, '_redirects');
  if (await exists(redirectsPath)) {
    const r = await readFile(redirectsPath, 'utf8');
    for (const [from, to] of [['/projects', '/work/'], ['/writings/', '/work/#personal']]) {
      const ok = r.split('\n').some((l) => { const [a, b, c] = l.trim().split(/\s+/); return a === from && b === to && c === '301'; });
      if (!ok) fail(`_redirects missing "${from} ${to} 301"`);
    }
  } else fail('_redirects missing from dist/');

  // 5: curated picks render.
  const curation = JSON.parse(await readFile(join(ROOT, 'src/data/curation.json'), 'utf8'));
  const home = texts.get(join(DIST, 'index.html')) || '';
  const work = texts.get(join(DIST, 'work', 'index.html')) || '';
  for (const u of curation.home || []) if (!home.includes(`href="${u}"`)) fail(`homepage is missing pick ${u}`);
  for (const u of curation.bestOf || []) if (!work.includes(`href="${u}"`)) fail(`/work is missing best-of pick ${u}`);

  // 6: never hide the page until JS runs.
  for (const [file, text] of texts) {
    if (/body\s*\{[^}]*opacity:\s*0/i.test(text)) fail(`${relative(DIST, file)}: body is hidden with opacity:0`);
  }

  if (errors.length) {
    console.error(`check-site: ${errors.length} problem(s)\n  - ${errors.join('\n  - ')}`);
    process.exit(1);
  }
  console.log(`check-site: OK (${texts.size} HTML/CSS files, ${mds.length} posts, ${(curation.home || []).length + (curation.bestOf || []).length} picks)`);
}

main().catch((err) => {
  console.error('check-site crashed:', err);
  process.exit(1);
});
