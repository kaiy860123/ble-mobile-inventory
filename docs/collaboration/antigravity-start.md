# 貼給 Google Antigravity 的啟動指令

先在獨立資料夾開啟 `https://github.com/kaiy860123/ble-mobile-inventory` 的 checkout，再貼以下文字。這是準備好的交接內容，尚未發送給另一工具。

```text
你加入 BLE 移動盤點與定位專題，使用繁體中文。Codex 負責架構、整合審查與部署，你負責交接任務的獨立開發／驗證。

先讀 AGENTS.md、docs/collaboration/README.md、docs/collaboration/tasks.md、docs/requirements.md、docs/test-log.md。先回報目前 commit、工作分支、未提交差異及你要做的任務。

第一個可立即開始的任務是 AG-002：審查報告四層架構圖、公式、程式與測試紀錄的一致性。允許修改 docs/report/diagrams/，新增 docs/report/diagram-review.md 與 docs/handoffs/AG-002-result.md。公式勘誤先列出來源／推導及影響，不直接改定位核心。依任務建立工作分支，避免與 Codex 共用 checkout。

AG-001 的座標設定已有本地可驗證版本；先回報 checkout 的完整 SHA 並確認含 TEST-011／TEST-012 與 web/site-settings.js，再依任務獨立驗證，不改 API 或相同前端檔案。RPi 尚未更新，請在自己的本機測試，不把舊版 RPi 視為新版結果。

合成資料、Gazebo、實體測試必須分開；真值只能供評估。AWS 目前尚未部署，XIAO 尚未刷機，不可將軟體準備寫成實測完成。

依 docs/collaboration/handoff-template.md 提交修改、驗證命令、結果、證據及限制。完成後交付分支／commit 給 Codex 審查，不直接改 main 或重啟 RPi。日常可逆工作依任務自主完成；真正缺少需求決策或硬體／登入條件時才提出具體問題。
```
