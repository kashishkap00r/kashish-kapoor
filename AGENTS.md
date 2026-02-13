# Repository Guidelines

## Project Structure & Module Organization
This is a Zola-based personal site.
- `content/`: Markdown pages and sections.
- `content/writings/`: long-form posts (one file per slug plus `_index.md`).
- `templates/` and `templates/partials/`: Tera templates for layout/nav/header overrides.
- `static/`: source assets (images, JS, fonts, CSS overrides).
- `scripts/`: migration and maintenance utilities (`cleanup_writings_import.py`, `import_medium_images.py`).
- `themes/apollo/`: upstream theme as a git submodule; avoid editing unless intentionally patching theme behavior.
- `public/` and `output/`: generated artifacts; do not commit.

## Build, Test, and Development Commands
- `zola serve`: run local dev server with live reload.
- `zola build`: generate production output and fail on template/content errors.
- `zola check`: validate links/front matter before publishing.
- `./scripts/check_mobile_theme_toggle.sh`: run mobile regression check for theme toggle visibility after switching dark → light (writes screenshot under `output/playwright/`).
- `python3 scripts/cleanup_writings_import.py --dry-run --report`: preview writing cleanup impact.
- `python3 scripts/import_medium_images.py --urls-file <file> --dry-run`: preview Medium image localization before writing files.

## Coding Style & Naming Conventions
- Use kebab-case file names for content (example: `company-radar.md`).
- Keep slugs stable once published; prefer editing copy over renaming paths.
- Preserve each file’s existing front matter style (`+++` TOML and `---` YAML both exist in this repo).
- Keep Tera/HTML formatting consistent with existing templates (4-space indentation, minimal logic in partials).
- Prefer local asset references (`/images/...`) over hotlinked external media.

## Testing Guidelines
There is no formal unit test suite. Use release checks:
1. Run `zola build` (required).
2. Spot-check affected routes in `zola serve` (nav, internal links, writing pages).
3. If scripts were used, run once with `--dry-run` first, then verify diffs for unintended mass edits.

## Commit & Pull Request Guidelines
- Match existing history: short, imperative commit subjects (examples: `Update company-radar.md`, `Fix Medium import images and optimize writing assets`).
- Keep commits scoped to one concern (content copy, template change, or script update).
- PRs should include: concise summary, impacted paths/routes, local validation notes (`zola build`), and screenshots for layout/styling changes.
