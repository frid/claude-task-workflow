---
name: task-explore
description: >-
  對 TODO.md 裡一項 UI 任務做「多變體探索」：先列 3–4 種實質不同的詮釋或設計（每種一行取捨），
  每個變體派一個 worker 在自己的 git worktree（分支 explore/<代號>-<字母>）做最小可運作版，
  用 headless Chrome 替每個變體截桌面 1440px 與手機 375px 畫面並量測（溢出、文字對比、元素數），
  產生 explore/<代號>/variants.html 並排比較頁並用使用者的 chrome alias 開啟，然後停下等使用者選。
  使用者選定（例「B」「B 但用 A 的配色」）並說「開始」後，刪其他 worktree／分支，把選中的分支交給
  task-next 產線測試、驗證、併入 dev。當使用者說「探索」「出幾個版本比較」「/task-explore」
  「用 explore 做下一個 UI 任務」時使用。硬規則：不碰 main 與 dev；使用者說「開始」之前絕不在選中的路徑上改檔。
metadata:
  version: "1.6.0"
---

# Task Explore — 一個 UI 任務，多個變體並排比較

流程：**選任務 → 列變體 → 每變體一個 worktree 派工 → 截圖＋量測 → 比較頁 → 停下等選 → 收斂交給 task-next**。
全程用繁體中文跟使用者溝通。專案設定一律讀專案 `CLAUDE.md` 的 `## task-workflow 設定`（主程式檔、自測 harness、語法檢查）。

適用對象：**UI／版面／互動方式**有多種合理設計的任務。純邏輯、文字修正、資料遷移類任務不要用這個 skill，直接走 `task-next`。

---

## 🚨 硬規則

1. **不碰 `main` 與 `dev`**：所有變體都在 `explore/<代號>-<字母>` 分支的 worktree 裡做，從最新 `dev` 分出。
2. **使用者說「開始」之前，絕不在選中的路徑上改檔**：步驟 5 停下後，主 session 與任何 subagent 都不得再改任何變體的檔；只能讀、截圖、回答問題。
3. **變體要「實質不同」**：不同的互動模型、資訊架構或版面結構（例：單一統一下拉 vs 各區塊各自控制；固定工具列 vs 側邊面板；疊層橫帶 vs 容器框）。只差顏色、字級、間距的不算變體。
4. **最小但可運作**：每個變體只做到能載入、能看出設計差異、既有功能不壞（連線、拖曳、改名等照專案設定的「回歸必查功能」）。不做存檔欄位、PPTX、手冊——那些留給 task-next 產線。
5. **一次只探索一項任務**；主 session 不直接改主程式檔，改檔全交 worker。
6. 選定後**只保留一條分支**，其他 worktree 與分支刪掉（步驟 6），避免分支堆積。

---

## 步驟 1 — 選任務

```bash
cat TODO.md
git status --short
git branch --show-current
git -C <dev 檢出目錄> log --oneline -1
```

- 使用者指定代號就做那一項；沒指定就取 TODO.md 第一個 `[ ]` 且屬於 UI／版面類的項目（跳過 `[~]` 進行中與非 UI 項）。有附圖先看圖。
- 把任務標題、已定事項（TODO 裡「已定：」行）、相依子項抄成一段「任務摘要」。已定事項是**約束**，不是變體的自由度。
- 派一個 `Explore` agent 讀主程式檔相關區塊（DOM 結構、CSS、資料形狀、要保留的互動與連線端點），回報帶行號的地圖；等它的同時寫步驟 2。

## 步驟 2 — 列變體（3–4 種）

格式固定，給使用者看一次：

```
▶ <代號> 變體
  A <名稱>：<一行設計描述> — 取捨：<一句>
  B <名稱>：... — 取捨：...
  C ...
  D ...（可選）
  共同約束：<已定事項、要保留的互動>
  量測：桌面 1440 / 手機 375 截圖；溢出、文字對比、元素數
```

不等使用者點頭，直接進步驟 3（探索本身就是給使用者看成品再選；但使用者若已回覆刪減變體，照辦）。

## 步驟 3 — 每變體一個 worktree，平行派工

從 dev 檢出目錄建分支與 worktree（**不要**從目前含未 commit 改動的工作分支分出）：

```bash
DEV=<dev 檢出目錄>; ROOT=$(git -C "$DEV" rev-parse --show-toplevel 2>/dev/null || git -C "$DEV" rev-parse --git-common-dir | xargs dirname)
for L in A B C D; do
  git -C "$DEV" worktree add -b explore/<代號>-$L "$ROOT/.claude/worktrees/explore-<代號>-$L" dev
done
```

每個變體派**一個** worker（`task-workflow:worker-sonnet`；動到資料結構或多處連動用 `worker-opus`），**同一則訊息一起派**。派工 brief 必含：

