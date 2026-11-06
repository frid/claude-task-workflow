---
name: task-submit-worklog
description: >-
  PA 工作紀錄寄送與彙整（pa-worklog/v2）：讓不同端點上的 Claude 把「這段時間做了什麼」整理成同一份欄位規格的
  工作紀錄信，寄到 Frid 自己的公司信箱；PA 統整端再用 Gmail 搜尋撈回，併入週報 md 與 PA-Frid-2026.pptx。
  專案名稱讀各專案 task-workflow 設定的「PA 專案名稱」（跟著 repo 走），信中附該專案的 ChangeLog 摘要。
  模式 A 寄送：使用者說「回報工作紀錄」「送工作紀錄」「/worklog」「把今天做的寄給 PA」時使用。
  模式 B 彙整：在 PA 統整端，使用者說「收工作紀錄」「整理PA」時作為資料來源之一。
  硬規則：只收公司工作、寄出前必做資安檢查、只寄本人信箱不加 cc／bcc、不用 SMTP 或任何需要帳密的方式寄信。
metadata:
  version: "2.0.0"
---

# PA 工作紀錄寄送（task-submit-worklog）

用途：讓不同端點上的 Claude 把「這段時間做了什麼」整理成**同一份欄位規格**的工作紀錄信，寄到 Frid 自己的公司信箱；PA 統整端再用 Gmail 搜尋把所有紀錄撈回來，併入週報 md 與 PA-Frid-2026.pptx。

一律使用台灣繁體中文；程式碼、指令、產品名稱保留原文。

## 兩種模式

- 模式 A「寄送」（預設）：使用者說「回報工作紀錄」「送工作紀錄」「/worklog」「把今天做的寄給 PA」。
- 模式 B「彙整」：在 PA 統整端，使用者說「收工作紀錄」「整理PA」時，作為資料來源之一。

---

## 回報欄位規格（pa-worklog/v2）

這是唯一的欄位標準。所有端點都照此填，不可自行增減欄位或改名。

通用規則：
- **必填**欄位一定要出現；答不出來先問使用者（最多一個問題），仍無資料就填 `未提供`，不可省略欄位。
- **選填**欄位無資料時給空字串 `""` 或空清單 `[]`，欄位仍保留。
- 有「受控詞」的欄位只能用下表的值。
- 日期一律 `YYYY-MM-DD`，時區 UTC+8；週次一律 ISO 週（週一起算，例：2026-10-12～10-18 = `2026-W42`）。
- 不可臆測數字（工時、token、進度）；只填使用者說過或工具算得出來的。

### 1. 信件抬頭（每封一份）

| 欄位 | 必填 | 說明／格式 |
|---|---|---|
| `schema` | 必填 | 固定 `pa-worklog/v2` |
| `worklog_id` | 必填 | `WL-YYYYMMDD-HHMM-<端點簡稱>-<4 碼隨機 hex>`，每封唯一 |
| `supersedes` | 必填 | 更正舊紀錄時填舊 `worklog_id`，否則 `""` |
| `reporter` | 必填 | 固定 `Frid Hou` |
| `report_date` | 必填 | 寄出當天日期 |
| `week` | 必填 | 工作發生的 ISO 週次，如 `2026-W45` |
| `period` | 必填 | `{start: YYYY-MM-DD, end: YYYY-MM-DD}`，工作發生區間 |
| `surface` | 必填 | 受控詞：`claude.ai-web`／`claude.ai-mobile`／`claude.ai-desktop`／`claude-code`／`其他` |
| `device` | 必填 | 電腦名稱（Claude Code 用 `hostname`）；網頁／手機填 `未提供` |
| `projects` | 必填 | 清單，依「專案名稱」取得；`items`、`changelog` 用到的專案都要列在這裡 |
| `summary` | 必填 | 本封一句話重點，40 字內 |

### 2. 工作項目 `items`（至少一項；每件事一項）

