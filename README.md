# agent_skill_kit

打造並維護你自己的跨工具 skill/rule/MCP 包。你的 skill、rule、MCP 集中放一處版控，一道指令就裝到多個 AI 工具（Kiro、KiroCrew、Antigravity、Cursor、Claude Code、Codex）；各工具格式不同，安裝時自動轉換。需要時可從上游 repo 引入既有 skill，之後追蹤官方更新並三方合併。

上游同步是輔助：你的 repo 是主角，可以完全自己寫，也可以借用上游再改寫成自己的。

需求：Python 3.11+ 和 git。

## 怎麼用：對 AI 說話

**kitpilot — 管理你的包**（在有 kit 的機器上，對 AI 說）

| 你說 | kitpilot 幫你做 |
|---|---|
| 「引入 github.com/someone/skills」 | 登記來源、列出它有哪些 skill、逐個和你討論要不要引入 / 合併 / 組成 playbook |
| 「檢查上游更新」 | 比對已引入 skill/rule 的上游變更，三方合併，更新 profile 與 playbook 引用 |
| 「幫我配一組前端用的 skill」 | 寫一個 profile（哪些 skill 裝、哪些 playbook 路由） |
| 「幫我為 ProjectA 設置 KIRO 環境」 | 把選好的這組裝進那個 project 的 Kiro（你確認後才動） |
| 「檢查工具路徑有沒有變」 | 讀各工具官方文件，比對安裝路徑有無變動 |

**pilot — 用你的包做開發**（裝進各 AI 工具後，日常對工具說）

| 你說 | pilot 幫你做 |
|---|---|
| 「幫我修這個 bug」 | 比對你建的 playbook，開對應的工作流（如 fix-bug）照步驟做 |
| 「加個前端元件」 | 路由到你為這情境建的 playbook |

kitpilot 負責管理你的包，只在有 kit 的機器上用，不裝進工具；pilot 負責用你的包做開發，裝進每個工具。
下面的章節是底層細節：這些 `kit.py` 指令由 AI 代跑，你平常不用自己記。

## 結構

