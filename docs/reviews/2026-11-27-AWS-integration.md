# AWS 整合與發布審查

- 審查版本：`ca01517e50afcadc7d76803e88d3a246cc9bb7ec`，其後文件只補真實部署證據及修正報告過時狀態；本輪由 Codex 實作、測試與發布。
- 修改範圍：`web/cloud.js` 的 IoT WSS 簽章、獨立前端 regression、npm 測試入口、官方 SDK CRT 開發依賴、公開連線設定與需求／部署文件。未修改定位核心、真值契約或 RPi 部署。
- 正確性：IoT STS token 於簽章後加入；固定日期與同一金鑰下更換 token 不改 canonical signature，URL 正確保留 token 特殊字元。原 WSS 斷線已由真實服務重現，修正後產品 TLS 發布／Cognito WSS 接收合成快照通過；觀看者發布後 broker 斷線。
- 邊界：公開 cloud-config 只含 region、endpoint、User Pool／Client／Identity Pool ID、topic 六個預期欄位。隨機觀看密碼、裝置憑證及 AWS 暫時登入均在既有忽略私密位置；未寄邀請信，未改 Free Plan。
- 實際檢查：149 個非 browser Python 測試、3 個前端測試、build 及 CI 45974522232 通過。CUA 查核 Pages 登入表單、AWS 選項要求登入、公開控制 disabled；沒有以 CUA 執行完整帳密登入，與產品 CloudSession 網路測試分開記錄。
- 文件補正：六塊刷機與各別 BLE 接收、AWS Sydney 資源／PC 合成通路均以 TEST-021–027 支持；圖示中的 RPi 雲端連線仍保留待串接，未冒稱新增 Mermaid 版面驗證。
- 使用者最新排程：先 AWS，同時通電實驗保留待處理；未啟動 RPi／六設備實驗。硬體實際精度、Gazebo、真實雲端延遲及長時間／復原測試不在此次通過範圍。

結論：可接受本輪 AWS 雲端階段整合；完整專題與實機路徑仍依待驗項目管理。
