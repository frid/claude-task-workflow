#!/usr/bin/env python3
"""task-workflow optimization：對話紀錄耗時統計（只讀）。

讀 ~/.claude/projects/<專案>/<session>.jsonl 與 <session>/subagents/agent-*.jsonl(+.meta.json)，
輸出 Markdown 報告：各 session／subagent 類型的掛鐘與模型生成時間、工具耗時排行、測試指令次數、
被守門擋下的指令、sleep／until 輪詢、契約檔重寫次數、主 session context 峰值。

資安：只輸出統計值、工具名、指令「第一個詞」與形狀特徵；不輸出 prompt 原文、完整指令或檔案內容。

用法：
  python3 -X utf8 transcript-stats.py [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                                      [--root ~/.claude/projects] [--project 子字串] [--json 輸出檔]
  預設 --since 為 7 天前。exit 0；找不到任何紀錄 exit 3。
"""
import argparse
import collections
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

BLOCK_RE = re.compile(r"too complex to verify|names git in a form|redirects git to the shared checkout|^<tool_use_error>Blocked:", re.I)
POLL_RE = re.compile(r"\bsleep\s+\d|\buntil\b|\bwhile\b[^\n]*\bsleep\b")
TEST_RE = re.compile(r"\bnpm (run )?test\b|\bnode --test\b|\bpytest\b|\bplaywright test\b|tests?/[\w./-]*\.sh\b|\bgo test\b|\bcargo test\b")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def load(path):
    out = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def bash_key(cmd):
    """指令分類鍵：只取第一個有意義的詞（測試指令統一成一類），不含參數。"""
    c = re.sub(r"^(\s*cd\s+[^&;|]+(&&|;)\s*)+", "", cmd.strip())
    if TEST_RE.search(c):
        m = TEST_RE.search(c)
        return "test:" + re.sub(r"tests?/[\w./-]*\.sh", "tests/*.sh", m.group(0))
    if POLL_RE.search(c):
        return "poll(sleep/until)"
    toks = c.split()
    if not toks:
        return "?"
    head = os.path.basename(toks[0])
    if head in ("git", "npm", "node", "docker", "python3", "python", "bash") and len(toks) > 1:
        sub = toks[1] if not toks[1].startswith("-") else (toks[1] if toks[1] in ("-C", "-c") else "")
        return f"{head} {sub}".strip() if not sub.startswith("/") else head
    if re.search(r"chrom|headless", c):
        return "chrome"
    return head[:24]


def shape(cmd):
    feats = []
    if "&&" in cmd or ";" in cmd:
        feats.append("串接")
    if "|" in cmd.replace("||", ""):
        feats.append("管線")
    if "<<" in cmd:
        feats.append("heredoc")
    if re.search(r"git -C\b", cmd):
        feats.append("git -C")
    if re.search(r"(^|\s)cd\s", cmd):
        feats.append("cd")
    if "$(" in cmd:
        feats.append("$()")
    if re.search(r"\b(for|while)\b", cmd):
        feats.append("迴圈")
    if re.search(r"\bsleep\b", cmd):
        feats.append("sleep")
    return "+".join(feats) or "單一指令"


def agent_type(path):
    meta = path[:-6] + ".meta.json"
    if os.path.exists(meta):
        try:
            with open(meta, encoding="utf-8") as f:
                m = json.load(f)
            return m.get("agentType") or "?", m.get("description", "")
        except (OSError, json.JSONDecodeError):
            pass
    return "?", ""


