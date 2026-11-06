# claude-task-workflow

Claude Code plugin `task-workflow`：TODO.md 驅動的開發流程。`task-plan` 把教材／需求規劃成任務；一次一項、先規劃再派 worker subagent 改檔、另派 verifier 驗證、`task-release` 收尾；三層分支 `worktree → dev → main`。從 strategy-matrix 專案的流程抽出，專案專屬內容改由各專案 `CLAUDE.md` 提供。

## 內容

| 類型 | 名稱 | 用途 |
|---|---|---|
| skill | `task-plan` | 規劃：從教材／需求盤點現況、登記並摘要參考資料（標頁碼）、做差距表、切階段與子任務、寫進 TODO.md |
| skill | `task-next` | 接下一項任務：補編號、核對事實、寫計畫、派 planner 寫 spec（先紅）、派 worker 做到綠、派 verifier 乾淨 checkout 重跑、ff 併入 dev |
| skill | `task-explore` | 探索：一個 UI 任務列 3–4 種變體，各自 worktree 做最小版，截圖量測、並排比較頁，使用者選定後交 task-next |
| skill | `task-release` | 收尾：勾 TODO、更新日期標記、decisions／pending-checks、commit、push；merge／release 步驟 |
| skill | `task-submit-worklog` | PA 工作紀錄（pa-worklog/v1）：各端點把工作整理成固定欄位的信寄給本人（模式 A），PA 統整端以 Gmail 撈回併入週報（模式 B） |
| agent | `planner-opus` | 寫驗收契約（測試）並證明先紅，只 commit 測試檔；固定 opus，專案細節讀 CLAUDE.md 設定 |
| agent | `worker-haiku` / `worker-sonnet` / `worker-opus` | 改檔的 worker，依任務輕重選模型 |
| agent | `verifier-sonnet` | 獨立驗證，不改檔 |
| tool | `tools/check-js.sh` | 單檔 HTML 抽 `<script>` 跑 `node --check` |
| tool | `tools/explore-shots.mjs` | task-explore 用：每變體截 1440／375、量溢出／對比／元素數，產 variants.html |
| tool | `tools/release-check.sh` | release 閘門：`npm test` |
| tool | `tools/clear-stale-lock.sh` | 安全清殘留 `index.lock`：確定沒有 git 在跑才刪（pgrep／Windows tasklist／ps -W；判斷不了就不刪）。git-guard、doctor [a] 共用 `tools/lib/procs.sh` |
| tool | `tools/find-chrome.sh`／`tools/open-browser.sh` | 跨平台找 Chrome（`CHROME_PATH` → PATH → 各平台預設位置 → Edge）、用瀏覽器開檔（取代 WSL 的 `chrome` alias） |
| tool | `tools/validate-yaml.sh` | worklog YAML 驗證：找有 PyYAML 的 Python、UTF-8 開檔（exit 0／1／3） |
| lib | `tools/lib/platform.sh`、`tools/lib/procs.sh` | 平台判斷 `tw_os`、`pick_py`、`install_hint`、`find_gs`、`find_chrome`；git 程序偵測與安全清 lock |
| templates | `templates/` | 新專案起手：CLAUDE.md 設定段、TODO.md、doc 骨架 |

## 安裝

```
/plugin marketplace add frid/claude-task-workflow
/plugin install task-workflow@claude-task-workflow
```

或在專案 `.claude/settings.json` 宣告，讓每位協作者開專案就自動帶入：

```json
{
  "extraKnownMarketplaces": {
    "claude-task-workflow": { "source": { "source": "github", "repo": "frid/claude-task-workflow" } }
  },
  "enabledPlugins": { "task-workflow@claude-task-workflow": true }
}
```

安裝或啟用後要**重開 session** 才會載入 skill／agent／hook。

## 平台需求

