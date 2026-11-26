# Codex ↔ Antigravity 自動接續

## 實際來源與啟動

2026-11-26 使用者要求停止人工轉貼。查核發現 Antigravity 實際已在獨立 scratch checkout 完成 AG-002，交付 commit `28d61d6dd4e82002d53e17a4119c54aba061c679` 尚未推送。先前主區無變更的掃描結果正確，但不足以發現另一 checkout。

目前沿用此既有獨立 checkout：Codex 維護主專題、任務佇列與驗收；Antigravity 使用自己的分支。實際本機路徑與官方 CLI 路徑存 `config/private/antigravity-bridge.local.json`，不放公開資料庫。這個實際來源取代舊版「只監看共用 checkout」的假設。

Google 官方 CLI `agy` 已安裝，版本 1.5.18；以既有登入執行無讀寫探測，實際回傳 `SUCCESS / BLE_BRIDGE_READY`。沒有建立 API key、付費 API 或 Google Cloud 計費專案。

第一個 AG-001 已由 Codex 直接呼叫 CLI 派工，開始於 AG-002 交付版本，結果依橋接器的實際 job／交接檔確認。啟動成功不等於驗收通過。

首輪實際結果：AG-001 自動完成並交付 `291f0d13c43fd9d589e9925f447168f8cc5b00eb`，Codex 直接匯入、重跑 80 個獨立 API 案例通過，修正四項發現後非 browser 全部 126 測試通過，再記錄 accept。AG-003 已依依賴自動派工。此輪派工、交付、審查、修正與下一任務都沒有人工轉貼；AG-003 的完成狀態仍依後續紀錄判斷。

## 循環與唯一負責人

1. Codex 更新 `queue/AG-001.json`／`AG-003.json`，明確列允許檔案、基準與依賴。使用者不需代貼 prompt。
2. `antigravity-bridge.py status` 檢查指定 checkout、工作樹、任務狀態及已提交的 ready handoff。
3. 沒有執行中工作且工作樹乾淨時，`run AG-001` 呼叫官方 CLI。Codex 建立分支，Antigravity 只編輯任務範圍、測試、寫交接，不自行切分支或發布。
4. 橋接器確認 CLI 結果、HEAD 未意外變更、差異在任務白名單內、handoff 明確為 ready_for_review，才提交本機交付分支。CLI 的 SUCCESS 不是測試通過證據。
5. Codex 用 `import TASK --sha SHA` 將本機分支讀入主區的專用追蹤 ref；不需要 Antigravity 推 GitHub，不覆寫主工作目錄。
6. Codex 逐檔審查、重跑受影響測試、處理可修正問題並在主區整合。完整 SHA 與限制寫入 `docs/reviews/`。
7. 使用 `accept TASK --sha SHA --review-file REPORT` 記錄已驗收。AG-003 只有在 AG-001 與 AG-002 均有驗收紀錄後才可派工。

所有工作由既有 `ble-antigravity` heartbeat 每五分鐘接續，不另建重複排程。主區原本的指紋監看繼續使用；外部交付以 commit SHA 及 ready handoff 辨識，避免把已存在的 AG-002 靜默納入「已審基準」。

## 執行與失敗處理

- 只有指定儲存庫 `kaiy860123/ble-mobile-inventory` 可作 worker checkout。執行鎖避免重複派工；未提交工作、既存任務分支、未完成依賴或已有 job 均停止派工並保留資料。
- runtime、prompt 與原始 stdout／stderr 保存在忽略的 `artifacts/collaboration/bridge/`；它們可能包含專案路徑或登入診斷，不公開上傳。
- 現有帳號不支援 CLI `auto` 模式，首輪 AG-001 回落 default 並完成。AG-003 揭露 Windows headless 命令權限、相對 sandbox 路徑及終端啟動問題；目前明確分工為 **Antigravity 只用內建檔案工具產生程式／測試／交接，Codex 執行命令、實際測試與整合**。session 明確拒絕 command(*)、僅授權任務的絕對檔案路徑，保留既有 Deny／Ask；不啟用全域 Turbo 或 dangerously-skip-permissions。
- 此分工已以官方 CLI 真實檔案探測確認：只有一個指定、被 Git 忽略的測試檔可寫入，命令全部禁止，結果 returncode=0 且檔案內容實際驗證成功。不是只看模型回覆。
- 不讀取／複製憑證來串接；沿用官方 keyring 登入。若 session 過期，可能仍需使用者完成一次官方登入，登入後循環可繼續；正常任務交接不需貼訊息。
- CLI timeout 為 20 分鐘，外層另設上限。失敗保留檔案與 blocked 原因；不自動清理工作樹、不無限重試。先查明原因並審查現有輸出，再修正派工設定。
- 查明並修正阻塞後，可用 `resume TASK` 保留允許範圍的未提交成果，確認原分支／HEAD 不變再接續；只接受已停止的 blocked 工作，每任務最多三次嘗試。已有提交或越界內容時先由 Codex 審查，不自動丟棄。
- 若 runner 異常退出而鎖仍在，先確認該 PID／程序已結束，再恢復；不僅因檔案時間久就移除鎖。
- 本機持續執行仍受電腦與 Codex 排程環境可用性影響，沒有宣稱外部雲端常駐。

## 操作命令

```text
python scripts/antigravity-bridge.py status
python scripts/antigravity-bridge.py run AG-001
python scripts/antigravity-bridge.py resume AG-001
python scripts/antigravity-bridge.py import AG-002 --sha <完整交付 SHA>
python scripts/antigravity-bridge.py accept AG-002 --sha <完整交付 SHA> --review-file docs/reviews/<審查文件>.md
```

唯讀查核外部 checkout 及寫入其任務分支時，若 Codex 沙箱限制該路徑，依正常工具審核申請範圍明確的執行，遵守審核結果，不繞過限制。

第一手文件：[官方 headless mode](https://antigravity.google/docs/cli/headless/)、[官方登入](https://antigravity.google/docs/install/)、[官方 CLI 權限](https://antigravity.google/docs/permissions)。實際支援旗標已以安裝的 CLI --help 查核；不以網站新功能推定本機帳號已支援。
