"""驗收契約：task-submit-worklog skill（來源需求：FolderScanner repo TODO WF-01）。

執行：python -m pytest -q -p no:cacheprovider tests/（需要 PyYAML；BN-RD-AIServer 可用 /home/nas/miniconda3/envs/NAS/bin/python）
"""
import json
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="需要 PyYAML：python -m pip install --user pyyaml")

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "task-workflow"
SKILL = PLUGIN / "skills" / "task-submit-worklog" / "SKILL.md"

HEADER_FIELDS = ["schema", "worklog_id", "supersedes", "reporter", "report_date", "week",
                 "period", "surface", "device", "projects", "summary"]
ITEM_FIELDS = ["category", "project", "title", "status", "progress", "detail",
               "outputs", "related", "due", "hours"]
TAIL_FIELDS = ["items", "decisions", "issues", "next_steps", "tracking", "ai_usage", "security_check"]
SURFACES = {"claude.ai-web", "claude.ai-mobile", "claude.ai-desktop", "claude-code", "其他"}
CATEGORIES = {"主線工作", "對外與供應鏈", "業務發展", "會議與行政", "品質法規", "其他"}
STATUSES = {"完成", "進行中", "阻塞", "取消"}
PATTERNS = {"程式開發", "文件撰寫", "資料分析", "查詢研究", "簡報製作", "會議整理", "其他"}
PROJECTS = {"QMSWeb", "QMS文件", "MDSAP", "AI Gateway", "本地轉錄MCP", "OCR", "PA週報", "內部工具", "行政"}


def _text():
    return SKILL.read_text(encoding="utf-8")


def _frontmatter():
    m = re.match(r"^---\n(.*?)\n---\n", _text(), re.S)
    assert m, "SKILL.md 缺 frontmatter"
    return yaml.safe_load(m.group(1))


def _example_yaml():
    m = re.search(r"---WORKLOG-BEGIN---\n(.*?)\n---WORKLOG-END---", _text(), re.S)
    assert m, "缺 WORKLOG-BEGIN/END 範例區塊"
    return yaml.safe_load(m.group(1))


def test_skill_exists_with_frontmatter():
    # WF-01：以 task-submit-worklog 名稱加入 task-workflow plugin
    fm = _frontmatter()
    assert fm["name"] == "task-submit-worklog"
    for kw in ["回報工作紀錄", "/worklog", "收工作紀錄", "整理PA"]:
        assert kw in fm["description"], kw


def test_required_sections_present():
    # 規格全文：欄位規格、兩種模式各步驟、規格變更
    t = _text()
    for h in ["pa-worklog/v1", "### 1. 信件抬頭", "### 2. 工作項目", "### 3. 整體區塊",
              "### 專案受控詞", "### A1.", "### A2.", "### A3.", "### A4.", "### A5.", "### A6.",
              "## 模式 B", "## 規格變更"]:
        assert h in t, h


def test_example_yaml_parses_and_follows_schema():
    # A4：範例 YAML 可解析、欄位齊全且順序同規格、受控詞合法
    d = _example_yaml()
    keys = list(d.keys())
    assert keys == HEADER_FIELDS + TAIL_FIELDS, keys
    assert d["schema"] == "pa-worklog/v1"
    assert d["reporter"] == "Frid Hou"
    assert re.fullmatch(r"WL-\d{8}-\d{4}-[\w.-]+-[0-9a-f]{4}", d["worklog_id"])
    assert re.fullmatch(r"\d{4}-W\d{2}", d["week"])
    assert d["surface"] in SURFACES
    assert set(d["projects"]) <= PROJECTS
    assert d["items"], "items 至少一項"
    for it in d["items"]:
        assert list(it.keys()) == ITEM_FIELDS
        assert it["category"] in CATEGORIES and it["status"] in STATUSES and it["project"] in PROJECTS
        if it["status"] == "進行中":
            assert isinstance(it["progress"], int) and 0 <= it["progress"] <= 100
        else:
            assert it["progress"] == ""
    assert set(d["ai_usage"]["patterns"]) <= PATTERNS
    assert d["ai_usage"]["source"] in {"jsonl", "self-report"}
    assert d["security_check"] == "passed"


def test_single_recipient_and_no_smtp():
    # A3／A4／A5：只寄 Frid 本人、不用 SMTP
    t = _text()
    assert "fridhou@brainnavi.com" in t
    assert set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", t)) == {"fridhou@brainnavi.com"}
    assert "不要用 SMTP" in t


def test_yaml_check_command_uses_nas_env():
    # 使用者決定：YAML 驗證改用已裝 PyYAML 的 conda NAS python
    assert "/home/nas/miniconda3/envs/NAS/bin/python" in _text()


def test_plugin_version_bumped_and_readme_lists_skill():
    meta = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert tuple(map(int, meta["version"].split("."))) >= (1, 8, 0)
    assert "task-submit-worklog" in (ROOT / "README.md").read_text(encoding="utf-8")