def analyze(root, since, until, project=None):
    files = sorted(set(glob.glob(os.path.join(root, "*", "*.jsonl")) + glob.glob(os.path.join(root, "*", "*", "subagents", "*.jsonl"))))
    R = {
        "sessions": [], "subagents": [],
        "tool": collections.defaultdict(lambda: [0, 0.0, 0.0]),
        "model": collections.defaultdict(lambda: collections.Counter()),
        "blocked": collections.Counter(), "blocked_shape": collections.Counter(), "blocked_reason": collections.Counter(),
        "poll": [0, 0.0], "bg_bash": 0, "spec_writes": collections.Counter(), "spec_chars": collections.Counter(),
        "max_ctx": 0, "files": 0,
    }
    rel = len(os.path.normpath(root).split(os.sep))
    for f in files:
        proj = os.path.normpath(f).split(os.sep)[rel]
        if project and project not in proj:
            continue
        recs = load(f)
        msgs = [r for r in recs if r.get("type") in ("user", "assistant") and r.get("timestamp")]
        msgs = [r for r in msgs if since <= r["timestamp"][:10] <= until]
        if not msgs:
            continue
        R["files"] += 1
        is_sub = "/subagents/" in f.replace(os.sep, "/")
        kind, desc = agent_type(f) if is_sub else ("MAIN", "")
        calls, prev, seen = {}, None, set()
        mc = R["model"][kind]
        for r in msgs:
            content = (r.get("message") or {}).get("content")
            if r["type"] == "assistant":
                mid = r["message"].get("id")
                if prev is not None:
                    dt = ts(r["timestamp"]) - ts(prev["timestamp"])
                    if 0 <= dt < 900:
                        mc["model_s"] += dt
                if mid not in seen:
                    seen.add(mid)
                    u = r["message"].get("usage") or {}
                    mc["out_tok"] += u.get("output_tokens", 0)
                    ctx = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                    mc["ctx_tok"] += ctx
                    if kind == "MAIN":
                        R["max_ctx"] = max(R["max_ctx"], ctx)
                if isinstance(content, list):
                    for b in content:
                        if b.get("type") != "tool_use":
                            continue
                        calls[b["id"]] = (r["timestamp"], b)
                        inp = b.get("input") or {}
                        if b["name"] == "Bash" and inp.get("run_in_background"):
                            R["bg_bash"] += 1
                        if b["name"] in ("Write", "Edit"):
                            p = str(inp.get("file_path", ""))
                            if re.search(r"(^|/)tests?/", p):
                                R["spec_writes"][os.path.basename(p)] += 1
                                R["spec_chars"][os.path.basename(p)] += len(json.dumps(inp, ensure_ascii=False))
            elif isinstance(content, list):
                for b in content:
                    if b.get("type") != "tool_result" or b.get("tool_use_id") not in calls:
                        continue
                    t0, call = calls[b["tool_use_id"]]
                    dt = ts(r["timestamp"]) - ts(t0)
                    if dt < 0 or dt > 7200:
                        continue
                    name = call["name"]
                    cmd = (call.get("input") or {}).get("command", "") if name == "Bash" else ""
                    key = name
                    if name == "Bash":
                        key = "Bash:" + bash_key(cmd)
                    elif name in ("Agent", "Task"):
                        key = "Agent:" + str((call.get("input") or {}).get("subagent_type", "general"))
                    t = R["tool"][key]
                    t[0] += 1
                    t[1] += dt
                    t[2] = max(t[2], dt)
                    if name == "Bash" and POLL_RE.search(cmd):
                        R["poll"][0] += 1
                        R["poll"][1] += dt
                    text = b.get("content")
                    text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
                    if b.get("is_error") and BLOCK_RE.search(text):
                        R["blocked"][kind] += 1
                        R["blocked_shape"][shape(cmd)] += 1
                        m = BLOCK_RE.search(text)
                        R["blocked_reason"][m.group(0).replace("<tool_use_error>", "")] += 1
            prev = r
        t0, t1 = ts(msgs[0]["timestamp"]), ts(msgs[-1]["timestamp"])
        if is_sub:
            R["subagents"].append({"project": proj, "type": kind, "desc": desc[:50], "wall_s": t1 - t0, "start": msgs[0]["timestamp"][:16]})
        else:
            active = sum(r.get("durationMs", 0) for r in recs if r.get("subtype") == "turn_duration" and since <= r.get("timestamp", "")[:10] <= until) / 1000
            humans = sum(1 for r in msgs if r["type"] == "user" and (r.get("origin") or {}).get("kind") == "human")
            title = next((r.get("aiTitle") for r in recs if r.get("type") == "ai-title" and r.get("aiTitle")), "")
            R["sessions"].append({"project": proj, "id": os.path.basename(f)[:8], "start": msgs[0]["timestamp"][:16], "wall_s": t1 - t0, "active_s": active, "prompts": humans, "title": title[:40]})
    return R


def H(s):
    return f"{s / 3600:.1f}h" if s >= 3600 else f"{s / 60:.0f}m" if s >= 60 else f"{s:.0f}s"


def summary(R):
    """固定欄位的指標摘要；欄位名稱不要改，報告靠它逐期比對。"""
    subs = collections.defaultdict(list)
    for s in R["subagents"]:
        subs[s["type"].split(":")[-1]].append(s["wall_s"])
    tests = [v for k, v in R["tool"].items() if k.startswith("Bash:test:")]
    avg = lambda xs: H(sum(xs) / len(xs)) if xs else "-"
    return {
        "主 session 模型生成時間": H(R["model"]["MAIN"]["model_s"]) if "MAIN" in R["model"] else "-",
        "主 session context 峰值（tokens）": f"{R['max_ctx']:,}",
        "subagent 掛鐘合計": H(sum(s["wall_s"] for s in R["subagents"])),
        "planner 次數／平均掛鐘": f"{len(subs.get('planner-opus', []))}／{avg(subs.get('planner-opus', []))}",
        "worker 次數／平均掛鐘": f"{sum(len(v) for k, v in subs.items() if k.startswith('worker'))}／{avg([x for k, v in subs.items() if k.startswith('worker') for x in v])}",
        "verifier 次數／平均掛鐘": f"{len(subs.get('verifier-sonnet', []))}／{avg(subs.get('verifier-sonnet', []))}",
        "測試指令次數／合計時間": f"{sum(t[0] for t in tests)}／{H(sum(t[1] for t in tests))}",
        "被隔離守門擋下次數": str(sum(R["blocked"].values())),
        "sleep／until 輪詢次數／時間": f"{R['poll'][0]}／{H(R['poll'][1])}",
        "契約檔最多重寫次數": str(max(R["spec_writes"].values(), default=0)),
    }


