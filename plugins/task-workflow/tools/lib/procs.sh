# shellcheck shell=bash
# procs.sh — 跨平台偵測 git 程序、安全清除殘留 lock。由 git-guard.sh、doctor.sh、clear-stale-lock.sh source。
#
# 原則：「無法判斷有沒有 git 在跑」≠「沒有 git 在跑」。判斷不了就不刪 lock。
#   （1.10.2 以前用 `pgrep -x git`；Git Bash 沒有 pgrep → 永遠判成「沒有」→ 會刪掉活著的 git 持有的 index.lock）

# git_pids：印出執行中 git 程序的 PID（空白分隔；可能為空）。
#   回傳 0＝偵測成功（輸出為空代表確定沒有 git 在跑）；回傳 2＝無法偵測。
#   偵測順序：pgrep → tasklist（Windows：Git Bash／MSYS／Cygwin）→ ps -W（MSYS 列出 Windows 程序）。
#   TW_PROC_METHOD=pgrep|tasklist|ps|none 可強制指定方法（測試用；none＝模擬全部不可用）。
git_pids() {
  local m="${TW_PROC_METHOD:-auto}" out
  if [ "$m" = auto ] || [ "$m" = pgrep ]; then
    if command -v pgrep >/dev/null 2>&1; then
      pgrep -x git 2>/dev/null | tr '\n' ' '; return 0
    fi
  fi
  if [ "$m" = auto ] || [ "$m" = tasklist ]; then
    if command -v tasklist >/dev/null 2>&1; then
      # MSYS2_ARG_CONV_EXCL：避免 Git Bash 把 /FI 當路徑轉換。CSV 格式不受系統語系影響（找不到時的提示文字會被 awk 忽略）
      if out=$(MSYS2_ARG_CONV_EXCL='*' tasklist /FI "IMAGENAME eq git.exe" /FO CSV /NH 2>/dev/null); then
        printf '%s\n' "$out" | tr -d '\r' | awk -F'","' 'tolower($1)=="\"git.exe" {printf "%s ", $2}'
        return 0
      fi
    fi
  fi
  if [ "$m" = auto ] || [ "$m" = ps ]; then
    if out=$(ps -W 2>/dev/null) && [ -n "$out" ]; then
      # 欄位：PID PPID PGID WINPID TTY UID STIME COMMAND。COMMAND 可能是 Windows 路徑（C:\…\git.exe），
      # 或 MSYS 路徑（Git Bash 啟動的 git 顯示為 /mingw64/bin/git，沒有 .exe）→ 兩種都認；只比對最後一段，不會誤中 GitExtensions.exe
      printf '%s\n' "$out" | awk 'tolower($0) ~ /[\\\/]git(\.exe)?[[:space:]]*$/ {printf "%s ", ($4 != "" ? $4 : "?")}'
      return 0
    fi
  fi
  return 2
}

# remove_stale_lock LOCK [MAX_WAIT_S]：確定沒有 git 程序時才刪 LOCK。
#   有 git 在跑 → 退避等待（1,2,4… 秒，合計不超過 MAX_WAIT_S，預設 7）；期間 lock 消失算正常。
#   回傳 0＝lock 不存在或已移除；回傳 2＝仍被持有／無法判斷／刪除失敗（不刪，說明寫到 stderr）。
remove_stale_lock() {
  local lock="$1" max="${2:-7}" pids rc wait=1 total=0 size
  [ -e "$lock" ] || return 0
  pids=$(git_pids); rc=$?
  while [ $rc -eq 0 ] && [ -n "${pids// /}" ] && [ $total -lt "$max" ]; do
    sleep $wait; total=$((total+wait)); wait=$((wait*2))
    [ -e "$lock" ] || return 0
    pids=$(git_pids); rc=$?
  done
  if [ $rc -ne 0 ]; then
    echo "[git-lock] 無法判斷是否有 git 程序在跑（pgrep／tasklist／ps -W 都不能用），不自動刪除 $lock。確認沒有 git 在跑後再手動刪。" >&2
    return 2
  fi
  if [ -n "${pids// /}" ]; then
    echo "[git-lock] $lock 仍被 git 程序持有（PID ${pids% }；已等 ${total}s）。等它結束再重試，不要 rm。" >&2
    return 2
  fi
  size=$(stat -c %s "$lock" 2>/dev/null || echo ?)
  if rm -f -- "$lock"; then
    echo "[git-lock] 已移除殘留 $lock（${size} byte，無 git 程序）；放行。" >&2
    return 0
  fi
  echo "[git-lock] 無法移除 $lock，請手動處理。" >&2
  return 2
}
