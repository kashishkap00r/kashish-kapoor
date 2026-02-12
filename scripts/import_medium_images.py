#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

FEED_URL = "https://medium.com/feed/@kashishkap00r"
SCRIBE_ROOT = "https://scribe.rip"
IMAGE_PLACEHOLDER = "Image unavailable (failed to import during WP migration)"
PLACEHOLDER_BLOCK_RE = re.compile(
    r"(?m)^> \*\*Image unavailable \(failed to import during WP migration\)\*\*[ \t]*(?:\n> [^\n]*)*"
)
POST_ID_RE = re.compile(r"-([0-9a-f]{10,13})(?:[/?#]|$)")
SAFE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}

# Medium slug -> local writings slug overrides.
SLUG_OVERRIDES = {
    "healthwise-notes-4": "healtwise-notes-4",
    "3-hacks-that-will-make-your-writing-stand-out-without-breaking-a-sweat": "3-hacks-to-make-your-writing-better-without-effort",
    "the-skinny-guys-guide-to-unlocking-captain-america-physique": "the-skinny-guys-guide-to-unlocking-captain-america-physique-and-the-tactics-that-delivered-results-for-me",
    "from-stress-to-serenity-what-i-learned-from-the-art-of-living-4-day-course": "lessons-from-art-of-living-happiness-program",
}


@dataclass
class MediumTarget:
    url: str
    post_id: str
    medium_slug: str
    local_slug: str | None


@dataclass
class FeedImage:
    src: str
    caption: str
    alt: str


@dataclass
class Placeholder:
    block: str
    caption: str
    alt: str


def normalize_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokenize(value: str) -> set[str]:
    norm = normalize_text(value)
    if not norm:
        return set()
    return {token for token in norm.split() if len(token) > 1}


def parse_medium_target(url: str, local_slugs: set[str]) -> MediumTarget:
    parsed = urlparse(url.strip())
    path_segment = parsed.path.strip("/").split("/")[-1]

    id_match = POST_ID_RE.search(path_segment)
    if not id_match:
        id_match = POST_ID_RE.search(url)
    if not id_match:
        raise ValueError(f"Could not parse Medium post id from URL: {url}")

    post_id = id_match.group(1)

    medium_slug = path_segment
    if medium_slug.endswith(post_id):
        medium_slug = medium_slug[: -(len(post_id) + 1)]

    local_slug = None
    if medium_slug in local_slugs:
        local_slug = medium_slug
    elif medium_slug in SLUG_OVERRIDES:
        override = SLUG_OVERRIDES[medium_slug]
        if override in local_slugs:
            local_slug = override

    return MediumTarget(url=url.strip(), post_id=post_id, medium_slug=medium_slug, local_slug=local_slug)


def parse_targets(urls: Iterable[str], local_slugs: set[str]) -> list[MediumTarget]:
    targets: list[MediumTarget] = []
    seen_ids: set[str] = set()

    for raw_url in urls:
        url = raw_url.strip()
        if not url:
            continue
        target = parse_medium_target(url, local_slugs)
        if target.post_id in seen_ids:
            continue
        seen_ids.add(target.post_id)
        targets.append(target)

    return targets


def parse_feed_images_by_id(feed_xml: str) -> dict[str, list[FeedImage]]:
    from xml.etree import ElementTree as ET

    root = ET.fromstring(feed_xml)
    by_id: dict[str, list[FeedImage]] = {}

    for item in root.findall("./channel/item"):
        guid = (item.findtext("guid") or "").strip()
        post_id = guid.rsplit("/", 1)[-1]
        if not post_id:
            continue

        content_html = ""
        for child in item:
            if child.tag.endswith("encoded"):
                content_html = child.text or ""
                break

        soup = BeautifulSoup(content_html, "html.parser")
        images: list[FeedImage] = []
        seen_srcs: set[str] = set()

        for figure in soup.find_all("figure"):
            img = figure.find("img")
            if not img:
                continue

            src = (img.get("src") or "").strip()
            if not src or "/_/stat" in src:
                continue
            if src.startswith("//"):
                src = f"https:{src}"

            if src in seen_srcs:
                continue
            seen_srcs.add(src)

            caption_tag = figure.find("figcaption")
            caption = caption_tag.get_text(" ", strip=True) if caption_tag else ""
            alt = (img.get("alt") or "").strip()

            images.append(FeedImage(src=src, caption=caption, alt=alt))

        by_id[post_id] = images

    return by_id


