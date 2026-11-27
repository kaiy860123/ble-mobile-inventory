# 操作說明

## Windows 本地展示

需要 Python 3.11+、Node.js 20+。首次執行：

```powershell
./scripts/setup.ps1 -PythonPath 'python'
./scripts/run-local.ps1
```

開啟 `http://127.0.0.1:8080`。預設是合成觀測（非硬體或 Gazebo），畫面會明確標示。可開始／結束任務、選設備、匯出 CSV／回放。切換實驗回放可載入包含範例 WGS84 原點與旋轉角的紀錄，僅示範底圖功能，不代表實際設備在該地點。

已有 Python 環境時：

```powershell
./.venv/Scripts/python.exe -m ble_inventory.cli serve --mode demo --port 8080
```

## Raspberry Pi

前置：RPi OS 已連網、Python 3.11+、venv、BlueZ 與藍牙可用。若缺少套件，使用 RPi 的套件管理工具安裝 `python3-venv`、`bluetooth`、`bluez`。

1. 在 RPi 的 Raspberry Pi Configuration／`raspi-config` 啟用 SSH，確認自己的使用者名稱與 IP，設定 SSH 金鑰。
2. 本機產生已建置網頁的部署套件：`python scripts/package-project.py`。
3. 執行 `python scripts/deploy-rpi.py <RPi-IP> --user <帳號> --install-service`，透過既有 SSH 驗證傳送並安裝。若使用密碼登入，加入 `--password-auth`，只在終端隱藏提示輸入，密碼不作命令參數或保存。首次需先以正常 SSH 完成主機金鑰信任，部署器拒絕未知或不符的主機金鑰。
4. 在 RPi 編輯 `config/site.local.json`，填入量測得到的座標、天線高度與校正參數。
5. 在 RPi 執行 `.venv/bin/python -m ble_inventory.cli serve --mode ble --host 0.0.0.0 --config config/site.local.json`。
6. 同 Wi-Fi 的手機／電腦開啟 `http://<RPi-IP>:8080`。

需開機自動執行時，在 RPi 執行 `bash scripts/install-service.sh`。若已存在 `config/private/site.cloud.json`，服務改用該設定。檢查 `journalctl -u ble-inventory -n 100 --no-pager`。不把本地 8080 埠直接公開到網際網路。

若 RPi 對外下載慢，可在 Windows 準備符合實機 Python 版本的離線套件：

```powershell
python scripts/download-rpi-wheels.py --python-version 313
python scripts/package-project.py --wheelhouse deliverables/rpi-wheels
python scripts/deploy-rpi.py <RPi-IP> --user <帳號> --password-auth --install-service
```

`313` 代表 CPython 3.13，其他版本需改為實機版本。套件在 `deliverables/` 本地保存，不提交 GitHub。範例設定 `configuration_status=example` 會提示場地尚待實測；完成座標與校正後再改為 `measured`。

## XIAO 刷機

一次只連接並辨識要刷的設備；腳本不猜 COM port：

```powershell
./.venv/Scripts/python.exe scripts/flash-device.py A01 --port COM5
```

初始刷 A01–A04、T01–T02。備品可刷 A05 或 T03，再修改場地名單。`firmware/platformio.ini` 固定工具鏈與 NimBLE 版本。若工具鏈下載失敗，保留錯誤並重試或改用 CI 編譯產物；不得把未編譯的程式說成刷機成功。

## 現場校正

1. 所有天線先採固定高度與方向，記錄外接天線擺放。
2. 量測 Anchor Local 座標及各設備高度；若有地理參考，設定 WGS84 原點與 `rotation_deg`。
3. 建立 CSV：`device_id,distance_m,rssi_dbm`；每設備至少六筆，距離至少涵蓋二倍範圍，建議多距離重複量測。
4. 執行 `python scripts/calibrate-rssi.py <樣本.csv>`，檢查結果並加入場地設定對應設備的 `rssi_at_1m_dbm`／`path_loss_exponent`。
5. Target 保持靜止；移動 RPi 沿有轉折的路徑收集資料，單一直線不足以穩定定位未知目標。
6. 量測 Target 參考位置另存評估資料，不放入定位器的 Target 設定。

## 紀錄與失敗處理

- 每任務自動分 run_id，原始觀測與 manifest 在 `data/raw/`，結果在 `data/processed/`。
- 未接 AWS 時本地照常運作；公開端超過 10 秒未收資料會提示中斷。
- 無效解保留最後有效位置與時間，顯示原因。
- 底圖需要網路；未地理對準時可用 Local，底圖失敗可切回 Local。
- 回放檔案目前限制 50 MB、20,000 影格；大型實驗請分任務記錄。完整原始 JSONL 仍保留在 RPi。
- 問題寫入 `docs/issues.md`，驗證寫入 `docs/test-log.md`，不得把合成測試當成實機精度報告。

AWS 操作另見 [aws-deployment.md](aws-deployment.md)，Gazebo 串接見 [contracts.md](contracts.md)。
# 場地／Anchor 座標設定（新版）

在 RPi 本地即時頁面按「場地／Anchor 座標設定」，依現場量測填入各 Anchor 的 Local X/Y/Z、公尺範圍及天線高度。有 WGS84 原點及方向時可開啟地理對準，設定緯經度、橢球高與 Local X 自正東逆時針旋轉角；Anchor 可改用 WGS84 輸入。

按「計算預覽」檢查 Local 與經緯度結果，再「保存並開始新巡查」。保存會備份原設定、寫入啟動時指定的設定檔，並建立新 run_id；舊紀錄保留。變更欄位後須重新預覽。遇到版本衝突先另行記錄修改，再重新載入。取消不保存。

GitHub Pages／AWS 觀看模式不提供遠端編輯。此功能須部署新版才會在 RPi 出現；本次部署狀態見 TEST-012。XIAO 封包沒有 Anchor 座標，移動 Anchor 後更新此介面即可，無須重刷韌體。

2026-11-28：TEST-031 已將新版部署至 RPi，座標欄位與不寫入預覽已實際開啟驗證；場地仍為示例值。開始實測前先量測四 Anchor 與天線高度，再保存新巡查。六設備接收已於 TEST-030 通過，詳見 docs/testing/physical-checklist.md。