| 欄位 | 必填 | 說明／格式 |
|---|---|---|
| `category` | 必填 | 受控詞（對應週報章節）：`主線工作`／`對外與供應鏈`／`業務發展`／`會議與行政`／`品質法規`／`其他` |
| `project` | 必填 | 依「專案名稱」取得 |
| `title` | 必填 | 30 字內；有任務編號放最前面（如 `BE-36 文件版次查詢 API`） |
| `status` | 必填 | 受控詞：`完成`／`進行中`／`阻塞`／`取消` |
| `progress` | 條件必填 | `進行中` 時填 0–100 的整數（使用者或追蹤檔有說才填，否則 `未提供`）；其他狀態填 `""` |
| `detail` | 必填 | 做了什麼／結果為何，100 字內 |
| `outputs` | 選填 | 清單，每筆 `類型:值`；類型限 `version`／`commit`／`doc`（文件編號＋版次）／`file`（檔名或路徑）／`link` |
| `related` | 選填 | 涉及的人員／部門／廠商名稱清單 |
| `due` | 選填 | 預定完成日 |
| `hours` | 選填 | 使用者自述的工時（小時），不可推估 |

### 3. 整體區塊

| 欄位 | 必填 | 說明／格式 |
|---|---|---|
| `decisions` | 必填 | 決議／定案事項清單；無則 `[]` |
| `issues` | 必填 | 每筆 `{issue: 問題或阻礙, need: 需誰協助或等待什麼}`；無則 `[]` |
| `next_steps` | 必填 | 每筆 `{task: 下一步, due: 日期或 ""}`；無則 `[]` |
| `tracking` | 選填 | 對上期追蹤事項的進展，每筆 `{item: 事項, status: 受控詞同 items.status, note: ""}` |
| `ai_usage` | 必填 | 見下表 |
| `security_check` | 必填 | 完成 A3 資安檢查後填 `passed` |

`ai_usage` 子欄位：

| 欄位 | 必填 | 說明 |
|---|---|---|
| `models` | 必填 | 使用的模型清單（如 `claude-opus-5-5`）；不確定填 `[未提供]` |
| `patterns` | 必填 | 受控詞清單：`程式開發`／`文件撰寫`／`資料分析`／`查詢研究`／`簡報製作`／`會議整理`／`其他` |
| `sessions` | 選填 | 對話／session 數 |
| `tokens_total` | 選填 | **僅 Claude Code 可填**：`~/.claude/projects/**/*.jsonl` 依 `message.usage` 加總 input＋output＋cache_creation＋cache_read，以 `uuid` 去重，限定 `period` 內、排除私人專案目錄；其他端點 `""` |
| `source` | 必填 | `jsonl`（腳本計算）／`self-report`（端點自述） |
| `note` | 選填 | 補充；有 token 數時加註「名目換算，非帳單」 |

### 4. ChangeLog 區塊 `changelog`（v2 新增）

必填；沒有可回報的 ChangeLog 給 `[]`。YAML 位置在 `items` 之後、`decisions` 之前。每個專案的每個版本一筆：

| 欄位 | 必填 | 說明／格式 |
|---|---|---|
| `project` | 必填 | 依「專案名稱」取得，須出現在 `projects` |
| `version` | 必填 | ChangeLog 上的版號（如 `v0.1.187`、`v2026.11.05`）；條目沒有版號（尚未發布）填 `""` |
| `date` | 必填 | 這個版本在 ChangeLog 上的日期；未發布那一筆填 `period.end` |
| `note` | 選填 | 上線狀態，20 字內，例：`已上線`／`預計今日上線`／`預計 11/20 上線`；無則 `""`（`version` 空就代表未發布，這裡不必再寫） |
| `source` | 必填 | 追溯用：ChangeLog 檔路徑＋條目範圍，如 `ChangeLog.md 2026-11-05（3 則）`；使用者口述填 `使用者口述` |
| `groups` | 必填 | 主題分組清單，每筆 `{heading: 主題, items: [一行一件事]}`，至少一組 |

撰寫規則：
- 分組：ChangeLog 原本就有主題小標的照用；沒有的由 Claude 依主題分 2–6 組。`heading` 用「中文 English」（如 `通知信 Email`、`穩定性 Reliability`、`維運 Ops`），英文可省略。
- 每行一件事、80 字內，寫「改了什麼／有什麼效果」，讓沒看過程式的人也看得懂；不照抄原文。
- 有任務代號就放行尾全形括號，多個用頓號：`（DV-05、FX-06）`。
- 同一版本重複的事合併成一行；只收 `period` 內已 commit 的條目，不收還沒做的計畫。
- 沒有版號的條目（尚未發布）同一專案合成一筆：`version` 給 `""`，人看的段落寫成「<project> 未發布（<date>）」；`note` 只放其他補充，無則 `""`。

### 專案名稱

