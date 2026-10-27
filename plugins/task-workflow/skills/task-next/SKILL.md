---
name: task-next
description: >-
  從 TODO.md 挑下一項未完成任務，先補編號、先寫計畫給使用者確認，點頭後走「測試先行」：
  先派 planner 寫 Playwright spec 並證明它在 dev 上失敗，再派 worker 在自己的 worktree 做到 spec 與全套測試通過（最多 6 輪），
  再派 verifier 從乾淨 checkout 重跑全套並比對 spec 未被改，全綠才 fast-forward 併入 dev、更新 TODO；最後交 task-release 收尾。當使用者說「下一步」「接著做」「做下一項」
  「/task-next」「把 TODO 的 XX-01 做掉」「做 XX-01a」時使用（指定代號就只做那一項或那個範圍）；
  使用者說「由你派、我不介入」「由你當最上層指揮者」「開第 N 波」「一個一個完整做」時進入授權批次模式，
  再說「沒問題就 merge」則每項 PASS 後自行併入 dev。硬規則：一次只做一項；先規劃、等使用者點頭再執行
  （批次模式例外，見步驟 0）；不在 main 上改；使用者沒說「merge」不併入 dev、沒說「release」不上 main。
metadata:
  version: "1.7.0"
---

# Task Next — 從 TODO.md 接手下一項任務

流程：**定模式 → 補編號 → 選一項 → 核對事實、寫計畫 → 等點頭（互動模式）→ planner 寫 spec（必須先紅）→ worker 做到綠（≤6 輪）→ verifier 乾淨 checkout 重跑 → 全綠才 ff 併入 dev → 收尾 → 回報／接下一項**。
一次只做一項。全程用繁體中文跟使用者溝通。

**專案設定從哪來**：每個專案的 `CLAUDE.md` 要有一節 `## task-workflow 設定`（範本見 plugin 的 `templates/CLAUDE.md.section`），寫明：主程式檔、版本日期標記、部署網址、舊存檔相容方式、資料慣例、參考資料位置、自測與 release 閘門。下文提到「主程式檔」「設定」都指這一節。找不到這一節：互動模式先停下請使用者補；**批次模式依 CLAUDE.md 既有內容、tests／tools 目錄與 TODO 推出一節自己補上並 commit**，在回報裡說明，不停下。

---

## 🚨 硬規則

1. **先規劃再執行**：互動模式下，步驟 3 的計畫沒被使用者點頭前，不改任何檔（補編號除外）。授權批次模式下由主 session 自己核對計畫（步驟 0）。
2. **一次一項**：上一項沒 commit，不開下一項。平行派工見附錄 C。
3. **不在 `main` 上改**：必須在 worktree／feature branch 上（專案 CLAUDE.md §Git 規則）。
4. **使用者沒說「merge」不合併到 `dev`；沒說「release」不合併到 `main`**。授權批次模式的「沒問題就 merge」只涵蓋 dev，`main` 永遠要聽到「release」。
5. **要刪檔、搬檔、改檔名，或規格有兩種以上合理解讀 → 停下問使用者**（批次模式下：產品層級的取捨自己決定並記進 `doc/decisions.md`，其餘仍停下問）。
6. **改檔、驗證都交給 subagent**：主 session 只負責讀 TODO、寫計畫、派工、檢查成果、收尾。主 session 不直接改主程式檔，連一行也一樣。`TODO.md`、`doc/*.md`、skill／agent 定義可由主 session 改。
7. **主 session 用量守在六成內**：超過約 60% → 先收尾 commit，寫 dev-log（步驟 7），提醒使用者 `/clear` 後用 `task-next` 接著做。
8. **測試先行**：每項任務先有 `tests/tasks/<代號>.spec.ts`，而且要**先證明它在目前 dev 上失敗**（失敗原因必須是可量測斷言，不能只是截圖基準不存在）才派 worker。沒有紅過的 spec 不算驗收。
9. **spec 是驗收契約，worker 不能改**：planner commit spec 後記下 `git hash-object` 的值；verifier 比對 hash，改了 spec 讓它過關的 commit 一律拒收（只有主 session 判定驗收條件本身寫錯，才由 planner 另開 commit 修 spec，並重新證明「先紅」）。

---

## 步驟 0 — 定模式

