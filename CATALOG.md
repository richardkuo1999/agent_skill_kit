# Skill 清單（請勾選要引入的項目）

勾選方式：把 `[ ]` 改成 `[x]`。勾完告訴 Kiro，由 `scripts/import.sh` 逐個匯入。

相容欄說明：
- ✅ 內容看起來與工具無關，可直接用
- ⚠ 描述提到 subagent、多模型、Cursor 或 Claude 專有功能，匯入後需改寫
- 此欄只依 frontmatter 描述判斷，尚未逐個讀完內文

名稱衝突：兩套都有 `tdd` 和 `teach`，匯入時分別用 `mp-` 和 `ps-` 前綴。
`grill-me`、`grill-with-docs`、`grilling` 已在 `~/.kiro/crew/skills/skillsh/` 安裝過，匯入前先確認是否要取代。

## A. mattpocock/skills（MIT，共 39 個）

### A1. engineering（20）

| 勾選 | skill | 用途 | 相容 |
|---|---|---|---|
| [ ] | ask-matt | 路由：問「我這情況該用哪個 skill」 | ✅ |
| [ ] | code-review | 對固定基準點後的 diff 做雙軸審查：程式規範、是否符合原始 spec | ⚠ 用平行 subagent |
| [ ] | codebase-design | 設計「深模組」（小介面、大功能）的共用詞彙與紀律 | ✅ |
| [ ] | diagnosing-bugs | 除錯迴圈：先建立能重現的紅燈 → 縮小 → 假設 → 加探針 → 修 → 補回歸測試 | ✅ |
| [ ] | domain-modeling | 維護 GLOSSARY.md 與 ADR，統一專案術語 | ✅ |
| [ ] | grill-with-docs | 訪談式逼問計畫，同時產出 ADR 與術語表（已有 skillsh 版） | ✅ |
| [ ] | implement | 依 spec 或 ticket 實作，用 tdd 驅動，結尾跑 code-review | ⚠ 串接其他 skill |
| [ ] | implement-spec | 整份 spec 在一條整合分支上實作，以 subagent 平行處理 ticket | ⚠ 用 subagent |
| [ ] | improve-codebase-architecture | 掃描程式庫找「可加深的模組」，產生 HTML 報告後逐項逼問 | ✅ |
| [ ] | pr | PR 內文格式：最小視覺摘要、前後證據、合併風險判斷 | ✅ |
| [ ] | prototype | 做拋棄式原型回答設計問題（單檔 HTML 或多版 UI） | ✅ |
| [ ] | research | 對高可信來源研究問題，產出附引用的 Markdown，背景執行 | ⚠ 背景 agent |
| [ ] | retro | 工作階段後建議改善 agent 環境（導覽、檢查、steering、工具） | ✅ |
| [ ] | setup-matt-pocock-skills | 每個 repo 設定一次：issue tracker、標籤、文件位置 | ✅ |
| [ ] | mp-tdd（tdd） | 紅綠重構、一次一個垂直切片 | ✅ |
| [ ] | to-spec | 把目前對話整理成 spec 並發佈到 issue tracker | ✅ |
| [ ] | to-tickets | 把計畫拆成 tracer-bullet ticket，標明阻擋關係 | ✅ |
| [ ] | triage | 以狀態機處理 issue 與外部 PR | ✅ |
| [ ] | wayfinder | 把超大工作拆成決策 ticket 地圖，逐一解決 | ✅ |
| [ ] | wizard | 產生互動式 bash 精靈，帶人完成只有人能做的步驟 | ✅ |

### A2. productivity（7）

| 勾選 | skill | 用途 | 相容 |
|---|---|---|---|
| [ ] | grill-me | 非程式用途的逼問訪談（已有 skillsh 版） | ✅ |
| [ ] | grilling | 逼問的共用基礎 skill（已有 skillsh 版） | ✅ |
| [ ] | handoff | 把對話壓縮成交接文件給另一個 agent | ✅ |
| [ ] | mp-teach（teach） | 跨多次工作階段教你新概念，以目前資料夾為教學工作區 | ✅ |
| [ ] | to-questionnaire | 把你無法獨自決定的事轉成問卷給對的人填 | ✅ |
| [ ] | wait-what | 訊息沒講清楚時，用你的術語重講一次 | ✅ |
| [ ] | writing-for-agents | 寫給 agent 看的文件（skill、AGENTS.md）的寫法 | ✅ |

### A3. misc（4）

