# 自動協作設定與整合審查

- 整合版本：`56a431e2ddb484660344f77634977f6ac514ea34`；包含本輪 Codex 的橋接器、派工佇列、AG-001 獨立交付及修正。AG-002 詳見同日各別審查。
- 主區指紋：`bba9edcbe31a92e6c9f2c48d0cf72e5fdceec1b623391fb37762e62a0eaf6fb2`。掃描的 28 個變動來源均為此次已審查交付或 Codex 設定／修正，沒有未知修改混入。
- 實際最終命令：`.venv/Scripts/python.exe -X utf8 -m pytest -q --ignore=tests/browser`，128 passed in 2.38s；`git diff --check` 通過。前端 build 及 80 個獨立 API 案例另見 AG-001 審查。
- 官方 CLI 1.5.18 已以既有登入完成唯讀與指定檔案寫入探測；無 API key、付費 API 或全域權限變更。設定保留既有 Deny／Ask，只給任務絕對路徑寫入權限，命令執行交 Codex。
- bridge 測試涵蓋交接狀態、儲存庫／任務範圍、依賴、既有權限保留、驗收回執、保留成果接續及最多三次嘗試。狀態 SUCCESS 本身不作驗收證據。
- 已更新既有每五分鐘 heartbeat，先查外部交付，再查主區指紋。使用者不必代貼任務或結果；排程仍受本機可用性限制。
- AG-003 第三次派工執行中，尚未交付，不屬於此次通過範圍。此前兩次無檔案的 SUCCESS 已記為 blocked，未混入驗收。browser CI 結果另查，不把本機未跑的 browser 案例算入 128。