| 模式 | 觸發 | 行為 |
|---|---|---|
| **互動模式**（預設） | 「下一步」「/task-next」 | 一次一項，每項計畫等使用者點頭；收尾只 commit／push 分支 |
| **指定代號** | 「做 ST-23」「把 ST-22a 做掉」「ST-24 到 ST-26」 | 只做指定的那一項／子項／範圍，做完就停；可與下面兩種模式任一搭配（例：「ST-23 由你派、我不介入」） |
| **授權批次模式** | 使用者明說「由你派、我不介入」「由你當最上層指揮者」「開第 N 波」「一個一個完整做」「一次做完」 | 先給路線圖（下方），之後一路跑到該波結束或 TODO 清空，只在硬規則 5 的情況停下。若同時（或中途）說了「沒問題就 merge」，每項驗證 PASS 後自行併入 dev 並 push dev |

批次模式的分支策略見步驟 1「整波一條分支」；中途使用者在 dev 加需求的處理見步驟 2。

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
- **互動模式／指定代號：每項任務開一個 worktree**（從最新 `dev` 分出，命名 `worktree-<代號>-<短名>`），做完併入再開下一個。不要預開一批。
- **批次模式：整波一條分支**（`worktree-<波名>`，如 `worktree-st22-28`，從最新 `dev` 分出），每項做完各自 commit（子項也各自 commit）；授權 merge 時，每項 PASS 後到 dev 檢出目錄 `git merge --no-ff <該項的 commit>`（**指定 commit，不指定分支名**，避免把下一項進行中的 commit 一起帶進去），再 `git push origin dev`，回到工作分支 `git merge --ff-only dev` 同步。整波結束、分支全部併入後才 `git worktree remove` 並刪分支。
  - EnterWorktree 隔離的 session 不能在 dev 目錄跑 git：先 `ExitWorktree(keep)` → 在 dev 做 merge／push → `EnterWorktree(path)` 回來。
  - 若使用者未授權 merge，整波只在工作分支 commit，結束時回報「說 merge 我就併」。

**補編號**（TODO.md「# 規則」）：
- 主 task `- [ ] XX-NN 標題`；子 task 縮排 `XX-NNa`。
- 前綴沿用同節既有項目；號碼取最大號＋1，不重用。
- 補完用 `git diff TODO.md` 秀給使用者看。

---

## 步驟 2 — 選任務

- 使用者有指定代號 → 做那一項；批次模式照路線圖順序。
- 沒指定 → 取第一個 `- [ ]` 的主 task；有子 task 從第一個未完成的子 task 做起。
- TODO 已無 `[ ]`，或使用者給的是「一個方向」（某幾章教材、一句需求）而不是任務 → 改用 `task-plan` skill 先規劃出任務。
- 任務帶圖片（`![](assets/xxx.png)`）→ **用 Read 打開每張圖看**。
- 任務標了參考資料頁碼 → 先讀設定裡的參考資料索引與對應摘要檔；要讀掃描 PDF 見附錄 A。

**使用者中途在 dev 加了需求**（merge 時發現 dev 的 `TODO.md` 有未 commit 改動、`assets/` 多了圖）：
1. Read 每張新圖，照規則補編號（號碼接目前最大號）。
2. 只用「`TODO.md`＋對應附圖」做一個 commit 進 dev（訊息「TODO：使用者新增 XX-NN～MM」），這是唯一允許主 session 直接在 dev commit 的情況。
3. 回工作分支 `git merge --ff-only dev` 同步。
4. 規格明確的項目接在本波路線圖尾端做；屬「一個方向」的先用 `task-plan` 拆成子任務並在回報裡列出，不自行猜規格。
5. 若新需求是對本波剛做完的項目的回饋（例如版面要改），視為新任務、不回頭改舊 commit。

**等 worker 時預先核對下一項**：Explore 只讀不改，可與目前 worker 並行；在 worker 跑的空檔派 Explore 做下一項的 3a，worker 回來就能直接派下一項。不要同時開兩個 worker（除非符合附錄 C）。

**任務太大就先切**：同時動到「資料結構＋UI＋匯出」或預估單一 worker 要讀外部資料又改 300 行以上 → 拆成子 task（如 a 資料與相容、b UI、c 匯出／範本），各自驗證。切法見 `task-plan` 步驟 5。

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
批次模式：主 session 自己過一遍「要決定的點」，直接進步驟 3c。

**3c 派 planner 寫 spec（測試先行，點頭後第一件事）**：

