#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


BLOG_HOSTS = {"kashishkapoor.com", "www.kashishkapoor.com"}
WP_UPLOAD_PREFIX = "https://kashishkapoor.com/wp-content/uploads/"
WP_IMPORT_FALLBACK_TEXT = "Image unavailable (failed to import during WP migration)"


@dataclass
class FileStats:
    path: Path
    changed: bool
    removed_wp_comments: int
    fixed_double_quotes: int
    rewritten_blog_links: int
    replaced_missing_images: int
    filled_alt_texts: int


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[: end + 5], text[end + 5 :]


def extract_slug(frontmatter: str, fallback: str) -> str:
    match = re.search(r"^slug:\s*\"?([^\"\n]+)\"?\s*$", frontmatter, flags=re.MULTILINE)
    return match.group(1).strip() if match else fallback


def strip_tags(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", "", value)
    no_entities = html.unescape(no_tags)
    return re.sub(r"\s+", " ", no_entities).strip()


def normalize_blank_lines(value: str) -> str:
    lines = [line.rstrip() for line in value.splitlines()]
    cleaned = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip() + "\n"


def rewrite_blog_url(url: str, valid_slugs: set[str]) -> str:
    parsed = urlparse(url)

    if parsed.scheme and parsed.netloc:
        if parsed.netloc.lower() not in BLOG_HOSTS or not parsed.path.startswith("/blog"):
            return url
        path = parsed.path
        fragment = parsed.fragment
    elif url.startswith("/blog"):
        path = url.split("#", 1)[0]
        fragment = url.split("#", 1)[1] if "#" in url else ""
    else:
        return url

    if path in {"/blog", "/blog/"}:
        new_path = "/writings/"
    else:
        tail = path[len("/blog/") :] if path.startswith("/blog/") else ""
        first_segment = tail.split("/", 1)[0].strip()
        first_segment = first_segment.removesuffix(".html")

        if first_segment and first_segment in valid_slugs:
            new_path = f"/writings/{first_segment}/"
        else:
            new_path = "/writings/"

    if fragment:
        return f"{new_path}#{fragment}"
    return new_path


def process_figure_block(block: str) -> tuple[str, int, int]:
    # returns (new_block, replaced_missing_images, filled_alt_texts)
    if "<img" not in block:
        return block, 0, 0

    src_match = re.search(r'<img[^>]*\bsrc="([^"]+)"', block)
    if not src_match:
        return block, 0, 0

    src = src_match.group(1)
    alt_match = re.search(r'<img[^>]*\balt="([^"]*)"', block)
    alt_text = alt_match.group(1).strip() if alt_match else ""
    if alt_text.lower().startswith("class="):
        alt_text = ""

    caption_match = re.search(r"<figcaption[^>]*>([\s\S]*?)</figcaption>", block)
    caption_text = strip_tags(caption_match.group(1)) if caption_match else ""

    if src.startswith(WP_UPLOAD_PREFIX):
        details = []
        if caption_text:
            details.append(f"> Caption: {caption_text}  ")
        if alt_text and alt_text != caption_text:
            details.append(f"> Alt text: {alt_text}  ")
        details.append(f"> Original URL: [{src}]({src})")
        fallback = "\n".join([f"> **{WP_IMPORT_FALLBACK_TEXT}**  "] + details)
        return f"\n{fallback}\n", 1, 0

    if alt_text:
        return block, 0, 0

    if caption_text:
        safe_alt = caption_text.replace('"', "&quot;")
        if alt_match:
            new_block = re.sub(
                r'(\balt=")([^"]*)(")',
                rf'\1{safe_alt}\3',
                block,
                count=1,
            )
            return new_block, 0, 1

        new_block = re.sub(
            r'(<img[^>]*\bsrc="[^"]+")',
            rf'\1 alt="{safe_alt}"',
            block,
            count=1,
        )
        return new_block, 0, 1

    return block, 0, 0


def cleanup_body(body: str, valid_slugs: set[str]) -> tuple[str, dict[str, int]]:
    stats = {
        "removed_wp_comments": 0,
        "fixed_double_quotes": 0,
        "rewritten_blog_links": 0,
        "replaced_missing_images": 0,
        "filled_alt_texts": 0,
    }

    # Fix malformed doubled quotes produced by WordPress export/import.
    body, fixed_attr_quotes = re.subn(r'=\s*""([^"\n]+?)""', r'="\1"', body)
    stats["fixed_double_quotes"] += fixed_attr_quotes
    body, fixed_text_quotes = re.subn(r'""([^"\n]+?)""', r'"\1"', body)
    stats["fixed_double_quotes"] += fixed_text_quotes

    # Remove WordPress block comment markers.
    body, removed = re.subn(r"<!--\s*/?wp:[^>]*-->", "", body)
    stats["removed_wp_comments"] += removed
    # Remove any malformed leftover comment lines from broken import fragments.
    body = re.sub(r"^\s*<!--.*$", "", body, flags=re.MULTILINE)

    # Remove spacer blocks.
    body = re.sub(
        r'<div[^>]*class="[^"]*wp-block-spacer[^"]*"[^>]*>\s*</div>',
        "",
        body,
        flags=re.IGNORECASE,
    )

    # Standardize separator blocks.
    body = re.sub(r"<hr[^>]*wp-block-separator[^>]*/?>", "\n\n---\n\n", body)
    # Collapse WordPress group wrappers used only around separators.
    body = re.sub(
        r'<div[^>]*class="[^"]*wp-block-group[^"]*"[^>]*>\s*---\s*</div>',
        "\n\n---\n\n",
        body,
        flags=re.DOTALL,
    )

    # Replace dead WordPress images and fill missing alt text for surviving images.
    def figure_replacer(match: re.Match[str]) -> str:
        replaced, missing_count, alt_count = process_figure_block(match.group(0))
        stats["replaced_missing_images"] += missing_count
        stats["filled_alt_texts"] += alt_count
        return replaced

    body = re.sub(r"<figure\b[\s\S]*?</figure>", figure_replacer, body)

    # Rewrite legacy /blog URLs in HTML attributes.
    def attr_url_replacer(match: re.Match[str]) -> str:
        url = match.group("url")
        rewritten = rewrite_blog_url(url, valid_slugs)
        if rewritten != url:
            stats["rewritten_blog_links"] += 1
        return f'{match.group("prefix")}{rewritten}{match.group("suffix")}'

    body = re.sub(
        r'(?P<prefix>\b(?:href|src)=["\'])(?P<url>[^"\']+)(?P<suffix>["\'])',
        attr_url_replacer,
        body,
    )

    # Rewrite legacy /blog URLs in markdown links.
    def md_url_replacer(match: re.Match[str]) -> str:
        url = match.group("url")
        rewritten = rewrite_blog_url(url, valid_slugs)
        if rewritten != url:
            stats["rewritten_blog_links"] += 1
        return f'{match.group("prefix")}{rewritten}{match.group("suffix")}'

    body = re.sub(
        r'(?P<prefix>\]\()(?P<url>[^)\s]+)(?P<suffix>\))',
        md_url_replacer,
        body,
    )

    body = normalize_blank_lines(body)
    return body, stats


def iter_writing_files(content_dir: Path) -> Iterable[Path]:
    for path in sorted(content_dir.glob("*.md")):
        if path.name == "_index.md":
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean imported writings markdown files")
    parser.add_argument(
        "--content-dir",
        default="content/writings",
        help="Path to writings content directory",
    )
    parser.add_argument("--dry-run", action="store_true", help="Analyze only")
    args = parser.parse_args()

    content_dir = Path(args.content_dir)
    files = list(iter_writing_files(content_dir))
    if not files:
        raise SystemExit(f"No writing files found in {content_dir}")

    slug_set: set[str] = set()
    for path in files:
        text = path.read_text(encoding="utf-8")
        frontmatter, _ = split_frontmatter(text)
        slug_set.add(extract_slug(frontmatter, path.stem))

    file_stats: list[FileStats] = []
    for path in files:
        original = path.read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(original)
        cleaned_body, stats = cleanup_body(body, slug_set)
        cleaned = f"{frontmatter}{cleaned_body}" if frontmatter else cleaned_body
        changed = cleaned != original

        if changed and not args.dry_run:
            path.write_text(cleaned, encoding="utf-8")

        file_stats.append(
            FileStats(
                path=path,
                changed=changed,
                removed_wp_comments=stats["removed_wp_comments"],
                fixed_double_quotes=stats["fixed_double_quotes"],
                rewritten_blog_links=stats["rewritten_blog_links"],
                replaced_missing_images=stats["replaced_missing_images"],
                filled_alt_texts=stats["filled_alt_texts"],
            )
        )

    changed_files = [s for s in file_stats if s.changed]
    print(f"Processed {len(file_stats)} files")
    print(f"Changed files: {len(changed_files)}")
    print(
        "Totals: "
        f"wp-comments={sum(s.removed_wp_comments for s in file_stats)}, "
        f"double-quotes-fixed={sum(s.fixed_double_quotes for s in file_stats)}, "
        f"blog-links-rewritten={sum(s.rewritten_blog_links for s in file_stats)}, "
        f"missing-images-replaced={sum(s.replaced_missing_images for s in file_stats)}, "
        f"alt-text-filled={sum(s.filled_alt_texts for s in file_stats)}"
    )

    if changed_files:
        print("Top changed files:")
        for stat in sorted(
            changed_files,
            key=lambda item: (
                item.removed_wp_comments
                + item.fixed_double_quotes
                + item.rewritten_blog_links
                + item.replaced_missing_images
                + item.filled_alt_texts
            ),
            reverse=True,
        )[:10]:
            print(
                f"- {stat.path}: "
                f"wp={stat.removed_wp_comments}, "
                f"quotes={stat.fixed_double_quotes}, "
                f"links={stat.rewritten_blog_links}, "
                f"img={stat.replaced_missing_images}, "
                f"alt={stat.filled_alt_texts}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
