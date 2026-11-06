# shellcheck shell=bash
# platform.sh — 平台判斷與跨平台工具挑選。由 git-guard.sh、doctor.sh、check-js.sh 等 source。

# tw_os：印出 linux｜wsl｜macos｜windows（Git Bash／MSYS／Cygwin 都算 windows）。TW_OS 可覆寫（測試用）。
tw_os() {
  if [ -n "${TW_OS:-}" ]; then printf '%s\n' "$TW_OS"; return; fi
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*) echo windows ;;
    Darwin) echo macos ;;
    Linux) if grep -qi microsoft /proc/version 2>/dev/null; then echo wsl; else echo linux; fi ;;
    *) echo linux ;;
  esac
}

# pick_py：印出「實際能執行」的 Python 3 指令（python3｜python｜py -3），找不到回傳 1。
#   只用 command -v 不夠：Windows 的 python3 可能是 Microsoft Store 的空殼（存在但執行失敗或跳出商店）。
#   呼叫端以不加引號的 $PY 使用（"py -3" 需要分詞），並一律加 -X utf8（cp950 主控台讀寫中文）。
#   TW_PY_CANDIDATES 可覆寫候選清單（測試用；以 | 分隔，例："nonexistent|python"）。
pick_py() {
  local IFS='|' c
  for c in ${TW_PY_CANDIDATES:-python3|python|py -3}; do
    IFS=' '
    # shellcheck disable=SC2086
    if command -v ${c%% *} >/dev/null 2>&1 && $c -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
      printf '%s\n' "$c"; return 0
    fi
    IFS='|'
  done
  return 1
}