def report(R, since, until):
    out = [f"# 對話紀錄耗時統計 {since}～{until}", "", f"紀錄檔 {R['files']} 個；主 session {len(R['sessions'])} 個；subagent {len(R['subagents'])} 個；主 session context 峰值 {R['max_ctx']:,} tokens", ""]
    out += ["## 0. 指標摘要（固定欄位，optimization 報告逐期比對用）", "", "| 指標 | 值 |", "|---|---|"]
    for k, v in summary(R).items():
        out.append(f"| {k} | {v} |")
    out.append("")
    out += ["## 1. 模型生成時間（依 agent 類型）", "", "| 類型 | 生成時間 | 輸出 tokens | 讀入 context tokens |", "|---|---|---|---|"]
    for k, c in sorted(R["model"].items(), key=lambda x: -x[1]["model_s"]):
        out.append(f"| {k} | {H(c['model_s'])} | {c['out_tok']:,} | {c['ctx_tok'] / 1e6:.1f}M |")
    out += ["", "## 2. subagent 掛鐘時間（依類型）", "", "| 類型 | 次數 | 合計 | 平均 |", "|---|---|---|---|"]
    bt = collections.defaultdict(lambda: [0, 0.0])
    for s in R["subagents"]:
        bt[s["type"]][0] += 1
        bt[s["type"]][1] += s["wall_s"]
    for k, (n, tot) in sorted(bt.items(), key=lambda x: -x[1][1]):
        out.append(f"| {k} | {n} | {H(tot)} | {H(tot / n)} |")
    out += ["", "最久的 10 個 subagent：", ""]
    for s in sorted(R["subagents"], key=lambda s: -s["wall_s"])[:10]:
        out.append(f"- {H(s['wall_s'])} {s['start']} `{s['type']}` {s['desc']}（{s['project']}）")
    out += ["", "## 3. 主 session", "", "| 專案 | session | 開始 | 掛鐘 | 執行中 | 使用者 prompt | 標題 |", "|---|---|---|---|---|---|---|"]
    for s in sorted(R["sessions"], key=lambda s: -s["active_s"])[:15]:
        out.append(f"| {s['project']} | {s['id']} | {s['start']} | {H(s['wall_s'])} | {H(s['active_s'])} | {s['prompts']} | {s['title']} |")
    out += ["", "## 4. 工具耗時排行（同步呼叫，主＋subagent）", "", "| 工具：指令類 | 次數 | 合計 | 平均 | 最長 |", "|---|---|---|---|---|"]
    for k, (n, tot, mx) in sorted(R["tool"].items(), key=lambda x: -x[1][1])[:25]:
        out.append(f"| {k} | {n} | {H(tot)} | {tot / n:.1f}s | {mx:.0f}s |")
    tests = {k: v for k, v in R["tool"].items() if k.startswith("Bash:test:")}
    out += ["", "## 5. 測試指令", ""]
    for k, (n, tot, mx) in sorted(tests.items(), key=lambda x: -x[1][1]):
        out.append(f"- `{k[10:]}`：{n} 次、合計 {H(tot)}、平均 {tot / n:.1f}s、最長 {mx:.0f}s")
    if not tests:
        out.append("- 無")
    out += ["", "## 6. 被隔離守門擋下的指令", "", f"合計 {sum(R['blocked'].values())} 次。", ""]
    out.append("- 依 agent：" + ("、".join(f"{k} {v}" for k, v in R["blocked"].most_common()) or "無"))
    out.append("- 依原因：" + ("、".join(f"{k} {v}" for k, v in R["blocked_reason"].most_common()) or "無"))
    out.append("- 依指令形狀：" + ("、".join(f"{k} {v}" for k, v in R["blocked_shape"].most_common(8)) or "無"))
    out += ["", "## 7. 等待與輪詢", "", f"- sleep／until 輪詢：{R['poll'][0]} 次、合計 {H(R['poll'][1])}", f"- run_in_background 的 Bash：{R['bg_bash']} 次", ""]
    out += ["## 8. 測試檔寫入（契約檔重寫）", "", "| 檔名 | Write／Edit 次數 | 寫入字元 |", "|---|---|---|"]
    for k, n in R["spec_writes"].most_common(12):
        out.append(f"| {k} | {n} | {R['spec_chars'][k]:,} |")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--since", default=(datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"))
    ap.add_argument("--until", default="9999-12-31")
    ap.add_argument("--project", default=None, help="只看資料夾名含此子字串的專案")
    ap.add_argument("--json", default=None, help="另存原始統計（JSON）")
    a = ap.parse_args(argv)
    R = analyze(a.root, a.since, a.until, a.project)
    if not R["files"]:
        print(f"找不到 {a.since}～{a.until} 的對話紀錄（{a.root}）", file=sys.stderr)
        return 3
    sys.stdout.write(report(R, a.since, a.until if a.until != "9999-12-31" else datetime.now().strftime("%Y-%m-%d")))
    if a.json:
        dump = {k: (dict(v) if isinstance(v, (collections.Counter, collections.defaultdict)) else v) for k, v in R.items()}
        dump["model"] = {k: dict(v) for k, v in R["model"].items()}
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(dump, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