def build_scribe_urls(source_url: str, post_id: str | None = None) -> list[str]:
    clean = source_url.strip()
    clean = re.sub(r"^https?://", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"[?#].*$", "", clean)

    candidates = [
        f"{SCRIBE_ROOT}/http://{clean}",
        f"{SCRIBE_ROOT}/https://{clean}",
    ]
    if post_id:
        candidates.extend(
            [
                f"{SCRIBE_ROOT}/http://medium.com/p/{post_id}",
                f"{SCRIBE_ROOT}/https://medium.com/p/{post_id}",
            ]
        )

    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def parse_article_images_from_html(html_text: str) -> list[FeedImage]:
    soup = BeautifulSoup(html_text, "html.parser")
    images: list[FeedImage] = []
    seen_srcs: set[str] = set()

    # scribe.rip generally preserves Medium's figure structure.
    figure_nodes = soup.select("article figure, main figure, figure")
    if not figure_nodes:
        figure_nodes = soup.select("article img, main img")

    for node in figure_nodes:
        if getattr(node, "name", "") == "img":
            img = node
        else:
            img = node.find("img")
        if not img:
            continue

        src = (img.get("src") or "").strip()
        if not src:
            continue
        if src.startswith("//"):
            src = f"https:{src}"
        if not src.startswith("http"):
            continue
        if "/_/stat" in src:
            continue
        if "cdn-images-1.medium.com/fit/c/150/150/" in src:
            # Medium profile/avatar image.
            continue
        if src in seen_srcs:
            continue
        seen_srcs.add(src)

        caption = ""
        alt = (img.get("alt") or "").strip()
        parent_figure = img.find_parent("figure")
        if parent_figure:
            caption_tag = parent_figure.find("figcaption")
            caption = caption_tag.get_text(" ", strip=True) if caption_tag else ""

        images.append(FeedImage(src=src, caption=caption, alt=alt))

    return images


def fetch_article_images_from_scribe(
    session: requests.Session, source_url: str, post_id: str | None = None
) -> list[FeedImage]:
    last_error: Exception | None = None

    for scribe_url in build_scribe_urls(source_url, post_id=post_id):
        for attempt in range(3):
            try:
                response = session.get(scribe_url, timeout=45)
                if response.status_code >= 500:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                response.raise_for_status()

                images = parse_article_images_from_html(response.text)
                if images:
                    return images
            except Exception as exc:
                last_error = exc
                time.sleep(0.8 * (attempt + 1))
                continue

    if last_error:
        raise last_error
    return []


def extract_placeholders(body: str) -> list[Placeholder]:
    placeholders: list[Placeholder] = []
    for match in PLACEHOLDER_BLOCK_RE.finditer(body):
        block = match.group(0)
        caption = ""
        alt = ""
        for line in block.splitlines():
            clean = line.strip()
            if clean.startswith("> Caption:"):
                caption = clean[len("> Caption:") :].strip()
            elif clean.startswith("> Alt text:"):
                alt = clean[len("> Alt text:") :].strip()
        placeholders.append(Placeholder(block=block, caption=caption, alt=alt))
    return placeholders


def score_image(placeholder: Placeholder, image: FeedImage) -> float:
    score = 0.0

    p_caption = normalize_text(placeholder.caption)
    p_alt = normalize_text(placeholder.alt)
    i_caption = normalize_text(image.caption)
    i_alt = normalize_text(image.alt)

    if p_caption and i_caption and p_caption == i_caption:
        score += 120
    elif p_caption and i_caption and (p_caption in i_caption or i_caption in p_caption):
        score += 80

    if p_alt and i_alt and p_alt == i_alt:
        score += 100
    elif p_alt and i_alt and (p_alt in i_alt or i_alt in p_alt):
        score += 60

    if p_alt and i_caption and p_alt == i_caption:
        score += 50
    if p_caption and i_alt and p_caption == i_alt:
        score += 50

    ptoks = tokenize(f"{placeholder.caption} {placeholder.alt}")
    itoks = tokenize(f"{image.caption} {image.alt}")
    if ptoks and itoks:
        overlap = len(ptoks & itoks)
        union = len(ptoks | itoks)
        if union:
            score += (overlap / union) * 30

    return score