| 勾選 | skill | 用途 | 相容 |
|---|---|---|---|
| [ ] | git-guardrails-claude-code | 用 Claude Code hook 擋危險 git 指令 | ⚠ Claude Code 專用 |
| [ ] | migrate-to-shoehorn | 測試中的 `as` 斷言改用 shoehorn | ✅（僅 TS 專案） |
| [ ] | scaffold-exercises | 建立課程練習目錄結構 | ✅（與你的工作無關） |
| [ ] | setup-pre-commit | 設定 Husky、lint-staged、型別檢查、測試 | ✅（僅 JS/TS 專案） |

### A4. in-progress（8，作者標示未完成）

| 勾選 | skill | 用途 | 相容 |
|---|---|---|---|
| [ ] | chief-of-staff | 單一工作階段內協調 subagent 追長期目標 | ⚠ subagent |
| [ ] | claude-handoff | 交接給新的背景 agent 立刻接手 | ⚠ Claude 專用 |
| [ ] | loop-me | 逼問你要建的工作流程 spec | ✅ |
| [ ] | setup-ts-deep-modules | 用 dependency-cruiser 強制深模組 | ✅（僅 TS） |
| [ ] | software-factory | 設計「軟體工廠」的共用語言 | ✅ |
| [ ] | writing-beats | 寫作：把素材組成節奏段落 | ✅ |
| [ ] | writing-fragments | 寫作：先挖片段，不排結構 | ✅ |
| [ ] | writing-shape | 寫作：逐段塑形成文章 | ✅ |

## B. cursor/plugins 的 pstack（MIT，共 58 個 skill、2 個 agent）

來源授權：`pstack/LICENSE`（repo 本身沒有授權檔）。
`poteto-mode` 內含 23 個 playbook（investigation、bug-fix、perf、hillclimb、feature、refactoring、shipping 等）和 TypeScript 腳本（`watch-pr`、`check-plan`），整包一起匯入。

### B1. 入口與編排（8）

| 勾選 | skill | 用途 | 相容 |
|---|---|---|---|
| [ ] | poteto-mode | 總入口：依任務挑 playbook，派 subagent，要求驗證過才算完成 | ⚠ 多模型與 subagent，需重寫派工 |
| [ ] | poteto-help | 說明 pstack 用法，協助挑 skill | ✅ |
| [ ] | setup-pstack | 設定各角色用哪個模型與推理預算 | ⚠ Cursor 專用，建議不引入 |
| [ ] | figure-it-out | 沒有合適 playbook 時，設計可稽核的流程（大型遷移等） | ✅ |
| [ ] | swarm | 平行 N 個 worker，收齊後回一份報告 | ⚠ subagent |
| [ ] | arena | 同一任務平行做 N 版，選基底並移植其他版優點 | ⚠ subagent |
| [ ] | interrogate | 多模型對抗式審查，找盲點 | ⚠ 多模型 |
| [ ] | automate-me | 把你的工作習慣寫成個人 `-mode` skill | ✅ |

### B2. 理解與設計（9）

| 勾選 | skill | 用途 | 相容 |
|---|---|---|---|
| [ ] | how | 「X 怎麼運作」「這該放哪層」的程式導覽 | ✅ |
| [ ] | why | 查設計理由、回歸、事後檢討，向各證據來源查詢 | ⚠ 依賴 MCP |
| [ ] | teach | 把 how 與 why 的結果整合成易懂的說明 | ✅ |
| [ ] | architect | 寫程式前先畫型別、簽章、模組結構 | ✅ |
| [ ] | blast-radius | 變更前找出會波及別處的風險，用實際執行證明安全 | ✅ |
| [ ] | sharpen | 讓任務更深而非更大，並改寫 prompt | ✅ |
| [ ] | in-your-own-words | 用自己的話複述你的目標與問題 | ✅ |
| [ ] | bro | 把上一則訊息用白話重講，不用術語 | ✅ |
| [ ] | statechart | 用 TLA+ 模型檢查狀態流程並畫 Mermaid 狀態圖 | ✅（需 TLA+ 工具） |

### B3. 實作與品質（11）

