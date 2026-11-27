# HW-002：RPi 六設備收包與新版部署

日期：2026-11-28（Asia/Taipei）。執行：Codex；設備通電：使用者。

## 已完成

1. 新位址 SSH／HTTP 可達，Ed25519 主機金鑰與先前信任的 RPi 相同；未自動信任未知金鑰。
2. aarch64、Python 3.13.5、BLE service active/running、藍牙 powered/discovering。
3. 新巡查 `20261127T172127Z_physical_2dd5d3`，60 秒檢查、59 次 API 取樣，A01–A04、T01、T02 均有本輪新觀測，missing_ids=[]。
4. 結束保存 67 幀回放、66 個 raw 批次、manifest 與 states；Target 已盤點／可見均為 2。
5. 備份原程式、設定、服務檔後部署 `8aab2aa956bdb0a2ad37f754a6cb1980d1a576e9` 程式與新建置網頁，使用現有 CPython 3.13 aarch64 離線套件。上傳包 SHA256 核對通過，site.local.json 更新前後位元組相同，舊資料未刪除。
6. 既有服務重啟成功。新任務 `20261127T172421Z_physical_b7bbeb`，再觀察 15 秒，六 ID 仍全數收到。
7. 設定 GET／preview 200、preview 前後 revision 不變。CUA 實際開啟 RPi 座標介面、四 Anchor／高度／Local／WGS84 欄位可見，預覽成功並警示示例座標，再取消返回；未保存場地數值。

## 寫入紀錄中的 RSSI

| ID | 觀測紀錄數 | 最小 RSSI（dBm） | 最大 RSSI（dBm） | 中位數（dBm） |
| --- | ---: | ---: | ---: | ---: |
| A01 | 62 | -66 | -58 | -62.5 |
| A02 | 65 | -30 | -25 | -27 |
| A03 | 63 | -57 | -46 | -55 |
| A04 | 64 | -61 | -56 | -57 |
| T01 | 63 | -76 | -60 | -62 |
| T02 | 66 | -74 | -63 | -69 |

來源為上述 66 個聚合批次，時間跨度約 65.06 秒。每設備每批最多一筆，**不是 BLE 廣播封包總數，也不能推算遺失率**。距離與擺放尚未量測，僅作收包功能證據，不作 RSSI 校正或位置精度。

## 待驗證

- 四 Anchor 實際座標、場地與天線高度、RSSI 校正。
- 轉折巡查、掃描器／Target 定位、獨立真值與誤差。目前設定 example，Target 資料不足，不將示例座標當實測。
- T02 斷電與 Anchor 不足。已請使用者只關 T02 並回覆，尚未收到確認，未列通過。
- RPi physical 資料上雲。本輪套件不含裝置憑證，cloud.enabled=false，未增加 AWS 資源。

## 本地證據與回復

主機、位址與私密設定只留忽略區：artifacts/rpi-ssh-inspection.json、artifacts/hardware/rpi-readiness-20261128.json、rpi-six-device-replay.json、update/before/、update/result.json、update/api-verification.json、rpi-after-update-readiness.json、rpi-reception-summary.json。

RPi 保留 code-config.tar.gz 與原 service 備份，路徑載於本地 update/result.json。若需回復，先停止服務，再依該備份還原程式／設定並重啟；本輪未需回復。密碼未保存。
