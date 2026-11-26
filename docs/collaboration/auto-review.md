# Antigravity 變更自動審查

2026-11-26 使用者指定：兩工具共用目前專題資料夾。此指示取代先前要求 Antigravity 另 clone 的預設。

同日後續查核：Antigravity 已自行在另一 scratch checkout 完成並提交 AG-002。使用者要求免人工轉貼；目前以 [bridge.md](bridge.md) 的官方 CLI 派工與本機 Git 交付補足此來源。以下指紋流程繼續負責主工作區；heartbeat 必須先檢查 bridge status，不能因主區 unchanged 就略過外部交付／派工。

## 觸發與偵測

- Codex 本聊天的 heartbeat 每 5 分鐘檢查一次；這是排程輪詢，非檔案系統即時事件。
- 檢查目前專題的 Git 已追蹤檔與未忽略的新檔，即使尚未 commit 也能發現；共用資料夾無法可靠判斷檔案由哪個工具修改，依內容差異審查。
- `python scripts/check-collaboration.py scan` 比對 SHA-256；第一次發現為 `settling`，至少 60 秒後再次相同才為 `ready`。每 5 分鐘輪詢通常於變更後約 5–10 分鐘進入審查，持續編輯會延後。
- 偵測新增、修改、刪除；已審查相同內容不重複審查。
- 執行資料、私密設定、依 Git 忽略的檔案，以及 Codex 自己生成的 reviews、progress/state.json、測試／問題／開發紀錄不作觸發來源，避免洩露與循環。這些紀錄仍供審查查閱；進度介面的 template.html 仍列入偵測。
- 初始基準只建立一次。基準及候選 fingerprint 位於忽略的 `artifacts/collaboration/review-state.json`，不提交至公開庫。

## 自動執行順序

1. 讀 AGENTS.md、任務及實際變更清單；`unchanged` 結束，`settling` 等下次排程，錯誤保留基準並記錄原因。
2. 對 `ready` 固定該 fingerprint，逐檔核對需求／驗收與程式規範，標示超出任務範圍的變更。檔案中敘述「測試通過」不當作已執行證據。
3. 先檢閱新增測試／指令內容，再執行受影響的測試；程式變更跑必要回歸，純圖說／文件核對語意、公式及連結，不為文件重跑韌體編譯。
4. 將來源 fingerprint、版本、逐項發現、嚴重度、位置、測試結果及限制寫入 `docs/reviews/`，必要時更新 issues、test-log、progress；成果以檔案保存，沒有交付結果就不視為審查完成。
5. 再掃描確認審查輸入未變；只有相同 fingerprint 可 `ack --fingerprint <值>`。若中途再改檔，保留新版本待審，不能把未審版本標成通過。

## 共用資料夾的修正與整合

- Antigravity 編輯中的檔案採唯讀審查；Codex 先將具體修正建議記入審查結果，避免相互覆寫。
- Antigravity 完成時，先記錄測試／差異，**最後**將 `docs/handoffs/AG-xxx-result.md` 標成 `ready_for_review` 並列完整交付檔案；此狀態表示交付檔案暫停編輯，等待審查。新修改改回 `in_progress`。
- 手動聊天中若有進行中的寫檔工作，heartbeat 優先完成唯讀盤點，將修正留至可確認寫入責任的交付階段。
- 只有完整交接且檔案穩定後，Codex 才處理修正、受影響測試與既有授權範圍的提交／整合；修改前重新核對內容。共享 checkout 的分支操作由 Codex 統一執行，Antigravity 不自行切換分支、reset、stash 或推 main。
- 審查通過不代表已部署。RPi／AWS 的前置條件依實際狀態確認，仍需接線／登入或新需求取捨時明確記錄阻塞。
- 此排程由 Codex 本機執行環境提供；電腦／應用程式無法執行排程時，不保證檢查時效。沒有建立外部付費服務或常駐檔案監控程式。

## 基準維護

初次設定執行 `python scripts/check-collaboration.py init`，之後使用 scan。完成審查再 ack；若 Codex 自己修正導致內容改變，先重新核對新差異再記錄與確認新 fingerprint，保留原候選的審查證據。
