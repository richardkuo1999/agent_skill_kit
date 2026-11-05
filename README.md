# agent_skill_kit

一份 skill 與 rule 來源，同時給 Kiro（公司）和 Google Antigravity（家裡）使用。
skill 兩邊共用 `<name>/SKILL.md` 格式，靠符號連結安裝；rule 兩邊 frontmatter 不同，安裝時轉格式。
一個 `setup.sh` 一次處理全部。

家裡的機器：clone 後跑 `./setup.sh antigravity`，之後 `git pull` 同步 skill，rule 改動要重跑 `setup.sh`。
公司的機器：`./setup.sh kiro`。

## 結構

```
agent_skill_kit/
+-- setup.sh                 單一入口：一次裝 skill + rule（+ 之後新增的）
+-- skills/                  已引入的 skill（每個一個資料夾）
|   +-- upstream-sync/       「檢查上游更新並與你討論」流程
+-- rules/                   rule 來源（每個一個 .md），安裝時轉成各工具格式
+-- upstream/
|   +-- skill-sources.tsv    skill 上游來源（repo、分支、skill 目錄）
|   +-- skill-selected.tsv   已引入 skill 與引入時的 commit
|   +-- skill-reviewed.txt   已列入 CATALOG 的上游 skill（偵測新增用）
|   +-- rule-sources.tsv     rule 上游來源（repo、分支）
|   +-- rule-selected.tsv    已引入 rule、來源檔路徑、載入模式、commit
|   +-- *.example.tsv        格式範例，腳本不讀，照格式填真檔用
|   +-- licenses/            上游授權檔
+-- scripts/
|   +-- install-skill.sh     skill 連結到 Kiro / Antigravity
|   +-- install-rule.sh      rule 轉格式後安裝到 Kiro / Antigravity
|   +-- import-skill.sh      從上游複製單一 skill
|   +-- import-rule.sh       從上游引入單一 rule（抽 body、套 kit frontmatter）
|   +-- check-updates.sh     唯讀，列出 skill 與 rule 的上游變更
+-- CATALOG.md               全部上游 skill 的勾選清單
```

## 安裝位置

| | 工具 | 全域 | 專案 |
|---|---|---|---|
| skill | Kiro | `~/.kiro/skills/` | `<project>/.kiro/skills/` |
| skill | Antigravity | `~/.gemini/config/skills/` | `<project>/.agents/skills/` |
| skill | Cursor | `~/.cursor/skills/` | `<project>/.cursor/skills/` |
| skill | Claude Code | `~/.claude/skills/` | `<project>/.claude/skills/` |
| skill | Codex | `~/.codex/skills/` | `<project>/.agents/skills/` |
| rule | Kiro | `~/.kiro/steering/` | `<project>/.kiro/steering/` |
| rule | Antigravity | `~/.gemini/config/rules/` | `<project>/.agents/rules/` |
| rule | Cursor | （無檔案式全域） | `<project>/.cursor/rules/*.mdc` |

工具清單定義在 `config/tools.tsv`，加一個新工具就是加一列（細節見 `docs/multi-tool-design.md`）。Cursor 的全域 rule 走它的 User Rules UI，不是檔案，所以全域 rule 安裝會略過。Claude Code 和 Codex 目前只支援 skill；它們的 rule 是單一檔（CLAUDE.md、AGENTS.md），合併安裝待後續步驟，現在會略過。

一個入口 `setup.sh` 一次處理 skill、rule 和之後加入的東西：

```bash
./setup.sh antigravity              # 家裡：skill + rule，全域
./setup.sh kiro                     # 公司：skill + rule，全域
./setup.sh all --workspace ~/proj   # 兩個工具，專案層級
./setup.sh kiro --only rules        # 只裝 rule
```

要分開跑也可以：

```bash
scripts/install-skill.sh antigravity  # 只裝 skill
scripts/install-rule.sh antigravity   # 只裝 rule
```

kit 之後長出新的管理對象（例如 MCP、hook）時，只在 `setup.sh` 的 `installers` 清單加一行，入口不變。

skill 用符號連結安裝，`git pull` 即同步。rule 兩邊 frontmatter 不同，用「轉格式後產生檔案」安裝，改了 rule 要重跑 `install-rule.sh`。
已存在且不是符號連結的同名 skill 會被略過。手寫的同名 rule（第一行沒有產生標記）也會被略過，兩者都不覆蓋。
rule 來源格式與載入模式映射見 `rules/README.md`。

## 更新流程

### skill（有上游，自動追蹤）

1. 對 agent 說「檢查上游更新」，會觸發 `upstream-sync` skill。
2. 它執行 `scripts/check-updates.sh`（唯讀），列出已引入 skill 的變更和上游新增的 skill。
3. 已改過的 skill 有上游變更時，用 `scripts/diff-upstream.sh <local_name>` 做三方比對，分開顯示你的修改和官方的修改。
4. 上游新增 skill 時，先檢查是否與現有 skill 重疊、是否影響現有流程，再列選項與你討論（採用 / 合併 / 取代 / 改流程 / 略過 / 暫緩）。
5. 逐項與你討論；你同意的項目才用 `scripts/import-skill.sh` 匯入或套用合併結果。
6. 匯入後只改工作樹，是否 commit 由你決定。

### rule（可有上游，也可自己寫）

rule 現在和 skill 一樣可追蹤上游。`check-updates.sh` 會印 `##### SKILLS` 和 `##### RULES` 兩段。

來源：
- 自己寫：在 `rules/` 新增 `.md`（格式見 `rules/README.md`）。
- 從 repo 引入：`scripts/import-rule.sh <source> <file_path> <local_name> [kit_load]`。它抽出上游檔的 body、套上 kit frontmatter、記下來源與 sha。範例來源是 pstack 的 `principle-*` 和 mattpocock 的 `AGENTS.md`。

更新：
1. 「檢查上游更新」時 `upstream-sync` 會一併處理 rule 的 `##### RULES` 段。
2. 已引入 rule 有上游變更時，用 `scripts/diff-upstream.sh --rule <local_name>` 做 body-only 三方比對。
3. 你同意採用時，把合併後的 body 重新套上 kit frontmatter 寫回，並更新 sha。
4. 改完一定要重跑 `./setup.sh <tool>`（或 `scripts/install-rule.sh <tool>`）重新產生各工具的 rule 檔，因為 rule 不是符號連結。

rule 沒有「掃 repo 找新 rule」這一步，因為任何 `.md` 都可能是 rule，由你指定哪個上游檔要變成 rule。

重裝只覆蓋 kit 產生的檔案（第一行有產生標記）。手寫的同名 rule 會被略過不覆寫。

## 限制

- `check-updates.sh`、`import-skill.sh`、`import-rule.sh`、`diff-upstream.sh` 需要 `gh` 已登入。
- 兩邊工具的 subagent、slash command、plugin 機制不同。標 ⚠ 的 skill 匯入後要改寫，改寫內容會留在本地副本，下次上游變更時由 `upstream-sync` 提醒衝突。
- Antigravity 的 skill 與 rule 路徑依官方文件（[skills](https://antigravity.google/docs/skills)、[rules](https://antigravity.google/docs/rules)）設定，尚未在 Antigravity 實機驗證。
- `rules/` 目前是空的。這個 kit 只提供 rule 管理工具，實際要帶哪些 rule 由你之後決定。
- Kiro 的 `fileMatchPattern`（glob rule）確切語法尚未確認，第一次裝 glob rule 時要驗證。
- Antigravity 全域 always_on rule 共用 20,000 token 預算，超過會被降級為指標。rule 不要放太多常駐的。
