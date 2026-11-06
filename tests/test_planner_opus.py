"""驗收契約：planner-opus agent（1.9.0）。

來源：FolderScanner repo session 分析（2026-11-05）——planner 17 次皆以 general-purpose 派出、
規則每次重寫於 prompt；改為固定 opus 的獨立 agent，專案專屬值改由 CLAUDE.md 設定節提供。

執行：/home/nas/miniconda3/envs/NAS/bin/python -m pytest -q -p no:cacheprovider tests/
"""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "task-workflow"
AGENT = PLUGIN / "agents" / "planner-opus.md"
TASK_NEXT = PLUGIN / "skills" / "task-next" / "SKILL.md"
TEMPLATE = PLUGIN / "templates" / "CLAUDE.md.section"
WORKERS = [PLUGIN / "agents" / f"worker-{m}.md" for m in ("haiku", "sonnet", "opus")]
VERIFIER = PLUGIN / "agents" / "verifier-sonnet.md"


def _read(p):
    return p.read_text(encoding="utf-8")


def _frontmatter(p):
    m = re.match(r"^---\n(.*?)\n---\n", _read(p), re.S)
    assert m, f"{p.name} 缺 frontmatter"
    return yaml.safe_load(m.group(1))


# P1：agent 存在、固定 opus、不能再派 subagent
def test_agent_frontmatter_fixed_opus():
    assert AGENT.exists(), "缺 agents/planner-opus.md"
    fm = _frontmatter(AGENT)
    assert fm["name"] == "planner-opus"
    assert fm["model"] == "opus"
    tools = {t.strip() for t in fm["tools"].split(",")}
    assert {"Bash", "Read", "Write", "Edit"} <= tools
    assert "Agent" not in tools and "Task" not in tools


# P2：通用化——讀 CLAUDE.md 設定節，缺項時依 repo 推定（含 pytest 與 playwright）
def test_agent_reads_settings_and_detects_runner():
    t = _read(AGENT)
    assert "task-workflow 設定" in t
    for key in ("測試指令", "驗收契約檔", "planner 可寫範圍", "測試隔離", "敏感資料", "git 身分"):
        assert key in t, f"agent 沒提到設定項 {key}"
    assert "pytest" in t and "playwright" in t.lower()
    assert "推定" in t


# P3：可寫範圍分級、別項 spec 需標「驗收條件變更」、不碰實作
def test_agent_scope_rules():
    t = _read(AGENT)
    assert "可寫範圍" in t and "申報" in t
    assert "驗收條件變更" in t
    assert "不寫" in t and "實作" in t


# P4：先紅標準——斷言失敗而非收集錯誤、防空轉、功能已存在的處理
def test_agent_red_criteria():
    t = _read(AGENT)
    assert "斷言失敗" in t and "ImportError" in t
    assert "防空轉" in t
    assert "補測試" in t


# P5：實戰踩坑固定化——git 身分不改 config、單一指令、敏感資料過濾
def test_agent_operational_rules():
    t = _read(AGENT)
    assert "git -c user.name" in t and "不改 git config" in t
    assert "絕對路徑" in t
    assert "password" in t


# P6：回報固定欄位，含所有被改 spec 的 hash
def test_agent_report_format():
    t = _read(AGENT)
    for field in ("契約檔：", "其他改動：", "本項輸出：", "全套輸出：", "給 worker 的實作提示："):
        assert field in t, f"回報缺欄位 {field}"
    assert "hash-object" in t


# P7：task-next 3c 改派 planner-opus，不再用 general-purpose，description 不再寫死 Playwright
def test_task_next_dispatches_planner_opus():
    t = _read(TASK_NEXT)
    sec = t.split("**3c")[1].split("## 步驟 4")[0]
    assert "planner-opus" in sec
    assert "general-purpose" not in sec
    fm = _frontmatter(TASK_NEXT)
    assert "Playwright" not in fm["description"]
    assert fm["metadata"]["version"] == "1.9.0"


# P8：設定範本新增 planner 會讀的六項
def test_template_has_planner_settings():
    t = _read(TEMPLATE)
    for key in ("測試指令", "驗收契約檔", "planner 可寫範圍", "測試隔離", "敏感資料", "git 身分"):
        assert f"- {key}：" in t, f"範本缺 {key}"


# P9：worker 不再寫死 npm test／.spec.ts，改讀設定
def test_workers_contract_generic():
    for w in WORKERS:
        sec = _read(w).split("## 測試先行（TDD）契約")[1].split("\n## ")[0]
        assert "驗收契約檔" in sec and "測試指令" in sec, w.name
        assert "`npm test` 全綠" not in sec, w.name


# P10：verifier 比對 planner 回報列出的所有 spec hash
def test_verifier_checks_all_touched_specs():
    t = _read(VERIFIER)
    assert "其他改動" in t and "每一支" in t


# P11：版本 1.9.0，README 列出 planner-opus
def test_version_and_readme():
    meta = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert tuple(map(int, meta["version"].split("."))) >= (1, 9, 0)  # 之後進版不應讓本契約失敗
    assert "planner-opus" in meta["description"]
    readme = _read(ROOT / "README.md")
    assert "planner-opus" in readme and "1.9.0" in readme
