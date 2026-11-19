#!/usr/bin/env bash
# task-workflow verifier 用：乾淨 checkout 重跑全套＋比對 spec hash，一次呼叫做完（1.12.0）。
# 為什麼：verifier 自己把 git worktree add、cd、cp、hash-object、npm test 串成一長串，
# 一週被 worktree 隔離守門擋下約 80 次（「too complex to verify」），每次都要重想重送。
#
# 用法：
#   verify-clean.sh --repo <repo 根目錄> --ref <分支或 commit> --name <代號> --test "<測試指令>"
#                   [--spec <相對路徑>=<hash>]... [--since <planner commit>] [--node-modules <來源目錄>] [--keep]
#   --spec   可重複；比對乾淨 checkout 裡該檔的 git hash-object
#   --since  給了就檢查 <since>..<ref> 之間沒有任何 commit 動到這些 spec
#   --node-modules  預設 <repo>/node_modules；存在才複製（cp -rL，不用 symlink／junction）
#   --keep   保留 checkout（預設跑完 git worktree remove --force）
# checkout 位置：$CLAUDE_JOB_DIR/tmp/verify-<代號>；沒有 CLAUDE_JOB_DIR 時 <repo>/.claude/worktrees/verify-<代號>。
# 輸出：spec 比對表、測試輸出最後 30 行、最後一行 `VERIFY-CLEAN: PASS|FAIL（原因）`。
# exit：0 PASS、1 FAIL、2 用法錯誤。
set -u

REPO="" REF="" NAME="" TEST="" SINCE="" NM="" KEEP=0
SPECS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --test) TEST="$2"; shift 2 ;;
    --spec) SPECS+=("$2"); shift 2 ;;
    --since) SINCE="$2"; shift 2 ;;
    --node-modules) NM="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "verify-clean: 不認得的參數 $1" >&2; exit 2 ;;
  esac
done
if [ -z "$REPO" ] || [ -z "$REF" ] || [ -z "$NAME" ] || [ -z "$TEST" ]; then
  echo "verify-clean: 需要 --repo --ref --name --test（--help 看用法）" >&2; exit 2
fi
case "$NAME" in *[!A-Za-z0-9._-]*) echo "verify-clean: --name 只能用英數 . _ -" >&2; exit 2 ;; esac
REPO="$(cd "$REPO" 2>/dev/null && pwd)" || { echo "verify-clean: repo 不存在" >&2; exit 2; }
git -C "$REPO" rev-parse --verify -q "$REF^{commit}" >/dev/null || { echo "verify-clean: 找不到 ref $REF" >&2; exit 2; }

if [ -n "${CLAUDE_JOB_DIR:-}" ]; then DEST="$CLAUDE_JOB_DIR/tmp/verify-$NAME"; else DEST="$REPO/.claude/worktrees/verify-$NAME"; fi
mkdir -p "$(dirname "$DEST")"
if [ -e "$DEST" ]; then git -C "$REPO" worktree remove --force "$DEST" >/dev/null 2>&1 || rm -rf "$DEST"; fi
git -C "$REPO" worktree prune >/dev/null 2>&1
git -C "$REPO" worktree add -q --detach "$DEST" "$REF" || { echo "VERIFY-CLEAN: FAIL（worktree add 失敗）"; exit 1; }
cleanup() { [ "$KEEP" = 1 ] || git -C "$REPO" worktree remove --force "$DEST" >/dev/null 2>&1; }
trap cleanup EXIT

echo "== 乾淨 checkout：$DEST（$(git -C "$DEST" log --oneline -1)）"
NM="${NM:-$REPO/node_modules}"
if [ -d "$NM" ] && [ ! -e "$DEST/node_modules" ]; then
  cp -rL --no-preserve=links "$NM" "$DEST/node_modules" 2>/dev/null || cp -R "$NM" "$DEST/node_modules"
  echo "== 已複製 node_modules（$NM）"
fi

FAIL=""
if [ ${#SPECS[@]} -gt 0 ]; then
  echo "== spec hash 比對"
  for s in "${SPECS[@]}"; do
    p="${s%%=*}"; want="${s#*=}"
    if [ ! -f "$DEST/$p" ]; then echo "  缺檔   $p"; FAIL="${FAIL}spec 缺檔；"; continue; fi
    got="$(git -C "$DEST" hash-object "$p")"
    if [ "$got" = "$want" ]; then echo "  相同   $p $got"; else echo "  不同   $p 期望 $want 實際 $got"; FAIL="${FAIL}spec hash 不同 $p；"; fi
    if [ -n "$SINCE" ]; then
      later="$(git -C "$DEST" log --format='%h %s' "$SINCE..HEAD" -- "$p")"
      if [ -n "$later" ]; then echo "  $SINCE 之後仍有 commit 改 $p："; echo "$later" | sed 's/^/    /'; FAIL="${FAIL}planner 之後有 commit 改 $p；"; fi
    fi
  done
fi

LOG="$(dirname "$DEST")/verify-$NAME.log"
echo "== 測試：$TEST"
start=$(date +%s)
( cd "$DEST" && bash -c "$TEST" ) >"$LOG" 2>&1
rc=$?
echo "== 最後 30 行（完整輸出 $LOG，exit $rc，$(( $(date +%s) - start ))s）"
tail -n 30 "$LOG"
[ "$rc" = 0 ] || FAIL="${FAIL}測試 exit $rc；"

if [ -z "$FAIL" ]; then echo "VERIFY-CLEAN: PASS"; exit 0; fi
echo "VERIFY-CLEAN: FAIL（${FAIL%；}）"
exit 1