| 平台 | 需要 | 安裝 |
|---|---|---|
| Linux／WSL | bash、git、jq、node、python3；選配 ghostscript、google-chrome | `sudo apt-get install -y jq nodejs python3 ghostscript` |
| macOS | 同上 | `brew install jq node python ghostscript` |
| Windows | **Git for Windows**（提供 Git Bash；hook 與 tools/*.sh 都在 Git Bash 執行）、jq、Node.js、Python 3；選配 Ghostscript、Chrome | `winget install Git.Git jqlang.jq OpenJS.NodeJS.LTS Python.Python.3.12`（選配：`winget install ArtifexSoftware.GhostScript Google.Chrome`） |

Windows 注意事項：

- 裝完要**完全重開** Claude Code（含背景 daemon：`claude daemon stop --any`），新的 PATH 才會生效。
- Python 3 的 `python3` 可能是 Microsoft Store 的空殼；工具會依序試 `python3`、`python`、`py -3`，並實際執行確認。
- `tools/doctor.sh --check` 會列出缺少的套件和該平台的安裝指令。

## 新專案要做的事

1. 把 `templates/CLAUDE.md.section` 貼進專案 `CLAUDE.md`，填好每一項（主程式檔、日期標記、舊存檔相容方式、資料慣例…）。skill／agent 都靠這一節知道專案細節。
2. 複製 `templates/TODO.md`、`templates/doc/` 到專案。
3. 專案 `CLAUDE.md` 保留自己的 Git 規則（三層分支、merge／release 口令）與參考資料位置。
4. 開一個 `dev` 分支與 `.claude/worktrees/dev` worktree。

## 更新流程

改 skill／agent 後把 `plugins/task-workflow/.claude-plugin/plugin.json` 的 `version` 加一，commit、push；各專案 `/plugin update task-workflow` 即同步。

## 版本

- 1.10.0（2026-11-06）：**Windows 支援**（WIN-02～08，#5～#11）——hook 涵蓋 PowerShell、以 `bash` 明確執行；Python 以實際執行挑選（`pick_py`）並一律 `-X utf8`；doctor [e] 依平台給 winget／brew／apt 提示、Ghostscript 跨平台；`find-chrome.sh`／`open-browser.sh` 取代 `google-chrome`／`chrome` alias，explore-shots 改用 `dirname`；worklog 改用 `validate-yaml.sh`、沒有 PyYAML 的測試改為 skip；`.gitattributes` 強制 LF、check-js 語法錯不再 exit 0；`DOCTOR_DRIVE_LETTERS` 雲端磁碟偵測、safe.directory 用 `D:/` 寫法、Windows hook 略過 [d]（SessionStart 4.8s→3.3s）；node_modules 警告勿用 junction。README 新增「平台需求」。新增 `tests/test_windows_support.py`。
- 1.9.2（2026-11-06）：**WIN-01 lock 安全**——Windows Git Bash 沒有 `pgrep`，舊版 git-guard／doctor [a]／task-release 會把「找不到 pgrep」當成「沒有 git 在跑」而刪掉活著的 git 持有的 `index.lock`。新增 `tools/lib/procs.sh`（`git_pids`：pgrep → tasklist → `ps -W`，全部不能用回報「無法判斷」；`remove_stale_lock`：確定沒有 git 才刪）與 `tools/clear-stale-lock.sh`；git-guard、doctor [a] 改用它，判斷不了一律不刪；task-release、task-next 附錄 B 不再教 `pgrep … || rm -f`。新增 `tests/test_lock_safety.py`。
- 1.9.1（2026-11-06）：修 `doctor.sh` [c] 在 Windows（Git Bash）誤報 worktree 指標失效——`D:/…` 磁碟代號路徑被當相對路徑；新增 `is_abs_path`／`norm_path`（cygpath 統一 `D:/x` 與 `/d/x` 再去重），去除 gitdir 的 CR；絕對路徑計數也認得磁碟代號；新增 `tests/test_doctor_worktree_paths.py`。
- 1.9.0（2026-11-05）：新增 `planner-opus` agent（固定 opus），task-next 步驟 3c 改派它、prompt 只寫任務本身；不再寫死 Playwright／`npm test`，改讀設定的「測試指令」「驗收契約檔」；設定範本加 6 項（測試指令、驗收契約檔、planner 可寫範圍、測試隔離、敏感資料、git 身分）；worker／verifier 比對所有被改 spec 的 hash；新增 `tests/test_planner_opus.py`。
- 1.8.0（2026-11-03）：新增 `task-submit-worklog` skill（PA 工作紀錄寄送／彙整，欄位規格 pa-worklog/v1；YAML 驗證改用有 PyYAML 的 conda NAS python）；新增 `tests/test_task_submit_worklog.py`。
- 1.7.1（2026-10-28）：task-next 步驟 6 補 ff merge 後核對（未追蹤檔會讓 ff 靜默 Aborting）。
- 1.7.0（2026-10-27）：`task-next` 改為測試先行——planner 先寫 `tests/tasks/<代號>.spec.ts`（量測斷言：矩形寬度／對齊、computed 顏色、375／1440 不橫向捲動、互動無 console error、截圖基準）並證明在 dev 上先紅；worker 在自己 worktree 做到 spec＋全套＋回歸全綠（≤6 輪、每輪貼實際輸出、不得改 spec）；verifier 從乾淨 checkout 重跑並比對 spec hash；全綠才 ff 併入 dev；依檔案重疊分波平行，波末回報表。
- 1.6.0（2026-10-26）：新增 `task-explore` skill 與 `tools/explore-shots.mjs`（UI 任務多變體探索：每變體一個 explore/<代號>-<字母> worktree、截圖量測、並排比較頁、選定後交 task-next）。
- 1.5.0（2026-10-26）：`task-next` 依實戰調整——指定代號模式；批次模式整波一條分支、每項 PASS 後以指定 commit 併入 dev；中途新增需求處理；等 worker 時預先 Explore；FAIL 先判斷驗收條件是否寫錯；verifier 掛住處理；最終回報固定格式；附錄 B 補鎖檔與守門處理。
- 1.4.0（2026-10-26）：新增 `task-plan` skill（規劃流程：盤點 → 找資料 → 摘要 → 差距表 → 切任務 → 寫 TODO）。
- 1.3.0（2026-10-25）：首版 plugin，功能對應 strategy-matrix 流程 1.3.0。
