#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-1111}"
MOBILE_DEVICE="${MOBILE_DEVICE:-iPhone 12}"
SCREENSHOT_PATH="${SCREENSHOT_PATH:-output/playwright/mobile-toggle-light-after-switch.png}"
SKIP_PLAYWRIGHT_INSTALL="${SKIP_PLAYWRIGHT_INSTALL:-0}"

if [[ -n "${BASE_URL:-}" ]]; then
  TARGET_URL="$BASE_URL"
  START_ZOLA=0
else
  TARGET_URL="http://${HOST}:${PORT}/"
  START_ZOLA=1
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "Error: npx is required but was not found on PATH." >&2
  exit 1
fi

if [[ "$START_ZOLA" -eq 1 ]] && ! command -v zola >/dev/null 2>&1; then
  echo "Error: zola is required when BASE_URL is not provided." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl is required but was not found on PATH." >&2
  exit 1
fi

mkdir -p "$(dirname "$SCREENSHOT_PATH")"

SERVER_PID=""
SERVER_LOG=""
cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ "$START_ZOLA" -eq 1 ]]; then
  SERVER_LOG="$(mktemp -t zola-theme-toggle.XXXXXX.log)"
  zola serve --interface "$HOST" --port "$PORT" >"$SERVER_LOG" 2>&1 &
  SERVER_PID="$!"

  for _ in $(seq 1 60); do
    if curl -fsS "$TARGET_URL" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done

  if ! curl -fsS "$TARGET_URL" >/dev/null 2>&1; then
    echo "Error: local Zola server did not start in time. Log: $SERVER_LOG" >&2
    exit 1
  fi
fi

if [[ "$SKIP_PLAYWRIGHT_INSTALL" != "1" ]]; then
  npx --yes --package @playwright/test playwright install chromium >/tmp/playwright-install.log 2>&1
fi

PLAYWRIGHT_NODE_MODULES="$(npx --yes --package @playwright/test bash -lc 'dirname "$(dirname "$(which playwright)")"')"

NODE_PATH="$PLAYWRIGHT_NODE_MODULES" \
TARGET_URL="$TARGET_URL" \
SCREENSHOT_PATH="$SCREENSHOT_PATH" \
MOBILE_DEVICE="$MOBILE_DEVICE" \
node <<'NODE'
const { chromium, devices } = require("playwright");

async function main() {
    const targetUrl = process.env.TARGET_URL;
    const screenshotPath = process.env.SCREENSHOT_PATH;
    const deviceName = process.env.MOBILE_DEVICE;

    if (!devices[deviceName]) {
        throw new Error(`Unknown Playwright device: ${deviceName}`);
    }

    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ ...devices[deviceName] });
    const page = await context.newPage();

    await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => localStorage.setItem("theme-storage", "dark"));
    await page.reload({ waitUntil: "domcontentloaded" });

    const beforeClass = await page.evaluate(() => document.documentElement.className);
    if (!/\bdark\b/.test(beforeClass)) {
        throw new Error(`Expected dark mode before toggle, got: ${beforeClass}`);
    }

    const toggle = page.locator("#dark-mode-toggle");
    await toggle.click();
    await page.waitForTimeout(200);

    const result = await page.evaluate(() => {
        const toggleEl = document.getElementById("dark-mode-toggle");
        const moonEl = document.getElementById("moon-icon");
        const htmlEl = document.documentElement;

        if (!toggleEl || !moonEl) {
            throw new Error("Theme toggle elements not found in DOM.");
        }

        const toggleStyle = window.getComputedStyle(toggleEl);
        const htmlStyle = window.getComputedStyle(htmlEl);
        const moonStyle = window.getComputedStyle(moonEl);
        const moonRect = moonEl.getBoundingClientRect();

        return {
            htmlClass: htmlEl.className,
            toggleColor: toggleStyle.color,
            htmlBackground: htmlStyle.backgroundColor,
            moonDisplay: moonStyle.display,
            moonVisibility: moonStyle.visibility,
            moonOpacity: moonStyle.opacity,
            moonWidth: moonRect.width,
            moonHeight: moonRect.height
        };
    });

    if (!/\blight\b/.test(result.htmlClass)) {
        throw new Error(`Expected light mode after toggle, got: ${result.htmlClass}`);
    }
    if (result.toggleColor === result.htmlBackground) {
        throw new Error(`Toggle color matches page background (${result.toggleColor}); icon may be invisible.`);
    }
    if (result.moonDisplay === "none") {
        throw new Error("Moon icon display is none after switching to light mode.");
    }
    if (result.moonVisibility !== "visible") {
        throw new Error(`Moon icon visibility is ${result.moonVisibility} after switching to light mode.`);
    }
    if (Number(result.moonOpacity) <= 0) {
        throw new Error(`Moon icon opacity is ${result.moonOpacity} after switching to light mode.`);
    }
    if (result.moonWidth <= 0 || result.moonHeight <= 0) {
        throw new Error(`Moon icon has non-positive size (${result.moonWidth}x${result.moonHeight}).`);
    }

    await page.screenshot({ path: screenshotPath });
    await context.close();
    await browser.close();

    console.log("REGRESSION_CHECK_RESULT=" + JSON.stringify(result));
    console.log("SCREENSHOT_PATH=" + screenshotPath);
}

main().catch((error) => {
    console.error(error.message || error);
    process.exit(1);
});
NODE
