---
name: workflow-optimization
description: >-
  分析一段期間（預設近 7 天）的 Claude Code 對話紀錄，量出開發流程裡最花時間的環節
  （模型生成、各類 subagent、測試執行、被 worktree 隔離守門擋下的指令、sleep 輪詢、檔案重寫、主 session context），
  追到根因、列優化清單給使用者確認後逐一修正，改完再量一次，報告寫進專案的 doc/optimization/ 供下次比對。
  任何專案都能用（預設只看目前專案）；有 task-workflow 設定的專案順著它的 TODO 流程修。
  當使用者說「優化流程」「分析這周的對話紀錄」「找出最花時間的環節」「每週優化」「workflow optimization」
  「/workflow-optimization」，或 task-next 波末提醒「距上次優化超過一週」時使用。
  硬規則：對話紀錄只讀、不外傳；報告只寫統計值與指令形狀；不放寬守門或權限來減少被擋；未經使用者說不 push、不開 PR、不 merge。
metadata:
  version: "1.12.0"
---

# Workflow Optimization — 從對話紀錄找最花時間的環節，逐一優化

流程：**定範圍 → 量測 → 對照上期 → 排名與找根因 → 優化清單（等點頭）→ 逐一修正（測試先行）→ 改後再量 → 寫報告 → 回報**。
全程繁體中文。概念、量測定義、根因手冊與反模式在同目錄的 **`concepts.md`**，開工先讀。

---

## 🚨 硬規則

1. **對話紀錄只讀、不外傳**：`~/.claude/projects/**` 的 jsonl 含使用者原話、指令與檔案內容，只在本機分析；不貼到外部服務、不寄信、不放進 artifact。
2. **報告只寫統計值與形狀**：次數、秒數、tokens、工具名、指令第一個詞、形狀特徵。不抄 prompt 原文、完整指令、檔案內容；任何疑似密碼、token、帳號一律不出現。
3. **只分析公司專案**。範圍裡有私人專案的資料夾就排除，並在回報說明排除了什麼。
4. **先量後改、改後再量**：每一項優化都要有 before／after 數字；只能等下期紀錄才看得出效果的，寫進報告「下次驗證」並附目標值。
5. **不放寬守門、權限或驗收來換速度**（見 `concepts.md` 反模式）。
6. **可追溯**：每項修正都有代號、分支、commit 與紀錄（見步驟 5）。
7. **不 push、不開 PR、不 merge**，除非使用者明說；dev／main 規則照該專案 CLAUDE.md。
8. **不直接改** `~/.claude/plugins/marketplaces/**` 或 `~/.claude/plugins/cache/**`：那是安裝副本，`/plugin update` 會覆蓋。

---

## 步驟 0 — 定範圍

- **期間**：使用者說「這周」→ 本週一到今天；沒說 → 近 7 天。
- **專案範圍**（預設 **本專案**）：
  - 本專案：統計時加 `--project <專案根目錄的絕對路徑>`（例：`--project /home/frontpage`）。工具會把它轉成對話紀錄資料夾名 `-home-frontpage`，並以子字串一起涵蓋它的 worktree（`-home-frontpage--claude-worktrees-…`）。直接寫資料夾名時要用 `--project=-home-frontpage`，否則開頭的 `-` 會被當成選項。
  - 全部專案：使用者說「所有專案」「全部的對話紀錄」，或要調整的是共用 plugin 本身時。
- **報告位置**：
  - 本專案範圍 → 專案 CLAUDE.md `## task-workflow 設定` 的「優化報告目錄」，沒寫就用專案的 `doc/optimization/`。
  - 全部專案或 plugin 層的優化 → plugin repo 的 `doc/optimization/`。
- **上期報告**：報告位置裡最新的一份；沒有就是首次。

## 步驟 1 — 量測

```bash
python3 -X utf8 "${CLAUDE_PLUGIN_ROOT}/tools/transcript-stats.py" --since <YYYY-MM-DD> --until <YYYY-MM-DD> [--project <專案根目錄>] --json "$CLAUDE_JOB_DIR/tmp/opt-stats.json"
```

Windows 用 `py -3 -X utf8`。輸出是 Markdown，各節如下：
- `0 指標摘要`：固定欄位，用來逐期比對。
- `1 模型生成時間`、`2 subagent 掛鐘`、`3 主 session`
- `4 工具耗時排行`、`5 測試指令`、`6 被擋指令`、`7 等待與輪詢`、`8 測試檔重寫`

沒用 task-workflow subagent 的專案，planner／worker／verifier 那幾列會是 `0／-`，看主 session 與工具時間即可。

## 步驟 2 — 對照上期

把本期「指標摘要」和上期報告的同一張表並列，算出增減。上期「下次驗證」的假設逐條檢查是否成立，沒成立的列入本期候選。

## 步驟 3 — 排名與找根因

