#!/usr/bin/env bash
# git-guard.sh — PreToolUse(Bash|PowerShell) 輕量守護：只在指令含 git 時動作（PowerShell 的 git 指令也經過這裡）
#   1. 殘留 index.lock：確定無 git 程序 → 移除（退避等待最多 ~7s）；仍被持有或無法判斷 → exit 2 擋下並說明
#      （程序偵測跨平台：pgrep／Windows tasklist／ps -W，見 tools/lib/procs.sh）
#   2. dubious ownership：git 在 cwd 打不開 → exit 2 擋下，附確切的 safe.directory 指令
# stdin：Claude Code hook JSON（tool_input.command、cwd）。不依賴 jq：jq → python（pick_py：python3／python／py -3，實際執行確認）→ node → sed。
# exit 0 放行；exit 2 擋下（stderr 會回給 Claude）。永不超過幾秒。
set -u
INPUT=$(cat)
LIBDIR="$(cd "$(dirname "$0")/.." && pwd)/tools/lib"
# shellcheck source=../tools/lib/platform.sh
. "$LIBDIR/platform.sh" 2>/dev/null || pick_py() { command -v python3 >/dev/null 2>&1 && echo python3; }
json_get() {  # json_get <key path a.b.c>：jq → python → node → sed；前一個「執行失敗」才換下一個（不只看指令存不存在）
  local path="$1" out PY
  if command -v jq >/dev/null 2>&1 && out=$(printf '%s' "$INPUT" | jq -r ".$path // empty" 2>/dev/null); then printf '%s' "$out"; return; fi
  if PY=$(pick_py); then
    # shellcheck disable=SC2086
    if out=$(printf '%s' "$INPUT" | $PY -X utf8 -c 'import json,sys
d=json.load(sys.stdin)
for k in sys.argv[1].split("."): d=d.get(k,{}) if isinstance(d,dict) else {}
print(d if isinstance(d,str) else "")' "$path" 2>/dev/null); then printf '%s' "$out"; return; fi
  fi
  if command -v node >/dev/null 2>&1 && out=$(printf '%s' "$INPUT" | node -e 'let s="";process.stdin.on("data",c=>s+=c).on("end",()=>{let d=JSON.parse(s);for(const k of process.argv[1].split("."))d=(d&&typeof d==="object")?d[k]:undefined;process.stdout.write(typeof d==="string"?d:"")})' "$path" 2>/dev/null); then
    printf '%s' "$out"; return
  fi
  local key="${path##*.}"
  printf '%s' "$INPUT" | sed -n "s/.*\"$key\"[[:space:]]*:[[:space:]]*\"\(\([^\"\\\\]\|\\\\.\)*\)\".*/\1/p" | head -1
}
CMD=$(json_get tool_input.command)
case "$CMD" in *git*) ;; *) exit 0;; esac
CWD=$(json_get cwd); [ -d "${CWD:-}" ] || CWD="$PWD"

# ---- dubious ownership ----
ERR=$(git -C "$CWD" rev-parse --git-dir 2>&1 >/dev/null)
if printf '%s' "$ERR" | grep -q "dubious ownership"; then
  P=$(printf '%s' "$ERR" | sed -n "s/.*repository at '\([^']*\)'.*/\1/p" | head -1)
  echo "[git-guard] git 回報 dubious ownership（repo 擁有者和目前使用者不同：常見於 WSL /mnt 掛載、雲端硬碟、或別的 Windows 帳號建立的 repo）。先執行這一行再重試：" >&2
  echo "git config --global --add safe.directory \"${P:-$CWD}\"" >&2
  exit 2
fi
GIT_DIR=$(git -C "$CWD" rev-parse --git-dir 2>/dev/null) || exit 0   # 不是 repo 就放行
GIT_DIR=$(cd "$CWD" && cd "$GIT_DIR" && pwd)

# ---- index.lock ----
LOCK="$GIT_DIR/index.lock"
[ -e "$LOCK" ] || exit 0
# 是否有 git 在跑：跨平台判斷（pgrep／tasklist／ps -W），判斷不了就不刪 → 見 tools/lib/procs.sh
LIB="$LIBDIR/procs.sh"
if [ -f "$LIB" ]; then
  # shellcheck source=../tools/lib/procs.sh
  . "$LIB"
  remove_stale_lock "$LOCK" 7
  exit $?
fi
echo "[git-guard] 缺 $LIB，無法判斷 $LOCK 是否殘留；不刪。確認沒有 git 在跑後再手動刪。" >&2
exit 2
