# AWS 與 GitHub Pages 部署

目標為 Free Plan 下 0 元現金支出，不升級付費方案；服務本身仍可能消耗免費抵用金。部署前需重新查核方案、期限與服務可用性，帳號截圖僅保存在本地 artifacts。

## 2026-11-27 實際部署

已透過官方 AWS CLI 2.42.4 的瀏覽器暫時登入，完成 `ap-southeast-2`（Sydney）的 `ble-mobile-inventory` stack、裝置憑證及專案擁有者唯讀觀看帳號。此新式 AWS 專案限制在 Sydney；原先預設 Tokyo 的登入被服務拒絕，因此本帳號所有部署命令必須明確指定 `--region ap-southeast-2`。

API preflight 確認 ACTIVE FREE，期限至 2027-05-15，當次剩餘額度約 US$119.998896；Console 顯示約 US$120、本月 US$0。這是查核當下狀態，不保證額度不再消耗。CloudShell 回報帳戶驗證進行中，改用官方 CLI 暫時登入成功，沒有建立長期 AWS access key 或升級方案。

已實跑產品 `CloudPublisher`（裝置 TLS）與前端 `CloudSession`（Cognito 登入、暫時身分、MQTT WSS）傳遞明確標記 simulation 的合成訊息。觀看者嘗試發布後被 broker 斷線，符合唯讀權限。這是雲端通路驗證，沒有使用 RPi／即時 BLE，也未驗證實體定位精度。

公開連線設定：`web/public/cloud-config.json`；觀看者登入資訊：本地忽略的 `config/private/viewer-login.json`（不寄信、不公開）。裝置私鑰在 `config/private/device/`，尚未傳送到 RPi；完整歷史仍按原設計留在 RPi。

本機官方暫時登入的設定檔、憑證快取分別存於 `config/private/aws/config`、`config/private/aws/login-cache/`。透過 `AWS_CONFIG_FILE`、`AWS_SHARED_CREDENTIALS_FILE`、`AWS_LOGIN_CACHE_DIRECTORY` 指向這些位置後，執行官方 `aws login --profile ble-project --region ap-southeast-2`；登入期限到期才需重新登入，不讀取瀏覽器 cookie。SDK 使用 `boto3[crt]`；依賴已納入開發環境。

## 架構

RPi → AWS IoT Core（MQTT TLS）；GitHub Pages 網頁 → Cognito 登入與臨時身分 → IoT Core（MQTT WSS）唯讀。完整歷史留在 RPi。

基礎建設模板：`infra/aws/template.json`。建立 Cognito User Pool／Identity Pool、限定本專題 topic 的 IAM／IoT 權限及 RPi Thing。第一版無 EC2、資料庫或雲端歷史。公網前端沒有長期 AWS 金鑰或裝置私鑰。

## 在已有 AWS 登入的環境執行

可使用 AWS CloudShell，或在本機以官方 AWS CLI 設定自己的登入 profile。不要把金鑰、密碼或 MFA 碼貼到聊天或提交 GitHub。

```bash
python -m pip install boto3
python scripts/aws-provision.py preflight
python scripts/aws-provision.py deploy
python scripts/aws-provision.py device
python scripts/aws-provision.py viewer --email <觀看者帳號>
```

- 預設 region 為 `ap-northeast-1`、stack 為 `ble-mobile-inventory`；需改時所有步驟使用相同 `--region`。
- 此帳號實際使用 Sydney，請在上述每個命令加入 `--region ap-southeast-2`，並使用對應的登入 profile。
- `preflight` 只讀取身分與 Free Plan 狀態；非 ACTIVE FREE、無登入或無查詢權限時停止，不嘗試升級。
- `deploy` 建立／更新本專題標記的 stack，輸出 `web/public/cloud-config.json`（可公開設定）。再次部署不會自動輪替裝置私鑰。
- `device` 保存裝置憑證、私鑰與本地雲端設定到 `config/private/`，不列印內容。部分步驟失敗可重跑已存在憑證的授權步驟；缺檔時停止，不覆寫金鑰。
- `viewer` 在安全終端要求觀看者密碼，建立／驗證受邀帳號並綁定該 Cognito Identity 的 IoT 唯讀 policy。不寄邀請信；由你以合適方式交付登入資訊。
- 公開頁禁止自助註冊，不授權觀看者發布或控制設備。

若使用 CloudShell，私密裝置檔需透過安全下載／傳輸放到自己的 RPi；不放 GitHub。`web/public/cloud-config.json` 可帶回本地專題再建置／推送。根據真實場地修改 `config/private/site.cloud.json`，不能把範例座標當實測值。

## RPi 啟用 AWS

把裝置檔放到 RPi 同樣的 `config/private/device/`，私鑰設為僅服務使用者可讀。以專題根目錄為工作目錄啟動：

```bash
.venv/bin/python -m ble_inventory.cli serve --mode ble --host 0.0.0.0 --config config/private/site.cloud.json
```

公開端每秒接收最新狀態。新登入者等待下一筆推送，看到的是當前狀態；斷線期間不補傳全部歷史。AWS 故障不阻止本地收集。

## GitHub Pages

儲存庫：`https://github.com/kaiy860123/ble-mobile-inventory`。

`.github/workflows/ci-pages.yml` 在 main 更新時執行 Python／前端測試、產生合成回放、建置並部署 Pages，另提供 RPi 套件 artifact。儲存庫 Pages Source 需設為 GitHub Actions。

未配置 `cloud-config.json` 前，公開頁提供明確標示的合成回放，登入按鈕會解釋尚未配置；不能宣稱 AWS 即時已連線。

已配置後可登入等待新訊息；沒有 RPi 發布時仍應顯示等待／中斷，不把回放當成目前即時資料。測試觀察新式登入與瀏覽器版面，仍須與傳輸驗證分開記錄。

## 檢查與清理

在 AWS Cost and Usage 持續檢查額度；不要升級方案或啟用額外付費服務。展示完成後先停止 RPi 雲端發布與觀看端連線；需要刪除資源時，依 stack 及私密 deployment state 確認本專題資源，先停用／解除附掛裝置憑證，再清除憑證與 stack。刪除前先保存本地資料及必要設定。

## 官方參考

- [AWS IoT 通訊與驗證](https://docs.aws.amazon.com/iot/latest/developerguide/protocols.html)
- [Cognito Identity 的 IoT 權限](https://docs.aws.amazon.com/iot/latest/developerguide/cognito-identities.html)
- [Free 與 Paid Plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
- [官方 CLI 瀏覽器暫時登入](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)
- [IoT STS 簽章特殊規則](https://docs.aws.amazon.com/iot/latest/developerguide/iam-users-groups-roles.html)：session token 必須在簽章計算後加入 query，不能納入 canonical query。