def assign_images(placeholders: list[Placeholder], images: list[FeedImage]) -> list[int | None]:
    assigned: list[int | None] = [None] * len(placeholders)
    used: set[int] = set()

    # First pass: metadata-aware matching.
    for i, placeholder in enumerate(placeholders):
        if not placeholder.caption and not placeholder.alt:
            continue

        best_idx: int | None = None
        best_score = 0.0
        for j, image in enumerate(images):
            if j in used:
                continue
            candidate = score_image(placeholder, image)
            if candidate > best_score:
                best_score = candidate
                best_idx = j

        if best_idx is not None and best_score >= 20:
            assigned[i] = best_idx
            used.add(best_idx)

    # Second pass: fill unmatched placeholders in order.
    for i in range(len(placeholders)):
        if assigned[i] is not None:
            continue
        for j in range(len(images)):
            if j in used:
                continue
            assigned[i] = j
            used.add(j)
            break

    return assigned


def safe_alt(alt: str) -> str:
    cleaned = re.sub(r"\s+", " ", alt).strip()
    if not cleaned:
        return "Embedded image"
    return cleaned.replace("[", "").replace("]", "")


def infer_suffix_from_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in SAFE_IMAGE_SUFFIXES:
        return suffix
    return ".jpg"


def build_download_candidates(src: str) -> list[str]:
    candidates: list[str] = []

    clean_src = src.strip()
    if clean_src.startswith("//"):
        clean_src = f"https:{clean_src}"
    if clean_src:
        candidates.append(clean_src)

    parsed = urlparse(clean_src)
    if parsed.netloc.startswith("cdn-images-") and parsed.path.startswith("/max/"):
        parts = parsed.path.split("/")
        # /max/<size>/<id>
        if len(parts) >= 4 and parts[2].isdigit():
            size = parts[2]
            rest = "/".join(parts[3:])
            miro = f"https://miro.medium.com/v2/resize:fit:{size}/{rest}"
            candidates.insert(0, miro)

    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def fetch_bytes_with_retries(session: requests.Session, url: str, attempts: int = 5) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=45)
            if response.status_code == 429:
                delay = 1.5 * (attempt + 1)
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.content
        except Exception as exc:
            last_error = exc
            # Small backoff between retries for transient network/CDN issues.
            time.sleep(1.2 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to download image: {url}")


def build_markdown_image_block(local_slug: str, filename: str, image: FeedImage) -> str:
    alt = safe_alt(image.alt or image.caption)
    rel_path = f"/images/writings/{local_slug}/{filename}"

    lines = [f"![{alt}]({rel_path})"]
    caption = image.caption.strip()
    if caption and normalize_text(caption) != normalize_text(alt):
        lines.extend(["", f"*{caption}*"])

    return "\n".join(lines)


def ensure_image_file(session: requests.Session, target_dir: Path, filename: str, src: str, dry_run: bool) -> Path:
    path = target_dir / filename
    if path.exists() or dry_run:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for candidate in build_download_candidates(src):
        try:
            payload = fetch_bytes_with_retries(session, candidate)
            path.write_bytes(payload)
            return path
        except Exception as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    return path


def replace_placeholder_blocks(body: str, replacements: list[str | None]) -> str:
    matches = list(PLACEHOLDER_BLOCK_RE.finditer(body))
    if not matches:
        return body

    chunks: list[str] = []
    cursor = 0

    for idx, match in enumerate(matches):
        chunks.append(body[cursor : match.start()])
        replacement = replacements[idx] if idx < len(replacements) else None
        if replacement:
            chunks.append(f"\n{replacement}\n")
        else:
            chunks.append(match.group(0))
        cursor = match.end()

    chunks.append(body[cursor:])
    return "".join(chunks)


def cleanup_orphan_placeholder_metadata(body: str) -> str:
    """
    Remove legacy placeholder metadata lines that can remain after replacement.
    """
    return re.sub(
        r"(?m)(!\[[^\n]*\]\(/images/writings/[^\n]+\)\n(?:\n\*[^\n]+\*\n)?)(> Caption:[^\n]*\n(?:> Alt text:[^\n]*\n)?)",
        r"\1",
        body,
    )


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[: end + 5], text[end + 5 :]


def collect_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = []
    if args.urls_file:
        for line in Path(args.urls_file).read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.strip().startswith("#"):
                urls.append(line.strip())
    urls.extend(args.url or [])
    return urls


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Medium-hosted images into writings markdown placeholders")
    parser.add_argument("--content-dir", default="content/writings", help="Path to writings directory")
    parser.add_argument("--static-dir", default="static", help="Path to static directory")
    parser.add_argument("--urls-file", help="File with one Medium URL per line")
    parser.add_argument("--url", action="append", help="Medium article URL (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, do not write files or download images")
    args = parser.parse_args()

    urls = collect_urls(args)
    if not urls:
        raise SystemExit("No Medium URLs provided. Use --url and/or --urls-file.")

    content_dir = Path(args.content_dir)
    static_dir = Path(args.static_dir)
    if not content_dir.exists():
        raise SystemExit(f"Content directory not found: {content_dir}")

    local_slugs = {p.stem for p in content_dir.glob("*.md") if p.name != "_index.md"}
    targets = parse_targets(urls, local_slugs)

    response = requests.get(FEED_URL, timeout=45)
    response.raise_for_status()
    feed_images_by_id = parse_feed_images_by_id(response.text)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        }
    )

    processed = 0
    changed = 0
    placeholder_replaced = 0
    downloaded = 0
    missing_local_slug = 0
    missing_image_source = 0
    unresolved_placeholders = 0
    scribe_used = 0

    for target in targets:
        if not target.local_slug:
            missing_local_slug += 1
            print(f"skip(no-local-slug): {target.url}")
            continue

        feed_images = feed_images_by_id.get(target.post_id)
        if not feed_images:
            try:
                feed_images = fetch_article_images_from_scribe(session, target.url, post_id=target.post_id)
            except Exception as exc:
                missing_image_source += 1
                print(f"skip(no-image-source): {target.local_slug} ({target.post_id}) ({exc})")
                continue
            if not feed_images:
                missing_image_source += 1
                print(f"skip(no-image-source): {target.local_slug} ({target.post_id})")
                continue
            scribe_used += 1

        file_path = content_dir / f"{target.local_slug}.md"
        if not file_path.exists():
            missing_local_slug += 1
            print(f"skip(missing-file): {file_path}")
            continue

        original = file_path.read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(original)
        placeholders = extract_placeholders(body)
        if not placeholders:
            cleaned_body = cleanup_orphan_placeholder_metadata(body)
            cleaned_text = f"{frontmatter}{cleaned_body}" if frontmatter else cleaned_body
            if cleaned_text != original:
                changed += 1
                if not args.dry_run:
                    file_path.write_text(cleaned_text, encoding="utf-8")
                print(f"updated(cleanup-only): {target.local_slug}")
            else:
                print(f"ok(no-placeholders): {target.local_slug}")
            processed += 1
            continue

        assignments = assign_images(placeholders, feed_images)

        replacements: list[str | None] = [None] * len(placeholders)
        post_image_dir = static_dir / "images" / "writings" / target.local_slug

        for idx, image_index in enumerate(assignments):
            if image_index is None:
                unresolved_placeholders += 1
                continue

            image = feed_images[image_index]
            suffix = infer_suffix_from_url(image.src)
            filename = f"medium-{idx + 1:02d}{suffix}"
            image_path_on_disk = post_image_dir / filename
            existed_before = image_path_on_disk.exists()

            try:
                image_path = ensure_image_file(
                    session=session,
                    target_dir=post_image_dir,
                    filename=filename,
                    src=image.src,
                    dry_run=args.dry_run,
                )
                if (
                    not args.dry_run
                    and not existed_before
                    and image_path.exists()
                    and image_path.stat().st_size > 0
                ):
                    downloaded += 1
            except Exception as exc:
                unresolved_placeholders += 1
                print(f"warn(download-failed): {target.local_slug} {filename} <- {image.src} ({exc})")
                continue

            replacements[idx] = build_markdown_image_block(target.local_slug, filename, image)

        new_body = replace_placeholder_blocks(body, replacements)
        new_body = cleanup_orphan_placeholder_metadata(new_body)
        new_text = f"{frontmatter}{new_body}" if frontmatter else new_body

        did_change = new_text != original
        processed += 1

        replaced_here = sum(1 for r in replacements if r)
        placeholder_replaced += replaced_here

        if did_change:
            changed += 1
            if not args.dry_run:
                file_path.write_text(new_text, encoding="utf-8")
            print(
                f"updated: {target.local_slug} | placeholders={len(placeholders)} | replaced={replaced_here} | feed-images={len(feed_images)}"
            )
        else:
            print(f"ok(no-change): {target.local_slug} | placeholders={len(placeholders)}")

    print("\nSummary")
    print(f"- targets: {len(targets)}")
    print(f"- processed: {processed}")
    print(f"- changed-files: {changed}")
    print(f"- placeholders-replaced: {placeholder_replaced}")
    print(f"- images-downloaded: {downloaded if not args.dry_run else 0}")
    print(f"- skipped-no-local-slug: {missing_local_slug}")
    print(f"- skipped-no-image-source: {missing_image_source}")
    print(f"- scribe-fallback-used: {scribe_used}")
    print(f"- unresolved-placeholders: {unresolved_placeholders}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