v2 起專案名稱跟著 repo 走：同一個 repo 不管在哪台電腦、哪個資料夾、用哪個 Claude 開，回報的名稱都一樣。

Claude Code 端取名順序：
1. 讀專案的 task-workflow 設定：`CLAUDE.md` 的「## task-workflow 設定」一節；該節若指向別的檔（如 `.claude/rules/task-workflow.md`），讀那個檔。取 `- PA 專案名稱：` 那一行。
2. 沒有這一行 → 問使用者一次，建議值用 `git remote get-url origin` 的 repo 名稱；**不用資料夾名稱**（每台電腦路徑不同，同一專案會被當成不同專案）。使用者給了名稱後，問要不要把 `- PA 專案名稱：<名稱>` 加進設定；使用者同意才寫，並照該專案的 commit 規則提交。
3. 同一段工作碰到多個 repo → 各 repo 用各自的設定。

不在 repo 裡做的事（claude.ai 網頁／手機、會議、行政）用下列常用名稱；表裡沒有就直接寫名稱：
`QMSWeb`／`QMS文件`／`MDSAP`／`AI Gateway`／`本地轉錄MCP`／`OCR`／`PA週報`／`內部工具`／`行政`

格式限制：1–30 字；不可含 `、`、`|`、冒號（主旨用頓號、直線分隔）。v1 的 `其他:<名稱>` 在 v2 直接寫 `<名稱>`。

### ChangeLog 檔

- 讀同一份 task-workflow 設定的 `- ChangeLog 檔：` 那一行。設定寫「無」→ `changelog: []`。
- 沒有這一行 → repo 根目錄有 `ChangeLog.md` 或 `CHANGELOG.md` 就用它，並在回覆使用者時說明用了哪個檔；都沒有 → `changelog: []`。
- 設定若註明舊月份另存封存檔（如 `ChangeLog/YYYY-MM.md`），`period` 跨到封存月份時一併讀。

---

## 模式 A：寄送

### A1. 界定範圍

- 預設範圍 = 本次對話（或 Claude Code 本 session）＋使用者口述的今日工作。使用者指定區間（如「這週」）則以其為準。
- 只收公司工作；私人專案（如 EMBA 課業）一律排除。
- Claude Code 端可參考專案的 `TODO.md`、ChangeLog 檔、`git log --since` 補齊 `outputs` 與 `progress`。
- Claude Code 端先讀專案的 task-workflow 設定，取得 `PA 專案名稱` 與 `ChangeLog 檔`（見「專案名稱」「ChangeLog 檔」）。
- `changelog`：只讀 ChangeLog 檔裡日期落在 `period` 內的條目，照「4. ChangeLog 區塊」整理。claude.ai 端讀不到檔，使用者貼上 ChangeLog 才填，否則 `[]`。

### A2. 依規格填欄位

照「回報欄位規格」逐欄填寫。填完自檢：
- [ ] 所有必填欄位都在，沒有自創欄位
- [ ] 受控詞欄位的值都在詞表內
- [ ] `進行中` 的項目都有 `progress`
- [ ] 沒有臆測的數字
- [ ] `projects`、`items[].project`、`changelog[].project` 名稱一致，且照「專案名稱」取得
- [ ] ChangeLog 每行 80 字內、有任務代號就放行尾括號、`source` 有寫

### A3. 資安檢查（寄出前必做）

逐項確認，命中就刪除或改寫成摘要，全部通過才把 `security_check` 填 `passed`：

- 不含密碼、API key、token、憑證、連線字串、內網 IP 與帳號。
- 不貼受控文件全文或大段原文，只寫文件編號＋版次＋做了什麼。
- 不含病患資料或可識別個資；他人只寫姓名／部門到工作必要程度。
- 不附加檔案；參照檔案寫路徑或 Drive 連結。
- ChangeLog 條目同樣適用以上各點：只寫功能層面的變更，不寫內網 IP、UNC 共享路徑、帳號、連線字串。
- 只寄給 Frid 本人信箱，不加 cc／bcc。

### A4. 組信

- 收件人：`fridhou@brainnavi.com`（只此一個）
- 主旨：`[PA-WORKLOG] <report_date> <week 的 Wxx> | <surface>@<device> | <projects 以頓號連接> | <summary>`；更正信在 `[PA-WORKLOG]` 後加 `更正`。
- 內文用純文字（`body`），不可用 Markdown 語法。分兩段，順序固定：
  1. 人看的摘要：標題行 → 依 category 分組列項目（只列有內容的分類，順序同受控詞）→ 【Changelog】（`changelog` 為 `[]` 時整段省略）→ 決議 → 問題／阻礙 → 下一步 → AI 使用。
  2. 機器讀的區塊：`---WORKLOG-BEGIN---` 與 `---WORKLOG-END---` 之間放完整 YAML，欄位順序同規格。

