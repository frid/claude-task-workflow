#!/usr/bin/env bash
# 抽出單檔 HTML 內嵌 <script>（排除有 src 的）接成一支 JS，跑 node --check。
# 用法：check-js.sh [HTML 路徑]   預設目前目錄的 index.html。印 "JS OK" 且 exit 0 才算過。
set -e
HTML="${1:-./index.html}"
[ -f "$HTML" ] || { echo "找不到 $HTML" >&2; exit 2; }
OUT="${CLAUDE_JOB_DIR:-/tmp}/tmp/_check_js_$$.js"
mkdir -p "$(dirname "$OUT")"
python3 - "$HTML" "$OUT" <<'PY'
import re, sys, pathlib
html = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
js = "\n;\n".join(re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S))
pathlib.Path(sys.argv[2]).write_text(js, encoding="utf-8")
PY
node --check "$OUT" && echo "JS OK"
rm -f "$OUT"
