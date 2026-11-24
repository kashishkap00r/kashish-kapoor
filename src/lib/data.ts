// Build-time data for the homepage and /work.
// One place that reads the JSON files, validates hand-edited picks, derives
// counts and resolves local image paths (images are self-hosted; see
// scripts/sync-images.mjs).

import { existsSync } from 'node:fs';
import { join } from 'node:path';
import writings from '../data/writings.json';
import curation from '../data/curation.json';
import videos from '../data/videos.json';

export interface Piece {
  title: string;
  subtitle?: string;
  date: string;
  url: string;
  coverImage?: string | null;
}

export interface Video {
  url: string;
  videoId: string | null;
  title: string;
}

const PUBLIC = join(process.cwd(), 'public');
const localImage = (rel: string) => (existsSync(join(PUBLIC, rel)) ? `/${rel}` : null);

const pieces = (writings as Piece[]).slice().sort((a, b) => b.date.localeCompare(a.date));
const byUrl = new Map(pieces.map((p) => [p.url, p]));

/** Curated picks, in the order listed in curation.json. Missing URLs fail the build. */
function picks(list: string[], name: string): Piece[] {
  const missing = list.filter((u) => !byUrl.has(u));
  if (missing.length) {
    throw new Error(`curation.json "${name}" lists URLs not in writings.json:\n  ${missing.join('\n  ')}`);
  }
  return list.map((u) => byUrl.get(u)!);
}

export const coverSlug = (url: string) => new URL(url).pathname.split('/').filter(Boolean).pop()!;
export const coverFor = (p: Piece) => localImage(`images/covers/${coverSlug(p.url)}.jpg`);
export const thumbFor = (v: Pick<Video, 'videoId'>) => (v.videoId ? localImage(`images/videos/${v.videoId}.jpg`) : null);

export const homePicks = picks(curation.home, 'home');
export const bestOf = picks(curation.bestOf, 'bestOf');
export const allPieces = pieces;

/** Pieces grouped by year, newest year first. */
export const piecesByYear: [string, Piece[]][] = Object.entries(
  pieces.reduce<Record<string, Piece[]>>((acc, p) => {
    (acc[p.date.slice(0, 4)] ||= []).push(p);
    return acc;
  }, {})
).sort((a, b) => b[0].localeCompare(a[0]));

const v = videos as {
  documentaries?: Video[];
  interviews?: Video[];
  course?: Video | null;
};
export const docs = v.documentaries ?? [];
export const interviews = v.interviews ?? [];
export const course = v.course ?? null;
export const videoCount = docs.length + interviews.length + (course ? 1 : 0);

export const firstYear = pieces.length ? pieces[pieces.length - 1].date.slice(0, 4) : '';
export const sinceLabel = pieces.length
  ? new Date(pieces[pieces.length - 1].date).toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' }).toUpperCase()
  : '';

export const fmtDay = (iso: string) => new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
export const fmtMonthYear = (iso: string) => new Date(iso).toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