【Changelog】段的排法（每個版本一段）：

```
【Changelog】
<project> <version；空的寫「未發布」>（<date>，<note>）   ← note 空就只寫日期
<heading>
・<一行一件事（任務代號）>
```

範例：

```
PA 工作紀錄｜2026-11-03（W45）｜claude-code@bn-lab-pc
摘要：eQMS v0.1.187 上線版次查詢 API，週會定案 CAPA 表單改版

【主線工作】
1. BE-36 文件版次查詢 API｜eQMS｜完成
   新增 /api/docs/{key}/revisions，含分頁。產出：v0.1.187、commit a1b2c3d
2. BE-37 權限檢查｜eQMS｜進行中 40%
   完成角色對照表，待接 middleware。
【會議與行政】
1. 部門週會｜行政｜完成
   討論 CAPA 表單改版時程。

【Changelog】
eQMS v0.1.187（2026-11-03，預計今日上線）
文件查詢 Search
・文件版次查詢 API，可分頁、依版次排序（BE-36）
・查詢頁顯示目前有效版次（FE-22）
權限 Access
・新增角色對照表，供後續權限檢查使用（BE-37a）

決議：下週起 CAPA 表單改版
問題／阻礙：無
下一步：BE-37 接 middleware（預計 2026-11-05）
AI 使用：claude-opus-5-5｜程式開發｜3 sessions｜約 12.3M tokens（名目換算，非帳單）

---WORKLOG-BEGIN---
schema: pa-worklog/v2
worklog_id: WL-20261103-1530-bn-lab-pc-7f3a
supersedes: ""
reporter: Frid Hou
report_date: 2026-11-03
week: 2026-W45
period: {start: 2026-11-03, end: 2026-11-03}
surface: claude-code
device: bn-lab-pc
projects: [eQMS, 行政]
summary: eQMS v0.1.187 上線版次查詢 API，週會定案 CAPA 表單改版
items:
  - category: 主線工作
    project: eQMS
    title: BE-36 文件版次查詢 API
    status: 完成
    progress: ""
    detail: 新增 /api/docs/{key}/revisions，含分頁
    outputs: ["version:v0.1.187", "commit:a1b2c3d"]
    related: []
    due: ""
    hours: ""
  - category: 主線工作
    project: eQMS
    title: BE-37 權限檢查
    status: 進行中
    progress: 40
    detail: 完成角色對照表，待接 middleware
    outputs: []
    related: []
    due: 2026-11-05
    hours: ""
  - category: 會議與行政
    project: 行政
    title: 部門週會
    status: 完成
    progress: ""
    detail: 討論 CAPA 表單改版時程
    outputs: []
    related: [品保部]
    due: ""
    hours: ""
changelog:
  - project: eQMS
    version: v0.1.187
    date: 2026-11-03
    note: 預計今日上線
    source: "ChangeLog.md 2026-11-03（3 則）"
    groups:
      - heading: 文件查詢 Search
        items:
          - 文件版次查詢 API，可分頁、依版次排序（BE-36）
          - 查詢頁顯示目前有效版次（FE-22）
      - heading: 權限 Access
        items:
          - 新增角色對照表，供後續權限檢查使用（BE-37a）
decisions: [下週起 CAPA 表單改版]
issues: []
next_steps:
  - {task: BE-37 接 middleware, due: 2026-11-05}
tracking: []
ai_usage:
  models: [claude-opus-5-5]
  patterns: [程式開發]
  sessions: 3
  tokens_total: 12300000
  source: jsonl
  note: 名目換算，非帳單
security_check: passed
---WORKLOG-END---
```

YAML 注意：含冒號或特殊字元的字串加雙引號；寄出前確認可正確解析。Claude Code 端驗證（Linux／WSL／macOS／Windows Git Bash 通用）：

```bash
"${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/marketplaces/claude-task-workflow/plugins/task-workflow}/tools/validate-yaml.sh" 區塊.yaml
```

