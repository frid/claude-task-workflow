"""驗收契約：OPT-01 workflow-optimization skill 與 1.12.0 流程優化。

來源：2026-11-13～19 對話紀錄耗時分析（5 個專案、72 個紀錄檔）——
planner-opus 17 次共 2.1h；測試指令 326 次共 1.2h（frontpage 一支測試等 Chrome keyring 25 秒）；
被 worktree 隔離守門擋下 110 次（verifier 佔七成）；sleep／until 輪詢 53 次共 18 分。

執行：python -m pytest -q -p no:cacheprovider tests/（需要 PyYAML 的項目沒裝會 skip）
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "task-workflow"
SKILL = PLUGIN / "skills" / "workflow-optimization" / "SKILL.md"
CONCEPTS = PLUGIN / "skills" / "workflow-optimization" / "concepts.md"
TEMPLATE = PLUGIN / "templates" / "CLAUDE.md.section"
STATS = PLUGIN / "tools" / "transcript-stats.py"
VERIFY = PLUGIN / "tools" / "verify-clean.sh"
AGENTS = PLUGIN / "agents"
TASK_NEXT = PLUGIN / "skills" / "task-next" / "SKILL.md"
BASH = shutil.which("bash")
GIT = shutil.which("git")


def _read(p):
    return Path(p).read_text(encoding="utf-8")


def _fm(p):
    m = re.match(r"^---\n(.*?)\n---\n", _read(p), re.S)
    assert m, f"{p} 缺 frontmatter"
    return m.group(1)


# O1：skill 存在、名稱 workflow-optimization、觸發詞與硬規則；舊名 optimization 已移除
def test_skill_frontmatter_and_rules():
    assert SKILL.exists(), "缺 skills/workflow-optimization/SKILL.md"
    assert not (PLUGIN / "skills" / "optimization").exists(), "舊名 skills/optimization 應改名"
    fm = _fm(SKILL)
    assert re.search(r"^name: workflow-optimization$", fm, re.M)
    for kw in ("優化流程", "最花時間", "/workflow-optimization"):
        assert kw in fm, f"description 缺觸發詞 {kw}"
    t = _read(SKILL)
    for kw in ("只讀", "不外傳", "transcript-stats.py", "doc/optimization/", "先量後改", "不 push", "concepts.md"):
        assert kw in t, f"SKILL 缺 {kw}"


# O1b：通用——不用 task-workflow 的專案也能用：預設只看本專案、報告寫本專案、沒有設定節時的做法
def test_skill_generic_for_any_project():
    t = _read(SKILL)
    assert "--project" in t and "本專案" in t
    assert "優化報告目錄" in t
    assert "沒有 `## task-workflow 設定`" in t
    assert "- 優化報告目錄：" in _read(TEMPLATE)


# O1c：概念文件——成本拆解、原則、根因手冊、反模式（不得用放寬守門／權限來減少被擋）
def test_concepts_doc():
    assert CONCEPTS.exists(), "缺 skills/workflow-optimization/concepts.md"
    c = _read(CONCEPTS)
    for kw in ("模型生成", "工具執行", "等待", "摩擦", "依時間排名", "根因手冊", "防再犯", "反模式", "放寬"):
        assert kw in c, f"concepts 缺 {kw}"


# ---------- transcript-stats.py ----------
def _ts(sec):
    return f"2026-11-18T01:{sec // 60:02d}:{sec % 60:02d}.000Z"


def _asst(sec, mid, blocks, out_tok=100, ctx=1000):
    return {"type": "assistant", "timestamp": _ts(sec), "message": {"id": mid, "role": "assistant", "content": blocks,
            "usage": {"output_tokens": out_tok, "input_tokens": ctx, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}}


def _result(sec, tid, text="ok", err=False):
    return {"type": "user", "timestamp": _ts(sec), "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "content": text, "is_error": err}]}}


def _write_jsonl(p, recs):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")


@pytest.fixture
def fake_root(tmp_path):
    proj = tmp_path / "projects" / "-home-demo"
    main = [
        {"type": "user", "timestamp": _ts(0), "origin": {"kind": "human"}, "message": {"role": "user", "content": "SECRET-PROMPT-xyz 請幫我做"}},
        _asst(5, "m1", [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "npm test --token=abc123"}}], ctx=5000),
        _result(35, "t1"),
        _asst(40, "m2", [{"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "cd /x && git status | wc -l"}}]),
        _result(41, "t2", "This session is isolated in the worktree /x, but this command is too complex to verify that it stays inside", err=True),
        _asst(50, "m3", [{"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "sleep 20; cat out.txt"}}]),
        _result(70, "t3"),
        {"type": "system", "subtype": "turn_duration", "durationMs": 70000, "timestamp": _ts(71)},
    ]
    _write_jsonl(proj / "s1.jsonl", main)
    sub = proj / "s1" / "subagents" / "agent-a1.jsonl"
    _write_jsonl(sub, [
        {"type": "user", "timestamp": _ts(100), "message": {"role": "user", "content": "寫契約"}},
        _asst(110, "p1", [{"type": "tool_use", "id": "w1", "name": "Write", "input": {"file_path": "/r/tests/tasks/XX-01.test.mjs", "content": "a" * 50}}]),
        _result(111, "w1"),
        _asst(120, "p2", [{"type": "tool_use", "id": "w2", "name": "Write", "input": {"file_path": "/r/tests/tasks/XX-01.test.mjs", "content": "b" * 50}}]),
        _result(121, "w2"),
        _asst(400, "p3", [{"type": "text", "text": "done"}]),
    ])
    (proj / "s1" / "subagents" / "agent-a1.meta.json").write_text(json.dumps({"agentType": "task-workflow:planner-opus", "description": "XX-01 spec"}), encoding="utf-8")
    return tmp_path / "projects"


def _run_stats(root, *extra):
    return subprocess.run([sys.executable, "-X", "utf8", str(STATS), "--root", str(root), "--since", "2026-11-17", "--until", "2026-11-19", *extra],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


# O2：統計值正確（測試指令、被擋、輪詢、planner、契約重寫、指標摘要）
def test_stats_numbers(fake_root):
    r = _run_stats(fake_root)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "## 0. 指標摘要" in out
    assert re.search(r"\| 測試指令次數／合計時間 \| 1／30s \|", out), out
    assert re.search(r"\| 被隔離守門擋下次數 \| 1 \|", out), out
    assert re.search(r"\| sleep／until 輪詢次數／時間 \| 1／20s \|", out), out
    assert re.search(r"\| planner 次數／平均掛鐘 \| 1／5m \|", out), out
    assert re.search(r"\| 契約檔最多重寫次數 \| 2 \|", out), out
    assert "串接+管線+cd" in out  # 被擋指令的形狀


# O3：隱私——不輸出 prompt 原文與指令參數
def test_stats_privacy(fake_root):
    out = _run_stats(fake_root).stdout
    assert "SECRET-PROMPT-xyz" not in out
    assert "abc123" not in out and "--token" not in out


# O3b：--project 接受專案路徑（/home/demo → -home-demo，含其 worktree），不必寫以 - 開頭的資料夾名
def test_stats_project_path(fake_root):
    r = _run_stats(fake_root, "--project", "/home/demo")
    assert r.returncode == 0, r.stderr
    assert re.search(r"\| 測試指令次數／合計時間 \| 1／30s \|", r.stdout)
    r = _run_stats(fake_root, "--project", "/home/other")
    assert r.returncode == 3


# O4：期間外沒有紀錄 → exit 3
def test_stats_empty_period(fake_root):
    r = subprocess.run([sys.executable, "-X", "utf8", str(STATS), "--root", str(fake_root), "--since", "2020-01-01", "--until", "2020-01-02"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 3


# ---------- verify-clean.sh ----------
needs_git = pytest.mark.skipif(not (BASH and GIT), reason="需要 bash 與 git")


def _git(cwd, *args):
    return subprocess.run([GIT, *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "tests" / "tasks").mkdir(parents=True)
    (r / "tests" / "tasks" / "XX-01.test.sh").write_text("exit 0\n", encoding="utf-8")
    _git(r, "init", "-q", "-b", "dev")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "add", ".")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "spec")
    spec_commit = _git(r, "rev-parse", "HEAD")
    h = _git(r, "hash-object", "tests/tasks/XX-01.test.sh")
    return r, spec_commit, h


def _verify(r, *args, job=None):
    env = dict(os.environ, CLAUDE_JOB_DIR=str(job))
    return subprocess.run([BASH, str(VERIFY), "--repo", str(r), *args], capture_output=True, text=True, timeout=120, env=env)


# O5：hash 相同＋測試通過 → PASS、exit 0、checkout 已移除
@needs_git
def test_verify_clean_pass(repo, tmp_path):
    r, c, h = repo
    p = _verify(r, "--ref", "dev", "--name", "XX-01", "--test", "bash tests/tasks/XX-01.test.sh", "--spec", f"tests/tasks/XX-01.test.sh={h}", "--since", c, job=tmp_path / "job")
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.stdout.strip().splitlines()[-1] == "VERIFY-CLEAN: PASS"
    assert not (tmp_path / "job" / "tmp" / "verify-XX-01").exists()


# O6：hash 不同、planner 之後又改 spec、測試失敗 → FAIL、exit 1
@needs_git
def test_verify_clean_fail_cases(repo, tmp_path):
    r, c, h = repo
    p = _verify(r, "--ref", "dev", "--name", "XX-01", "--test", "true", "--spec", "tests/tasks/XX-01.test.sh=0000", job=tmp_path / "j1")
    assert p.returncode == 1 and "spec hash 不同" in p.stdout
    p = _verify(r, "--ref", "dev", "--name", "XX-01", "--test", "exit 4", job=tmp_path / "j2")
    assert p.returncode == 1 and "測試 exit 4" in p.stdout
    (r / "tests" / "tasks" / "XX-01.test.sh").write_text("exit 0  # 放寬\n", encoding="utf-8")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qam", "worker 改 spec")
    h2 = _git(r, "hash-object", "tests/tasks/XX-01.test.sh")
    p = _verify(r, "--ref", "dev", "--name", "XX-01", "--test", "true", "--spec", f"tests/tasks/XX-01.test.sh={h2}", "--since", c, job=tmp_path / "j3")
    assert p.returncode == 1 and "planner 之後有 commit 改" in p.stdout


# O7：用法錯誤 exit 2
@needs_git
def test_verify_clean_usage(tmp_path):
    p = subprocess.run([BASH, str(VERIFY), "--repo", str(tmp_path)], capture_output=True, text=True, timeout=30)
    assert p.returncode == 2


# ---------- agent／skill 規則 ----------
# O8：verifier 有 Write（限暫存）、Bash 規則在可寫範圍之前、用 verify-clean.sh
def test_verifier_rules():
    t = _read(AGENTS / "verifier-sonnet.md")
    tools = {x.strip() for x in re.search(r"^tools: (.*)$", _fm(AGENTS / "verifier-sonnet.md"), re.M).group(1).split(",")}
    assert "Write" in tools and "Edit" not in tools
    assert t.index("## Bash 指令規則") < t.index("## 可寫範圍")
    assert "verify-clean.sh" in t
    assert "$CLAUDE_JOB_DIR/tmp/<代號>/" in t


# O9：所有 agent 都有「不背景輪詢」與 Chrome keyring 旗標
@pytest.mark.parametrize("name", ["planner-opus", "verifier-sonnet", "worker-haiku", "worker-sonnet", "worker-opus"])
def test_agents_no_polling_and_chrome_flags(name):
    t = _read(AGENTS / f"{name}.md")
    assert "run_in_background" in t and "輪詢" in t, name
    assert "--use-mock-keychain" in t and "--password-store=basic" in t, name


# O10：planner 效率規則
def test_planner_efficiency():
    t = _read(AGENTS / "planner-opus.md")
    assert "一個 planner 只寫一項" in t
    assert "300 行" in t
    assert "只跑本項" in t


# O11：task-next 接上新流程
def test_task_next_wiring():
    t = _read(TASK_NEXT)
    assert "verify-clean.sh" in t
    assert "一個 planner 只寫一項" in t
    assert "一波一個 session" in t
    assert re.search(r"^10\. \*\*主 session 的 Bash", t, re.M)
    assert "workflow-optimization" in t


# O12：README 列出新 skill／工具與 1.12.0；首份報告存在
def test_readme_and_report():
    readme = _read(ROOT / "README.md")
    for kw in ("`workflow-optimization`", "tools/transcript-stats.py", "tools/verify-clean.sh", "- 1.12.0（"):
        assert kw in readme, kw
    reports = sorted((ROOT / "doc" / "optimization").glob("*.md"))
    assert reports, "缺 doc/optimization/*.md"
    r = _read(reports[0])
    for sec in ("## 指標摘要", "## 本期優化", "## 下次驗證"):
        assert sec in r, sec
