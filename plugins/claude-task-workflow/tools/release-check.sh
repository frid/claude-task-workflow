#!/usr/bin/env bash
# release 前本機測試閘門：在專案根目錄跑 npm test，以 exit code 判定，印 PASS 才能 release。
# 用法：release-check.sh [專案根目錄]   預設目前目錄。
set -e
cd "${1:-.}"
[ -f package.json ] || { echo "RELEASE CHECK: 找不到 package.json，略過" >&2; exit 2; }

if [ ! -d node_modules ]; then
  npm install
  [ -d node_modules/@playwright/test ] && node node_modules/@playwright/test/cli.js install chromium
fi

if npm test; then
  echo "RELEASE CHECK: PASS"
else
  echo "RELEASE CHECK: FAIL"
  exit 1
fi
