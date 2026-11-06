#!/usr/bin/env bash
# open-browser.sh [--print] <檔案或網址> — 用使用者的瀏覽器開啟（取代只在 WSL 才有的 `chrome` alias）。
#   順序：TW_BROWSER（自訂指令）→ Chrome／Edge（find_chrome）→ 系統預設（Windows start、macOS open、Linux xdg-open、WSL wslview／explorer.exe）。
#   Windows／WSL 會把本機檔案路徑轉成 Windows 路徑再交給瀏覽器。
#   --print：只印出要執行的指令，不實際開啟（測試、或給使用者自己點）。
set -u
PRINT=0
[ "${1:-}" = --print ] && { PRINT=1; shift; }
T="${1:-}"
[ -n "$T" ] || { echo "用法：open-browser.sh [--print] <檔案或網址>" >&2; exit 2; }
# shellcheck source=lib/platform.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/platform.sh"
OS=$(tw_os)

ARG="$T"
case "$T" in
  *://*) ;;  # 網址原樣
  *)
    [ -e "$T" ] || { echo "找不到 $T" >&2; exit 2; }
    case "$OS" in
      windows) ARG=$(cygpath -w "$(cd "$(dirname "$T")" && pwd)/$(basename "$T")") ;;
      wsl) ARG=$(wslpath -w "$(cd "$(dirname "$T")" && pwd)/$(basename "$T")" 2>/dev/null || printf '%s' "$T") ;;
      *) ARG="$(cd "$(dirname "$T")" && pwd)/$(basename "$T")" ;;
    esac ;;
esac

run() {
  if [ $PRINT = 1 ]; then printf '%q ' "$@"; echo; return 0; fi
  "$@" >/dev/null 2>&1 &
  disown 2>/dev/null || true
}

if [ -n "${TW_BROWSER:-}" ]; then run "$TW_BROWSER" "$ARG"; exit 0; fi
if C=$(find_chrome); then run "$C" "$ARG"; exit 0; fi
case "$OS" in
  windows) run cmd //c start "" "$ARG" ;;
  macos) run open "$ARG" ;;
  wsl) if command -v wslview >/dev/null 2>&1; then run wslview "$ARG"; else run explorer.exe "$ARG"; fi ;;
  *) if command -v xdg-open >/dev/null 2>&1; then run xdg-open "$ARG"; else echo "找不到瀏覽器；請手動開啟：$ARG" >&2; exit 1; fi ;;
esac