- 它會依序找有 PyYAML 的 Python：環境變數 `TW_YAML_PY` → BN-RD-AIServer 的 conda `NAS`（`/home/nas/miniconda3/envs/NAS/bin/python`，存在才用）→ 本機 `python3`／`python`／`py -3`；一律以 UTF-8 開檔（Windows cp950 下不會把中文誤判成錯誤）。
- exit 0＝通過；1＝YAML 有錯，修正後重驗；3＝沒有可用的 PyYAML：照提示 `python -m pip install --user pyyaml`，或逐欄人工核對並在回報中說明未經解析器驗證。
- 不要用 `python -c "…yaml.safe_load(sys.stdin)" < 區塊.yaml`：Windows 上 stdin 以 cp950 解碼，合法的中文 YAML 也會報 `ReaderError`。

### A5. 寄出（依可用工具降級）

1. 有 Gmail `send_message`：先把主旨與人看的摘要給使用者過目，再寄出（使用者明說「直接寄」就不必等）。回報 message id。
2. 只有 `create_draft`：建草稿，給使用者 viewUrl，請他按送出。
3. 完全沒有 Gmail 工具：
   - Claude Code：寫到 `~/pa-worklog-outbox/<worklog_id>.txt`，並在回覆中印出主旨與內文請使用者自行寄出；提醒可啟用 claude.ai 的 Gmail connector。
   - claude.ai：直接在回覆中給出主旨與內文供複製。
- 不要用 SMTP 腳本或任何需要帳密的方式寄信（資安考量）。

### A6. 收尾

一句話回報：主旨、worklog_id、message id（或草稿連結／檔案路徑）。

---

## 模式 B：彙整（PA 統整端）

1. Gmail 搜尋：`subject:"[PA-WORKLOG]" after:YYYY/MM/DD before:YYYY/MM/DD`（before 為結束日隔天）。寄給自己的信同時在寄件備份與收件匣，以 message 為單位處理。
2. 對每封 `get_thread`（PLAIN_TEXT），擷取 BEGIN／END 之間的 YAML 解析並依規格檢查：`schema` 不是 `pa-worklog/v1` 或 `pa-worklog/v2`、缺必填欄位、受控詞不符、`security_check` 非 `passed` → 仍納入但在週報資料來源聲明標「格式異常：<worklog_id>＜原因＞」；完全無法解析則改讀人看的摘要。
   - v1 相容：沒有 `changelog` 視同 `[]`；專案 `其他:<名稱>` 去掉前綴後當專案名稱。
3. 以 `worklog_id` 去重；有 `supersedes` 的以新的覆蓋舊的。
4. 依 `items[].category` 併入週報 md 對應章節；`decisions`、`issues`、`next_steps` 併入「後續追蹤重點」；`tracking` 併入「上期追蹤事項進度」。與 Gmail／Calendar／本機 jsonl 交叉比對，同一件事只寫一次。
5. `ai_usage.tokens_total` 只在該 `device` 不在本機 jsonl 統計範圍內時才加總，避免重複計算；`patterns` 供「AI 使用模式觀察」。
6. `changelog` 併入週報 md 該專案段落下的「版本更新」，排法同 A4【Changelog】段；以 `project`＋`version` 去重（同一版本取較新那封），未發布（`version` 為空）的同專案同週合併。
7. 週報「資料來源聲明」列出本週工作紀錄封數、端點清單與 worklog_id，確保可追溯；常用名稱表以外第一次出現的專案名稱另列，方便發現打錯字。
8. 不修改、不刪除原始工作紀錄信（保留為佐證）。

---

## 規格變更

增減欄位或受控詞時：更新本 skill，把 `schema` 升版（如 `pa-worklog/v2`），並在此記錄變更日期與內容。模式 B 需同時接受新舊版。

- 2026-11-03：v1 建立（以 `task-submit-worklog` 名稱加入 task-workflow plugin 1.8.0；來源需求 FolderScanner repo TODO WF-01）。
- 2026-11-06：v2（task-workflow plugin 1.10.0；來源：PM 口述需求）。①專案名稱改由各專案 task-workflow 設定的 `PA 專案名稱` 提供（跟著 repo 走，不用資料夾名稱），不再限固定詞表，取消 `其他:<名稱>` 前綴；②新增 `changelog` 區塊（版本 → 主題分組 → 一行一件事、行尾括號寫任務代號）與設定 `ChangeLog 檔`；③模式 B 同時接受 v1／v2。
