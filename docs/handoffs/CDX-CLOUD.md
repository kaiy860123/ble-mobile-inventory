# CDX-CLOUD：AWS 部署與雲端合成通路交接

- 日期：2026-11-27；執行者／整合者：Codex。
- 程式發布版本：`ca01517e50afcadc7d76803e88d3a246cc9bb7ec`；CI `45974522232` 的測試、建置與 Pages 部署成功。
- 完成範圍：Sydney `ble-mobile-inventory` CloudFormation、IoT 裝置／topic 限定權限、Cognito 唯讀觀看登入、裝置憑證、Pages 雲端設定及合成通路驗證。
- 未完成範圍：RPi 雲端設定／憑證傳送、即時 BLE 上雲、實體或 Gazebo 定位與端到端延遲測量。六塊同時通電實驗依使用者最新指示待處理。

## 證據

1. 官方 CLI 瀏覽器暫時登入及 preflight：ACTIVE FREE、期限 2027-05-15，無長期 access key，沒有升級方案。
2. 官方 Sydney 區域 stack 建立完成；原本 Tokyo 被此新式專案限制拒絕。CloudShell 的帳戶驗證問題以 CLI 暫時登入替代。
3. 產品 Python `CloudPublisher` 使用裝置 TLS 發布 simulation 合成快照；產品前端 `CloudSession` 以 Cognito 身分登入、取得暫時權限、WSS 訂閱並收到相同 run_id／schema 1.0。觀看者嘗試發布後 broker 斷線，符合唯讀權限。
4. 修正 IoT STS token 簽章規則後，前端 3 項測試及 build 通過；Python 非 browser 149 passed in 3.83s；遠端 CI 也通過。
5. CUA 確認公開網站有可用登入表單，AWS 模式要求登入，公開巡查／座標控制不可用。CUA 未輸入帳密；不將表單檢查冒充完整瀏覽器登入驗證。

## 操作與檔案

- 公開設定只含 endpoint、region、Cognito 識別與 topic：`web/public/cloud-config.json`；這些是連線識別，不含密碼或私鑰。
- 私密檔案均在忽略的 `config/private/`：AWS 暫時登入快取、`aws-deployment.json`、`device/`、`site.cloud.json`、`viewer-login.json`。不提交、不寄出；使用者在本機讀取觀看登入資訊。
- 網頁：https://kaiy860123.github.io/ble-mobile-inventory/ 。未接 RPi 時只可觀看回放或等待下一筆雲端資料，不能聲稱實機已在線。
- 本地驗證工具及原始結果在 `artifacts/aws-cloud-smoke.mjs`、`aws-publish-smoke.py`、`aws-cloud-smoke.json`；登入包裝與 CLI 只存在本機忽略區。可重現環境設定與正式部署命令見 `docs/aws-deployment.md`。
- 回復／清理：暫停發布及登出不會刪除本地歷史；需要撤銷裝置或刪除 stack 時，先核對本專題的部署狀態與資源，不影響其他 IoT／DynamoDB 課程資源。
