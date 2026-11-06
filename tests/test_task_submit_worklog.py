"""驗收契約：task-submit-worklog skill（來源需求：FolderScanner repo TODO WF-01；v2 需求：2026-11-06 PM 口述）。

v2（pa-worklog/v2）需求：
- 專案名稱可由各專案自行設定（同一 repo 在不同電腦／資料夾開，名稱都一樣），不再限固定詞表。
- 回報加 ChangeLog 區塊：版本 → 主題分組 → 一行一件事、行尾括號寫任務代號。

執行：/home/nas/miniconda3/envs/NAS/bin/python -m pytest -q -p no:cacheprovider tests/
"""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "task-workflow"
SKILL = PLUGIN / "skills" / "task-submit-worklog" / "SKILL.md"
TEMPLATE = PLUGIN / "templates" / "CLAUDE.md.section"

HEADER_FIELDS = ["schema", "worklog_id", "supersedes", "reporter", "report_date", "week",
                 "period", "surface", "device", "projects", "summary"]
ITEM_FIELDS = ["category", "project", "title", "status", "progress", "detail",
               "outputs", "related", "due", "hours"]
TAIL_FIELDS = ["items", "changelog", "decisions", "issues", "next_steps", "tracking",
               "ai_usage", "security_check"]
CHANGELOG_FIELDS = ["project", "version", "date", "note", "source", "groups"]
SURFACES = {"claude.ai-web", "claude.ai-mobile", "claude.ai-desktop", "claude-code", "其他"}
CATEGORIES = {"主線工作", "對外與供應鏈", "業務發展", "會議與行政", "品質法規", "其他"}
STATUSES = {"完成", "進行中", "阻塞", "取消"}
PATTERNS = {"程式開發", "文件撰寫", "資料分析", "查詢研究", "簡報製作", "會議整理", "其他"}
# v2：專案名稱為自由字串（各 repo 設定），只限格式：1–30 字、不含主旨分隔用的「、」「|」與冒號
PROJECT_NAME = re.compile(r"[^、|:：\n]{1,30}")


def _text():
    return SKILL.read_text(encoding="utf-8")


def _frontmatter():
    m = re.match(r"^---\n(.*?)\n---\n", _text(), re.S)
    assert m, "SKILL.md 缺 frontmatter"
    return yaml.safe_load(m.group(1))


def _example_block():
    m = re.search(r"```\n(PA 工作紀錄.*?)---WORKLOG-BEGIN---\n(.*?)\n---WORKLOG-END---", _text(), re.S)
    assert m, "缺範例（人看的摘要＋WORKLOG-BEGIN/END 區塊）"
    return m.group(1), yaml.safe_load(m.group(2))


def _example_yaml():
    return _example_block()[1]


def test_skill_exists_with_frontmatter():
    # WF-01：以 task-submit-worklog 名稱加入 task-workflow plugin；v2 描述同步
    fm = _frontmatter()
    assert fm["name"] == "task-submit-worklog"
    for kw in ["回報工作紀錄", "/worklog", "收工作紀錄", "整理PA", "pa-worklog/v2"]:
        assert kw in fm["description"], kw
    assert str(fm["metadata"]["version"]).startswith("2."), fm["metadata"]


def test_required_sections_present():
    # 規格全文：欄位規格（含 v2 新增的 ChangeLog 區塊、專案名稱）、兩種模式各步驟、規格變更
    t = _text()
    for h in ["pa-worklog/v2", "### 1. 信件抬頭", "### 2. 工作項目", "### 3. 整體區塊",
              "### 4. ChangeLog 區塊", "### 專案名稱", "### A1.", "### A2.", "### A3.",
              "### A4.", "### A5.", "### A6.", "## 模式 B", "## 規格變更"]:
        assert h in t, h
    assert "### 專案受控詞" not in t, "v2 已改為各專案設定，不再是固定受控詞"


def test_example_yaml_parses_and_follows_schema():
    # A4：範例 YAML 可解析、欄位齊全且順序同規格、受控詞合法
    d = _example_yaml()
    keys = list(d.keys())
    assert keys == HEADER_FIELDS + TAIL_FIELDS, keys
    assert d["schema"] == "pa-worklog/v2"
    assert d["reporter"] == "Frid Hou"
    assert re.fullmatch(r"WL-\d{8}-\d{4}-[\w.-]+-[0-9a-f]{4}", d["worklog_id"])
    assert re.fullmatch(r"\d{4}-W\d{2}", d["week"])
    assert d["surface"] in SURFACES
    projects = set(d["projects"])
    assert projects and all(PROJECT_NAME.fullmatch(p) for p in projects), projects
    assert d["items"], "items 至少一項"
    for it in d["items"]:
        assert list(it.keys()) == ITEM_FIELDS
        assert it["category"] in CATEGORIES and it["status"] in STATUSES
        assert it["project"] in projects, it["project"]
        if it["status"] == "進行中":
            assert isinstance(it["progress"], int) and 0 <= it["progress"] <= 100
        else:
            assert it["progress"] == ""
    assert set(d["ai_usage"]["patterns"]) <= PATTERNS
    assert d["ai_usage"]["source"] in {"jsonl", "self-report"}
    assert d["security_check"] == "passed"


