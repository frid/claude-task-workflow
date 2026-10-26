# claude-task-workflow

Claude Code plugin `task-workflow`：TODO.md 驅動的開發流程。`task-plan` 把教材／需求規劃成任務；一次一項、先規劃再派 worker subagent 改檔、另派 verifier 驗證、`task-release` 收尾；三層分支 `worktree → dev → main`。從 strategy-matrix 專案的流程抽出，專案專屬內容改由各專案 `CLAUDE.md` 提供。

## 內容

| 類型 | 名稱 | 用途 |
|---|---|---|
| skill | `task-plan` | 規劃：從教材／需求盤點現況、登記並摘要參考資料（標頁碼）、做差距表、切階段與子任務、寫進 TODO.md |
| skill | `task-next` | 接下一項任務：補編號、核對事實、寫計畫、派 worker、派 verifier |
| skill | `task-release` | 收尾：勾 TODO、更新日期標記、decisions／pending-checks、commit、push；merge／release 步驟 |
| agent | `worker-haiku` / `worker-sonnet` / `worker-opus` | 改檔的 worker，依任務輕重選模型 |
| agent | `verifier-sonnet` | 獨立驗證，不改檔 |
| tool | `tools/check-js.sh` | 單檔 HTML 抽 `<script>` 跑 `node --check` |
| tool | `tools/release-check.sh` | release 閘門：`npm test` |
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

## 新專案要做的事

1. 把 `templates/CLAUDE.md.section` 貼進專案 `CLAUDE.md`，填好每一項（主程式檔、日期標記、舊存檔相容方式、資料慣例…）。skill／agent 都靠這一節知道專案細節。
2. 複製 `templates/TODO.md`、`templates/doc/` 到專案。
3. 專案 `CLAUDE.md` 保留自己的 Git 規則（三層分支、merge／release 口令）與參考資料位置。
4. 開一個 `dev` 分支與 `.claude/worktrees/dev` worktree。

## 更新流程

改 skill／agent 後把 `plugins/task-workflow/.claude-plugin/plugin.json` 的 `version` 加一，commit、push；各專案 `/plugin update task-workflow` 即同步。

## 版本

- 1.5.0（2026-10-26）：`task-next` 依實戰調整——指定代號模式；批次模式整波一條分支、每項 PASS 後以指定 commit 併入 dev；中途新增需求處理；等 worker 時預先 Explore；FAIL 先判斷驗收條件是否寫錯；verifier 掛住處理；最終回報固定格式；附錄 B 補鎖檔與守門處理。
- 1.4.0（2026-10-26）：新增 `task-plan` skill（規劃流程：盤點 → 找資料 → 摘要 → 差距表 → 切任務 → 寫 TODO）。
- 1.3.0（2026-10-25）：首版 plugin，功能對應 strategy-matrix 流程 1.3.0。
