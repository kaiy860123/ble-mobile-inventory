# AWS 與 GitHub Pages 部署

目標為 Free Plan 下 0 元現金支出，不升級付費方案；服務本身仍可能消耗免費抵用金。部署前需重新查核方案、期限與服務可用性，帳號截圖僅保存在本地 artifacts。

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

## 檢查與清理

在 AWS Cost and Usage 持續檢查額度；不要升級方案或啟用額外付費服務。展示完成後先停止 RPi 雲端發布與觀看端連線；需要刪除資源時，依 stack 及私密 deployment state 確認本專題資源，先停用／解除附掛裝置憑證，再清除憑證與 stack。刪除前先保存本地資料及必要設定。

## 官方參考

- [AWS IoT 通訊與驗證](https://docs.aws.amazon.com/iot/latest/developerguide/protocols.html)
- [Cognito Identity 的 IoT 權限](https://docs.aws.amazon.com/iot/latest/developerguide/cognito-identities.html)
- [Free 與 Paid Plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
