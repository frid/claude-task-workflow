---
name: optimization
description: >-
  分析一段期間（預設近 7 天）的 Claude Code 對話紀錄，量出 task-workflow 流程裡最花時間的環節
  （模型生成、planner／worker／verifier、測試執行、被 worktree 隔離守門擋下的指令、sleep 輪詢、契約檔重寫、主 session context），
  找根因、列優化清單給使用者確認後逐一修正（專案問題走該專案 TODO→分支→測試先行→ChangeLog；流程問題改 plugin 並進版），
  改完再量一次，把前後數字寫進 plugin repo 的 doc/optimization/YYYY-MM-DD.md 供下次比對。
  當使用者說「優化流程」「分析這周的對話紀錄」「找出最花時間的環節」「每週優化」「/optimization」，
  或 task-next 波末提醒「距上次 optimization 超過一週」時使用。
  硬規則：對話紀錄只讀、不外傳；報告只寫統計值與指令形狀，不抄 prompt、指令全文或任何憑證；未經使用者說不 push、不開 PR、不 merge。
metadata:
  version: "1.12.0"
---

# Optimization — 從對話紀錄找最花時間的環節，逐一優化

流程：**定範圍 → 量測 → 對照上期 → 排名與找根因 → 優化清單（等點頭）→ 逐一修正（測試先行）→ 改後再量 → 寫報告 → 回報**。
全程繁體中文。這是「改流程本身」的工作，跟 task-next（改產品）分開跑。

---

## 🚨 硬規則

1. **對話紀錄只讀、不外傳**：`~/.claude/projects/**` 的 jsonl 含使用者原話、指令與檔案內容，只在本機分析；不貼到外部服務、不寄信、不放進 artifact。
2. **報告只寫統計值與形狀**：次數、秒數、tokens、工具名、指令第一個詞、形狀特徵（串接／heredoc／git -C）。不抄 prompt 原文、完整指令、檔案內容；任何疑似密碼、token、帳號一律不出現。
3. **只分析公司專案**（組織規範）。看到私人專案的資料夾就排除，並在回報說明排除了什麼。
4. **先量後改、改後再量**：每一項優化都要有 before／after 數字；只能等下一期紀錄才看得到效果的，寫進報告「下次驗證」。
5. **可追溯**：專案層的修正走該專案的 TODO 代號 → 分支／worktree → 先紅測試 → commit → ChangeLog；plugin 層的修正走 plugin repo 分支 → `tests/test_*.py` 契約 → 進版（`plugin.json`、README 版本紀錄、相關 skill 的版本表）。
6. **不 push、不開 PR、不 merge**，除非使用者明說；專案的 dev／main 規則照各專案 CLAUDE.md。
7. **不直接改** `~/.claude/plugins/marketplaces/**` 或 `~/.claude/plugins/cache/**`：那是安裝副本，`/plugin update` 會覆蓋。

---

## 步驟 0 — 定範圍

- 期間：使用者說「這周」→ 本週一到今天；沒說 → 近 7 天。
- 專案：預設全部（`~/.claude/projects/` 下所有資料夾）；指定專案就加 `--project <資料夾名子字串>`。
- 找上一份報告：plugin repo 的 `doc/optimization/` 最新一份（沒有就是首次）。

## 步驟 1 — 量測

```bash
python3 -X utf8 "${CLAUDE_PLUGIN_ROOT}/tools/transcript-stats.py" --since <YYYY-MM-DD> --until <YYYY-MM-DD> --json "$CLAUDE_JOB_DIR/tmp/opt-stats.json"
```

（Windows 用 `py -3 -X utf8`；輸出直接是 Markdown。）報告各節：
`0 指標摘要`（固定欄位，逐期比對用）、`1 模型生成時間`、`2 subagent 掛鐘`、`3 主 session`、`4 工具耗時排行`、`5 測試指令`、`6 被擋指令`、`7 等待與輪詢`、`8 契約檔重寫`。

注意：「掛鐘」包含等使用者回覆的時間；**「執行中」與「模型生成」才是流程本身的成本**。使用者離開造成的長掛鐘不是優化對象。

## 步驟 2 — 對照上期

把本期「指標摘要」與上一份報告的同一張表並列，算增減；逐條檢查上一份報告「下次驗證」的假設是否成立（例如「verifier 被擋次數應降到 10 以下」）。沒成立的，列入本期候選。

## 步驟 3 — 排名與找根因

依「花掉的時間」排前 5 名（不是依次數）。每一名都要追到根因再提解法；只寫症狀不算完成。