- 開這項任務的 worktree（從最新 dev 分出，`tdd-<代號>`），確認裡面有 `node_modules`（雲端掛載不能 symlink → 從本機安裝目錄 `cp -rL --no-preserve=links`）。
- 派一個 planner subagent（`general-purpose`，只能新增 `tests/tasks/<代號>.spec.ts`，不碰主程式檔），prompt 給：TODO 原文與附圖路徑、相關函式／class 的 grep 線索、下面的 spec 規格、`npm test` 與回歸腳本的跑法。
- **spec 規格**（寫進 prompt）：
  - 驗收條件寫成可量測斷言：`getBoundingClientRect` 的寬度與對齊（±1px）、`getComputedStyle` 的顏色／字級／邊框、375×667 與 1440×900 兩種 viewport 下 `document.documentElement.scrollWidth <= clientWidth`（不得橫向捲動；容器內捲動屬設計者另斷言容器）、拖曳／匯出／匯入等互動過程 `pageerror` 與 `console.error` 必須為 `[]`、視覺重要處 `toHaveScreenshot(..., { maxDiffPixelRatio: 0.01 })`。
  - 每個 test 註解寫對應 TODO 的哪句驗收條件；不測實作細節（函式名、內部變數），除非 TODO 指名。
  - 不用 `test.skip`／`fixme`／`only`、不用 try/catch 吞斷言、`waitForTimeout` ≤ 500ms。
  - 截圖基準 PNG **planner 不產生**（dev 上沒有目標狀態可拍），跑完要刪掉自動產生的 `*-snapshots/` 與 `test-results/`。
- planner 回報必須貼 **在 dev 上跑的實際輸出**：至少一個「任務核心驗收」斷言失敗，而且失敗訊息是量測值（寬度、顏色、文字、位置），不是只有「snapshot doesn't exist」；既有測試仍全綠。核心斷言在 dev 上就通過 → 兩種情況：量測方式錯（退回 planner 重寫）或功能其實已在 dev 上（回報使用者，該項改走「補測試＋收尾」不派 worker）。
- planner 只 commit spec 一個檔，主 session 記下 commit 與 `git hash-object tests/tasks/<代號>.spec.ts`，寫進 worker 與 verifier 的 prompt。
- 既有測試在 dev 上本來就紅（例如缺截圖基準）→ 先另開小分支補基準、ff 併入 dev、任務分支 rebase，再派 planner；不要讓 worker 面對本來就紅的套件。

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

**prompt 另要給 TDD 契約**：spec 路徑與 hash、「完成定義」＝`npm test` 全綠（含這支 spec 與既有全部）＋ 回歸腳本 ALL PASS、最多 6 輪、每輪要貼實際測試輸出（最後 30 行左右，含 passed／failed 計數與 exit code）、不得改 spec、截圖基準只在非截圖斷言全綠後用 `--update-snapshots` 產生一次並 commit。

worker 回來後：
- `git diff --stat` 看改動範圍有沒有超出計畫；超出 → 回報使用者（批次模式：自行判斷是否接受並記錄）。
- `git hash-object tests/tasks/<代號>.spec.ts` 必須等於 planner 的值；不等 → 退回，不進 verifier。
- 回報裡沒有貼測試輸出、或只有摘要 → 用 SendMessage 要它補貼，不自己猜。
- 6 輪仍紅 → 停下回報（互動模式問使用者；批次模式把該項標「【6 輪未過】」留在 TODO，附最後一輪輸出，接下一項）。

---

## 步驟 5 — 派 verifier subagent 驗證

**改的人不驗自己。** 另派 `subagent_type: verifier-sonnet`（只有 Read／Bash／Grep／Glob）。subagent 不能再開 subagent，一定是主 session 依序派。

verifier prompt 交代：任務代號、計畫中的【驗收】、worker 報告的改動清單與自測腳本路徑（`tools/selftest/<代號>.mjs`）、這項特有的檢查點、專案設定裡的舊存檔相容方式，以及 **TDD 契約**：任務分支名、要比對的 spec hash、乾淨 checkout 的做法（`git worktree add --detach .claude/worktrees/verify-<代號> <分支>`，複製 `node_modules`，跑 `npm test` 全套＋回歸腳本；跑完 `git worktree remove`）。標準四項檢查（語法、舊存檔相容、截圖、回歸）已在 agent 定義裡，不必重抄。

verifier 的 TDD 判定（agent 定義已寫，主 session 只看結果）：spec hash 不同、`git log -p -- tests/tasks/<代號>.spec.ts` 在 planner 之後還有 commit、截圖基準重跑不符、全套有任何紅 → **FAIL**，不得以「只是截圖差一點」放行。

