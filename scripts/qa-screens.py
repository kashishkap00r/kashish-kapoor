"""Visual + flow QA for the site (eng review D8).

Usage:
  npm run build && npx astro preview --port 4321 &   # or a deployed preview URL
  python3 scripts/qa-screens.py http://localhost:4321 out-dir

Takes full-page screenshots of 6 routes at 390px and 1440px in light and dark,
and asserts: no horizontal scroll; theme choice persists after reload; the
/work year chips scroll the archive box, not the page; content is visible on
first paint with JavaScript disabled. Exits 1 on any failure.
Needs Python Playwright (already installed on the dev machine).
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4321").rstrip("/")
OUT = sys.argv[2] if len(sys.argv) > 2 else "qa-screens"
ROUTES = ["/", "/work/", "/about/", "/finance-radar/", "/financial-planning/",
          "/writings/these-3-costly-blunders-denied-me-my-first-mma-win/"]
WIDTHS = {"phone": (390, 844), "desktop": (1440, 900)}
os.makedirs(OUT, exist_ok=True)
failures = []


def name(route):
    return route.strip("/").replace("/", "_") or "home"


with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ["light", "dark"]:
        for label, (w, h) in WIDTHS.items():
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
            ctx.add_init_script(f"try{{localStorage.setItem('theme','{theme}')}}catch(e){{}}")
            page = ctx.new_page()
            for route in ROUTES:
                page.goto(BASE + route, wait_until="networkidle")
                # Scroll through once so lazy images load before the full-page shot.
                page.evaluate("""async () => { for (let y = 0; y < document.body.scrollHeight; y += innerHeight / 2) { scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } scrollTo(0, 0); }""")
                page.wait_for_load_state("networkidle")
                over = page.evaluate("document.documentElement.scrollWidth - innerWidth")
                if over > 0:
                    failures.append(f"{route} {label} {theme}: horizontal scroll {over}px")
                got = page.evaluate("document.documentElement.dataset.theme")
                if got != theme:
                    failures.append(f"{route} {label}: theme {got}, expected {theme}")
                page.screenshot(path=f"{OUT}/{name(route)}-{label}-{theme}.png", full_page=True)
            ctx.close()

    # Theme toggle persists across reload.
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/", wait_until="networkidle")
    if page.evaluate("document.documentElement.dataset.theme") != "light":
        failures.append("default theme is not light")
    page.click("#theme-toggle")
    page.reload(wait_until="networkidle")
    if page.evaluate("document.documentElement.dataset.theme") != "dark":
        failures.append("theme toggle did not persist after reload")

    # Year chip scrolls the box, not the page.
    page.goto(BASE + "/work/", wait_until="networkidle")
    chips = page.locator(".chips .chip")
    if chips.count() > 1:
        # html has scroll-behavior: smooth; jump instantly so "before" is settled.
        page.evaluate("document.getElementById('archive').scrollIntoView({behavior: 'instant', block: 'start'})")
        page.wait_for_timeout(300)
        before = page.evaluate("scrollY")
        chips.nth(1).click()
        page.wait_for_timeout(900)
        box_top = page.evaluate("document.getElementById('abox').scrollTop")
        after = page.evaluate("scrollY")
        if box_top <= 0:
            failures.append("year chip did not scroll the archive box")
        if abs(after - before) > 2:
            failures.append(f"year chip moved the page by {after - before}px")
    ctx.close()

    # No-JS first paint shows content.
    ctx = browser.new_context(java_script_enabled=False, viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/", wait_until="load")
    visible = page.locator("h1").first.is_visible()
    if not visible:
        failures.append("homepage h1 not visible with JavaScript disabled")
    ctx.close()
    browser.close()

if failures:
    print("qa-screens: FAIL\n  - " + "\n  - ".join(failures))
    sys.exit(1)
print(f"qa-screens: OK ({len(ROUTES)} routes x 2 widths x 2 themes) -> {OUT}/")