依**花掉的時間**排出前 5 名（不是依次數），每一名都用 `concepts.md` 的根因手冊追到根因再提解法。要看單一 session 細節時，派 `Explore` 或 `general-purpose` subagent 去讀 jsonl，prompt 明說「**只回報統計值與指令形狀，不要貼原文**」。

常用的往下挖方法（在專案裡跑）：
- 測試逐檔計時：`node --test --test-reporter=spec <檔>` 看子測試毫秒數、`pytest --durations=10`。
- 被擋指令看統計 §6 的「依 agent」與「依指令形狀」。

## 步驟 4 — 優化清單（強制關卡）

```
▶ 本期最花時間的環節（<期間>，<範圍>）
| # | 環節 | 本期耗時 | 根因 | 改哪裡 | 預估節省 | 風險 | 怎麼驗證 |
|---|---|---|---|---|---|---|---|
| 1 | … | … | … | <本專案：代號 XX-NN>／<plugin：檔名>／<其他工具：只提建議> | … | … | <before/after 怎麼量> |
與上期比：<指標摘要增減；上期假設成立／不成立>
```

使用者點頭前**不改任何檔**。使用者說「直接做」「逐一優化」→ 照清單順序做完（節省大、風險低的先做），只在要刪檔、改產品行為、或規格有兩種以上合理解讀時停下。

## 步驟 5 — 逐一修正

**本專案層**（測試、腳本、設定、專案文件）：
1. 讀專案 CLAUDE.md 的分支與變更規則。
2. 有 `## task-workflow 設定` → 照它：依 TODO 規則編號（修正多用 `FX` 類前綴）、從 dev 開自己的 worktree、先寫「驗收契約檔」並證明先紅、修正、跑「測試指令」全套、TODO 標 `[x]`（含 before→after 數字）、ChangeLog。
3. 沒有 `## task-workflow 設定` → 從預設開發分支開 worktree／分支；有測試框架就先加一個會紅的防再犯測試；commit 訊息寫清楚 before→after；專案有 ChangeLog／CHANGELOG 就補一節。
4. 不要在使用者的開發檢出目錄直接改（那裡可能有使用者還沒 commit 的改動）。不 merge。

**plugin 層**（task-workflow 的 skill、agent 定義、tools）：
1. 工作目錄 `~/worktrees/ctw-<短名>`。沒有就 `git clone ~/.claude/plugins/marketplaces/claude-task-workflow ~/worktrees/ctw-<短名>`，把 origin 設回 marketplace 那份的 `git remote get-url origin` 並 `git fetch`；從最新 `origin/main` 開 `feat/<短名>` 或 `fix/<短名>`。
2. 先在 `tests/test_<短名>.py` 寫契約並證明先紅，commit。
3. 改 agent／skill／tools。新工具要跨平台：bash＋標準工具，Python 只用標準函式庫並加 `-X utf8`。
4. 進版：`plugin.json` 的 `version`、README「內容」表與「版本」紀錄、改到的 skill 版本表與 `metadata.version`。
5. `python -m pytest -q -p no:cacheprovider tests/` 全綠才 commit。合併後各專案 `/plugin update task-workflow` 才生效。

**其他工具的問題**（官方 plugin、Claude Code 本身）：不改，寫進報告「未處理」，附建議。

## 步驟 6 — 改後再量

- 能當場量的當場量（全套測試秒數、單一工具的執行時間），寫進 after 欄。
- 只能從下期紀錄看出的（被擋次數、平均掛鐘、context 峰值），寫成「下次驗證」，附目標值。

## 步驟 7 — 寫報告

寫到步驟 0 決定的報告位置，檔名 `YYYY-MM-DD.md`（同日第二份加 `-2`），和修正放在同一個分支 commit：

```
# 流程優化報告 YYYY-MM-DD
期間：<since>～<until>；範圍：<本專案／專案清單／全部>；排除：<私人專案或「無」>
## 指標摘要（本期／上期／增減）
<步驟 1 的 §0 表，加上期與增減兩欄>
## 前 5 名耗時環節與根因
## 本期優化
| # | 環節 | 改了什麼 | 位置（repo、分支、commit） | before | after |
## 下次驗證
- [ ] <可檢查的假設與目標值>
## 未處理（與原因）
```

## 步驟 8 — 回報

```
本期最花時間：<前 3 名，一行一個，附耗時>
已優化：<逐項一行：環節 → 改了什麼（before→after），位置>
待你決定：<push／PR／merge 指令、要不要接受某項取捨>
下次驗證：<目標值>；建議 <日期> 再跑一次 workflow-optimization
```

---

## 版本紀錄

| 版號 | 日期 | 變更 |
|---|---|---|
| 1.12.0 | 2026-11-19 | 建立（OPT-01，原名 optimization）；OPT-02 改名 workflow-optimization、通用化（預設本專案範圍、報告寫專案的「優化報告目錄」、沒有 task-workflow 設定的專案也能用），概念與根因手冊移到 `concepts.md`。首次執行分析 2026-11-13～19（5 個專案、72 個紀錄檔），報告在 plugin repo `doc/optimization/2026-11-19.md` |