```
agent_skill_kit/
+-- kit.py                   Agent 用的底層工具（子命令）：install / list-skills /
|                            import-skill / import-rule / check-updates / diff /
|                            manifest / check-public / setup
+-- kitlib.py                共用邏輯（讀表、路徑、frontmatter、密鑰、GitHub、合併）
+-- test_kit.py              端對端 smoke test
+-- requirements.txt         Python 相依（toml 寫入，給 Codex MCP）
+-- skills/                  skill（每個一個資料夾）
|   +-- pilot/               用包做開發的入口（你的 poteto-mode）+ playbooks/，裝進工具
|   +-- kitpilot/            管包助手（機制 skill，不裝進工具）
|   +-- curate/              引入/追更新核心流程（機制 skill）
|   +-- tools-sync/          「檢查各工具路徑有無變動」流程（機制 skill）
|   +-- profiles/            各 profile 清單（決定裝哪些 skill + pilot playbook）
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

## 底層：install 指令（AI 代跑）

以下指令由 kitpilot 助手依你的話代跑，列在這裡供參考或手動除錯。`<tool>` 可填：`kiro`、`kirocrew`、`antigravity`、`cursor`、`claude`、`codex`，或 `all`（全部）。

```bash
python kit.py install kiro                     # 單一工具：skill + rule + MCP，全域
python kit.py install all --workspace ~/proj   # 所有工具，專案層級
python kit.py install kiro --only rules        # 只裝 rule
python kit.py install kiro --copy              # skill 強制用複製，不用符號連結
python kit.py install kiro --profile web       # 用 web 這組（見下方 profile）
python kit.py manifest --profile web           # 產 pilot/MANIFEST.md 骨架（給人看的地圖）
python kit.py setup all                        # setup 是 install 的別名
```

裝哪些 skill 由 profile 決定（`skills/profiles/<name>.txt`，預設 `default`）。清單分兩段：`[skills]` 列要裝到工具的 skill，`[playbooks]` 列要填進 pilot 路由表的 playbook。沒列到的不裝，所以 kit 自己的機制 skill（kitpilot、curate、tools-sync）不會洩漏進工具。入口 `pilot` 一律裝。複製 `default.txt` 成 `web.txt` 之類即可為不同 workspace 準備不同組，用 `--profile web` 選用。pilot 的路由表因 profile 而異，所以帶自訂路由表的 pilot 需搭 `--copy`。

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

## 底層：從上游引入（AI 代跑）

你只要對 kitpilot 說「引入這個 repo」，下面的步驟它會幫你做。這裡說明底層機制：要從某個 repo 引入 skill，先把它登記成一個來源，`import-skill` 的 `<source>` 就是這個登記名（不是 repo URL）。

1. 在 `upstream/skill-sources.tsv` 加一列（tab 分隔）：

   ```
   name    repo                ref   skills_dir  license_path
   myrepo  someone/cool-skills main  skills       LICENSE
   ```

   `skills_dir` 是 repo 裡放各 skill 資料夾的目錄。範例見 `*.example.tsv`。

2. 查該 repo 的 `skills_dir`，看有哪些含 `SKILL.md` 的資料夾。

3. 引入：`python kit.py import-skill myrepo <skill資料夾名> [本地名]`。它抓下來放進 `skills/`、記下來源與 commit sha，之後才能被 `curate` 追蹤更新。

rule 相同：先登記到 `upstream/rule-sources.tsv`（欄位少一個 `skills_dir`，因為 rule 引入時逐檔指定路徑），再 `python kit.py import-rule <source> <file_path> <local_name> [kit_load]`。

## 底層：更新流程（AI 代跑）

對 kitpilot 說「檢查上游更新」即可，下面是它背後做的事。

### skill（有上游，自動追蹤）

`kitpilot` 助手路由到 `curate` 核心流程：

1. 跑 `check-updates`（唯讀），列出已引入 skill 的變更和上游新增的 skill。
2. 已改過的 skill 有上游變更時，`diff <local_name>` 做三方比對，分開顯示你的修改和官方的修改。
3. 新增 skill 先檢查是否與現有重疊、是否影響現有流程，再列選項與你討論（採用 / 合併 / 取代 / 略過 / 暫緩）。
4. 你同意的項目才套用；套用後 curate 維護下游（更新 profile、查 playbook 引用）。
5. 只改 kit 內部，不碰你的工具；要生效需另外確認一次 install。是否 commit 由你決定。

### rule（可有上游，也可自己寫）

rule 一樣由 curate 處理，`check-updates` 同時列出 skill 和 rule 的變更。

來源：自己寫（在 `rules/` 新增 `.md`，見 `rules/README.md`），或從上游引入（見上方「從上游引入」）。

curate 處理 rule 時用 `diff --rule <local_name>` 做 body-only 三方比對，你同意後寫回並更新 sha，再重跑 `install` 重新產生 rule 檔。rule 沒有「掃 repo 找新 rule」這步，由你指定哪個上游檔變成 rule。

### 工具路徑（各家官方可能改）

安裝路徑（`tools.tsv`、`mcp-targets.tsv`）來自官方文件，可能變動。對 kitpilot 說「檢查工具路徑」，它路由到 `tools-sync`：讀每個工具的 `doc_url` 比對現有路徑，有變才跟你討論。讀不到或 JS 頁標 UNVERIFIED，不亂猜。

## 公開與 push

repo 可公開，密鑰只放 gitignored 的 `config/secrets.env`，repo 內用 `${KIT_SECRET:NAME}` 引用。

**每次 push 前都跑 `python kit.py check-public`**，不只第一次——之後引入的 rule 或 MCP server 可能夾帶密鑰。它唯讀，檢查七項（secrets.env 未進歷史且 gitignored、無 token 樣式、無嵌入密鑰、作者 email 等），有 FAIL 會顯示「DO NOT PUSH」。全 PASS 才推。

## 測試

`python test_kit.py` 在沙盒裡跑完整安裝流程（七工具 × skill/rule/MCP），斷言產出正確、測冪等與專案模式，最後清掉。改過 `kit.py` 或 `kitlib.py` 後跑一次。

## 限制

- `import-skill`、`import-rule`、`check-updates`、`diff` 需要網路存取 GitHub；匿名 API 每小時 60 次，設 `GITHUB_TOKEN` 可提高上限。`diff` 的三方合併用到 `git`。
- 各工具的 subagent、slash command、plugin 機制不同。標 ⚠ 的 skill 匯入後要改寫，改寫留在本地副本，上游變更時 `curate` 會提醒衝突。
- Antigravity 的 skill 與 rule 路徑依官方文件（[skills](https://antigravity.google/docs/skills)、[rules](https://antigravity.google/docs/rules)）設定，尚未在 Antigravity 實機驗證。
- `rules/` 目前是空的。這個 kit 只提供 rule 管理工具，實際要帶哪些 rule 由你之後決定。
- Kiro 的 `fileMatchPattern`（glob rule）確切語法尚未確認，第一次裝 glob rule 時要驗證。
- Antigravity 全域 always_on rule 共用 20,000 token 預算，超過會被降級為指標。rule 不要放太多常駐的。
- `kit.py` 目標 Python 3.11+。尚未在實機 Windows 驗證（symlink 退回複製、各工具路徑），第一次在 Windows 用時要確認。