| 勾選 | skill | 用途 | 相容 |
|---|---|---|---|
| [ ] | ps-tdd（tdd） | 只在明確要求或有便宜的測試目標時用 | ✅ |
| [ ] | correct | 找出 agent 反覆犯的錯，依序用架構、型別、lint、測試把它變不可能 | ✅ |
| [ ] | no-comments | 派「討厭註解」的 agent 審查並刪除多餘註解 | ⚠ subagent |
| [ ] | unslop | 去除文字的 AI 味 | ✅ |
| [ ] | technical-writing | 技術文件標準（Diátaxis、Google 風格、STE） | ✅ |
| [ ] | typescript-best-practices | 讀寫 .ts/.tsx 時的最佳實務 | ✅（僅 TS） |
| [ ] | benchmark-checklist | 報告效能數字前先檢查量測是否可信 | ✅ |
| [ ] | show-me-your-work | 長時間無人值守工作時，記錄每個決策的 TSV | ✅ |
| [ ] | recall | 從聊天歷史重建最近的工作脈絡 | ⚠ 依賴各工具的歷史存取 |
| [ ] | reflect | 平行三個 subagent 回顧對話，把學到的寫回 skill | ⚠ subagent |
| [ ] | ketchup | 白話補上這段對話的變化與等你決定的事項 | ✅ |

### B4. 驗證與自動化（7）

| 勾選 | skill | 用途 | 相容 |
|---|---|---|---|
| [ ] | create-verification-skill | 產生專案內的驗證 skill，像使用者一樣操作你的 app | ✅ |
| [ ] | maintain-verification-skill | 定期維護上面那個驗證 skill | ⚠ 平行讀取 |
| [ ] | create-formal-verification-skill | 產生形式化驗證 skill | ✅ |
| [ ] | maintain-formal-verification-skill | 程式變動後同步形式化驗證 | ✅ |
| [ ] | ketchup-video | ketchup 的影片版 | ⚠ Cursor 專用，建議不引入 |
| [ ] | make-bot-ui | 產生 bot UI | ⚠ 未讀內文，用途不明 |
| [ ] | benny 自動化（3 個 skill） | 自動分流 issue、重現並修復（Cursor automations） | ⚠ Cursor 專用，建議不引入 |

### B5. 原則（24，每個都是短小的「遇到某情境就套用」規則）

| 勾選 | skill | 情境 |
|---|---|---|
| [ ] | principle-attack-the-premise | 多個共用同一前提的修法連續失敗時，先直接測前提 |
| [ ] | principle-boundary-discipline | 驗證與錯誤處理集中在系統邊界 |
| [ ] | principle-build-the-lever | 非瑣碎工作先做工具（codemod、腳本），不手工做 |
| [ ] | principle-encode-lessons-in-structure | 同一指令寫第二次時，改成 lint 或檢查 |
| [ ] | principle-exhaust-the-design-space | 全新設計先做 2-3 個原型並排比較 |
| [ ] | principle-experience-first | 取捨時選使用者體驗，少而精 |
| [ ] | principle-explain-the-number | 量到數字後先找出限制因素，排除量錯 |
| [ ] | principle-fix-root-causes | 除錯追到系統第一個出錯處 |
| [ ] | principle-foundational-thinking | 先把核心型別與資料結構選對 |
| [ ] | principle-guard-the-context-window | 大量輸出交給 subagent，主執行緒只留摘要 |
| [ ] | principle-laziness-protocol | 偏向刪除與最小變更 |
| [ ] | principle-make-operations-idempotent | 指令與重試流程收斂到同一終態 |
| [ ] | principle-migrate-callers-then-delete-legacy-apis | 新 API 出現時同批遷移呼叫端並刪舊 API |
| [ ] | principle-minimize-reader-load | 折疊單一呼叫者的包裝層、縮小可變範圍 |
| [ ] | principle-model-the-domain | 狀態邏輯或重複分支時先建模 |
| [ ] | principle-never-block-on-the-human | 可逆的工作不要停下來問 |
| [ ] | principle-outcome-oriented-execution | 規劃式重寫直奔目標架構，不留過渡相容碼 |
| [ ] | principle-prove-it-works | 宣告完成前對真實產物驗證 |
| [ ] | principle-redesign-from-first-principles | 新需求進來時從第一原理重新設計 |
| [ ] | principle-separate-before-serializing-shared-state | 先消除共用寫入，再考慮序列化 |
| [ ] | principle-sequence-verifiable-units | 多步工作切成各自可驗證的小單元 |
| [ ] | principle-subtract-before-you-add | 先刪死碼再加功能 |
| [ ] | principle-test-behavior-not-implementation | 測試斷言使用者可觀察的行為 |
| [ ] | principle-type-system-discipline | 讓不合法狀態無法表示 |

### B6. pstack 的 agent（2，Kiro 與 Antigravity 沒有對應格式）

| 勾選 | agent | 用途 |
|---|---|---|
| [ ] | poteto-agent | `poteto-mode` 派出的寫碼 delegate |
| [ ] | comment-sicko | 刪註解審查者（`no-comments` 會用到） |
