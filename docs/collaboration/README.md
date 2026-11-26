# Codex、Antigravity 與 Gazebo 共同開發

## 角色與權責

| 角色 | 負責 | 交付與完成條件 |
| --- | --- | --- |
| 使用者 | 需求取捨、設備接線／標記、場地量測、帳號登入與最終展示 | 確認實際設備與參考座標；完成必要的人工作業 |
| Codex | 架構與資料契約、定位／座標核心、設定 API、整合審查、發布與部署 | 審查差異，重跑受影響檢查，更新需求、證據與看板 |
| Antigravity | 首批獨立測試、介面可用性、圖表／公式核對；後續 AG-003 實驗彙整工具開發 | 在指定分支交付可重現測試與差異；尚未接入，不能當成已在執行 |
| Gazebo 組員 | 世界、SITL、航線、BLE 觀測模型與獨立真值輸出 | 依共用契約提供樣本、版本、執行方式及模擬紀錄 |

「Codex 監督」指檢查交付與整合證據；不是假設 Codex 可以背景監看另一工具的私人對話。狀態透過本儲存庫的交接文件與分支同步。

## Checkout 與分支

1. Codex 繼續使用目前工作區；Antigravity 在另一個資料夾 clone 同一 GitHub 儲存庫。
2. 每個任務從指定的基準 commit 建立分支，例如 `antigravity/AG-001-settings-review`。
3. 同一時間每個檔案只指定一位修改者；要跨範圍先列出所需修改及影響。
4. Antigravity 交付 commit SHA 或分支；Codex 在自己的 checkout 審查及整合，再驗證合併後狀態。
5. 有衝突時回到原始契約／需求判斷，不以「保留我的版本」取代審查。
6. 尚未交付的分支保留原狀；開始新任務前確認既有未提交差異。

目前程式交付基準為 `9225d6be262071ab8ad31d6fb1f8b76526a5b04e`（座標介面、報告與共同開發）；GitHub Actions `45841081307` 通過。本地與 Pages 已驗證，RPi 仍是舊版 `0bdeea4`，更新因 SSH 逾時未傳檔。後續任務明確記錄基準 SHA，不把舊 SHA 當成永遠最新版本。

## 檔案負責範圍

| 範圍 | 主要修改者 | 其他人可做 |
| --- | --- | --- |
| `src/ble_inventory/`、`src/contracts/` | Codex | Antigravity 讀取、提具體問題與獨立測試；跨檔修改需協調 |
| `web/site-settings.js`、設定介面掛接 | Codex（首版） | Antigravity 在 AG-001 驗證；若接手改 UI，另開明確任務 |
| 新增獨立測試／`docs/handoffs/AG-*.md` | Antigravity（指定任務） | Codex 審查及重跑 |
| `docs/report/methods.md` | Codex | Antigravity 逐式核對並交付勘誤，不直接改動公式定義 |
| `docs/report/diagrams/`、報告圖說 | Antigravity（AG-002） | 依已確認架構修正，圖中標示部署狀態 |
| `infra/`、部署／刷機腳本、RPi 服務 | Codex | 其他角色交付建議；避免兩工具同時重啟或改憑證 |
| Gazebo 工程 | Gazebo 組員 | 此儲存庫只維護介面、送出器、樣本與整合測試 |
| `docs/progress/state.json` | 當前整合者 Codex | 其他人回報狀態與證據，由整合者更新 |

## 狀態與交接

使用 `todo → in_progress → ready_for_review → verified`；`blocked` 必須填原因。程式完成但未部署時明確寫 `implementation=done, deployment=pending`，不合併成虛構的完成百分比。

交接以 [handoff-template.md](handoff-template.md) 為格式，至少含基準／交付 SHA、修改檔案、驗收、測試、證據、限制及下一步。測試未執行須寫明；收到交接不等於已核准合併。

## 審查與整合門檻

1. **範圍**：修改符合任務、沒有改掉共用語意或別人的未提交內容。
2. **正確性**：邊界條件與失敗路徑有測試，數值對照有獨立基準。
3. **產品行為**：本地控制與公開唯讀分開，設定保存、舊任務保留及資料不足提示正確。
4. **證據**：合成／模擬／實體來源清楚，單元測試不冒充實機精度。
5. **整合**：Codex 針對合併後版本重跑必要檢查，再更新報告與看板。

套件安裝、讀檔與程式已被使用者授權的日常工作照既有範圍進行；真正需要登入、實體接線或未授權的需求取捨才交給使用者。

## Antigravity 的載入方式

官方文件說明支援 `AGENTS.md`／`GEMINI.md` 等工作區規則。本專案以短版 `AGENTS.md` 作共同入口，具體規劃放在此處，避免兩份規則彼此漂移。請先確認你安裝的版本確實讀到此工作區規則。

- [Antigravity Rules](https://antigravity.google/docs/rules/)
- [Verification and guardrails](https://antigravity.google/docs/learn/verification-and-guardrails)

查核日期：2026-11-26。