- 工作目錄（該 worktree 絕對路徑）與「只在這個目錄改檔、不要 cd 到別處、不要 commit 到別的分支」。
- 任務摘要＋共同約束＋**該變體的設計描述**（只做自己這一個，不要順手做別的變體）。
- Explore 回報的程式地圖（行號、函式名、要保留的 selector／data 屬性）。
- 最小範圍：改哪些函式／CSS；不做什麼（存檔、PPTX、手冊）。
- 完成條件：專案設定的語法檢查過；載入兩個範例與 fixtures 無 console error；`git add -A && git commit -m "explore <代號>-<字母>：<變體名>"`。
- 回報格式：改了哪些函式／行數、新增的 CSS class、已知限制，10 行內。

## 步驟 4 — 截圖與量測

worker 全部回來後，主 session 自己跑 plugin 的 `tools/explore-shots.mjs`（零 npm 依賴，用專案 `tools/cdp-harness.mjs`）：

```bash
node <plugin>/tools/explore-shots.mjs \
  --harness <專案>/tools/cdp-harness.mjs \
  --out <專案 dev 檢出目錄>/explore/<代號> \
  --example <範例名> --step <步驟選擇器或 goto 表達式> \
  --focus '<要截的區塊 selector>' \
  A=<worktree A>/index.html B=<worktree B>/index.html ...
```

它會替每個變體在 1440×900 與 375×812 各截一張（整頁＋ focus 區塊），並寫 `metrics.json`：

- **溢出**：`document.documentElement.scrollWidth > innerWidth`、focus 區塊內 `scrollWidth > clientWidth` 的元素數。
- **文字對比**：focus 區塊內所有有文字的元素，取 computed color 與最近非透明背景算 WCAG 對比，回報最低值與 < 4.5 的數量。
- **元素數**：focus 區塊內 DOM 節點數；全頁 console error 數。

截圖寫 `explore/<代號>/<字母>-desktop.png`、`<字母>-desktop-focus.png`、`<字母>-mobile.png`。`explore/` 目錄加進專案 `.gitignore`（若還沒有）；比較頁不進 git。

## 步驟 5 — 比較頁，開給使用者，停下

主 session 跑 `tools/explore-shots.mjs` 時加 `--html` 會同時產生 `explore/<代號>/variants.html`：每個變體一欄，標籤＝字母＋名稱＋一行取捨，下面桌面圖、手機圖、量測摘要表（溢出／最低對比／對比不足數／元素數／console error），底部列各分支名與 commit。

```bash
chrome <專案>/explore/<代號>/variants.html     # 使用者的 alias：用 Windows Chrome 開 WSL 檔案
```

然後**停下**，訊息固定格式：

```
▶ <代號> 變體已開在 Chrome（explore/<代號>/variants.html）
  A <名稱> — 分支 explore/<代號>-A — <量測一行>
  B ...
  請回覆選擇，例「B」或「B 但用 A 的配色」，後面接「開始」。
  我在聽到「開始」前不會再改任何變體。
```

等待期間只回答問題、補截圖，不改檔。

## 步驟 6 — 使用者選定並說「開始」後

1. 解析選擇：主分支（例 B）＋要從其他變體搬過來的元素（例「A 的配色」）。有搬運需求時，把要搬的具體 diff（`git -C <A worktree> diff dev -- index.html` 的相關段落）寫進 task-next 的任務描述，**由產線的 worker 做**，不是在這裡做。
2. 刪其他變體：
   ```bash
   for L in <未選字母>; do git -C "$DEV" worktree remove --force "$ROOT/.claude/worktrees/explore-<代號>-$L"; git -C "$DEV" branch -D explore/<代號>-$L; done
   ```
3. 把選中的 worktree 改名為產線慣例並交棒：
   ```bash
   git -C "$ROOT/.claude/worktrees/explore-<代號>-<選>" branch -m explore/<代號>-<選> worktree-<代號小寫>
   ```
   在 `TODO.md` 該任務下加一行「探索（YYYY-MM-DD）：選 <字母> <名稱>，搬 <...>；分支 worktree-<代號>」，然後呼叫 `task-workflow:task-next`，以「做 <代號>」指定代號模式接手：task-next 從該分支現狀出發，補完整版（存檔欄位、PPTX、手冊、自測）、派 verifier、task-release 收尾。合併到 dev 仍要聽到使用者說「merge」。
4. `explore/<代號>/` 比較頁留著給使用者對照，不進 git。

---

## 附錄 — 常見問題

- **worker 在錯的目錄改檔**：brief 第一行就寫絕對路徑；回來後 `git -C <worktree> status` 確認只有該分支有 diff。
- **某變體做不出來或壞了既有功能**：比較頁照樣列出並標「未完成／壞了 X」，讓使用者知道這條路的成本；不要悄悄砍掉。
- **截圖不到該區塊**：`--step` 可傳 JS 表達式（例 `guideGoto(1)`），`--focus` 可傳多個 selector 用逗號分隔；harness 的 `shot(selector)` selector 為 null 即整頁。
- **Explore 回報與實際不符**：worker 以程式為準，回報裡註明。
