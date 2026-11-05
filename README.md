# agent_skill_kit

一份 skill 與 rule 來源，給多個 AI 工具共用（Kiro、KiroCrew、Antigravity、Cursor、Claude Code、Codex）。skill 用共用的 `<name>/SKILL.md`，靠符號連結安裝；rule 安裝時轉成各工具格式。一支跨平台的 `kit.py` 處理全部。

需求：Python 3.11+ 和 git。clone 後跑 `python kit.py install <tool>`。之後 `git pull` 同步 skill，rule 改動要重跑 install。

## 結構

```
agent_skill_kit/
+-- kit.py                   單一入口（子命令）：install / import-skill /
|                            import-rule / check-updates / diff / check-public / setup
+-- kitlib.py                共用邏輯（讀表、路徑、frontmatter、密鑰、GitHub、合併）
+-- test_kit.py              端對端 smoke test
+-- requirements.txt         Python 相依（toml 寫入，給 Codex MCP）
+-- skills/                  已引入的 skill（每個一個資料夾）
|   +-- upstream-sync/       「檢查上游更新並與你討論」流程
|   +-- tools-sync/          「檢查各工具路徑有無變動」流程
+-- rules/                   rule 來源（每個一個 .md），安裝時轉成各工具格式
+-- config/
|   +-- tools.tsv            各工具的 skill/rule 安裝路徑與格式
|   +-- mcp-targets.tsv      各工具的 MCP 設定檔位置與格式
|   +-- mcp/                 MCP server 定義（每個一個 .json，工具無關）
|   +-- secrets.env          真實密鑰，gitignored，永不 commit
|   +-- secrets.env.example  密鑰範本
+-- upstream/
|   +-- skill-sources.tsv    skill 上游來源（repo、分支、skill 目錄）
|   +-- skill-selected.tsv   已引入 skill 與引入時的 commit
|   +-- skill-reviewed.txt   已檢視過的上游 skill（偵測新增用）
|   +-- rule-sources.tsv     rule 上游來源（repo、分支）
|   +-- rule-selected.tsv    已引入 rule、來源檔路徑、載入模式、commit
|   +-- *.example.tsv        格式範例，程式不讀，照格式填真檔用
|   +-- licenses/            上游授權檔
+-- docs/
    +-- multi-tool-design.md      多工具設計：tools.tsv 欄位、加新工具的方式
    +-- mcp-and-secrets-design.md MCP 與密鑰分離設計
    +-- python-rewrite-plan.md    Python 重寫計畫（移植紀錄）
    +-- windows-paths.md          各工具在 Windows 的完整路徑表
```

## 安裝

`<tool>` 可填：`kiro`、`kirocrew`、`antigravity`、`cursor`、`claude`、`codex`，或 `all`（全部）。

```bash
python kit.py install kiro                     # 單一工具：skill + rule + MCP，全域
python kit.py install all --workspace ~/proj   # 所有工具，專案層級
python kit.py install kiro --only rules        # 只裝 rule
python kit.py install kiro --copy              # skill 強制用複製，不用符號連結
python kit.py setup all                        # setup 是 install 的別名
```

skill 預設符號連結，`git pull` 即同步。symlink 建不了（如 Windows 無權限）自動退回複製，更新要重跑 install；`--copy` 可強制複製。rule 轉格式後產生檔案，改了要重跑 install。

同名 skill 若不是符號連結則略過；含 kit 標記以外的手寫同名 rule 也略過。兩者都不覆蓋你的檔案。rule 格式與載入模式見 `rules/README.md`。

## 安裝位置

| | 工具 | 全域 | 專案 |
|---|---|---|---|
| skill | Kiro | `~/.kiro/skills/` | `<project>/.kiro/skills/` |
| skill | KiroCrew | `~/.kiro/crew/skills/` ¹ | （無專案層級） |
| skill | Antigravity | `~/.gemini/config/skills/` | `<project>/.agents/skills/` |
| skill | Cursor | `~/.cursor/skills/` | `<project>/.cursor/skills/` |
| skill | Claude Code | `~/.claude/skills/` | `<project>/.claude/skills/` |
| skill | Codex | `~/.codex/skills/` | `<project>/.agents/skills/` |
| rule | Kiro | `~/.kiro/steering/` | `<project>/.kiro/steering/` |
| rule | Antigravity | `~/.gemini/config/rules/` | `<project>/.agents/rules/` |
| rule | Cursor | （無檔案式全域）³ | `<project>/.cursor/rules/*.mdc` |
| rule | Claude Code | `~/.claude/CLAUDE.md`（合併）⁴ | `<project>/CLAUDE.md`（合併）⁴ |
| rule | Codex | `~/.codex/AGENTS.md`（合併）⁴ | `<project>/AGENTS.md`（合併）⁴ |
| MCP | Kiro | `~/.kiro/settings/mcp.json` | `<project>/.kiro/settings/mcp.json` |
| MCP | Antigravity | `~/.gemini/config/mcp_config.json` | （由 app 管理） |
| MCP | Cursor | `~/.cursor/mcp.json` | `<project>/.cursor/mcp.json` |
| MCP | Claude Code | `~/.claude.json` | `<project>/.mcp.json` |
| MCP | Codex | `~/.codex/config.toml` | `<project>/.codex/config.toml` |