verifier 回報後，主 session **自己 Read 一張關鍵截圖**確認。
**FAIL → 先判斷是誰錯**：FAIL 可能是程式真的有問題，也可能是主 session 的驗收條件寫錯（例如要求「捲動 < 300px」但面板本來就在頁面下方）、或 verifier 自己的腳本門檻設錯。屬後兩者 → 記進 `doc/decisions.md`／回報，當 PASS 收尾；屬程式問題 → **不收尾**：互動模式回報使用者問要不要再派 worker 修；批次模式直接再派 worker 修（同一 worker 用 SendMessage 續做），最多兩輪，仍 FAIL 才停下回報。
**verifier 掛住**（回報「等待自己的背景工作」超過約 10 分鐘沒下文）：用 SendMessage 催一次「已完成的先回報、沒結束的列未完成」；仍無回應就 `ls` 它的輸出目錄、讀 out.txt 等已寫出的結果，缺的部分主 session 自己補驗（小腳本或直接看檔），並 `kill` 它殘留的 node／Chrome。常見原因：共用 harness 對超長頁（如手冊）整頁截圖會卡，驗證 prompt 要寫「截元素或視窗，不要整頁」。

驗證後若只做小修，主 session 至少自己跑一次語法檢查再收尾：

```bash
"${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/marketplaces/claude-task-workflow/plugins/task-workflow}/tools/check-js.sh" <主程式檔>
```

---

## 步驟 6 — 收尾

呼叫 `task-release` skill：TODO.md 標 `[x]`＋完成摘要（含「新增 N 個 test、worker N 輪」）、版本日期標記、commit、push 分支；批次模式含 merge 到 dev。
**併入 dev 只用 fast-forward**：先在任務分支 `git rebase dev`（有衝突就解完再派 verifier 重跑一次，rebase 後的狀態才是要併的狀態），再到 dev `git merge --ff-only tdd-<代號>`；ff 不了就不併，回頭 rebase。verifier 不是全綠絕不併。
同時更新：
- `doc/decisions.md`：這項任務裡主 session 替使用者做的產品決定（一行一條：日期、任務、決定、理由、可逆性）。
- `doc/pending-checks.md`：verifier 列的「待使用者手點」項目（勾選式清單，release 前清掉）。
- 驗證時新發現的問題 → 照 TODO 規則編號加進 `TODO.md`。

---

## 步驟 7 — 回報／接下一項

每項做完回報：代號、commit、分支（批次模式含 merge 到 dev 的 commit）、驗證結果、下一個未完成項目。

**一波（或批次）結束時**：
1. 寫 `doc/dev-log/YYYY-MM-DD.md`（或當日檔追加一節）：做了哪些（表格：任務／worker／commit／merge commit）、順手修到的舊 bug、決定了什麼、待確認、閘門結果、流程觀察、下一波建議。這是 `/clear` 後接手的檢查點。
2. 跑設定裡的 release 閘門（預設 plugin 的 `tools/release-check.sh`，需要 `node_modules`；裝不起來（如雲端掛載權限）就說明略過，改以專案零依賴的回歸腳本為準）。
3. 建議使用者 tag 或 release：「dev 比 main 多 N 個 commit，建議 release vX.Y.Z」。沒聽到「release」不動 main。
4. 彙整 `doc/pending-checks.md` 未勾項目給使用者。
5. 還沒做的任務在 `TODO.md` 標清楚（例如前綴「【尚未做】」或「待排程」），並把需要使用者決定的事（會改 PPTX／匯出基準、需舊檔遷移、規格有歧義）單獨列一段。

**最終回報固定格式**（讓只看最後一則訊息的人也看得懂）：
```
已完成並併入 dev：<逐項一行：代號 標題（一句話）>
順手修到：<舊 bug 或新發現，附已登記的 TODO 代號>
要請你決定：<條列>
待你本機手點：<指向 pending-checks.md 的節>
建議下一步：release vX.Y.Z（dev 比 main 多 N 個 commit）／接著做 XX-NN
```

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

