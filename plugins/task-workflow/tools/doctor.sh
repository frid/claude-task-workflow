#!/usr/bin/env bash
# doctor.sh — WSL + Google Drive（/mnt/<盤>）+ git worktree 環境醫生
#
# 用法：
#   doctor.sh [--check|--fix] [--hook] [--repo <path>] [--todo <file>] [--no-fetch] [--quiet]
#     --check   只偵測、不改任何東西（預設）
#     --fix     能自動修的就修：移除無人持有的 index.lock、補 safe.directory、git worktree repair
#     --hook    SessionStart 用：精簡輸出，只有 WARN/FAIL 才列細節；永遠 exit 0
#     --repo    指定 repo（預設從目前目錄 git rev-parse）
#     --todo    Drive 同步比對的檔案（預設 TODO.md）
#     --no-fetch  不 git fetch origin（離線）
#
# 檢查項目（對應歷史已知失敗 a～f）：
#   [a] index.lock 殘留／被佔住   [b] /mnt/<盤> dubious ownership／safe.directory
#   [c] 磁碟代號改變→worktree 指標失效   [d] Google Drive 同步延遲（TODO.md vs HEAD vs origin）
#   [e] jq 等 statusline 相依套件     [f] worker agent 定義含「一次一個簡單指令」指引
#
# exit code：0 全 OK（或 --hook）；1 有 WARN；2 有 FAIL
# 測試用環境變數：DOCTOR_ASSUME_DRVFS=1 把非 /mnt 路徑也當 Drive 掛載檢查；
#   GIT_TEST_ASSUME_DIFFERENT_OWNER=1（git 內建）讓 git 把 repo 當成別人的，模擬 dubious ownership。

set -u
MODE=check; HOOK=0; QUIET=0; FETCH=1; REPO=""; TODO_FILE="TODO.md"
while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE=check;; --fix) MODE=fix;; --hook) HOOK=1;; --quiet) QUIET=1;;
    --no-fetch) FETCH=0;; --repo) REPO="$2"; shift;; --todo) TODO_FILE="$2"; shift;;
    -h|--help) sed -n '2,20p' "$0"; exit 0;;
    *) echo "未知參數：$1" >&2; exit 2;;
  esac; shift
done

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
N_OK=0; N_WARN=0; N_FAIL=0; N_FIXED=0
LINES=()
ok()    { N_OK=$((N_OK+1));     LINES+=("OK    $1"); }
warn()  { N_WARN=$((N_WARN+1)); LINES+=("WARN  $1"); }
fail()  { N_FAIL=$((N_FAIL+1)); LINES+=("FAIL  $1"); }
fixed() { N_FIXED=$((N_FIXED+1)); LINES+=("FIXED $1"); }
info()  { [ "$HOOK" = 1 ] || LINES+=("      $1"); }
hint()  { LINES+=("      → $1"); }

# ---------- repo 定位 ----------
if [ -z "$REPO" ]; then REPO="$PWD"; fi
GIT_DIR=$(git -C "$REPO" rev-parse --git-dir 2>/tmp/doctor_err.$$ || true)
GIT_ERR=$(cat /tmp/doctor_err.$$ 2>/dev/null); rm -f /tmp/doctor_err.$$
COMMON_DIR=""; TOPLEVEL=""
if [ -n "$GIT_DIR" ]; then
  GIT_DIR=$(cd "$REPO" && cd "$GIT_DIR" && pwd)
  COMMON_DIR=$(cd "$REPO" && cd "$(git rev-parse --git-common-dir)" && pwd)
  TOPLEVEL=$(git -C "$REPO" rev-parse --show-toplevel 2>/dev/null || true)
fi

short() { printf "%.7s" "$1"; }

