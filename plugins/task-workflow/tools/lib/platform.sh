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

# install_hint 套件…：印出該平台一行安裝指令。套件用邏輯名稱：git jq node python gs chrome bc。
#   windows → winget（Git Bash 沒有 bc 套件，略過）；macos → brew；linux／wsl → apt-get。
install_hint() {
  local os b ids=()
  os=$(tw_os)
  for b in "$@"; do
    case "$os:$b" in
      windows:git) ids+=(Git.Git) ;;
      windows:jq) ids+=(jqlang.jq) ;;
      windows:node) ids+=(OpenJS.NodeJS.LTS) ;;
      windows:python) ids+=(Python.Python.3.12) ;;
      windows:gs) ids+=(ArtifexSoftware.GhostScript) ;;
      windows:chrome) ids+=(Google.Chrome) ;;
      windows:*) ;;
      macos:gs) ids+=(ghostscript) ;;
      macos:chrome) ids+=(google-chrome) ;;
      macos:*) ids+=("$b") ;;
      *:node) ids+=(nodejs) ;;
      *:python) ids+=(python3) ;;
      *:gs) ids+=(ghostscript) ;;
      *:chrome) ids+=(chromium) ;;
      *) ids+=("$b") ;;
    esac
  done
  [ ${#ids[@]} -eq 0 ] && return 1
  case "$os" in
    windows) echo "winget install ${ids[*]}" ;;
    macos) echo "brew install ${ids[*]}" ;;
    *) echo "sudo apt-get install -y ${ids[*]}" ;;
  esac
}

# find_gs：印出 Ghostscript 執行檔（Linux／macOS：gs；Windows：gswin64c／gswin32c），找不到回傳 1。
find_gs() {
  local c
  for c in gs gswin64c gswin32c; do command -v "$c" >/dev/null 2>&1 && { command -v "$c"; return 0; }; done
  return 1
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
