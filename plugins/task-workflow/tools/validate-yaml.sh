#!/usr/bin/env bash
# validate-yaml.sh <檔案> — 以 UTF-8 解析 YAML（PyYAML），跨平台。
#   exit 0：解析成功；1：YAML 有錯；2：用法錯誤／找不到檔案；3：沒有可用的 PyYAML（不算通過）。
# Python 依序試：TW_YAML_PY（指定有 PyYAML 的 python，路徑不可含空白）→ BN-RD-AIServer 的 conda NAS（存在才用）→ pick_py。
# 一律以 UTF-8 開檔：cp950 主控台下 `yaml.safe_load(sys.stdin) < 檔案` 會把合法的中文 YAML 誤判成 ReaderError。
set -u
F="${1:-}"
[ -n "$F" ] || { echo "用法：validate-yaml.sh <檔案>" >&2; exit 2; }
[ -f "$F" ] || { echo "找不到 $F" >&2; exit 2; }
# shellcheck source=lib/platform.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/platform.sh"
cands=()
[ -n "${TW_YAML_PY:-}" ] && cands+=("$TW_YAML_PY")
NAS_PY=/home/nas/miniconda3/envs/NAS/bin/python
[ -x "$NAS_PY" ] && cands+=("$NAS_PY")
PY=$(pick_py) && cands+=("$PY")
for c in "${cands[@]}"; do
  # shellcheck disable=SC2086
  $c -X utf8 -c 'import yaml' >/dev/null 2>&1 || continue
  # shellcheck disable=SC2086
  if $c -X utf8 -c 'import sys, yaml; yaml.safe_load(open(sys.argv[1], encoding="utf-8"))' "$F"; then
    echo "YAML OK（$c）"; exit 0
  fi
  echo "YAML 解析錯誤：$F" >&2; exit 1
done
echo "沒有可用的 PyYAML（試過：${cands[*]:-無}）。安裝：${PY:-python} -m pip install --user pyyaml；或逐欄人工核對，並在回報中註明未經解析器驗證。" >&2
exit 3
