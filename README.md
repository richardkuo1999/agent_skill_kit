# agent_skill_kit

一份 skill 來源，同時給 Kiro（公司）和 Google Antigravity（家裡）使用。
兩者都用 `<name>/SKILL.md` 資料夾格式，所以 `skills/` 只維護一份，靠符號連結安裝。

## 結構

```
agent_skill_kit/
+-- skills/                  已引入的 skill（每個一個資料夾）
|   +-- upstream-sync/       「檢查上游更新並與你討論」流程
+-- upstream/
|   +-- sources.tsv          上游來源（repo、分支、skill 路徑）
|   +-- selected.tsv         已引入項目與引入時的 commit
|   +-- reviewed.txt         已列入 CATALOG 的上游 skill（用來偵測新增）
|   +-- licenses/            上游授權檔
+-- scripts/
|   +-- install.sh           連結到 Kiro / Antigravity
|   +-- import.sh            從上游複製單一 skill
|   +-- check-updates.sh     唯讀，列出上游變更
+-- CATALOG.md               全部上游 skill 的勾選清單
```

## 安裝位置

| 工具 | 全域 | 專案 |
|---|---|---|
| Kiro | `~/.kiro/skills/` | `<project>/.kiro/skills/` |
| Antigravity | `~/.gemini/config/skills/` | `<project>/.agents/skills/` |

```bash
scripts/install.sh kiro                    # 公司
scripts/install.sh antigravity             # 家裡
scripts/install.sh all --workspace ~/proj  # 專案層級
```

家裡的機器：`git clone` 這個 repo 後執行 `install.sh antigravity`，之後 `git pull` 即同步。
已存在且不是符號連結的同名 skill 會被略過，不會覆蓋。

## 更新流程

1. 對 agent 說「檢查上游更新」，會觸發 `upstream-sync` skill。
2. 它執行 `scripts/check-updates.sh`（唯讀），列出已引入 skill 的變更和上游新增的 skill。
3. 逐項與你討論；你同意的項目才用 `scripts/import.sh` 匯入。
4. 匯入後只改工作樹，是否 commit 由你決定。

## 限制

- `check-updates.sh` 與 `import.sh` 需要 `gh` 已登入。
- 兩邊工具的 subagent、slash command、plugin 機制不同。標 ⚠ 的 skill 匯入後要改寫，改寫內容會留在本地副本，下次上游變更時由 `upstream-sync` 提醒衝突。
- Antigravity 的路徑依 [官方文件](https://antigravity.google/docs/skills) 設定，尚未在 Antigravity 實機驗證。
