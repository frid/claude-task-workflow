#!/usr/bin/env bash
# clear-stale-lock.sh [repo 或 worktree 目錄] — 只在「確定沒有 git 程序」時清掉殘留的 index.lock。
#   每個 worktree 的 git-dir 不同（.git/worktrees/<名>/index.lock），以 git rev-parse --git-dir 定位。
#   跨平台判斷見 lib/procs.sh：Linux／WSL 用 pgrep，Windows Git Bash 用 tasklist；判斷不了就不刪。
# exit 0：沒有 lock，或已移除殘留；exit 2：有 git 在跑、無法判斷、或不是 repo（不刪，stderr 說明）。
set -u
DIR="${1:-$PWD}"
LIB="$(cd "$(dirname "$0")" && pwd)/lib/procs.sh"
# shellcheck source=lib/procs.sh
[ -f "$LIB" ] && . "$LIB" || { echo "[git-lock] 缺 $LIB，無法判斷 lock 是否殘留；不刪。" >&2; exit 2; }
GD=$(git -C "$DIR" rev-parse --git-dir 2>/dev/null) || { echo "[git-lock] 不是 git repo：$DIR" >&2; exit 2; }
case "$GD" in /*|[A-Za-z]:/*|[A-Za-z]:\\*) ;; *) GD="$DIR/$GD";; esac
LOCK="$GD/index.lock"
[ -e "$LOCK" ] || { echo "[git-lock] 沒有 index.lock：$GD"; exit 0; }
remove_stale_lock "$LOCK" "${TW_LOCK_MAX_WAIT:-7}"
