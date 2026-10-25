---
name: task-next
description: >-
  從 TODO.md 挑下一項未完成任務，先補編號、先寫計畫給使用者確認，點頭後才派 worker subagent 改檔，
  改完另派 verifier 驗證，再交給 task-release 收尾。當使用者說「下一步」「接著做」「做下一項」
  「/task-next」「把 TODO 的 XX-01 做掉」時使用；使用者說「由你派、我不介入」「開第 N 波」
  時進入授權批次模式。硬規則：一次只做一項；先規劃、等使用者點頭再執行（批次模式例外，見步驟 0）；
  不在 main 上改；使用者沒說「merge」不併入 dev、沒說「release」不上 main。
metadata:
  version: "1.3.0"
---

# Task Next — 從 TODO.md 接手下一項任務

流程：**定模式 → 補編號 → 選一項 → 核對事實、寫計畫 → 等點頭（互動模式）→ 執行 → 驗證 → 收尾 → 回報／接下一項**。
一次只做一項。全程用繁體中文跟使用者溝通。

**專案設定從哪來**：每個專案的 `CLAUDE.md` 要有一節 `## task-workflow 設定`（範本見 plugin 的 `templates/CLAUDE.md.section`），寫明：主程式檔、版本日期標記、部署網址、舊存檔相容方式、資料慣例、參考資料位置、自測與 release 閘門。下文提到「主程式檔」「設定」都指這一節；找不到這一節就先停下請使用者補。

---

## 🚨 硬規則

1. **先規劃再執行**：互動模式下，步驟 3 的計畫沒被使用者點頭前，不改任何檔（補編號除外）。授權批次模式下由主 session 自己核對計畫（步驟 0）。
2. **一次一項**：上一項沒 commit，不開下一項。平行派工見附錄 C。
3. **不在 `main` 上改**：必須在 worktree／feature branch 上（專案 CLAUDE.md §Git 規則）。
4. **使用者沒說「merge」不合併到 `dev`；沒說「release」不合併到 `main`**。授權批次模式的「沒問題就 merge」只涵蓋 dev，`main` 永遠要聽到「release」。
5. **要刪檔、搬檔、改檔名，或規格有兩種以上合理解讀 → 停下問使用者**（批次模式下：產品層級的取捨自己決定並記進 `doc/decisions.md`，其餘仍停下問）。
6. **改檔、驗證都交給 subagent**：主 session 只負責讀 TODO、寫計畫、派工、檢查成果、收尾。主 session 不直接改主程式檔，連一行也一樣。`TODO.md`、`doc/*.md`、skill／agent 定義可由主 session 改。
7. **主 session 用量守在六成內**：超過約 60% → 先收尾 commit，寫 dev-log（步驟 7），提醒使用者 `/clear` 後用 `task-next` 接著做。

---

## 步驟 0 — 定模式

| 模式 | 觸發 | 行為 |
|---|---|---|
| **互動模式**（預設） | 「下一步」「/task-next」 | 一次一項，每項計畫等使用者點頭；收尾只 commit／push 分支 |
| **授權批次模式** | 使用者明說「由你派、我不介入」「開第 N 波」「一次做完」 | 先給路線圖（下方），之後一路跑到該波結束或 TODO 清空，只在硬規則 5 的情況停下。若同時說了「沒問題就 merge」，每項驗證 PASS 後自行併入 dev |

**路線圖格式**（批次模式開跑前給使用者看一次，之後不再逐項問）：

```
▶ 本波路線圖（N 項）
  1. <代號> <標題> — worker-xxx，動到 <區塊>，需讀外部資料：是／否
  2. ...
  相依與順序：<哪些要先做、為什麼>
  驗不到的部分：<例如匯出檔版面需本機軟體確認>
  本波結束後：建議 tag／release 版號 <vX.Y.Z>
```

---

## 步驟 1 — 讀 TODO.md，補編號

```bash
cat TODO.md
git status --short
git branch --show-current
```

- 若目前在 `main` → 停下，請使用者開 worktree／branch（或經同意後用 EnterWorktree）。
- 有別人未 commit 的改動（`TODO.md` 以外）→ 先回報，別動。
- **每項任務開一個 worktree**（從最新 `dev` 分出，命名 `worktree-<代號>-<短名>`），做完併入再開下一個。不要預開一批。

**補編號**（TODO.md「# 規則」）：
- 主 task `- [ ] XX-NN 標題`；子 task 縮排 `XX-NNa`。
- 前綴沿用同節既有項目；號碼取最大號＋1，不重用。
- 補完用 `git diff TODO.md` 秀給使用者看。

