# BLE 專題協作入口

本儲存庫由 Codex 統整與審查，Antigravity 依交接任務開發／獨立驗證，Gazebo 由組員負責。

## 開始工作

1. 讀 `docs/collaboration/README.md`，確認任務、分支及檔案負責人。
2. 依 `docs/collaboration/tasks.md` 選取已交付任務；Antigravity 實際來源與自動派工依 `docs/collaboration/bridge.md`。主工作區分支由 Codex 統一操作；共用檔案時再依 `auto-review.md` 交接。
3. 先確認目前差異與既有測試證據，再修改任務允許的檔案。

## 依工作類型讀取

- 產品範圍、驗收或修改需求：`docs/requirements.md`。
- BLE／Gazebo 格式或時間、座標語意：`docs/contracts.md`、`src/contracts/observation.schema.json`。
- 座標設定介面／API：`docs/design/site-settings.md`。
- 定位、誤差或報告公式：`docs/report/methods.md`，逐項核對實作。
- 報告圖表與結果：`docs/report/report-draft.md`；將未完成項目保留為待驗證。
- Antigravity 新增／修改、排程審查或交接：`docs/collaboration/auto-review.md`，依共用資料夾與 fingerprint 流程執行。
- Antigravity 自動派工、外部 checkout 或免轉貼接續：先讀 `docs/collaboration/bridge.md`，以實際來源與任務佇列取代共用資料夾假設。
- 部署／刷機：`docs/runbook.md`、`docs/aws-deployment.md`。

## 交付

- 依 `docs/collaboration/test-matrix.md` 跑受影響的檢查，記錄命令、版本、結果及證據。
- 問題與修正記入 `docs/issues.md`；測試記入 `docs/test-log.md`。
- 依 `docs/collaboration/handoff-template.md` 交付，不以「已寫程式」替代「驗收通過」。
- 工作狀態改變時更新 `docs/progress/state.json` 並執行 `scripts/render-progress.py`。

## 共同邊界

- 使用者最新指示優先於工作規劃；影響其他負責人檔案時，先在交接中指出影響並協調。
- 定位輸入只包含觀測，真值另存評估；圖表區分合成、Gazebo 與實機。
- 登入資料、憑證、主機證據與原始課程附件留在既定本地忽略位置。
- 雲端維持已確認的 0 元支出與 Free Plan 限制；由 Codex 統一執行 RPi／雲端整合部署。
- 以證據更新狀態，保留未執行、失敗、阻塞與限制；依原始紀錄可重現結果。
