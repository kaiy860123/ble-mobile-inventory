# Antigravity 自動接續入口

使用者已要求免人工複製貼上；本檔保留作舊連結入口，不再要求貼 prompt 或代傳回覆。

- 自動工作流程：[bridge.md](bridge.md)。
- 任務與範圍：[tasks.md](tasks.md)，派工規格在 queue/。
- 執行程式：scripts/antigravity-bridge.py。
- 既有 Codex heartbeat 已更新為「BLE 專題 Antigravity 自動派工與審查」，每 5 分鐘接續。

Codex 直接呼叫官方 CLI、讀取已確認的 Antigravity 獨立 checkout；ready handoff 與本機分支即可交付，不必先推送 GitHub。Codex 審查／重測後記錄 accept，再依依賴派送下一任務。

人工作業只保留實體接線、必要的一次登入或真正的需求取捨；正常派工、交付、審查與可處理的修正由兩工具接續。