- 掛載偶爾殘留 `index.lock`（0 byte）。看到「Another git process seems to be running」時：`ls -la "$(git rev-parse --git-dir)/index.lock"` 確認是 0 byte 且 `pgrep -x git` 沒有程序，才 `rm -f` 重試；每個 worktree 的 git-dir 不同（`.git/worktrees/<名>/index.lock`），要用 `git rev-parse --git-dir` 找。不是 0 byte 或有程序在跑就等幾秒重試，不要硬刪。
- `tools/release-task.sh`（或同類收尾腳本）若在 `git commit` 那步被鎖擋下，TODO 已勾、檔案已 stage：清鎖後手動 `git commit -F`，不要重跑腳本（會重複勾 TODO）。
- `sed -i` 在該掛載會印「preserving permissions … Operation not permitted」，改動仍生效，可忽略；改檔優先用 python 或 Edit 工具。
- `git push -u` 在該掛載會印 chmod 警告，push 本身成功，用 `git ls-remote` 確認即可。
- `git branch -m` 在該掛載會印 config.lock chmod 錯誤，但分支已改名，`git branch --show-current` 確認即可。
- 被 worktree 隔離守門擋下的指令（「too complex to verify」「names git in a form…」）：把 heredoc／python 文字裡含「git」字樣的內容先用 Write 工具寫到暫存檔再 `cat >>`，git 指令單獨一行跑。

## 附錄 C — 平行派工：依檔案重疊分波

planner 可以全部同時派（只各自新增一個 spec 檔，不衝突）。worker 依「會動到的函式／CSS 區塊」分波：

1. 從 planner 的實作提示列出每項會動到的區塊（函式名、CSS 選擇器、資料欄位）。
2. 區塊不重疊的任務放同一波同時派 worker，各自 worktree；重疊的排到下一波，並在上一波 ff 併入 dev 後 `git rebase dev` 再開工（spec 不用重寫，但要在 rebase 後的 dev 上重新確認仍是紅的）。
3. 同一波內先綠的先併（rebase → verifier 重跑 → ff）；後併的必須 rebase 到最新 dev 後再過一次 verifier。
4. 一波結束回報一張表：任務／worker 輪數／新增 test 數／合併狀態（已 ff 併入 dev 的 commit、或「6 輪未過」「verifier FAIL：原因」）。

舊的平行條件仍適用：
- 各任務動到的函式區塊不重疊。
- 共用熱點（如存檔／載入函式）各只加一行，且約定「新欄位獨立一行、接在前一個新欄位之後」。
- `TODO.md` 只動自己那一行。
merge 順序：文件 → 視覺 → 資料結構，衝突由主 session 解。verifier 仍一項一個，依序派。

---

## 版本紀錄

| 版號 | 日期 | 變更 |
|---|---|---|
| 1.7.0 | 2026-10-27 | 測試先行：硬規則 8–9；步驟 3c 派 planner 寫 `tests/tasks/<代號>.spec.ts` 並證明在 dev 上先紅（量測斷言，不是只缺截圖）；步驟 4 worker 以 spec＋全套＋回歸全綠為完成、≤6 輪、每輪貼實際輸出、不得改 spec、hash 比對；步驟 5 verifier 從乾淨 checkout 重跑並拒收改 spec；步驟 6 只 ff 併入 dev；附錄 C 改為依檔案重疊分波與回報表 |
| 1.5.0 | 2026-10-26 | 依 strategy-matrix 第六波（ST-22～34a，11 項一次跑完）經驗：步驟 0 加「指定代號」模式與新觸發詞；批次模式改「整波一條分支、每項 PASS 後以指定 commit 併入 dev」；中途使用者在 dev 加需求的處理；等 worker 時預先 Explore 下一項；FAIL 先判斷是驗收條件錯還是程式錯；verifier 掛住的處理；批次模式缺 CLAUDE.md 設定節自行補；最終回報固定格式；附錄 B 補鎖檔、收尾腳本中斷、隔離守門的處理 |
| 1.3.0 | 2026-10-25 | 改為 plugin 版：專案專屬內容（主程式檔名、頁碼對照、資料慣例）移到各專案 CLAUDE.md 的「task-workflow 設定」；工具路徑改走 `CLAUDE_PLUGIN_ROOT`。功能同 strategy-matrix 1.3.0（授權批次模式、派工前核對事實、decisions／pending-checks／dev-log） |
| 1.2.0 | 2026-09-28 | 派工改用 `worker-haiku`／`worker-sonnet`／`worker-opus`、驗證改用 `verifier-sonnet` |
| 1.1.0 | 2026-09-28 | 改檔交 worker subagent、驗證另派 verifier、讀主程式用 Explore；主 session 用量守六成 |
| 1.0.0 | 2026-09-28 | 建立：參考 QMSWeb `qms-next` |