is_drvfs() {  # 路徑在 /mnt/<一個字母>/ 底下（WSL DrvFs，Google Drive 掛載在這）
  case "$1" in /mnt/[a-z]/*|/mnt/[a-z]) return 0;; esac
  [ "${DOCTOR_ASSUME_DRVFS:-0}" = 1 ]
}

# ---------- [b] dubious ownership / safe.directory ----------
check_ownership() {
  if printf '%s' "$GIT_ERR" | grep -q "dubious ownership"; then
    local p; p=$(printf '%s' "$GIT_ERR" | sed -n "s/.*detected dubious ownership in repository at '\([^']*\)'.*/\1/p" | head -1)
    [ -z "$p" ] && p="$REPO"
    local cmd="git config --global --add safe.directory \"$p\""
    if [ "$MODE" = fix ]; then
      if eval "$cmd"; then fixed "[b] 已加入 safe.directory：$p"; hint "重新執行 doctor 確認其餘項目"; else fail "[b] 加 safe.directory 失敗"; fi
    else
      fail "[b] git 回報 dubious ownership：$p"; hint "執行：$cmd"
    fi
    return
  fi
  [ -z "$GIT_DIR" ] && { fail "[b] 目前目錄不是 git repo：$REPO（${GIT_ERR:-無錯誤訊息}）"; return; }
  # 在 DrvFs 上，即使現在沒報錯，也確認 safe.directory 已登記（Windows 端改權限後會突然報）
  local main_wt; main_wt=$(dirname "$COMMON_DIR")
  if is_drvfs "$main_wt"; then
    local have; have=$(git config --global --get-all safe.directory 2>/dev/null || true)
    local missing=() wts=()
    mapfile -t wts < <(list_worktree_paths)
    local p
    for p in "$main_wt" "${wts[@]}"; do
      printf '%s\n' "$have" | grep -qxF -- "$p" || printf '%s\n' "$have" | grep -qx '\*' || missing+=("$p")
    done
    if [ ${#missing[@]} -eq 0 ]; then ok "[b] safe.directory 已涵蓋主 checkout 與所有 worktree（/mnt 掛載）"
    else
      if [ "$MODE" = fix ]; then
        for p in "${missing[@]}"; do git config --global --add safe.directory "$p"; done
        fixed "[b] 補登 ${#missing[@]} 個 safe.directory"
      else
        warn "[b] /mnt 掛載上有 ${#missing[@]} 個路徑未登記 safe.directory（目前還沒報錯，但 Windows 端權限一變就會）"
        for p in "${missing[@]}"; do hint "git config --global --add safe.directory \"$p\""; done
      fi
    fi
  else
    ok "[b] repo 不在 /mnt 掛載上，不需 safe.directory"
  fi
}

list_worktree_paths() {  # 由 porcelain 列出非主 checkout 的 worktree 路徑（不含 bare/prunable 判斷）
  [ -z "$GIT_DIR" ] && return
  git -C "$REPO" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p' | tail -n +2
}

# ---------- [a] index.lock ----------
git_procs() { pgrep -x git 2>/dev/null | tr '\n' ' '; }
check_locks() {
  [ -z "$GIT_DIR" ] && return
  local locks=() d
  for d in "$COMMON_DIR" "$COMMON_DIR"/worktrees/*; do
    [ -d "$d" ] || continue
    for f in "$d/index.lock" "$d/HEAD.lock" "$d/config.lock" "$d/refs/heads"/*.lock "$d/packed-refs.lock"; do
      [ -e "$f" ] && locks+=("$f")
    done
  done
  if [ ${#locks[@]} -eq 0 ]; then ok "[a] 沒有殘留的 git lock 檔"; return; fi
  local f
  for f in "${locks[@]}"; do
    local size age procs
    size=$(stat -c %s "$f" 2>/dev/null || echo ?)
    age=$(( $(date +%s) - $(stat -c %Y "$f" 2>/dev/null || date +%s) ))
    procs=$(git_procs)
    if [ -n "$procs" ]; then
      # 退避等待：1,2,4,8 秒，期間 git 程序結束且 lock 消失就算正常
      local wait=1 total=0
      while [ -n "$procs" ] && [ $total -lt 15 ]; do
        sleep $wait; total=$((total+wait)); wait=$((wait*2))
        [ -e "$f" ] || break
        procs=$(git_procs)
      done
      if [ ! -e "$f" ]; then ok "[a] $f 在等待 ${total}s 後由 git 自行釋放"; continue; fi
      if [ -n "$procs" ]; then
        fail "[a] $f 仍被持有（git PID：$procs；等了 ${total}s）"; hint "等該 git 程序結束，或確認是殭屍程序後 kill 再重跑 doctor --fix"; continue
      fi
    fi
    # 走到這裡：沒有任何 git 程序存活 → 殘留
    if [ "$MODE" = fix ]; then
      rm -f -- "$f" && fixed "[a] 移除殘留 lock：$f（${size} byte，${age}s 前；無 git 程序）" || fail "[a] 無法移除 $f"
    else
      warn "[a] 殘留 lock：$f（${size} byte，${age}s 前；目前無 git 程序）"; hint "doctor.sh --fix 會移除；或手動 rm -f \"$f\""
    fi
  done
}

# ---------- [c] worktree 指標 ----------
check_worktrees() {
  [ -z "$GIT_DIR" ] && return
  local broken=() n gd target wtpath
  # 方向 1：.git/worktrees/<n>/gitdir → 該 worktree 的 .git 檔是否存在
  for n in "$COMMON_DIR"/worktrees/*/; do
    [ -d "$n" ] || continue
    gd=$(cat "$n/gitdir" 2>/dev/null || true)
    [ -z "$gd" ] && { broken+=("$(basename "$n")：gitdir 檔空白"); continue; }
    case "$gd" in /*) target="$gd";; *) target="$n/$gd";; esac
    [ -e "$target" ] || broken+=("$(basename "$n")：gitdir 指向不存在的 $gd")
  done
  # 方向 2：各 worktree 目錄的 .git 檔 → .git/worktrees/<n> 是否存在
  local candidates=() c wts=()
  mapfile -t wts < <(list_worktree_paths)
  for c in "${wts[@]}" "$(dirname "$COMMON_DIR")"/.claude/worktrees/*; do
    [ -d "$c" ] && [ -f "$c/.git" ] && candidates+=("$c")
  done
  # 去重
  mapfile -t candidates < <(printf '%s\n' "${candidates[@]}" | awk '!seen[$0]++')
  for c in "${candidates[@]}"; do
    [ -f "$c/.git" ] || continue
    gd=$(sed -n 's/^gitdir: //p' "$c/.git")
    case "$gd" in /*) target="$gd";; *) target="$c/$gd";; esac
    [ -d "$target" ] || broken+=("$(basename "$c")：.git 指向不存在的 $gd")
  done
  # 相對 vs 絕對
  local abs=0
  for n in "$COMMON_DIR"/worktrees/*/gitdir; do [ -f "$n" ] && grep -q '^/' "$n" && abs=$((abs+1)); done
  local rel_cfg; rel_cfg=$(git -C "$REPO" config --get worktree.useRelativePaths 2>/dev/null || echo unset)

  if [ ${#broken[@]} -eq 0 ]; then
    ok "[c] worktree 指標雙向都解析得到（$(list_worktree_paths | wc -l) 個 worktree）"
  else
    if [ "$MODE" = fix ]; then
      local out; out=$(git -C "$REPO" worktree repair "${candidates[@]}" 2>&1)
      # 修完再驗一次
      local still=0
      for c in "${candidates[@]}"; do [ -f "$c/.git" ] && ! git -C "$c" rev-parse --git-dir >/dev/null 2>&1 && still=$((still+1)); done
      if [ $still -eq 0 ]; then fixed "[c] git worktree repair 修好 ${#broken[@]} 個失效指標"; info "$out"
      else fail "[c] repair 後仍有 $still 個 worktree 打不開"; info "$out"; fi
    else
      fail "[c] ${#broken[@]} 個 worktree 指標失效（磁碟代號或路徑改變）"
      local b; for b in "${broken[@]}"; do hint "$b"; done
      hint "doctor.sh --fix 會跑：git worktree repair ${candidates[*]}"
    fi
  fi
  if [ "$abs" -gt 0 ] && is_drvfs "$(dirname "$COMMON_DIR")"; then
    if [ "$MODE" = fix ]; then
      git -C "$REPO" config worktree.useRelativePaths true && git -C "$REPO" worktree repair "${candidates[@]}" >/dev/null 2>&1 \
        && fixed "[c] 已設 worktree.useRelativePaths=true 並重寫為相對路徑（$abs 個原為絕對）"
    else
      warn "[c] $abs 個 worktree 指標是絕對路徑，/mnt 盤代號一變就斷（useRelativePaths=$rel_cfg）"
      hint "git config worktree.useRelativePaths true && git worktree repair .claude/worktrees/*"
    fi
  elif [ "$rel_cfg" != true ] && is_drvfs "$(dirname "$COMMON_DIR")"; then
    info "[c] 建議 git config worktree.useRelativePaths true（新 worktree 才會用相對路徑）"
  fi
}

# ---------- [d] Google Drive 同步延遲 ----------
check_drive_sync() {
  [ -z "$GIT_DIR" ] && return
  local f="$TOPLEVEL/$TODO_FILE"
  [ -f "$f" ] || { info "[d] 沒有 $TODO_FILE，略過同步比對"; return; }
  local branch upstream fetched="未 fetch"
  branch=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null)
  upstream=$(git -C "$REPO" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
  [ -z "$upstream" ] && git -C "$REPO" rev-parse --verify -q origin/dev >/dev/null && upstream=origin/dev
  if [ "$FETCH" = 1 ] && git -C "$REPO" remote get-url origin >/dev/null 2>&1; then
    if timeout 20 git -C "$REPO" fetch -q origin 2>/dev/null; then fetched="已 fetch"; else fetched="fetch 失敗（離線？）"; fi
  fi
  local h_wt h_head h_up m_file t_head
  h_wt=$(git -C "$REPO" hash-object "$f")
  h_head=$(git -C "$REPO" rev-parse -q --verify "HEAD:$TODO_FILE" 2>/dev/null || echo none)
  h_up=none; [ -n "$upstream" ] && h_up=$(git -C "$REPO" rev-parse -q --verify "$upstream:$TODO_FILE" 2>/dev/null || echo none)
  m_file=$(stat -c %Y "$f"); t_head=$(git -C "$REPO" log -1 --format=%ct -- "$TODO_FILE" 2>/dev/null || echo 0)

  info "[d] $TODO_FILE 工作區=$(short "$h_wt") HEAD=$(short "$h_head") ${upstream:-無上游}=$(short "$h_up")（$fetched）"
  local problems=0
  if [ -n "$upstream" ]; then
    local behind ahead
    behind=$(git -C "$REPO" rev-list --count "HEAD..$upstream" 2>/dev/null || echo 0)
    ahead=$(git -C "$REPO" rev-list --count "$upstream..HEAD" 2>/dev/null || echo 0)
    if [ "$behind" -gt 0 ]; then
      warn "[d] $branch 落後 $upstream $behind 個 commit（另一台機器／另一 session 推過）→ 規劃前先 git pull --ff-only"; problems=1
    fi
    [ "$ahead" -gt 0 ] && info "[d] $branch 領先 $upstream $ahead 個 commit（尚未 push）"
  fi
  if [ "$h_wt" != "$h_head" ]; then
    if [ "$h_wt" = "$h_up" ] && [ "$h_up" != none ]; then
      warn "[d] 工作區 $TODO_FILE 等於 $upstream 的版本但不等於 HEAD：像是 Drive 把別台機器的檔先同步過來、git 還沒跟上 → 先 git pull，不要直接編輯"; problems=1
    elif [ "$m_file" -lt "$t_head" ]; then
      warn "[d] 工作區 $TODO_FILE 與 HEAD 不同，且檔案 mtime（$(date -d @"$m_file" '+%F %T')）早於最後 commit（$(date -d @"$t_head" '+%F %T')）→ Google Drive 可能回寫了舊版，規劃前先 git diff $TODO_FILE 確認"; problems=1
    else
      info "[d] 工作區 $TODO_FILE 有未 commit 的修改（mtime 晚於最後 commit，正常編輯中）"
    fi
  fi
  if [ "$branch" != "HEAD" ] && [ "$h_wt" = "$h_head" ] && [ "$m_file" -lt $((t_head - 60)) ] && [ "$h_head" != none ]; then
    # 內容相同但 mtime 比 commit 早很多：Drive 以舊 mtime 回寫，常是同步延遲的前兆；只提示
    info "[d] $TODO_FILE mtime 早於 commit 時間但內容一致（Drive 保留了舊 mtime，無害）"
  fi
  [ $problems -eq 0 ] && ok "[d] $TODO_FILE 無 Google Drive 同步延遲跡象（HEAD 未落後${upstream:+ $upstream}）"
}

# ---------- [e] 相依套件 ----------
check_deps() {
  local need="git jq python3 node" missing=() b
  # statusline 腳本裡實際用到的指令也納入
  local sl; sl=$(python3 - <<'PY' 2>/dev/null
import json,os
p=os.path.expanduser('~/.claude/settings.json')
try:
    d=json.load(open(p)); c=d.get('statusLine',{}).get('command','')
    print(c.split()[0] if c else '')
except Exception: print('')
PY
)
  if [ -n "$sl" ] && [ -f "$sl" ]; then
    for b in jq python3 node bc; do grep -qE "(^|[^[:alnum:]_])$b([^[:alnum:]_]|$)" "$sl" && need="$need $b"; done
  fi
  for b in $(printf '%s\n' $need | sort -u); do command -v "$b" >/dev/null 2>&1 || missing+=("$b"); done
  if [ ${#missing[@]} -eq 0 ]; then ok "[e] 相依套件齊全：$(printf '%s\n' $need | sort -u | tr '\n' ' ')"; return; fi
  local apt=()
  for b in "${missing[@]}"; do case "$b" in node) apt+=(nodejs);; *) apt+=("$b");; esac; done
  if [ "$MODE" = fix ] && sudo -n true 2>/dev/null; then
    sudo -n apt-get install -y "${apt[@]}" >/dev/null 2>&1 && { fixed "[e] 已安裝：${missing[*]}"; return; }
  fi
  fail "[e] 缺套件：${missing[*]}${sl:+（statusline：$sl 會用到）}"
  hint "sudo apt-get install -y ${apt[*]}"
}

# ---------- [f] worker agent 定義 ----------
check_agents() {
  local a n=0 miss=()
  for a in "$PLUGIN_ROOT"/agents/worker-*.md "$PLUGIN_ROOT"/agents/verifier-*.md; do
    [ -f "$a" ] || continue; n=$((n+1))
    grep -q "一個簡單指令" "$a" || miss+=("$(basename "$a")")
  done
  [ $n -eq 0 ] && { info "[f] 找不到 agent 定義（PLUGIN_ROOT=$PLUGIN_ROOT）"; return; }
  if [ ${#miss[@]} -eq 0 ]; then ok "[f] $n 個 agent 定義都含「每次呼叫只送一個簡單指令」指引"
  else fail "[f] agent 定義缺指引：${miss[*]}"; hint "在該檔加上 ## Bash 指令規則 區段（見 worker-sonnet.md）"; fi
}

check_ownership
check_locks
check_worktrees
check_drive_sync
check_deps
check_agents

# ---------- 輸出 ----------
summary="doctor：OK $N_OK／WARN $N_WARN／FAIL $N_FAIL／FIXED $N_FIXED（mode=$MODE，repo=${TOPLEVEL:-$REPO}）"
if [ "$HOOK" = 1 ]; then
  if [ $((N_WARN+N_FAIL)) -eq 0 ]; then
    [ "$QUIET" = 1 ] || echo "[task-workflow] 環境醫生：全部正常（$N_OK 項）"
  else
    echo "[task-workflow] 環境醫生發現問題，規劃前先處理："
    for l in "${LINES[@]}"; do case "$l" in OK*) ;; *) echo "  $l";; esac; done
    echo "  修復：\"$PLUGIN_ROOT/tools/doctor.sh\" --fix"
  fi
  exit 0
fi
for l in "${LINES[@]}"; do echo "$l"; done
echo "$summary"
[ $N_FAIL -gt 0 ] && exit 2
[ $N_WARN -gt 0 ] && exit 1
exit 0