---

## 步驟 2 — 選任務

- 使用者有指定代號 → 做那一項；批次模式照路線圖順序。
- 沒指定 → 取第一個 `- [ ]` 的主 task；有子 task 從第一個未完成的子 task 做起。
- 任務帶圖片（`![](assets/xxx.png)`）→ **用 Read 打開每張圖看**。
- 任務標了參考資料頁碼 → 先讀設定裡的參考資料索引與對應摘要檔；要讀掃描 PDF 見附錄 A。

**任務太大就先切**：同時動到「資料結構＋UI＋匯出」或預估單一 worker 要讀外部資料又改 300 行以上 → 拆成子 task（如 a 資料與相容、b UI、c 匯出／範本），各自驗證。

---

## 步驟 3 — 核對事實、寫計畫（強制關卡）

主程式檔通常很大，**不要整份讀進主 session**。

**3a 核對事實**：派 `Explore`（thoroughness "medium"）確認計畫依賴的 3–5 個事實——相關函式名與行號、資料怎麼存（儲存結構、key 慣例）、既有行為、匯出功能要不要跟著改。**不要沿用上一項任務的 Explore 結果**，每項重查；查錯的假設會讓 worker 中途停下來問。

**3b 寫計畫**（目標＋限制＋驗收，實作細節留給 worker 提）：

```
▶ 準備動工：<代號> <標題>

【目標】<一句話：做完後產品會多了／變成什麼>
【依據】<摘要檔與頁碼；需讀外部資料的範圍>
【動作】
  1. <動詞開頭，具體到主程式檔的哪個區塊／函式>
  2. ...（≤5 步；超過表示太大，回步驟 2 切）
【限制】<資料 key 慣例、舊存檔要能載、不動哪些功能>
【會動到】<檔案清單>　【不會動】<明確劃界>
【要決定的點】<條列，最多 2 個選項＋建議；批次模式下寫「我決定：…」並記 decisions.md>
【驗收】<verifier 要看到什麼；哪些驗不到要列入 pending-checks.md>
【派工】worker：<worker-haiku／worker-sonnet／worker-opus>，理由 <一句>；verifier：verifier-sonnet
```

互動模式：**使用者沒回應前不改任何檔。** 點頭後把 TODO.md 該項改成 `[~]`。
批次模式：主 session 自己過一遍「要決定的點」，直接進步驟 4。

---

## 步驟 4 — 派 worker subagent 執行

`subagent_type` 依下表選（plugin 的 `agents/`，frontmatter 已固定模型，**不另傳 `model`**）：

| 任務性質 | `subagent_type` |
|---|---|
| 機械性小改：文字、顏色、日期、加一顆按鈕呼叫既有函式 | `worker-haiku` |
| 規格清楚的一般功能：新 UI 區塊、文件、單一區塊的視覺調整、範例補資料 | `worker-sonnet` |
| 動到資料結構／多處連動／規格要推敲／要讀外部資料定義 | `worker-opus` |

判準：規格越清楚、動到的地方越少 → 越輕。拿不準往重的選一級。

**prompt 只寫任務本身**（固定規則已在 agent 定義裡）：
- 工作目錄（worktree 絕對路徑）與分支名
- 任務代號、TODO.md 原文、附圖路徑、摘要檔與頁範圍
- 步驟 3 的計畫全文
- Explore 找到的行號（註明「可能偏移」）
- 這項特有的禁區或相容要求

worker 會先核對計畫與程式現況、一次回報差異（agent 定義要求）；主 session 收到差異後**一次決定完**再讓它繼續（用 SendMessage 續同一個 worker，不重開）。

worker 回來後：`git diff --stat` 看改動範圍有沒有超出計畫；超出 → 回報使用者（批次模式：自行判斷是否接受並記錄）。

---

## 步驟 5 — 派 verifier subagent 驗證

**改的人不驗自己。** 另派 `subagent_type: verifier-sonnet`（只有 Read／Bash／Grep／Glob）。subagent 不能再開 subagent，一定是主 session 依序派。

verifier prompt 交代：任務代號、計畫中的【驗收】、worker 報告的改動清單與自測腳本路徑（`tools/selftest/<代號>.mjs`）、這項特有的檢查點、以及專案設定裡的舊存檔相容方式。標準四項檢查（語法、舊存檔相容、截圖、回歸）已在 agent 定義裡，不必重抄。