def test_example_project_name_comes_from_repo_setting():
    # v2 需求：專案名稱不限舊詞表，範例要示範「舊詞表外、由 repo 設定」的名稱
    d = _example_yaml()
    old_vocab = {"QMSWeb", "QMS文件", "MDSAP", "AI Gateway", "本地轉錄MCP", "OCR", "PA週報", "內部工具", "行政"}
    assert set(d["projects"]) - old_vocab, "範例應至少有一個舊詞表外的專案名稱"


def test_example_changelog_block():
    # v2 需求：ChangeLog 區塊＝版本 → 主題分組 → 一行一件事、行尾全形括號寫任務代號
    d = _example_yaml()
    cl = d["changelog"]
    assert isinstance(cl, list) and cl, "範例要有 ChangeLog 區塊"
    for e in cl:
        assert list(e.keys()) == CHANGELOG_FIELDS, list(e.keys())
        assert e["project"] in set(d["projects"]), e["project"]
        assert e["source"], "source 必填（ChangeLog 檔與條目範圍，供追溯）"
        assert e["groups"], "至少一個主題分組"
        for g in e["groups"]:
            assert list(g.keys()) == ["heading", "items"]
            assert g["heading"] and g["items"]
            for line in g["items"]:
                assert isinstance(line, str) and len(line) <= 80, line
                assert re.search(r"（[A-Za-z]+-\d+[A-Za-z]?(、[A-Za-z]+-\d+[A-Za-z]?)*）$", line), line


def test_human_summary_shows_changelog_between_items_and_decisions():
    # A4：人看的摘要依序 → 項目 → 【Changelog】 → 決議；ChangeLog 行逐條出現
    human, d = _example_block()
    assert "【Changelog】" in human
    assert human.index("【主線工作】") < human.index("【Changelog】") < human.index("決議：")
    for e in d["changelog"]:
        assert f'{e["project"]} {e["version"]}' in human
        for g in e["groups"]:
            assert g["heading"] in human
            for line in g["items"]:
                assert line in human, line


def test_project_name_and_changelog_settings():
    # v2 需求：專案名稱／ChangeLog 檔由各專案 task-workflow 設定提供，跟著 repo 走
    t = _text()
    for kw in ["PA 專案名稱", "ChangeLog 檔", "task-workflow 設定", "git remote", "資料夾名稱"]:
        assert kw in t, kw
    tpl = TEMPLATE.read_text(encoding="utf-8")
    assert re.search(r"^- PA 專案名稱：", tpl, re.M), "設定範本缺 PA 專案名稱"
    assert re.search(r"^- ChangeLog 檔：", tpl, re.M), "設定範本缺 ChangeLog 檔"


def test_mode_b_accepts_v1_and_v2():
    # 規格變更規則：升版後模式 B 需同時接受新舊版
    b = _text().split("## 模式 B", 1)[1]
    assert "pa-worklog/v1" in b and "pa-worklog/v2" in b
    assert "changelog" in b


def test_single_recipient_and_no_smtp():
    # A3／A4／A5：只寄 Frid 本人、不用 SMTP
    t = _text()
    assert "fridhou@brainnavi.com" in t
    assert set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", t)) == {"fridhou@brainnavi.com"}
    assert "不要用 SMTP" in t


def test_security_check_covers_changelog():
    # A3：ChangeLog 條目同樣要過資安檢查
    a3 = _text().split("### A3.", 1)[1].split("### A4.", 1)[0]
    assert "ChangeLog" in a3


def test_yaml_check_command_uses_nas_env():
    # 使用者決定：YAML 驗證改用已裝 PyYAML 的 conda NAS python
    assert "/home/nas/miniconda3/envs/NAS/bin/python" in _text()


def test_plugin_version_bumped_and_readme_lists_skill():
    meta = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert tuple(map(int, meta["version"].split("."))) >= (1, 10, 0)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "task-submit-worklog" in readme and "pa-worklog/v2" in readme