| 症狀（統計表哪一節） | 往下挖的方法 | 常見根因 | 典型解法 |
|---|---|---|---|
| 測試指令合計時間高（§5） | 在專案裡逐檔計時：`for f in tests/**/*.test.mjs; do …; done`、`pytest --durations=10`、`node --test --test-reporter=spec` 看子測試毫秒數 | 單一檔卡住：Chrome 等 keyring（缺 `--password-store=basic --use-mock-keychain`）、固定 sleep、真的等逾時、每個 test 重啟伺服器 | 修那一檔的啟動參數或改共用 helper；加防再犯的契約（掃描所有啟動點） |
| planner 久、輸出 tokens 高（§1、§2、§8） | §8 看哪些契約檔被寫很多次、多大；§2 看 description 是否一次包多項 | 一個 planner 循序寫多項；契約檔過肥；整檔重寫；反覆跑全套 | `planner-opus.md` 效率規則；task-next 平行派 planner |
| 被隔離守門擋很多（§6） | 依 agent 與形狀分布；抽幾筆看形狀（不抄全文） | agent 沒有 Write 只能用 heredoc；把 cd／git／管線串成一行；`git -C` 指向共用 checkout | 該 agent 的 Bash 規則移到最前；給 Write（限暫存）；把多步驟包成一支 `tools/*.sh` 一次呼叫 |
| 輪詢（§7） | 誰在 `run_in_background` 後 `sleep`／`until` | 怕測試跑太久就丟背景 | 規則：前景跑＋timeout；真的慢就先修慢的測試 |
| 主 session 生成時間高、context 峰值大（§0、§3） | 看最大的 session 跨了幾波、幾個 prompt | 一個 session 跑多波；subagent 回報太長；主 session 自己讀大檔 | 一波一個 session（波末 dev-log 後 `/clear`）；回報格式精簡；讀大檔交 Explore |
| verifier 久（§2） | 最久的幾次 verifier 用了哪些工具（§4） | 整頁截圖卡住、重跑太多次、手動串 checkout | `tools/verify-clean.sh`；截元素不截整頁 |

需要看單一 session 細節時，派 `Explore`／`general-purpose` subagent 去讀 jsonl，prompt 明說「**只回報統計值與指令形狀，不要貼原文**」，避免主 session context 被紀錄灌爆。

## 步驟 4 — 優化清單（強制關卡）

```
▶ 本期最花時間的環節（<期間>，<專案範圍>）
| # | 環節 | 本期耗時 | 根因 | 改哪裡 | 預估節省 | 風險 | 怎麼驗證 |
|---|---|---|---|---|---|---|---|
| 1 | … | … | … | <專案 repo：代號 XX-NN>／<plugin：檔名> | … | … | <before/after 怎麼量> |
與上期比：<指標摘要增減；上期假設成立／不成立>
```

互動模式：**使用者點頭前不改任何檔**。使用者說「直接做」「逐一優化」→ 照清單順序（節省大、風險低的先做）一路做完，只在要刪檔、改產品行為、或規格有兩種以上合理解讀時停下。

## 步驟 5 — 逐一修正

**專案層**（某個專案的測試、腳本、設定）：
1. 讀該專案 CLAUDE.md 的分支規則與 `## task-workflow 設定`。
2. 依 TODO 規則編號（修正通常用 `FX` 類前綴），從 dev 開 worktree（不要在使用者的 dev 檢出目錄改；那裡可能有使用者未 commit 的改動）。
3. 先寫契約測試並證明先紅（例如「所有直接啟動 Chrome 的檔都帶 keyring 旗標」），commit；再修，跑全套。
4. TODO 標 `[x]`＋完成摘要（含 before→after 數字）、ChangeLog 一節，commit。不 merge。

**plugin 層**（skill、agent 定義、tools）：
1. 工作目錄：`~/worktrees/ctw-<短名>`。沒有就 `git clone ~/.claude/plugins/marketplaces/claude-task-workflow ~/worktrees/ctw-<短名>`，再把 origin 設回 GitHub 網址（照 marketplace 那份的 `git remote get-url origin`）並 `git fetch`；分支 `feat/<短名>` 或 `fix/<短名>`，從最新 `origin/main` 分出。
2. 先在 `tests/test_<短名>.py` 寫契約（agent 定義含哪條規則、工具在暫存 repo／假紀錄上的行為），證明先紅後 commit。
3. 改 agent／skill／tools；新工具要能跨平台（bash＋標準工具、Python 只用標準函式庫、`-X utf8`）。
4. 進版：`plugin.json` 的 `version`、README「內容」表與「版本」紀錄、改到的 skill 版本表與 `metadata.version`。
5. 跑 `python -m pytest -q -p no:cacheprovider tests/`（需要 PyYAML 的測試沒裝會 skip），全綠才 commit。
6. 回報 push／PR 指令給使用者，**等使用者說才 push**。合併後各專案 `/plugin update task-workflow` 才會生效。

## 步驟 6 — 改後再量

- 能立刻量的立刻量（例如全套測試秒數、單一工具的執行時間），寫進報告的 after 欄。
- 只能從下期紀錄看出的（被擋次數、planner 平均掛鐘、context 峰值），寫成「下次驗證」的可檢查假設，附目標值。

## 步驟 7 — 寫報告

plugin repo `doc/optimization/YYYY-MM-DD.md`（同一天第二份加 `-2`），與 plugin 改動同一個分支 commit：

```
# 流程優化報告 YYYY-MM-DD
期間：<since>～<until>；範圍：<專案清單或「全部」>；排除：<私人專案或「無」>
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
本期最花時間：<前 3 名一行一個，附耗時>
已優化：<逐項一行：環節 → 改了什麼（before→after），位置>
待你決定：<push／PR／merge 指令、要不要接受某項取捨>
下次驗證：<目標值>；建議 <日期> 再跑一次 optimization
```

---

## 版本紀錄

| 版號 | 日期 | 變更 |
|---|---|---|
| 1.12.0 | 2026-11-19 | 建立。首次執行分析 2026-11-13～19（5 個專案、72 個紀錄檔），報告 `doc/optimization/2026-11-19.md` |