verifier 回報後，主 session **自己 Read 一張關鍵截圖**確認。
**FAIL → 不收尾**：互動模式回報使用者問要不要再派 worker 修；批次模式直接再派 worker 修（同一 worker 用 SendMessage 續做），最多兩輪，仍 FAIL 才停下回報。

驗證後若只做小修，主 session 至少自己跑一次語法檢查再收尾：

```bash
"${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/marketplaces/claude-task-workflow/plugins/task-workflow}/tools/check-js.sh" <主程式檔>
```

---

## 步驟 6 — 收尾

呼叫 `task-release` skill：TODO.md 標 `[x]`＋完成摘要、版本日期標記、commit、push 分支；批次模式含 merge 到 dev。
同時更新：
- `doc/decisions.md`：這項任務裡主 session 替使用者做的產品決定（一行一條：日期、任務、決定、理由、可逆性）。
- `doc/pending-checks.md`：verifier 列的「待使用者手點」項目（勾選式清單，release 前清掉）。
- 驗證時新發現的問題 → 照 TODO 規則編號加進 `TODO.md`。

---

## 步驟 7 — 回報／接下一項

每項做完回報：代號、commit、分支、驗證結果、下一個未完成項目。

**一波（或批次）結束時**：
1. 寫 `doc/dev-log/YYYY-MM-DD.md`（或當日檔追加一節）：做了哪些、決定了什麼、待確認、下一波建議。這是 `/clear` 後接手的檢查點。
2. 跑設定裡的 release 閘門（預設 plugin 的 `tools/release-check.sh`，需要 `node_modules`；沒有就說明略過）。
3. 建議使用者 tag 或 release：「dev 比 main 多 N 個 commit，建議 release vX.Y.Z」。沒聽到「release」不動 main。
4. 彙整 `doc/pending-checks.md` 未勾項目給使用者。

互動模式：回報後**停下來**，等使用者決定。批次模式：接路線圖下一項，直到該波結束。

---

## 附錄 A — 讀掃描 PDF

- `Read` 工具讀不了掃描 PDF 的文字，要先用 Ghostscript 轉圖再 Read：
  ```bash
  gs -sDEVICE=png16m -r110 -dFirstPage=<n> -dLastPage=<m> \
     -o "$CLAUDE_JOB_DIR/tmp/<前綴>-%02d.png" "<pdf 路徑>"
  ```
- 頁碼對照（PDF 頁 ↔ 書上頁）寫在專案設定或參考資料索引裡；引用前仍以頁面上印的頁號為準。
- 摘要寫進參考資料目錄、用自己的話、標頁碼，並在索引登記；TODO 只指向摘要。

## 附錄 B — Git 小事（雲端硬碟掛載常見）

- 掛載偶爾殘留 `index.lock`（0 byte）。先 `pgrep -a git` 確認沒有程序在跑，再 `rm -f "$(git rev-parse --git-dir)/index.lock"` 重試。
- `sed -i` 在該掛載會印「preserving permissions … Operation not permitted」，改動仍生效，可忽略；改檔優先用 python 或 Edit 工具。
- `git push -u` 在該掛載會印 chmod 警告，push 本身成功，用 `git ls-remote` 確認即可。

## 附錄 C — 平行派工（選用）

預設串行。只有在下列條件都成立時才同時派 2–3 個 worker：
- 各任務動到的函式區塊不重疊。
- 共用熱點（如存檔／載入函式）各只加一行，且約定「新欄位獨立一行、接在前一個新欄位之後」。
- `TODO.md` 只動自己那一行。
merge 順序：文件 → 視覺 → 資料結構，衝突由主 session 解。verifier 仍一項一個，依序派。

---

## 版本紀錄

| 版號 | 日期 | 變更 |
|---|---|---|
| 1.3.0 | 2026-10-25 | 改為 plugin 版：專案專屬內容（主程式檔名、頁碼對照、資料慣例）移到各專案 CLAUDE.md 的「task-workflow 設定」；工具路徑改走 `CLAUDE_PLUGIN_ROOT`。功能同 strategy-matrix 1.3.0（授權批次模式、派工前核對事實、decisions／pending-checks／dev-log） |
| 1.2.0 | 2026-09-28 | 派工改用 `worker-haiku`／`worker-sonnet`／`worker-opus`、驗證改用 `verifier-sonnet` |
| 1.1.0 | 2026-09-28 | 改檔交 worker subagent、驗證另派 verifier、讀主程式用 Explore；主 session 用量守六成 |
| 1.0.0 | 2026-09-28 | 建立：參考 QMSWeb `qms-next` |
