#!/usr/bin/env bash
# git-guard.sh — PreToolUse(Bash) 輕量守護：只在指令含 git 時動作
#   1. 殘留 index.lock：無 git 程序持有 → 直接移除（退避等待最多 ~7s）；仍被持有 → exit 2 擋下並說明
#   2. dubious ownership：git 在 cwd 打不開 → exit 2 擋下，附確切的 safe.directory 指令
# stdin：Claude Code hook JSON（tool_input.command、cwd）。不依賴 jq：jq → python3 → node → sed 擇一。
# exit 0 放行；exit 2 擋下（stderr 會回給 Claude）。永不超過幾秒。
set -u
INPUT=$(cat)
json_get() {  # json_get <key path a.b.c>
  local path="$1"
  if command -v jq >/dev/null 2>&1; then printf '%s' "$INPUT" | jq -r ".$path // empty" 2>/dev/null; return; fi
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$INPUT" | python3 -c 'import json,sys
d=json.load(sys.stdin)
for k in sys.argv[1].split("."): d=d.get(k,{}) if isinstance(d,dict) else {}
print(d if isinstance(d,str) else "")' "$path" 2>/dev/null; return
  fi
  if command -v node >/dev/null 2>&1; then
    printf '%s' "$INPUT" | node -e 'let s="";process.stdin.on("data",c=>s+=c).on("end",()=>{let d=JSON.parse(s);for(const k of process.argv[1].split("."))d=(d&&typeof d==="object")?d[k]:undefined;process.stdout.write(typeof d==="string"?d:"")})' "$path" 2>/dev/null; return
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
  echo "[git-guard] git 回報 dubious ownership（/mnt 掛載的 Windows 權限）。先執行這一行再重試：" >&2
  echo "git config --global --add safe.directory \"${P:-$CWD}\"" >&2
  exit 2
fi
GIT_DIR=$(git -C "$CWD" rev-parse --git-dir 2>/dev/null) || exit 0   # 不是 repo 就放行
GIT_DIR=$(cd "$CWD" && cd "$GIT_DIR" && pwd)

# ---- index.lock ----
LOCK="$GIT_DIR/index.lock"
[ -e "$LOCK" ] || exit 0
wait=1; total=0
while pgrep -x git >/dev/null 2>&1 && [ $total -lt 7 ]; do
  sleep $wait; total=$((total+wait)); wait=$((wait*2))
  [ -e "$LOCK" ] || exit 0
done
if pgrep -x git >/dev/null 2>&1; then
  echo "[git-guard] $LOCK 仍被 git 程序持有（PID $(pgrep -x git | tr '\n' ' ')；已等 ${total}s）。等它結束再重試，不要 rm。" >&2
  exit 2
fi
SIZE=$(stat -c %s "$LOCK" 2>/dev/null || echo ?)
if rm -f -- "$LOCK"; then
  echo "[git-guard] 已移除殘留 $LOCK（${SIZE} byte，無 git 程序）；放行。" >&2
  exit 0
fi
echo "[git-guard] 無法移除 $LOCK，請手動處理。" >&2
exit 2
