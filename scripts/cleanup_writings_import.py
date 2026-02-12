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
WP_CLASS_PREFIXES = ("wp-", "uagb-", "is-", "has-")
WP_CLASS_EXACT = {"aligncenter", "alignleft", "alignright"}


@dataclass
class FileStats:
    path: Path
    changed: bool
    removed_wp_comments: int
    fixed_double_quotes: int
    rewritten_blog_links: int
    replaced_missing_images: int
    filled_alt_texts: int
    removed_empty_paragraphs: int
    stripped_wp_classes: int
    removed_inline_styles: int
    normalized_headings: int
    removed_wrapper_divs: int


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
        first_segment = tail.split("/", 1)[0].strip().removesuffix(".html")
        if first_segment and first_segment in valid_slugs:
            new_path = f"/writings/{first_segment}/"
        else:
            new_path = "/writings/"

    if fragment:
        return f"{new_path}#{fragment}"
    return new_path


def derive_alt_from_src(src: str) -> str:
    parsed = urlparse(src)
    base = Path(parsed.path).stem
    base = re.sub(r"\b\d{2,4}x\d{2,4}\b", "", base)
    base = re.sub(r"[-_]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    if not base or not re.search(r"[A-Za-z]{3,}", base):
        return "Embedded image"
    if len(base) > 80:
        base = base[:80].rstrip()
    return base


def is_wp_class_token(token: str) -> bool:
    lc = token.lower()
    if lc in WP_CLASS_EXACT:
        return True
    return lc.startswith(WP_CLASS_PREFIXES)


def normalize_class_attributes(body: str, full_mode: bool, stats: dict[str, int]) -> str:
    if not full_mode:
        return body

    def class_replacer(match: re.Match[str]) -> str:
        classes = match.group("value").split()
        kept: list[str] = []
        removed = 0
        for cls in classes:
            if is_wp_class_token(cls):
                removed += 1
            else:
                kept.append(cls)

        stats["stripped_wp_classes"] += removed

        if not kept:
            return ""
        return f' class="{" ".join(kept)}"'

    body = re.sub(r'\sclass="(?P<value>[^"]+)"', class_replacer, body)

    body, removed_styles = re.subn(r'\sstyle="[^"]*"', "", body)
    stats["removed_inline_styles"] += removed_styles
    return body


def process_figure_block(
    block: str,
    full_mode: bool,
) -> tuple[str, int, int]:
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
        fallback = "\n".join([f"> **{WP_IMPORT_FALLBACK_TEXT}**  "] + details)
        return f"\n{fallback}\n", 1, 0

    filled = 0
    if not alt_text:
        alt_text = caption_text or derive_alt_from_src(src)
        filled = 1

    safe_alt = alt_text.replace("[", "").replace("]", "").strip()

    if full_mode:
        image_line = f"![{safe_alt}]({src})"
        if caption_text and caption_text != alt_text:
            return f"\n{image_line}\n\n*{caption_text}*\n", 0, filled
        return f"\n{image_line}\n", 0, filled

    if filled:
        escaped_alt = safe_alt.replace('"', "&quot;")
        if alt_match:
            new_block = re.sub(
                r'(\balt=")([^"]*)(")',
                rf'\1{escaped_alt}\3',
                block,
                count=1,
            )
            return new_block, 0, filled
        new_block = re.sub(
            r'(<img[^>]*\bsrc="[^"]+")',
            rf'\1 alt="{escaped_alt}"',
            block,
            count=1,
        )
        return new_block, 0, filled

    return block, 0, 0


def metrics_for_body(body: str) -> dict[str, int]:
    raw_html_lines = 0
    for line in body.splitlines():
        if re.search(r"<(p|div|figure|blockquote|h[1-6]|ul|ol|li|pre|cite|img)\b|</", line):
            raw_html_lines += 1

    return {
        "wp_comments": len(re.findall(r"<!--\s*/?wp:", body)),
        "malformed_attrs": len(re.findall(r'href=""|src=""', body)),
        "legacy_blog_links": len(
            re.findall(r"kashishkapoor\.com/blog/|href=\"/blog|\]\(/blog", body)
        ),
        "dead_wp_img_src": len(
            re.findall(r"<img[^>]+https://kashishkapoor.com/wp-content/uploads/", body)
        ),
        "empty_alt_imgs": len(re.findall(r'<img[^>]+alt=""', body)),
        "empty_paragraphs": len(re.findall(r"<p>\s*</p>", body)),
        "wp_class_markup": len(re.findall(r"wp-block-|wp-element-caption|uagb-|\bclass=", body)),
        "inline_styles": len(re.findall(r'\sstyle="', body)),
        "raw_html_lines": raw_html_lines,
    }


def cleanup_body(body: str, valid_slugs: set[str], mode: str) -> tuple[str, dict[str, int]]:
    full_mode = mode == "full"
    stats = {
        "removed_wp_comments": 0,
        "fixed_double_quotes": 0,
        "rewritten_blog_links": 0,
        "replaced_missing_images": 0,
        "filled_alt_texts": 0,
        "removed_empty_paragraphs": 0,
        "stripped_wp_classes": 0,
        "removed_inline_styles": 0,
        "normalized_headings": 0,
        "removed_wrapper_divs": 0,
    }

    # Fix malformed doubled quotes produced by WordPress export/import.
    body, fixed_attr_quotes = re.subn(r'=\s*""([^"\n]+?)""', r'="\1"', body)
    stats["fixed_double_quotes"] += fixed_attr_quotes

    # Remove WordPress block comment markers.
    body, removed = re.subn(r"<!--\s*/?wp:[^>]*-->", "", body)
    stats["removed_wp_comments"] += removed
    body = re.sub(r"^\s*<!--.*$", "", body, flags=re.MULTILINE)

    # Normalize previously generated fallback text and remove legacy source lines.
    body = body.replace("Image unavailable (WordPress import)", WP_IMPORT_FALLBACK_TEXT)
    body = re.sub(r"(?m)^> Original URL: .*$", "", body)

    # Remove spacer blocks.
    body = re.sub(
        r'<div[^>]*class="[^"]*wp-block-spacer[^"]*"[^>]*>\s*</div>',
        "",
        body,
        flags=re.IGNORECASE,
    )

    # Standardize separator blocks.
    body = re.sub(r"<hr[^>]*wp-block-separator[^>]*/?>", "\n\n---\n\n", body)
    body = re.sub(
        r'<div[^>]*class="[^"]*wp-block-group[^"]*"[^>]*>\s*---\s*</div>',
        "\n\n---\n\n",
        body,
        flags=re.DOTALL,
    )

    # Normalize image figures.
    def figure_replacer(match: re.Match[str]) -> str:
        replaced, missing_count, alt_count = process_figure_block(match.group(0), full_mode)
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

    # Remove empty paragraphs globally.
    body, removed_empty = re.subn(r"<p>\s*</p>", "", body)
    stats["removed_empty_paragraphs"] += removed_empty

    if full_mode:
        # Remove layout-only WordPress wrappers.
        body, removed_wrappers = re.subn(
            r'<div[^>]*class="[^"]*(wp-block-group|wp-block-columns|wp-block-column)[^"]*"[^>]*>\s*',
            "",
            body,
            flags=re.IGNORECASE,
        )
        stats["removed_wrapper_divs"] += removed_wrappers

        body, removed_close_divs = re.subn(r"(?m)^\s*</div>\s*$", "", body)
        stats["removed_wrapper_divs"] += removed_close_divs
        body, removed_open_divs = re.subn(r"(?m)^\s*<div>\s*$", "", body)
        stats["removed_wrapper_divs"] += removed_open_divs

        # Convert heading tags into markdown headings.
        def heading_replacer(match: re.Match[str]) -> str:
            level = int(match.group(1))
            inner = match.group(2).strip()
            inner = re.sub(r"\s+", " ", inner)
            stats["normalized_headings"] += 1
            return f"\n{'#' * level} {inner}\n"

        body = re.sub(
            r"<h([1-6])(?:\s+[^>]*)?>([\s\S]*?)</h\1>",
            heading_replacer,
            body,
        )
        body, unwrapped_heading_divs = re.subn(
            r"<div>\s*(#{1,6}\s+[^\n]+)\s*</div>",
            r"\n\1\n",
            body,
            flags=re.DOTALL,
        )
        stats["removed_wrapper_divs"] += unwrapped_heading_divs

        # Convert plain paragraph tags to markdown paragraphs.
        def paragraph_replacer(match: re.Match[str]) -> str:
            inner = match.group(1).strip()
            return f"\n{inner}\n" if inner else "\n"

        body = re.sub(r"<p>([\s\S]*?)</p>", paragraph_replacer, body)

        # Strip WordPress classes and redundant inline styles.
        body = normalize_class_attributes(body, full_mode=True, stats=stats)
        # Clean up now-empty class attributes.
        body = re.sub(r"<([a-zA-Z0-9]+)\s+>", r"<\1>", body)

    body = normalize_blank_lines(body)
    return body, stats


def iter_writing_files(content_dir: Path) -> Iterable[Path]:
    for path in sorted(content_dir.glob("*.md")):
        if path.name == "_index.md":
            continue
        yield path


def add_metric_totals(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean and normalize imported writings markdown files")
    parser.add_argument(
        "--content-dir",
        default="content/writings",
        help="Path to writings content directory",
    )
    parser.add_argument("--dry-run", action="store_true", help="Analyze only")
    parser.add_argument(
        "--mode",
        choices=["safe", "full"],
        default="safe",
        help="Normalization intensity",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print before/after formatting metrics",
    )
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

    before_metrics: dict[str, int] = {}
    after_metrics: dict[str, int] = {}

    file_stats: list[FileStats] = []
    for path in files:
        original = path.read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(original)
        cleaned_body, stats = cleanup_body(body, slug_set, args.mode)
        cleaned = f"{frontmatter}{cleaned_body}" if frontmatter else cleaned_body
        changed = cleaned != original

        add_metric_totals(before_metrics, metrics_for_body(body))
        add_metric_totals(after_metrics, metrics_for_body(cleaned_body))

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
                removed_empty_paragraphs=stats["removed_empty_paragraphs"],
                stripped_wp_classes=stats["stripped_wp_classes"],
                removed_inline_styles=stats["removed_inline_styles"],
                normalized_headings=stats["normalized_headings"],
                removed_wrapper_divs=stats["removed_wrapper_divs"],
            )
        )

    changed_files = [s for s in file_stats if s.changed]
    print(f"Processed {len(file_stats)} files")
    print(f"Mode: {args.mode}")
    print(f"Changed files: {len(changed_files)}")
    print(
        "Totals: "
        f"wp-comments={sum(s.removed_wp_comments for s in file_stats)}, "
        f"double-quotes-fixed={sum(s.fixed_double_quotes for s in file_stats)}, "
        f"blog-links-rewritten={sum(s.rewritten_blog_links for s in file_stats)}, "
        f"missing-images-replaced={sum(s.replaced_missing_images for s in file_stats)}, "
        f"alt-text-filled={sum(s.filled_alt_texts for s in file_stats)}, "
        f"empty-paragraphs-removed={sum(s.removed_empty_paragraphs for s in file_stats)}, "
        f"wp-classes-stripped={sum(s.stripped_wp_classes for s in file_stats)}, "
        f"inline-styles-removed={sum(s.removed_inline_styles for s in file_stats)}, "
        f"headings-normalized={sum(s.normalized_headings for s in file_stats)}, "
        f"wrapper-divs-removed={sum(s.removed_wrapper_divs for s in file_stats)}"
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
                + item.removed_empty_paragraphs
                + item.stripped_wp_classes
                + item.removed_inline_styles
                + item.normalized_headings
                + item.removed_wrapper_divs
            ),
            reverse=True,
        )[:10]:
            print(
                f"- {stat.path}: "
                f"wp={stat.removed_wp_comments}, "
                f"quotes={stat.fixed_double_quotes}, "
                f"links={stat.rewritten_blog_links}, "
                f"img={stat.replaced_missing_images}, "
                f"alt={stat.filled_alt_texts}, "
                f"empty-p={stat.removed_empty_paragraphs}, "
                f"classes={stat.stripped_wp_classes}, "
                f"styles={stat.removed_inline_styles}, "
                f"h={stat.normalized_headings}, "
                f"div={stat.removed_wrapper_divs}"
            )

    if args.report:
        print("Report:")
        for key in [
            "wp_comments",
            "malformed_attrs",
            "legacy_blog_links",
            "dead_wp_img_src",
            "empty_alt_imgs",
            "empty_paragraphs",
            "wp_class_markup",
            "inline_styles",
            "raw_html_lines",
        ]:
            before = before_metrics.get(key, 0)
            after = after_metrics.get(key, 0)
            delta = after - before
            print(f"- {key}: {before} -> {after} ({delta:+d})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