¹ KiroCrew 的 skill 與 Kiro IDE 不同目錄；rule 共用 Kiro 的 `~/.kiro/steering/`，裝 kiro 即涵蓋，kirocrew 不另裝 rule。
³ Cursor 全域 rule 走它的 User Rules UI，不是檔案，全域 rule 安裝會略過。
⁴ Claude/Codex 的 rule 是單一檔，kit 只合併 `kit_load: always` 的 rule（glob/manual/model 略過），你手寫的其餘內容保留。

MCP server 定義放 `config/mcp/<name>.json`（工具無關），install 時轉成各工具格式並合併進既有設定檔，保留你其餘的 server。密鑰用 `${KIT_SECRET:NAME}` 引用，真值放 gitignored 的 `config/secrets.env`（範本 `secrets.env.example`），安裝時代入；缺 key 報錯中止。這讓 repo 可安全公開。

工具清單在 `config/tools.tsv`，加新工具就是加一列（見 `docs/multi-tool-design.md`）。路徑特例見上方表格腳註。

## 更新流程

### skill（有上游，自動追蹤）

1. 對 agent 說「檢查上游更新」，會觸發 `upstream-sync` skill。
2. 它執行 `python kit.py check-updates`（唯讀），列出已引入 skill 的變更和上游新增的 skill。
3. 已改過的 skill 有上游變更時，用 `python kit.py diff <local_name>` 做三方比對，分開顯示你的修改和官方的修改。
4. 上游新增 skill 時，先檢查是否與現有 skill 重疊、是否影響現有流程，再列選項與你討論（採用 / 合併 / 取代 / 改流程 / 略過 / 暫緩）。
5. 逐項與你討論；你同意的項目才用 `python kit.py import-skill` 匯入或套用合併結果。
6. 匯入後只改工作樹，是否 commit 由你決定。

### rule（可有上游，也可自己寫）

rule 可追蹤上游，`check-updates` 同時列出 skill 和 rule 的變更。

來源：
- 自己寫：在 `rules/` 新增 `.md`（見 `rules/README.md`）。
- 從 repo 引入：`python kit.py import-rule <source> <file_path> <local_name> [kit_load]`，會套上 kit frontmatter 並記下來源 sha。

更新時 `upstream-sync` 一併處理 rule：用 `diff --rule <local_name>` 做 body-only 三方比對，你同意後寫回並更新 sha，再重跑 `install` 重新產生 rule 檔。rule 沒有「掃 repo 找新 rule」這步，由你指定哪個上游檔變成 rule。

### 工具路徑（各家官方可能改）

安裝路徑（`tools.tsv`、`mcp-targets.tsv`）來自官方文件，可能變動。對 agent 說「檢查工具路徑」觸發 `tools-sync`：它讀每個工具的 `doc_url` 比對現有路徑，有變才跟你討論。讀不到或 JS 頁標 UNVERIFIED，不亂猜。

## 公開與 push

repo 可公開，密鑰只放 gitignored 的 `config/secrets.env`，repo 內用 `${KIT_SECRET:NAME}` 引用。

**每次 push 前都跑 `python kit.py check-public`**，不只第一次——之後引入的 rule 或 MCP server 可能夾帶密鑰。它唯讀，檢查七項（secrets.env 未進歷史且 gitignored、無 token 樣式、無嵌入密鑰、作者 email 等），有 FAIL 會顯示「DO NOT PUSH」。全 PASS 才推。

## 測試

`python test_kit.py` 在沙盒裡跑完整安裝流程（七工具 × skill/rule/MCP），斷言產出正確、測冪等與專案模式，最後清掉。改過 `kit.py` 或 `kitlib.py` 後跑一次。

## 限制

- `import-skill`、`import-rule`、`check-updates`、`diff` 需要網路存取 GitHub；匿名 API 每小時 60 次，設 `GITHUB_TOKEN` 可提高上限。`diff` 的三方合併用到 `git`。
- 各工具的 subagent、slash command、plugin 機制不同。標 ⚠ 的 skill 匯入後要改寫，改寫留在本地副本，上游變更時 `upstream-sync` 會提醒衝突。
- Antigravity 的 skill 與 rule 路徑依官方文件（[skills](https://antigravity.google/docs/skills)、[rules](https://antigravity.google/docs/rules)）設定，尚未在 Antigravity 實機驗證。
- `rules/` 目前是空的。這個 kit 只提供 rule 管理工具，實際要帶哪些 rule 由你之後決定。
- Kiro 的 `fileMatchPattern`（glob rule）確切語法尚未確認，第一次裝 glob rule 時要驗證。
- Antigravity 全域 always_on rule 共用 20,000 token 預算，超過會被降級為指標。rule 不要放太多常駐的。
- `kit.py` 目標 Python 3.11+。尚未在實機 Windows 驗證（symlink 退回複製、各工具路徑），第一次在 Windows 用時要確認。
