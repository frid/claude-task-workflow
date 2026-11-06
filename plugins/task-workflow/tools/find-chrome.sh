#!/usr/bin/env bash
# find-chrome.sh — 印出本機 Chrome／Chromium（或 Edge）執行檔路徑，給 headless 截圖與 CDP 用；找不到 exit 1 並提示安裝。
#   用法：CHROME="$(find-chrome.sh)" && "$CHROME" --headless=new --remote-debugging-port=9222 …
#   可用環境變數 CHROME_PATH 指定。Windows 印出 Git Bash 路徑（/c/…）；加 --windows 改印 C:\… 給 node／PowerShell 用。
set -u
# shellcheck source=lib/platform.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/platform.sh"
if p=$(find_chrome); then
  if [ "${1:-}" = --windows ] && command -v cygpath >/dev/null 2>&1; then cygpath -w "$p"; else printf '%s\n' "$p"; fi
  exit 0
fi
echo "找不到 Chrome／Chromium／Edge。可設 CHROME_PATH，或安裝：$(install_hint chrome)" >&2
exit 1
